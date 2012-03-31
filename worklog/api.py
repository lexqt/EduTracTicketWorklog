# -*- coding: utf-8 -*-

from time import time

from trac.core import *
from trac.env import IEnvironmentSetupParticipant

from usermanual import *
from manager import *
from webui import *
from webadminui import *
from ticket_filter import *
from timeline_hook import *
from ticket_daemon import *
try:
    from xmlrpc import *
except:
    pass

class WorkLogSetupParticipant(Component):

    implements(IEnvironmentSetupParticipant)

    db_version_key = 'TicketWorklogPlugin'
    db_version = 1

    """Extension point interface for components that need to participate in the
    creation and upgrading of Trac environments, for example to create
    additional database tables."""
    def __init__(self):
        # Initialise database schema version tracking.
        db = self.env.get_read_db()
        cursor = db.cursor()
        cursor.execute("SELECT value FROM system WHERE name=%s", (self.db_version_key,))
        try:
            self.db_installed_version = int(cursor.fetchone()[0])
        except:
            @self.env.with_transaction()
            def do_init(db):
                cursor = db.cursor()
                self.db_installed_version = 0
                cursor.execute("INSERT INTO system (name,value) VALUES(%s,%s)",
                               (self.db_version_key, self.db_installed_version))

    def environment_created(self):
        """Called when a new Trac environment is created."""

    def system_needs_upgrade(self):
        return self.db_installed_version < self.db_version

    def do_db_upgrade(self, db):
        # Do the staged updates
        cursor = db.cursor()
        if self.db_installed_version < 1:
            print 'Creating work_log table'
            cursor.execute('CREATE TABLE work_log ('
                           'worker     VARCHAR(255) REFERENCES users (username) ON DELETE CASCADE ON UPDATE CASCADE,'
                           'ticket     INTEGER REFERENCES ticket (id) ON DELETE CASCADE,'
                           'lastchange INTEGER,'
                           'starttime  INTEGER,'
                           'endtime    INTEGER,'
                           'comment    TEXT,'
                           'CONSTRAINT work_log_pk PRIMARY KEY (worker, ticket, lastchange)'
                           ')')

        # Updates complete, set the version
        cursor.execute("UPDATE system SET value=%s WHERE name=%s", 
                       (self.db_version, self.db_version_key))

    def needs_user_man(self):
        db = self.env.get_read_db()
        cursor = db.cursor()
        try:
            cursor.execute('SELECT MAX(version) FROM wiki WHERE name=%s', (user_manual_wiki_title,))
            maxversion = int(cursor.fetchone()[0])
        except:
            maxversion = 0

        return maxversion < user_manual_version

    def do_user_man_update(self, db):
        when = int(time())
        cursor = db.cursor()
        cursor.execute('INSERT INTO wiki (name,version,time,author,ipnr,text,comment,readonly) '
                       'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                       (user_manual_wiki_title, user_manual_version, when,
                        'trac', '127.0.0.1', user_manual_content,
                        '', 0))

    def environment_needs_upgrade(self, db):
        """Called when Trac checks whether the environment needs to be upgraded.
        
        Should return `True` if this participant needs an upgrade to be
        performed, `False` otherwise.

        """
        return self.system_needs_upgrade() or self.needs_user_man()

    def upgrade_environment(self, db):
        """Actually perform an environment upgrade.

        Implementations of this method should not commit any database
        transactions. This is done implicitly after all participants have
        performed the upgrades they need without an error being raised.
        """
        print "Worklog needs an upgrade"
        if self.system_needs_upgrade():
            print " * Upgrading Database"
            self.do_db_upgrade(db)
        if self.needs_user_man():
            print " * Upgrading usermanual"
            self.do_user_man_update(db)
        print "Done upgrading Worklog"

