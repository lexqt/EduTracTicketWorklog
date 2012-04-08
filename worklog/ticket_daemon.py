from trac.ticket import ITicketChangeListener
from trac.core import Component, implements
from manager import WorkLogManager



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
        syllabus_id = ticket.syllabus_id
        if self.mgr.autostop.syllabus(syllabus_id) \
               and 'closed' == ticket['status'] \
               and 'closed' != old_values.get('status'):
            who, since = self.mgr.who_is_working_on(ticket.id)
            if who:
                self.mgr.stop_work(who, ticket.pid)

    def ticket_deleted(self, ticket):
        """Called when a ticket is deleted."""
        pass

