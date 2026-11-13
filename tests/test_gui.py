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
        self.window.document.mark_saved()
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
    def test_unsaved_close_cancel_and_save_dialog_cancel(self):
        self.add('gamma')
        self.assertTrue(self.window.isWindowModified())
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QMessageBox
        with patch('workbench.QMessageBox.question',return_value=QMessageBox.StandardButton.Cancel):
            event=QCloseEvent();self.window.closeEvent(event);self.assertFalse(event.isAccepted())
        with patch('workbench.QMessageBox.question',return_value=QMessageBox.StandardButton.Save),patch('workbench.QFileDialog.getSaveFileName',return_value=('','')):
            self.assertFalse(self.window.confirm_unsaved())
        self.assertTrue(self.window.document.dirty)
    def test_open_cancel_and_failed_save_preserve_unsaved_recipe(self):
        self.add('gamma');before=copy.deepcopy(self.window.document.pipeline)
        path=self.root/'incoming.json';engine.save_pipeline(path,{'version':1,'steps':[]})
        from PySide6.QtWidgets import QMessageBox
        with patch('workbench.QFileDialog.getOpenFileName',return_value=(str(path),'')),patch('workbench.QMessageBox.question',return_value=QMessageBox.StandardButton.Cancel):
            self.window.open_pipeline()
        self.assertEqual(self.window.document.pipeline,before)
        with patch('workbench.QFileDialog.getSaveFileName',return_value=(str(path),'')),patch('engine.save_pipeline',side_effect=OSError('Disk full')),patch('workbench.QMessageBox.warning'):
            self.assertFalse(self.window.save_pipeline())
        self.assertTrue(self.window.document.dirty)
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
        with patch('workbench.QFileDialog.getOpenFileName',return_value=(path,'')),patch.object(self.window,'confirm_unsaved',return_value=True):self.window.open_pipeline()
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
    def test_guided_random_settings_roundtrip_and_validation(self):
        from generation_ui import RandomSettings
        import json
        dialog=RandomSettings(engine.new_step('gaussian_blur'),self.window)
        mode,low,high,choices,spec=dialog.rule_widgets['kernel']
        mode.setCurrentText('Choices');choices.setText('3, 5, 7')
        self.assertEqual(json.loads(dialog.editor.toPlainText()),{'kernel':{'choices':[3,5,7]}})
        dialog.accept_checked();self.assertEqual(dialog.step['random']['params']['kernel']['choices'],[3,5,7])
        dialog.deleteLater()
        other=RandomSettings(engine.new_step('gamma'),self.window)
        mode,low,high,choices,spec=other.rule_widgets['gamma'];mode.setCurrentText('Range');low.setValue(2);high.setValue(1)
        other.accept_checked();self.assertTrue(other.error.text());self.assertNotIn('random',other.step)
        other.deleteLater()
    def test_preview_preserves_viewport_zoom(self):
        self.window.after.scale(2,2);scale=self.window.after.transform().m11()
        self.add('brightness_contrast');self.window.change_parameter('brightness',15);self.wait_preview()
        self.assertAlmostEqual(self.window.after.transform().m11(),scale)
        self.window.gallery.setCurrentRow(1);self.wait_preview()
        self.assertNotAlmostEqual(self.window.after.transform().m11(),scale)
    def test_advanced_precision_is_not_silently_quantized(self):
        from generation_ui import RandomSettings
        step=engine.new_step('gamma');rules={'gamma':{'min':.812345678,'max':1.123456789}}
        step['random']={'params':rules}
        dialog=RandomSettings(step,self.window)
        self.assertEqual(dialog.tabs.currentIndex(),1)
        dialog.accept_checked();self.assertEqual(dialog.step['random']['params'],rules)
        dialog.deleteLater()
    def test_background_exact_save_uses_recipe_snapshot(self):
        self.add('brightness_contrast');self.window.change_parameter('brightness',10);self.wait_preview()
        expected=engine.run(self.image,self.window.document.pipeline)[0];path=str(self.root/'saved.png')
        with patch('workbench.QFileDialog.getSaveFileName',return_value=(path,'')):
            self.window.save_output()
        self.window.change_parameter('brightness',60)
        for _ in range(500):
            self.app.processEvents();QTest.qWait(10)
            if not self.window.save_jobs:break
        self.assertFalse(self.window.save_jobs);np.testing.assert_array_equal(engine.read_image(path),expected)
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
    def test_settings_include_help(self):
        from PySide6.QtWidgets import QLabel
        self.add('clahe')
        text=' '.join(w.text() for w in self.window.settings.findChildren(QLabel))
        self.assertIn('Contrast Limited Adaptive Histogram Equalization',text);self.assertIn('cv2.createCLAHE',text)
    def test_fixed_generation_requires_confirmation(self):
        from generation_ui import GenerationDialog
        from PySide6.QtWidgets import QMessageBox
        dialog=GenerationDialog({'version':1,'steps':[engine.new_step('grayscale')]},[str(self.root/'one.png')],self.window)
        dialog.output.setText(str(self.root/'no-duplicates'))
        with patch('generation_ui.QMessageBox.question',return_value=QMessageBox.StandardButton.No) as question:
            dialog.generate();question.assert_called_once()
        self.assertIsNone(dialog.task);self.assertFalse((self.root/'no-duplicates').exists());dialog.close();dialog.deleteLater()

if __name__=='__main__':unittest.main()
