import re

from trac.core import *
from trac.web.api import ITemplateStreamFilter
from trac.web.chrome import add_stylesheet, add_script
from trac.wiki import wiki_to_oneliner
from trac.util import pretty_timedelta
from trac.project.api import ProjectManagement

from manager import WorkLogManager

from genshi import XML
from genshi.filters.transform import Transformer

class WorkLogTicketAddon(Component):

    implements(ITemplateStreamFilter)

    def __init__(self):
        self.mgr = WorkLogManager(self.env)
        self.pm = ProjectManagement(self.env)

    def get_task_markup(self, req, ticket, task):
        if not task:
            return ''

        ticket_text = 'ticket #' + str(task['ticket'])
        if task['ticket'] == ticket:
            ticket_text = 'this ticket'
        timedelta = pretty_timedelta(task['starttime'], None);

        return '<li>%s</li>' % wiki_to_oneliner('You have been working on %s for %s' % (ticket_text, timedelta), self.env, req=req)

    def get_ticket_markup(self, who, since):
        timedelta = pretty_timedelta(since, None);
        return '<li>%s has been working on this ticket for %s</li>' % (who, timedelta)

    def get_ticket_markup_noone(self):
        return '<li>Nobody is working on this ticket</li>'

    def get_button_markup(self, req, ticket, stop=False):
        if stop:
            action = 'stop'
            label = 'Stop Work'
        else:
            action = 'start'
            label = 'Start Work'

        return '''
            <form id="worklogTicketForm" method="post" action="%s" class="inlinebuttons" onsubmit="return tracWorklog.%s();">
              <input type="hidden" name="source_url" value="%s" />
              <input type="hidden" name="ticket" value="%s" />
              <input type="submit" name="%swork" value="%s" />
            </form>
            <div id="worklogPopup" class="jqmWindow">
              <div style="text-align: right;">
                <span style="text-decoration: underline; color: blue; cursor: pointer;" class="jqmClose">close</span>
              </div>
              <form method="post" action="%s" class="inlinebuttons">
                <input type="hidden" name="source_url" value="%s" />
                <input type="hidden" name="ticket" value="%s" />
                <input id="worklogStoptime" type="hidden" name="stoptime" value="" />
                <fieldset>
                  <legend>Stop work</legend>
                  <div class="field">
                    <fieldset class="iefix">
                      <label for="worklogComment">Optional: Leave a comment about the work you have done...</label>
                      <p><textarea id="worklogComment" name="comment" class="wikitext" rows="6" cols="60"></textarea></p>
                    </fieldset>
                  </div>
                  <div class="field">
                    <label>Override end time</label>
                    <div align="center">
                      <div style="width: 185px;">
                        <div id="worklogStopDate"></div>
                        <br clear="all" />
                        <div style="text-align: right;">
                          &nbsp;&nbsp;@&nbsp;<input id="worklogStopTime" type="text" size="6" />
                        </div>
                      </div>
                    </div>
                  </div>
                  <div style="text-align: right;"><input id="worklogSubmit" type="submit" name="%swork" value="%s" /></div>
                </fieldset>
              </form>
            </div>
            ''' % (req.href.worklog(), action,
                   req.href.ticket(ticket),
                   ticket,
                   action, label,
                   req.href.worklog(),
                   req.href.ticket(ticket),
                   ticket,
                   action, label)

    # ITemplateStreamFilter

    def filter_stream(self, req, method, filename, stream, data):
        match = re.match(r'/ticket/([0-9]+)$', req.path_info)
        if match and req.perm.has_permission('WORK_LOG') and 'ticket' in data:
            ticket = data['ticket']
            self.pm.check_component_enabled(self, pid=ticket.pid)
            tkt_id = ticket.id

            add_stylesheet(req, "worklog/worklogplugin.css")

            add_script(req, 'worklog/jqModal.js')
            add_stylesheet(req, 'worklog/jqModal.css')

            add_stylesheet(req, 'common/css/jquery-ui/jquery.ui.core.css')
            add_stylesheet(req, 'common/css/jquery-ui/jquery.ui.datepicker.css')
            add_stylesheet(req, 'common/css/jquery-ui/jquery.ui.theme.css')
            add_script(req, 'common/js/jquery.ui.core.js')
            add_script(req, 'common/js/jquery.ui.widget.js')
            add_script(req, 'common/js/jquery.ui.datepicker.js')

            add_script(req, 'worklog/jquery.mousewheel.pack.js')
            add_script(req, 'worklog/jquery.timeentry.pack.js')

            add_script(req, 'worklog/tracWorklog.js')

            username = req.authname
            task_markup = ''
            if username != 'anonymous':
                task = self.mgr.get_active_task(username, ticket.pid)
                if task:
                    task_markup = self.get_task_markup(req, tkt_id, task)

            who, since = self.mgr.who_is_working_on(tkt_id)
            ticket_markup = ''
            if who:
                if who != username:
                    ticket_markup = self.get_ticket_markup(who, since)
            else:
                ticket_markup = self.get_ticket_markup_noone()

            button_markup = ''
            if username != 'anonymous':
                can, _ = self.mgr.can_work_on(username, ticket)
                if can:
                    # Display a "Work on Link" button.
                    button_markup = self.get_button_markup(req, tkt_id)
                elif task and task['ticket'] == tkt_id:
                    # We are currently working on this, so display the stop button...
                    button_markup = self.get_button_markup(req, tkt_id, True)

            # User's current task information
            html = XML('''
              <fieldset class="workloginfo">
                <legend>Work Log</legend>
                %s
                <ul>
                  %s
                  %s
                </ul>
              </fieldset>
              ''' % (button_markup, task_markup, ticket_markup))
            stream |= Transformer('.//div[@id="ticket"]').before(html)
        return stream

