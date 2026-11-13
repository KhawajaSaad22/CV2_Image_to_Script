import copy
import unittest
import engine
from project import Document


class DocumentStateTests(unittest.TestCase):
    def test_saved_state_follows_undo_redo_and_noops(self):
        doc=Document();self.assertFalse(doc.dirty)
        recipe={'version':1,'steps':[engine.new_step('gamma')]}
        doc.commit(recipe);self.assertTrue(doc.dirty)
        doc.mark_saved();doc.commit(copy.deepcopy(recipe));self.assertFalse(doc.dirty)
        changed=copy.deepcopy(recipe);changed['steps'][0]['params']['gamma']=2
        doc.commit(changed);self.assertTrue(doc.dirty)
        doc.undo();self.assertFalse(doc.dirty)
        doc.redo();self.assertTrue(doc.dirty)

    def test_load_resets_history_and_invalid_load_is_non_destructive(self):
        doc=Document();doc.commit({'version':1,'steps':[engine.new_step('flip')]})
        snapshot=copy.deepcopy(doc.pipeline)
        with self.assertRaises(ValueError):doc.load({'version':999,'steps':[]})
        self.assertEqual(doc.pipeline,snapshot);self.assertTrue(doc.dirty)
        doc.load(snapshot);self.assertFalse(doc.dirty);self.assertFalse(doc.undo_stack)
