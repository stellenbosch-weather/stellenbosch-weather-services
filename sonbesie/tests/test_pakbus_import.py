import datetime
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pakbus_import as importer
from settings_loader import configparser


class PakBusTests(unittest.TestCase):
    def setUp(self):
        self.definition = {'Header': {'TableName': b'TMin', 'TableSize': 100}, 'Signature': 1,
                           'Fields': [{'FieldName': b'Rain_1_Tot', 'FieldType': 'IEEE4B', 'Dimension': 1},
                                      {'FieldName': b'PeakTime', 'FieldType': 'NSec', 'Dimension': 1}]}
        self.stamp = datetime.datetime(2026, 10, 9, 12)
        self.row = {'TimeOfRec': self.stamp, 'RecNbr': 123,
                    'Fields': {b'Rain_1_Tot': float('nan'), b'PeakTime': (60, 500000000)}}

    def test_host_uses_pakbus_port_not_http_port(self):
        config = configparser.ConfigParser()
        config.add_section('sonbesie')
        for address in ('127.0.0.1:8888', 'http://127.0.0.1:8888', '127.0.0.1'):
            config.set('sonbesie', 'address', address)
            self.assertEqual(importer.pakbus_url(config), 'tcp:127.0.0.1:5001')
        config.set('sonbesie', 'pakbus_port', '5002')
        self.assertEqual(importer.pakbus_url(config), 'tcp:127.0.0.1:5002')

    def test_timestamp_page_boundary_preserves_microseconds(self):
        self.assertEqual(importer.time_to_nsec(importer.EPOCH + datetime.timedelta(seconds=1, microseconds=1)), (1, 1000))

    def test_binary_fields_and_nan(self):
        values = importer.row_values(self.row, self.definition)
        self.assertEqual(values[:4], [self.stamp.date(), self.stamp.time(), self.stamp, 123])
        self.assertIsNone(values[4])
        self.assertEqual(values[5], datetime.datetime(1990, 1, 1, 0, 1, 0, 500000))

    def test_mapping_and_array_rejection(self):
        logger = Mock(table_def=[self.definition])
        self.assertEqual(importer.table_definition(logger, 'TMin')[2],
                         ['Date', 'Time', 'TimeStamp', 'Record', 'Rain_1_Tot', 'PeakTime'])
        self.definition['Fields'][0]['Dimension'] = 2
        with self.assertRaises(ValueError):
            importer.table_definition(logger, 'TMin')

    @patch.object(importer, 'collect')
    def test_record_backfill_pages_and_ignores_database_watermark(self, collect):
        second = dict(self.row, RecNbr=124)
        collect.side_effect = [([second], False), ([self.row], True), ([second], False)]
        batches = list(importer.record_batches(Mock(), 1, self.definition, self.stamp, 2))
        self.assertEqual([r['RecNbr'] for b in batches for r in b], [123, 124])
        self.assertEqual(collect.call_args_list[1].args[3:], (6, 123, 125))
        self.assertEqual(collect.call_args_list[2].args[3:], (6, 124, 125))

    @patch.object(importer, 'collect')
    def test_timestamp_catchup_and_empty_database(self, collect):
        from pakbus_import import time_to_nsec
        logger = Mock()
        logger.gettime.return_value = self.stamp + datetime.timedelta(minutes=3)
        collect.side_effect = [([self.row], True), ([], False)]
        list(importer.record_batches(logger, 1, self.definition, self.stamp))
        self.assertEqual(collect.call_args_list[0].args[4], time_to_nsec(self.stamp))
        self.assertEqual(collect.call_args_list[1].args[4], time_to_nsec(self.stamp + datetime.timedelta(microseconds=1)))
        collect.reset_mock()
        collect.side_effect = [([], False)]
        self.assertEqual(list(importer.record_batches(logger, 1, self.definition)), [])
        self.assertEqual(collect.call_args.args[4], (1, 0))

    @patch.object(importer, 'collect')
    def test_logger_rounds_timestamp_boundary_down(self, collect):
        logger = Mock()
        logger.gettime.return_value = self.stamp + datetime.timedelta(minutes=2)
        second = dict(self.row, RecNbr=124, TimeOfRec=self.stamp + datetime.timedelta(minutes=1))
        collect.side_effect = [([self.row], True), ([self.row, second], False)]
        rows = [row for batch in importer.record_batches(logger, 1, self.definition, self.stamp) for row in batch]
        self.assertEqual([r['RecNbr'] for r in rows], [123, 124])

    @patch.object(importer, 'collect', return_value=([], True))
    def test_no_progress_is_an_error(self, collect):
        logger = Mock()
        logger.gettime.return_value = self.stamp + datetime.timedelta(minutes=1)
        with self.assertRaises(RuntimeError):
            list(importer.record_batches(logger, 1, self.definition, self.stamp))

    def test_failed_response_is_not_empty_success(self):
        logger = Mock()
        logger.send_wait.return_value = (None, {'RespCode': 7}, None)
        with self.assertRaises(RuntimeError):
            importer.collect(logger, 1, self.definition, 5, 1)

    def test_duplicate_skip_commit_and_rollback(self):
        connection, cursor = Mock(), Mock()
        cursor.fetchone.side_effect = [(1,), None]
        self.assertEqual(importer.save_batch(connection, cursor, 'TMin',
                         ['Date', 'Time', 'TimeStamp', 'Record', 'Rain_1_Tot', 'PeakTime'],
                         [self.row, self.row], self.definition), 1)
        connection.commit.assert_called_once_with()
        self.assertEqual(len([c for c in cursor.execute.call_args_list if c.args[0].startswith('INSERT')]), 1)
        cursor.execute.side_effect = RuntimeError('database failure')
        with self.assertRaises(RuntimeError):
            importer.save_batch(connection, cursor, 'TMin', ['TimeStamp'], [self.row], self.definition)
        connection.rollback.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
