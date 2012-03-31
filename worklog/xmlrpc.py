import xmlrpclib
import posixpath

from manager import WorkLogManager

from trac.core import *
from trac.perm import IPermissionRequestor
from tracrpc.api import IXMLRPCHandler, expose_rpc

class WorlLogRPC(Component):
    """ Interface to the [http://trac-hacks.org/wiki/WorkLogPlugin Work Log Plugin] """
    implements(IXMLRPCHandler)

    def __init__(self):
        self.mgr = WorkLogManager(self.env)

    def xmlrpc_namespace(self):
        return 'worklog'

    def xmlrpc_methods(self):
        yield ('WIKI_VIEW', ((int,),), self.getRPCVersionSupported)
        yield ('WIKI_VIEW', ((str, int),), self.startWork)
        yield ('WIKI_VIEW', ((str, int), (str, int, str), (str, int, str, int),), self.stopWork)
        yield ('WIKI_VIEW', ((dict, int), (dict, int, str),), self.getLatestTask)
        yield ('WIKI_VIEW', ((dict, int), (dict, int, str),), self.getActiveTask)
        yield ('WIKI_VIEW', ((str, int,),), self.whoIsWorkingOn)
        yield ('WIKI_VIEW', ((str, int,),), self.whoLastWorkedOn)

    def getRPCVersionSupported(self, req):
        """ Returns 1 with this version of the Work Log XMLRPC API. """
        return 1

    def startWork(self, req, ticket):
        """ Start work on a ticket. Returns the string 'OK' on success or an explanation on error (requires authentication)"""
        res, err = self.mgr.start_work(req.authname, ticket)
        if res:
            return 'OK'
        else:
            return err
            
    def stopWork(self, req, pid, comment=None, stoptime=None):
        """ Stops work. Returns the string 'OK' on success or an explanation on error (requires authentication, stoptime is seconds since epoch) """
        res, err = self.mgr.stop_work(req.authname, pid, stoptime, comment)
        if res:
            return 'OK'
        else:
            return err

    def getLatestTask(self, req, pid, username=None):
        """ Returns a structure representing the info about the latest task. """
        if not username:
            username = req.authname
        return self.mgr.get_latest_task(username, pid)
        
    def getActiveTask(self, req, pid, username=None):
        """ Returns a structure representing the info about the active task (identical to getLatestTask but does not return anything if the work has stopped). """
        if not username:
            username = req.authname
        return self.mgr.get_active_task(username, pid)
        
    def whoIsWorkingOn(self, req, ticket):
        """ Returns the username of the person currently working on the given ticket """
        who, since = self.mgr.who_is_working_on(ticket)
        return who
            
    def whoLastWorkedOn(self, req, ticket):
        """ Returns the username of the person last worked on the given ticket """
        return self.mgr.who_last_worked_on(ticket)
            
