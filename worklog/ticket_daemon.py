from trac.ticket import ITicketChangeListener, Ticket
from trac.core import *
from manager import WorkLogManager

from trac.project.api import ProjectManagement

class WorkLogTicketObserver(Component):

    implements(ITicketChangeListener)

    def __init__(self):
        self.mgr = WorkLogManager(self.env)

    def ticket_created(self, ticket):
        """Called when a ticket is created."""
        pass

    def ticket_changed(self, ticket, comment, author, old_values):
        """Called when a ticket is modified.
        
        `old_values` is a dictionary containing the previous values of the
        fields that have changed.
        """
        syllabus_id = ProjectManagement(self.env).get_project_syllabus(ticket.pid)
        if self.mgr.autostop.syllabus(syllabus_id) \
               and 'closed' == ticket['status'] \
               and 'closed' != old_values.get('status'):
            who, since = self.mgr.who_is_working_on(ticket.id)
            if who:
                self.mgr.stop_work(who, ticket.pid)

    def ticket_deleted(self, ticket):
        """Called when a ticket is deleted."""
        pass

