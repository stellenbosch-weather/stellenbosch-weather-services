"""Terminal-only progress using the standard library (including Python 2.7)."""
from contextlib import contextmanager
import sys
import threading
import time


def progress(message):
    if sys.stdout.isatty():
        sys.stdout.write(str(message) + '\n')
        sys.stdout.flush()


def error(message):
    sys.stderr.write(str(message) + '\n')
    sys.stderr.flush()


@contextmanager
def stage(message, interval=5):
    """Show elapsed time even while a blocking network/database call is waiting."""
    if not sys.stdout.isatty():
        yield
        return
    started = time.time()
    stopped = threading.Event()
    progress(message)

    def heartbeat():
        while not stopped.wait(interval):
            progress('%s (%ds elapsed)' % (message, time.time() - started))

    worker = threading.Thread(target=heartbeat)
    worker.daemon = True
    worker.start()
    try:
        yield
    finally:
        stopped.set()
        worker.join()
