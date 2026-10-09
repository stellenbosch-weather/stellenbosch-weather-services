import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tmin_html import parse_tmin_html


class TMinHTMLTests(unittest.TestCase):
    def setUp(self):
        path = os.path.join(os.path.dirname(__file__), 'fixtures', 'tmin.html')
        with open(path, 'rb') as handle:
            self.html = handle.read().decode('utf-8')

    def test_live_response_column_alignment(self):
        columns, rows = parse_tmin_html(self.html)
        self.assertEqual(len(columns), 20)
        self.assertEqual(len(rows), 3)
        self.assertEqual(columns[-2:], ['Rain_1_Tot', 'Rain_1_Accumulated'])
        for row in rows:
            self.assertEqual(len(row), len(columns))
            self.assertEqual(row[-2:], ['0', '0'])
            self.assertTrue(row[0].endswith(':00.0'))

    def test_nonzero_rain_nan_and_markup(self):
        html = '''<table><tr><th>TIMESTAMP</th><th>RECORD</th>
            <th>Rain_1_Tot</th><th>Rain_1_Accumulated</th><th>AirTC_Avg</th></tr>
            <tr><td> "2026-10-09 16:12:00.0" </td><td>42</td>
            <td><b>0.2</b></td><td>12.6</td><td>NAN</td></tr></table>'''
        columns, rows = parse_tmin_html(html)
        self.assertEqual(columns[:2], ['TimeStamp', 'Record'])
        self.assertEqual(rows[0], ['2026-10-09 16:12:00.0', '42', '0.2', '12.6', None])

    def test_missing_cell_rejected(self):
        with self.assertRaises(ValueError):
            parse_tmin_html(self.html.replace('<td nowrap>0</td>', '', 1))

    def test_error_response_rejected(self):
        with self.assertRaises(ValueError):
            parse_tmin_html('<html><body>Table unavailable</body></html>')

    def test_invalid_or_duplicate_headers_rejected(self):
        for header in ['Rain_1_Tot`', 'Rain_1_Tot']:
            with self.assertRaises(ValueError):
                parse_tmin_html(self.html.replace('Rain_1_Accumulated', header))

    def test_invalid_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            parse_tmin_html(self.html.replace('2026-10-09', '2026-99-09'))


if __name__ == '__main__':
    unittest.main()
