import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import engine
from recovery import RecoveryStore, read_snapshot


class RecoveryTests(unittest.TestCase):
    def test_isolated_windows_round_trip_and_clear_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            first=RecoveryStore(directory);second=RecoveryStore(directory)
            recipe={'version':1,'steps':[engine.new_step('gamma')]}
            first.write(recipe,'original.json');second.write(recipe)
            self.assertNotEqual(first.path,second.path)
            self.assertEqual(read_snapshot(first.path)['pipeline'],recipe)
            self.assertEqual(read_snapshot(first.path)['source_path'],'original.json')
            self.assertEqual(len(first.available()),2)
            first.clear();self.assertFalse(first.path.exists());self.assertTrue(second.path.exists())

    def test_failed_atomic_save_preserves_previous_recipe_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'recipe.json';before={'version':1,'steps':[]}
            engine.save_pipeline(path,before)
            after={'version':1,'steps':[engine.new_step('gamma')]}
            with patch.object(Path,'replace',side_effect=OSError('replacement denied')):
                with self.assertRaises(OSError):engine.save_pipeline(path,after)
            self.assertEqual(engine.load_pipeline(path),before)
            self.assertEqual(list(root.glob('*.tmp')),[])

    def test_failed_snapshot_update_preserves_last_good_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            store=RecoveryStore(directory);recipe={'version':1,'steps':[]};store.write(recipe)
            with patch.object(Path,'replace',side_effect=OSError('write failure')):
                with self.assertRaises(OSError):store.write({'version':1,'steps':[engine.new_step('flip')]})
            self.assertEqual(read_snapshot(store.path)['pipeline'],recipe)

    def test_invalid_oversized_and_non_recipe_snapshots_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json'
            for value in ({}, {'schema_version':2,'pipeline':{}},
                          {'schema_version':1,'pipeline':{'version':999,'steps':[]}},
                          {'schema_version':1,'pipeline':{'version':1,'steps':[]},'source_path':7}):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):read_snapshot(path)
            path.write_text('not JSON')
            with self.assertRaises(ValueError):read_snapshot(path)
            path.write_bytes(b' '*(4*1024*1024+1))
            with self.assertRaisesRegex(ValueError,'4 MiB'):read_snapshot(path)
