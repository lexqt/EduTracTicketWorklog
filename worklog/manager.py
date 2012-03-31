# -*- coding: utf-8 -*-
from time import time

from trac.core import Component
from trac.config import Option, BoolOption, IntOption, ListOption
from trac.ticket.notification import TicketNotifyEmail
from trac.ticket import Ticket
from trac.util.datefmt import pretty_timedelta, format_datetime, to_datetime

from trac.project.api import ProjectManagement



class WorkLogManager(Component):

    comment = BoolOption('worklog', 'comment', False,
           '''Automatically add a comment when you stop work on a ticket?''', switcher=True)
    autostop = BoolOption('worklog', 'autostop', False,
           '''Stop work automatically if ticket is closed?''', switcher=True)
    autoreassignaccept = BoolOption('worklog', 'autoreassignaccept', False,
           '''Automatically reassign and accept (if necessary) when starting work?''', switcher=True)
    autoreassignaccept_status = Option('worklog', 'autoreassignaccept.status', 'assigned',
           '''Change to this status (see autoreassignaccept option)''', switcher=True)
    autoreassignaccept_resolution = Option('worklog', 'autoreassignaccept.resolution', 'reassigned',
           '''Change to this resolution (see autoreassignaccept option)''', switcher=True)
    autostopstart = BoolOption('worklog', 'autostopstart', False,
           '''Allow users to start working on a different ticket'''
           ''' (i.e. automatically stop working on current ticket)?''', switcher=True)

    work_statuses = ListOption('worklog', 'work_status', 'assigned', sep=',',
           doc='''List of ticket statuses at which it is considered to be available to work on.''',
           switcher=True)

    # Timing and Estimation / Trac Hours Plugins integration

    timingandestimation = BoolOption('worklog', 'timingandestimation', False,
           '''Record time via Timing and Estimation Plugin?''', switcher=True)
    trachoursplugin = BoolOption('worklog', 'trachoursplugin', False,
           '''Record time via Trac Hours Plugin?''', switcher=True)
    roundup = IntOption('worklog', 'roundup', 1,
           '''Automatically reassign and accept (if necessary) when starting work?''', switcher=True)

    def __init__(self):
        self.pm = ProjectManagement(self.env)

    def can_work_on(self, username, ticket, syllabus_id=None):
        '''Check if username can start working on given ticket.
        Return (<bool result>, <msg on False>).

        `ticket` - Ticket instance.'''
        # Need to check several things.
        # 1. Is ticket status allow to work on it?
        # 2. Is some other user working on this ticket?
        # 3. a) Is the autostopstart setting true? or
        #    b) Is the user working on a ticket already?
        # 4. a) Is the autoreassignaccept setting true? or
        #    b) Is the ticket assigned to the user?

        if syllabus_id is None:
            syllabus_id = self.pm.get_project_syllabus(ticket.pid)
        msg = None

        # Are you logged in?
        if username == 'anonymous':
            return False, 'You need to be logged in to work on tickets.'

        # Check ticket status
        if ticket['status'] not in self.work_statuses.syllabus(syllabus_id):
            return False, 'You can not work on ticket with status "%s"' % ticket['status']

        # Other user working on it?
        who, since = self.who_is_working_on(ticket.id)
        if who:
            if who != username:
                msg = 'Another user (%s) has been working on ticket #%s since %s' % (who, ticket.id, since)
            else:
                msg = 'You are already working on ticket #%s' % (ticket.id,)
            return False, msg

        # a) Is the autostopstart setting true? or
        # b) Is the user working on a ticket already?
        if not self.autostopstart.syllabus(syllabus_id):
            active = self.get_active_task(username, ticket.pid)
            if active:
                msg = 'You cannot work on ticket #%s as you are currently working on ticket #%s. You have to chill out.' % (ticket.id, active['ticket'])
                return False, msg
        
        # a) Is the autoreassignaccept setting true? or
        # b) Is the ticket assigned to the user?
        if not self.autoreassignaccept.syllabus(syllabus_id):
            if username != ticket['owner']:
                msg = 'You cannot work on ticket #%s as you are not the owner. You should speak to %s.' % (ticket.id, ticket['owner'])
                return False, msg

        # If we get here then we know we can start work
        return True, None

    def save_ticket(self, tkt, who, msg, when):
        when = to_datetime(when)
        tkt.save_changes(who, msg, when)
        
        tn = TicketNotifyEmail(self.env)
        tn.notify(tkt, newticket=0, modtime=when)

    def start_work(self, username, tkt_or_id, when=None):

        if isinstance(tkt_or_id, Ticket):
            tkt_id = tkt_or_id.id
            tkt = tkt_or_id
        else:
            tkt_id = int(tkt_or_id)
            tkt = Ticket(self.env, tkt_id)

        syllabus_id = self.pm.get_project_syllabus(tkt.pid)

        if when is None:
            when = int(time())

        can, why = self.can_work_on(username, tkt, syllabus_id)
        if not can:
            return False, why

        # We could just horse all the fields of the ticket to the right values
        # bit it seems more correct to follow the in-build state-machine for
        # ticket modification.

        if username != tkt['owner']:
            tkt['owner'] = username
            tkt['status'] = self.autoreassignaccept_status.syllabus(syllabus_id)
            tkt['resolution'] = self.autoreassignaccept_resolution.syllabus(syllabus_id)
            self.save_ticket(tkt, username, 'Automatically reassigning in order to start work.', when)

            # Reinitialise for next test
            tkt = Ticket(self.env, tkt_id)

        # Stop work on another ticket
        # depending on config options
        if self.autostopstart.syllabus(syllabus_id):
            # Don't care if this fails, as with these arguments the only failure
            # point is if there is no active task... which is the desired scenario
            self.stop_work(username, tkt.pid, when-1,
                           'Stopping work on this ticket to start work on #%s.' % (tkt_id))
 
        @self.env.with_transaction()
        def do_log(db):
            cursor = db.cursor()
            cursor.execute('INSERT INTO work_log (worker, ticket, lastchange, starttime, endtime) '
                           'VALUES (%s, %s, %s, %s, %s)',
                           (username, tkt_id, when, when, 0))

        return True, None

    def stop_work(self, username, pid, stoptime=None, comment=None):
        '''Stop active user task in specified project.

        `stoptime` - UNIX timestamp
        '''

        active = self.get_active_task(username, pid)
        if not active:
            return False, 'There are no active tasks.'

        now = int(time())
        if stoptime:
            if stoptime <= active['starttime']:
                return False, 'You cannot set your stop time to that value as it is before the start time!'
            elif stoptime > now:
                return False, 'You cannot set your stop time to that value as it is in the future!'
        else:
            stoptime = now

        tkt_id = active['ticket']

        @self.env.with_transaction()
        def do_log(db):
            cursor = db.cursor()
            cursor.execute('UPDATE work_log '
                           'SET endtime=%s, lastchange=%s, comment=%s '
                           'WHERE worker=%s AND ticket=%s AND lastchange=%s AND endtime=0',
                           (stoptime, stoptime, comment,
                            username, tkt_id, active['lastchange']))

        syllabus_id = self.pm.get_project_syllabus(pid)

        plugtne = self.timingandestimation.syllabus(syllabus_id) and self.configs.syllabus(syllabus_id).get('ticket-custom', 'hours')
        plughrs = self.trachoursplugin.syllabus(syllabus_id) and self.configs.syllabus(syllabus_id).get('ticket-custom', 'totalhours')

        message = ''
        hours = 0.0

        if plugtne or plughrs:
            round_delta = self.roundup.syllabus(syllabus_id) or 1
            # Get the delta in minutes
            delta = ( int(stoptime) - int(active['starttime']) ) / 60.0
            # Round up if needed
            delta = int(round((delta / round_delta) + 0.5)) * round_delta
            hours = delta / 60.0

        if plughrs:
            message = 'Hours recorded automatically by the worklog plugin. %s hours' % hours
        elif self.comment.syllabus(syllabus_id) or comment:
            started = to_datetime(active['starttime'])
            finished = to_datetime(stoptime)
            message = '%s worked on this ticket for %s between %s and %s.' % (
                       username, pretty_timedelta(started, finished),
                       format_datetime(active['starttime']), format_datetime(stoptime))
        if comment:
            message += "\n\n" + comment

        if plugtne or plughrs:
            if not message:
                message = 'Hours recorded automatically by the worklog plugin.'

            tckt = Ticket(self.env, tkt_id)

            if plugtne:
                tckt['hours'] = hours
            self.save_ticket(tckt, username, message, stoptime)
            message = None

        if message:
            tckt = Ticket(self.env, active['ticket'])
            self.save_ticket(tckt, username, message, stoptime)

        return True, None

    def who_is_working_on(self, tkt_id):
        '''Return (who, since) are working on ticket'''
        db = self.env.get_read_db()
        cursor = db.cursor()
        cursor.execute('SELECT worker,starttime FROM work_log WHERE ticket=%s AND endtime=0', (tkt_id,))
        res = cursor.fetchone()
        if res:
            return res
        return None,None

    def who_last_worked_on(self, tkt_id):
        raise NotImplementedError

    def get_latest_task(self, username, pid):
        if username == 'anonymous':
            return None

        db = self.env.get_read_db()
        cursor = db.cursor()

        task = {}
        cursor.execute('''
            SELECT worker, ticket, summary, lastchange, starttime, endtime, comment
            FROM (
                SELECT wl.worker, wl.ticket, t.summary, wl.lastchange, wl.starttime, wl.endtime, wl.comment,
                MAX(wl.lastchange) OVER (PARTITION BY wl.worker) latest
                FROM work_log wl
                JOIN ticket t ON wl.ticket=t.id AND t.project_id=%s
                WHERE wl.worker=%s
            ) wll
            WHERE lastchange=latest
            ORDER BY endtime
            LIMIT 1
            ''', (pid, username))

        for user,ticket,summary,lastchange,starttime,endtime,comment in cursor:
            task['user'] = user
            task['ticket'] = ticket
            task['summary'] = summary
            task['lastchange'] = lastchange
            task['starttime'] = starttime
            task['endtime'] = endtime
            task['comment'] = comment
        return task
    
    def get_active_task(self, username, pid):
        task = self.get_latest_task(username, pid)
        if not task:
            return None
        if not task.has_key('endtime'):
            return None

        if task['endtime'] > 0:
            return None

        return task

    def get_work_log(self, pid, username=None, mode='all'):
        db = self.env.get_read_db()
        cursor = db.cursor()
        if mode == 'user':
            assert username is not None
            cursor.execute('SELECT wl.worker, wl.starttime, wl.endtime, wl.ticket, t.summary, t.status, wl.comment '
                           'FROM work_log wl '
                           'JOIN ticket t ON wl.ticket=t.id '
                           'WHERE t.project_id=%s AND wl.worker=%s '
                           'ORDER BY wl.lastchange DESC',
                           (pid, username))
        elif mode == 'latest':
            cursor.execute('''
                SELECT worker, starttime, endtime, ticket, summary, status, comment 
                FROM (
                    SELECT wl.worker, wl.starttime, wl.endtime, wl.ticket, wl.comment, wl.lastchange,
                    MAX(wl.lastchange) OVER (PARTITION BY wl.worker) latest,
                    t.summary, t.status
                    FROM work_log wl
                    JOIN ticket t ON wl.ticket=t.id AND project_id=%s
                ) wll
                WHERE lastchange=latest
                ORDER BY lastchange DESC, worker
               ''', (pid,))
        else:
            cursor.execute('SELECT wl.worker, wl.starttime, wl.endtime, wl.ticket, t.summary, t.status, wl.comment '
                           'FROM work_log wl '
                           'JOIN ticket t ON wl.ticket=t.id '
                           'WHERE t.project_id=%s '
                           'ORDER BY wl.lastchange DESC, wl.worker',
                           (pid,))

        rv = []
        for user,starttime,endtime,ticket,summary,status,comment in cursor:
            started = to_datetime(starttime)

            if endtime != 0:
                finished = to_datetime(endtime)
                delta = 'Worked for %s (between %s and %s)' % (
                         pretty_timedelta(started, finished),
                         format_datetime(started), format_datetime(finished))
            else:
                finished = 0
                delta = 'Started %s ago (%s)' % (
                         pretty_timedelta(started),
                         format_datetime(started))

            rv.append({'user': user,
                       'starttime': started,
                       'endtime': finished,
                       'delta': delta,
                       'ticket': ticket,
                       'summary': summary,
                       'status': status,
                       'comment': comment})
        return rv
        