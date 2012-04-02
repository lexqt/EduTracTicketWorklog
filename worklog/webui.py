import re
from StringIO import StringIO
import csv

from usermanual import user_manual_title, user_manual_wiki_title
from manager import WorkLogManager
from trac.core import *
from trac.perm import IPermissionRequestor
from trac.web import IRequestHandler
from trac.util import Markup
from trac.web.chrome import add_stylesheet, INavigationContributor, ITemplateProvider

from trac.project.api import ProjectManagement


class WorkLogPage(Component):

    implements(IPermissionRequestor, INavigationContributor, IRequestHandler, ITemplateProvider)

    def __init__(self):
        self.mgr = WorkLogManager(self.env)

    # IPermissionRequestor

    def get_permission_actions(self):
        return ['WORK_LOG', ('WORK_VIEW', ['WORK_LOG']), ('WORK_ADMIN', ['WORK_VIEW'])]

    # INavigationContributor

    def get_active_navigation_item(self, req):
        return 'worklog'

    def get_navigation_items(self, req):
        url = req.href.worklog()
        if req.perm.has_permission("WORK_VIEW"):
            yield 'mainnav', "worklog", \
                  Markup('<a href="%s">%s</a>' % \
                         (url , "Work Log"))

    # Internal Methods
    def _worklog_csv(self, req, log):
        #req.send_header('Content-Type', 'text/plain')
        req.send_header('Content-Type', 'text/csv;charset=utf-8')
        req.send_header('Content-Disposition', 'filename=worklog.csv')

        # Headers
        fields = ['user',
                  'starttime',
                  'endtime',
                  'ticket',
                  'summary',
                  'comment']
        sep=','

        content = StringIO()
        writer = csv.writer(content, delimiter=sep, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([unicode(c).encode('utf-8') for c in fields])

        # Rows
        for row in log:
            values=[]
            for field in fields:
                values.append(unicode(row[field]).encode('utf-8'))
            writer.writerow(values)

        req.send_header('Content-Length', content.len)
        req.write(content.getvalue())

    # IRequestHandler

    def match_request(self, req):
        return req.path_info.startswith('/worklog')

    def process_request(self, req):
        req.perm.require('WORK_VIEW')
        
        messages = []

        def addMessage(s):
            messages.extend([s]);

        pm = ProjectManagement(self.env)
        self.pm = pm
        pid = pm.get_and_check_current_project(req, allow_multi=True)
        pm.check_component_enabled(self, pid=pid)

        add_stylesheet(req, "worklog/worklogplugin.css")

        # Specific pages

        match = re.search('/worklog/users/(.*)', req.path_info)
        if match:
            username = match.group(1)
            return self._user_worklog(req, username, pid)

        match = re.search('/worklog/stop/([0-9]+)', req.path_info)
        if match:
            tkt_id = match.group(1)
            return self._work_stop(req, tkt_id)


        username = req.authname
        if req.args.has_key('format') and req.args['format'] == 'csv':
            return self._worklog_csv(req, self.mgr.get_work_log(pid))

        # Not any specific page, so process POST actions here.
        if req.method == 'POST':
            if req.args.has_key('startwork') and req.args.has_key('ticket'):
                tkt_id = req.args['ticket']
                res, err = self.mgr.start_work(username, tkt_id)
                if not res:
                    addMessage(err)
                else:
                    addMessage('You are now working on ticket #%s.' % (tkt_id,))

                req.redirect(req.args['source_url'])

            elif req.args.has_key('stopwork'):
                res, err = self.mgr.stop_work(username, pid, req.args.getint('stoptime'), req.args.get('comment'))
                if not res:
                    addMessage(err)
                else:
                    addMessage('You have stopped working.')

                req.redirect(req.args.get('source_url'))

        # no POST, so they're just wanting a list of the worklog entries
        data = {"messages": messages,
                "worklog": self.mgr.get_work_log(pid, mode='latest'),
                "worklog_href": req.href.worklog(),
                "ticket_href": req.href.ticket(),
                "usermanual_href": req.href.wiki(user_manual_wiki_title),
                "usermanual_title": user_manual_title
                }
        return 'worklog.html', data, None

    def _user_worklog(self, req, username, pid):
        users = self.pm.get_project_users(pid)
        if username not in users:
            raise TracError('You can not view work log for users from other projects')

        worklog = self.mgr.get_work_log(pid, username, mode='user')

        if req.args.has_key('format') and req.args['format'] == 'csv':
            return self._worklog_csv(req, worklog)

        data = {"worklog": worklog,
                "username": username,
                "ticket_href": req.href.ticket(),
                "usermanual_href": req.href.wiki(user_manual_wiki_title),
                "usermanual_title": user_manual_title
                }
        return 'worklog_user.html', data, None

    def _work_stop(self, req, tkt_id):
        data = {'worklog_href': req.href.worklog(),
                'ticket_href':  req.href.ticket(tkt_id),
                'ticket':       tkt_id,
                'xhr':          req.is_ajax,
                'action':       'stop',
                'label':        'Stop Work'}
        return 'worklog_stop.html', data, None

    # ITemplateProvider
    def get_htdocs_dirs(self):
        """Return the absolute path of a directory containing additional
        static resources (such as images, style sheets, etc).
        """
        from pkg_resources import resource_filename
        return [('worklog', resource_filename(__name__, 'htdocs'))]

    def get_templates_dirs(self):
        """Return the absolute path of the directory containing the provided
        ClearSilver templates.
        """
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]
    
