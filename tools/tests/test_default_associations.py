"""回归：系统异步确认未完成时，只能提交一个关联变更。"""
import importlib.util
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'set_defaults.py'
spec = importlib.util.spec_from_file_location('set_defaults', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AssociationTests(unittest.TestCase):
    def test_pending_confirmation_stops_and_resume_preserves_original_state(self):
        with tempfile.TemporaryDirectory() as folder:
            app = (Path(folder) / 'Test.app').resolve()
            (app / 'Contents').mkdir(parents=True)
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
                'CFBundleIdentifier': 'com.haihome.localdocuments',
                'CFBundleDocumentTypes': [{'CFBundleTypeExtensions': ['docx', 'xlsx']}],
            }))
            report = Path(folder) / 'report.json'
            selected, submitted = set(), []

            def run(command, **kwargs):
                output = ''
                if '-x' in command:
                    ext = command[-1]
                    output = ('海家本地文档.app\n' + str(app) + '\ncom.haihome.localdocuments\n'
                              if ext in selected else 'Old.app\n/Applications/Old.app\ncom.example.old\n')
                if '-s' in command:
                    submitted.append(command[-2])
                return subprocess.CompletedProcess(command, 0, output, '')

            args = ['set_defaults.py', str(app), '--report', str(report), '--apply']
            with patch.object(module.subprocess, 'run', side_effect=run), \
                    patch.object(module.shutil, 'which', return_value='/mock/duti'), \
                    patch.object(sys, 'argv', args):
                self.assertEqual(module.main(), 2)
                self.assertEqual(submitted, ['.docx'])
                first = json.loads(report.read_text())
                self.assertEqual(first['pending_confirmation'], 'docx')
                selected.add('docx')
                self.assertEqual(module.main(), 2)
                self.assertEqual(submitted, ['.docx', '.xlsx'])
                selected.add('xlsx')
                self.assertEqual(module.main(), 0)
                self.assertEqual(submitted, ['.docx', '.xlsx'])
                final = json.loads(report.read_text())
                self.assertTrue(all(item['passed'] for item in final['extensions']))
                self.assertEqual([item['before'] for item in first['extensions']],
                                 [item['before'] for item in final['extensions']])


if __name__ == '__main__':
    unittest.main()
