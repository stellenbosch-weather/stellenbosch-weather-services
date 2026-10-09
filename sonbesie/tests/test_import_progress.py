import os
import sys
import threading
import unittest
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from import_progress import progress, error, stage


class Output(StringIO):
    def __init__(self, terminal):
        super(Output, self).__init__()
        self.terminal = terminal
        self.flushed = 0
        self.heartbeat = threading.Event()

    def isatty(self):
        return self.terminal

    def write(self, value):
        result = super(Output, self).write(value)
        if 'elapsed' in value:
            self.heartbeat.set()
        return result

    def flush(self):
        self.flushed += 1


class ProgressTests(unittest.TestCase):
    def test_cron_is_silent_and_starts_no_thread(self):
        output = Output(False)
        with patch('sys.stdout', output), patch('import_progress.threading.Thread') as worker:
            progress('normal progress')
            with stage('download'):
                pass
            worker.assert_not_called()
        self.assertEqual(output.getvalue(), '')

    def test_tty_shows_and_flushes_heartbeat_and_stops_on_error(self):
        output = Output(True)
        with patch('sys.stdout', output):
            with self.assertRaises(ValueError):
                with stage('Downloading', interval=0.01):
                    self.assertTrue(output.heartbeat.wait(2))
                    raise ValueError('network failed')
        self.assertIn('Downloading\n', output.getvalue())
        self.assertIn('elapsed)', output.getvalue())
        self.assertGreaterEqual(output.flushed, 2)

    def test_errors_remain_visible_without_tty(self):
        output = Output(False)
        with patch('sys.stderr', output):
            error('database failed')
        self.assertEqual(output.getvalue(), 'database failed\n')
        self.assertEqual(output.flushed, 1)


if __name__ == '__main__':
    unittest.main()
