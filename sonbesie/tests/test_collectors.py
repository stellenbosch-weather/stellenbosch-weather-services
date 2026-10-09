"""Exercise the collectors with the legacy MySQLdb connection API."""
import datetime
import os
import runpy
import shutil
import sys
import tempfile
import types
import unittest

try:
    import urllib.request as urllib2
    from io import StringIO
except ImportError:
    import urllib2
    from StringIO import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tmin_html import parse_tmin_html


class Output(StringIO):
    def __init__(self, terminal):
        StringIO.__init__(self)
        self.terminal = terminal

    def isatty(self):
        return self.terminal


class CollectorCompatibilityTests(unittest.TestCase):
    def test_collectors_with_legacy_mysql_driver(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'tests', 'fixtures', 'tmin.html'), 'rb') as handle:
            fixture = handle.read()
        columns, rows = parse_tmin_html(fixture)
        for script, terminal in [(s, tty) for s in ['TMinHTML.py', 'THourHTML.py', 'TDailyHTML.py', 'ThermocoupleHTML.py'] for tty in (False, True)]:
            inserted = []
            autocommit = []

            class Cursor(object):
                def execute(self, sql, params=None):
                    self.sql, self.params = sql, params
                    if sql.startswith('INSERT'):
                        inserted.append(params)

                def fetchone(self):
                    if 'MAX(Date)' in self.sql:
                        return (datetime.date(2026, 10, 9),)
                    if 'MAX(' in self.sql:
                        return (datetime.datetime(2026, 10, 9),)
                    # The first fixture record already exists and must be skipped.
                    return (1,) if self.params[0] == rows[0][0] else None

                def close(self):
                    pass

            class Connection(object):
                def autocommit(self, value):
                    autocommit.append(value)

                def cursor(self):
                    return Cursor()

                def commit(self):
                    pass

                def close(self):
                    pass

            # Older MySQLdb rejects autocommit as a connect() keyword.
            def connect(host, user, passwd, db, port):
                return Connection()

            class Config(object):
                def get(self, section, option):
                    return 'unused'

                def has_option(self, section, option):
                    return False

            mysql = types.ModuleType('MySQLdb')
            mysql.connect = connect
            mysql.Error = RuntimeError
            settings = types.ModuleType('settings_loader')
            settings.load_settings = lambda: Config()
            saved_modules = {name: sys.modules.get(name) for name in ['MySQLdb', 'settings_loader']}
            saved_argv, saved_stdout, saved_urlopen = sys.argv, sys.stdout, urllib2.urlopen
            saved_path = list(sys.path)
            directory = tempfile.mkdtemp()
            try:
                sys.modules['MySQLdb'] = mysql
                sys.modules['settings_loader'] = settings
                sys.argv = [script] + (['--records', '3'] if script == 'TMinHTML.py' else [])
                sys.stdout = Output(terminal)
                urllib2.urlopen = lambda *args, **kwargs: type('Response', (object,), {
                    'read': lambda self: fixture, 'close': lambda self: None})()
                target = os.path.join(directory, script)
                shutil.copyfile(os.path.join(root, script), target)
                runpy.run_path(target, run_name='__main__')
                output = sys.stdout.getvalue()
                if terminal:
                    self.assertIn('Downloading http://', output)
                    self.assertIn('Downloaded ', output)
                    self.assertIn('processed 3/3 records; inserted 2, skipped 1', output)
                    self.assertIn('complete;', output)
                else:
                    self.assertEqual(output, '', script)
                self.assertEqual(autocommit, [True], script)
                self.assertEqual(len(inserted), 2, script)
                self.assertEqual(inserted[0][2:], rows[1], script)
                self.assertEqual(len(inserted[0]), len(columns) + 2, script)
            finally:
                sys.argv, sys.stdout, urllib2.urlopen = saved_argv, saved_stdout, saved_urlopen
                sys.path[:] = saved_path
                for name, module in saved_modules.items():
                    if module is None:
                        sys.modules.pop(name, None)
                    else:
                        sys.modules[name] = module
                shutil.rmtree(directory)
