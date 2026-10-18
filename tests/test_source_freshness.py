import json
import tempfile
import unittest
from pathlib import Path

from tests.test_build import FX, run


class SourceFreshness(unittest.TestCase):
    def test_missing_today_is_not_reported_as_sales_collapse(self):
        dump = json.loads((FX / 'sync_dump.json').read_text())
        dump['days']['2026-09-11'].update(wf1=0, wf2=0, wf_complete=False)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'dump.json'
            source.write_text(json.dumps(dump))
            sheet = Path(tmp) / 'sheet.csv'
            sheet.write_text('date,total\n2026-09-10,413509\n')
            data, report = run('--vashun-sheet-csv', str(sheet),
                               '--w1-extra-csv', str(Path(tmp) / 'no_extra.csv'),
                               sync_dump=source)
        for code in ('w1', 'v1'):
            block = data['objects'][code]
            self.assertFalse(block['today']['complete'])
            self.assertIsNone(block['today']['pct'])
            self.assertEqual(block['source']['today_status'], 'unavailable')
            self.assertEqual(block['source']['latest_available_day'], '2026-09-10')
        self.assertIn('vashun_today_source_missing', report['warnings'])
        self.assertIn('waterfalls_today_source_incomplete', report['warnings'])
        self.assertIsNone(data['objects']['all']['today']['pct'])

    def test_recovered_source_clears_missing_warning_without_changing_totals(self):
        data, _ = run()
        self.assertEqual(data['objects']['v1']['today']['value'], 461730)
        self.assertEqual(data['objects']['v1']['source']['today_status'], 'available')
        self.assertNotIn('vashun_today_source_missing', data['objects']['v1']['warnings'])
        self.assertEqual(data['objects']['w1']['today']['value'], 349750)
        self.assertEqual(data['objects']['w1']['source']['today_status'], 'incomplete')
