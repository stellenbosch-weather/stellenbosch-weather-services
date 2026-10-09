"""Read Sonbesie tables over PakBus/TCP and store them in the weather database."""
from __future__ import print_function

import argparse
from contextlib import contextmanager
import datetime
import fcntl
import math
import os
import re
import sys
try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings_loader import load_settings
from import_progress import progress

TABLES = ('TMin', 'THour', 'TDaily', 'Thermocouple')
EPOCH = datetime.datetime(1990, 1, 1)


def text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else value


def pakbus_url(config):
    address = config.get('sonbesie', 'address')
    host = urlsplit(address if '://' in address else 'http://' + address).hostname
    if not host:
        raise ValueError('sonbesie.address must contain a hostname')
    port = config.getint('sonbesie', 'pakbus_port') if config.has_option('sonbesie', 'pakbus_port') else 5001
    if not 1 <= port <= 65535:
        raise ValueError('Invalid sonbesie.pakbus_port')
    return 'tcp:%s:%d' % (host, port)


def table_definition(logger, table):
    for number, definition in enumerate(logger.table_def, 1):
        if text(definition['Header']['TableName']) == table:
            names = [text(f['FieldName']) for f in definition['Fields']]
            columns = ['Date', 'Time', 'TimeStamp', 'Record'] + names
            if (len(set(c.lower() for c in columns)) != len(columns) or
                    any(not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', c) for c in columns)):
                raise ValueError('Invalid or duplicate logger column names')
            for field in definition['Fields']:
                if field['Dimension'] != 1 and field['FieldType'] != 'ASCII':
                    raise ValueError('Array fields are not supported: %s' % text(field['FieldName']))
            return number, definition, columns
    raise ValueError('Logger table not found: ' + table)


def collect(logger, number, definition, mode, p1, p2=0):
    command = logger.pakbus.get_collectdata_cmd(number, definition['Signature'], mode, p1, p2)
    _, message, _ = logger.send_wait(command)
    if not message or message.get('RespCode') != 0:
        raise RuntimeError('PakBus collection failed: %s' % (message.get('RespCode') if message else 'no response'))
    fragments, more = logger.pakbus.parse_collectdata(message['RecData'], logger.table_def)
    rows = []
    for fragment in fragments:
        if fragment['TableNbr'] != number or fragment['IsOffset']:
            raise ValueError('Unexpected table or incomplete PakBus record')
        rows.extend(fragment['RecFrag'])
    return rows, more


def time_to_nsec(stamp):
    # pycampbellcr1000 0.4 drops microseconds; preserve them for page boundaries.
    delta = stamp - EPOCH
    return delta.days * 86400 + delta.seconds, delta.microseconds * 1000


def record_batches(logger, number, definition, last_date=None, records=None):
    """Page by record number for backfills, timestamp for automatic catch-up."""
    if records is not None:
        latest, _ = collect(logger, number, definition, 0x05, 1)
        if not latest:
            return
        stop = latest[-1]['RecNbr'] + 1  # PakBus's upper record bound is exclusive.
        start = max(0, stop - min(records, definition['Header']['TableSize']))
        mode = 0x06
    else:
        start = last_date or EPOCH + datetime.timedelta(seconds=1)
        stop = logger.gettime()  # Logger-local time, like the existing database.
        mode = 0x07
    while start < stop:
        p1, p2 = (time_to_nsec(start), time_to_nsec(stop)) if mode == 0x07 else (start, stop)
        rows, more = collect(logger, number, definition, mode, p1, p2)
        # The logger can round a timestamp request down to the preceding record.
        # Enforce the requested bounds locally so page boundaries never repeat.
        rows = [row for row in rows if
                (start <= row['TimeOfRec'] <= stop if mode == 0x07
                 else start <= row['RecNbr'] < stop)]
        if not rows:
            if more:
                raise RuntimeError('PakBus returned no records but reports more data')
            return
        next_start = (rows[-1]['TimeOfRec'] + datetime.timedelta(microseconds=1)
                      if mode == 0x07 else rows[-1]['RecNbr'] + 1)
        if next_start <= start:
            raise RuntimeError('PakBus collection did not advance')
        yield rows
        if not more:
            return
        start = next_start


def row_values(record, definition):
    stamp = record['TimeOfRec']
    values = [stamp.date(), stamp.time(), stamp, record['RecNbr']]
    for field in definition['Fields']:
        value = record['Fields'][field['FieldName']]
        if field['FieldType'] == 'NSec':
            value = EPOCH + datetime.timedelta(seconds=value[0], microseconds=value[1] / 1000)
        elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            value = None
        elif isinstance(value, bytes):
            value = text(value)
        values.append(value)
    return values


def save_batch(connection, cursor, table, columns, rows, definition):
    sql = 'INSERT INTO `SB_%s` (%s) VALUES (%s)' % (
        table, ', '.join('`%s`' % c for c in columns), ', '.join(['%s'] * len(columns)))
    inserted = 0
    try:
        for row in rows:
            values = row_values(row, definition)
            cursor.execute('SELECT 1 FROM `SB_%s` WHERE `TimeStamp` = %%s LIMIT 1' % table, (values[2],))
            if cursor.fetchone() is None:
                cursor.execute(sql, values)
                inserted += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return inserted


@contextmanager
def import_lock():
    # Serialize all PakBus collectors: the connection uses a single source node ID.
    # Keep the lock inode in place; flock releases it even if the process crashes.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PakBus.lock')
    with open(path, 'a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run(table, args):
    from pycampbellcr1000 import CR1000
    if table not in TABLES:
        raise ValueError('Unsupported Sonbesie table: ' + table)
    config = load_settings()
    connection = cursor = logger = None
    with import_lock():
        try:
            if not args.dry_run:
                try:
                    import MySQLdb
                except ImportError:
                    import pymysql as MySQLdb
                connection = MySQLdb.connect(
                    host=config.get('database', 'host'), user=config.get('database', 'username'),
                    passwd=config.get('database', 'password'), db=config.get('database', 'database'),
                    port=config.getint('database', 'port') if config.has_option('database', 'port') else 3306)
                connection.autocommit(False)
                cursor = connection.cursor()
                cursor.execute('SELECT MAX(`TimeStamp`) FROM `SB_%s`' % table)
                last_date = cursor.fetchone()[0]
            else:
                last_date = None
            logger = CR1000.from_url(pakbus_url(config), timeout=10)
            number, definition, columns = table_definition(logger, table)
            count = inserted = 0
            for rows in record_batches(logger, number, definition, last_date, args.records):
                if args.dry_run:
                    for row in rows:
                        row_values(row, definition)  # Validate conversions without database access.
                else:
                    inserted += save_batch(connection, cursor, table, columns, rows, definition)
                count += len(rows)
                progress('%s: read %d records, latest %s' % (table, count, rows[-1]['TimeOfRec']))
            summary = '%s: read %d, inserted %d%s' % (table, count, inserted, ' (dry run)' if args.dry_run else '')
            progress(summary)
            if not args.dry_run:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), table + '.log')
                with open(path, 'a') as log:
                    log.write('%s %s\n' % (datetime.datetime.now(), summary))
        finally:
            try:
                if logger is not None:
                    try:
                        logger.bye()
                    finally:
                        logger.pakbus.link.close()
            finally:
                try:
                    if cursor is not None:
                        cursor.close()
                finally:
                    if connection is not None:
                        connection.close()


def main(table):
    parser = argparse.ArgumentParser(description='Import Sonbesie %s over PakBus' % table)
    parser.add_argument('--records', type=int, help='Read this many latest retained records instead of automatic catch-up')
    parser.add_argument('--dry-run', action='store_true', help='Read and validate logger data without connecting to the database')
    args = parser.parse_args()
    if args.records is not None and args.records <= 0:
        parser.error('--records must be positive')
    if args.dry_run and args.records is None:
        parser.error('--dry-run requires --records to bound the read')
    try:
        run(table, args)
    except Exception as error:
        print('%s PakBus import failed: %s' % (table, error), file=sys.stderr)
        return 1
    return 0
