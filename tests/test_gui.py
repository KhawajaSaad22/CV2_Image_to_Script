import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import copy
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PySide6.QtWidgets import QApplication,QComboBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from unittest.mock import patch
import engine
from workbench import Workbench

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    @classmethod
    def tearDownClass(cls):
        cls.app.processEvents(); cls.app.quit()
        # Destroy Qt before Python module finalization (notably Python 3.12 on Windows).
        import shiboken6
        shiboken6.delete(cls.app); cls.app=None
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.image=np.random.default_rng(7).integers(0,256,(80,100,3),dtype=np.uint8)
        engine.write_image(self.root/'one.png',self.image); engine.write_image(self.root/'two.png',np.zeros_like(self.image))
        self.window=Workbench(); self.window.show(); self.window.load_paths([str(self.root/'one.png'),str(self.root/'two.png')]); self.wait_preview()
    def tearDown(self):
        self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents(); self.temp.cleanup()
    def wait_preview(self):
        for _ in range(500):
            self.app.processEvents(); QTest.qWait(10)
            if self.window.final is not None:return
        self.fail('Preview did not finish: '+self.window.metadata.text())
    def add(self,kind):self.window.kind.setCurrentText(kind); self.window.add_step(); self.wait_preview()
    def test_gallery_and_stage(self):
        self.add('grayscale'); self.assertEqual(self.window.final.ndim,2)
        self.assertEqual(self.window.stage.count(),2)
        self.window.gallery.setCurrentRow(1); self.wait_preview(); self.assertEqual(self.window.final.max(),0)
    def test_reorder_disable_history(self):
        self.add('grayscale'); self.add('gaussian_blur'); ids=[s['id'] for s in self.window.document.pipeline['steps']]
        self.window.move(-1); self.wait_preview(); self.assertEqual(self.window.document.pipeline['steps'][0]['id'],ids[1])
        self.window.undo(); self.wait_preview(); self.assertEqual(self.window.document.pipeline['steps'][0]['id'],ids[0])
        self.window.redo(); self.wait_preview(); self.assertEqual(self.window.document.pipeline['steps'][0]['id'],ids[1])
    def test_rapid_edits_latest_wins(self):
        self.add('brightness_contrast')
        for value in range(0,80,5):self.window.change_parameter('brightness',value)
        self.wait_preview(); expected=engine.run(self.image,self.window.document.pipeline)[0]
        np.testing.assert_array_equal(self.window.final,expected)
    def test_duplicate_remove(self):
        self.add('gamma'); self.window.duplicate(); self.wait_preview()
        self.assertEqual(len(set(s['id'] for s in self.window.document.pipeline['steps'])),2)
        self.window.remove(); self.wait_preview(); self.assertEqual(len(self.window.document.pipeline['steps']),1)
    def test_exact_mode(self):
        self.window.exact.setChecked(True); self.wait_preview(); self.assertIn('EXACT',self.window.metadata.text())
    def test_toggle_recomputes(self):
        self.add('grayscale'); self.window.steps.item(0).setCheckState(Qt.CheckState.Unchecked); self.wait_preview()
        np.testing.assert_array_equal(self.window.final,self.image)
    def test_save_open_and_export(self):
        self.add('gamma'); path=str(self.root/'pipeline.json'); script=str(self.root/'process.py')
        with patch('workbench.QFileDialog.getSaveFileName',return_value=(path,'')):self.window.save_pipeline()
        self.window.remove(); self.wait_preview()
        with patch('workbench.QFileDialog.getOpenFileName',return_value=(path,'')):self.window.open_pipeline()
        self.wait_preview(); self.assertEqual(self.window.document.pipeline['steps'][0]['type'],'gamma')
        with patch('workbench.QFileDialog.getSaveFileName',return_value=(script,'')):self.window.export()
        self.assertIn('run_cli(PIPELINE)',Path(script).read_text())
    def test_random_settings_validation(self):
        from generation_ui import RandomSettings
        import json
        dialog=RandomSettings(engine.new_step('gaussian_blur'),self.window)
        dialog.editor.setPlainText(json.dumps({'kernel':{'choices':[2,4]}}));dialog.accept_checked()
        self.assertIn('odd',dialog.error.text())
        dialog.editor.setPlainText(json.dumps({'kernel':{'choices':[3,5,7]}}));dialog.probability.setValue(.4);dialog.accept_checked()
        self.assertEqual(dialog.step['random']['probability'],.4);dialog.deleteLater()
    def test_generation_preview_and_dataset(self):
        from generation_ui import GenerationDialog
        import json
        recipe={'version':1,'steps':[engine.new_step('brightness_contrast')]}
        recipe['steps'][0]['random']={'params':{'brightness':{'min':-20,'max':20}}}
        dialog=GenerationDialog(recipe,[str(self.root/'one.png')],self.window);dialog.count.setValue(2)
        def wait():
            for _ in range(500):
                self.app.processEvents();QTest.qWait(10)
                if dialog.task is None:return
            self.fail('Generation worker timeout')
        dialog.preview();wait();self.assertEqual(len(dialog.samples),2);self.assertFalse(dialog.sheet.pixmap().isNull())
        sampled=copy.deepcopy(dialog.samples);dialog.preview();wait();self.assertEqual(dialog.samples,sampled)
        dialog.output.setText(str(self.root/'generated'));dialog.generate();wait()
        status=json.loads((self.root/'generated'/'run.json').read_text());self.assertEqual(status['generated'],2)
        dialog.close();dialog.deleteLater()

if __name__=='__main__':unittest.main()
