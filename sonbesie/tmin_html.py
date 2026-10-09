"""Parse Campbell TableDisplay HTML without database or network side effects."""
from __future__ import absolute_import

import datetime
import re

try:
    from html.parser import HTMLParser
except ImportError:  # Python 2 on the collector
    from HTMLParser import HTMLParser


class _TableParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('th', 'td') and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('th', 'td') and self.cell is not None:
            self.row.append(''.join(self.cell).strip().strip('"').strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None


def parse_tmin_html(document):
    """Return validated column names and rows; map logger NAN values to None."""
    if isinstance(document, bytes):
        document = document.decode('utf-8')
    parser = _TableParser()
    parser.feed(document)
    parser.close()
    if not parser.rows:
        raise ValueError('No TMin table found in HTML response')
    columns = [{'TIMESTAMP': 'TimeStamp', 'RECORD': 'Record'}.get(c.upper(), c)
               for c in parser.rows[0]]
    if columns[:2] != ['TimeStamp', 'Record']:
        raise ValueError('Expected TimeStamp and Record as the first TMin columns')
    if (len(set(c.lower() for c in columns)) != len(columns) or
            any(not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', c) for c in columns)):
        raise ValueError('Invalid or duplicate TMin column names')
    rows = []
    for number, values in enumerate(parser.rows[1:], 2):
        if len(values) != len(columns):
            raise ValueError('TMin row %d has %d values; expected %d' %
                             (number, len(values), len(columns)))
        # Campbell includes fractional seconds (e.g. 16:12:00.0).
        timestamp = values[0]
        date_format = '%Y-%m-%d %H:%M:%S.%f' if '.' in timestamp else '%Y-%m-%d %H:%M:%S'
        datetime.datetime.strptime(timestamp, date_format)
        int(values[1])
        rows.append([None if value.upper() == 'NAN' else value for value in values])
    return columns, rows
