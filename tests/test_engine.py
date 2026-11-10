import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
import engine
from project import Document,export_script

def pipeline(*kinds):return {'version':1,'steps':[engine.new_step(k) for k in kinds]}

class EngineTests(unittest.TestCase):
    def setUp(self):self.image=np.random.default_rng(17).integers(0,256,(128,160,3),dtype=np.uint8)
    def test_every_operation(self):
        for kind in engine.OPERATIONS:
            with self.subTest(kind=kind):
                result,steps,times=engine.run(self.image,pipeline(kind))
                self.assertEqual(result.dtype,np.uint8); self.assertEqual(len(steps),1); self.assertEqual(len(times),1)
    def test_order(self):
        p=pipeline('brightness_contrast','threshold'); p['steps'][0]['params']['brightness']=100
        a=engine.run(self.image,p)[0]; p['steps'].reverse(); b=engine.run(self.image,p)[0]
        self.assertFalse(np.array_equal(a,b))
    def test_disable_recomputes_downstream(self):
        p=pipeline('brightness_contrast','gaussian_blur'); p['steps'][0]['params']['brightness']=100
        cache={}; engine.run(self.image,p,cache); p['steps'][0]['enabled']=False
        result=engine.run(self.image,p,cache)[0]
        np.testing.assert_array_equal(result,engine.run(self.image,pipeline('gaussian_blur'))[0])
    def test_cache_image_scope(self):
        p=pipeline('brightness_contrast'); cache={}; engine.run(self.image,p,cache)
        other=np.zeros_like(self.image); np.testing.assert_array_equal(engine.run(other,p,cache)[0],other)
    def test_negative_brightness_clips(self):
        p=pipeline('brightness_contrast'); p['steps'][0]['params']['brightness']=-100
        np.testing.assert_array_equal(engine.run(np.full((2,2,3),20,np.uint8),p)[0],0)
    def test_grayscale_chain(self):
        out=engine.run(self.image,pipeline('grayscale','clahe','canny','morphology'))[0]
        self.assertEqual(out.ndim,2)
    def test_bad_kernel(self):
        p=pipeline('gaussian_blur'); p['steps'][0]['params']['kernel']=4
        with self.assertRaises(ValueError):engine.validate(p)
    def test_reject_unknown_parameters(self):
        p=pipeline('grayscale'); p['steps'][0]['params']['code']='eval()'
        with self.assertRaises(ValueError):engine.validate(p)
    def test_reject_nan(self):
        p=pipeline('gamma'); p['steps'][0]['params']['gamma']=float('nan')
        with self.assertRaises(ValueError):engine.validate(p)
    def test_duplicate_id(self):
        p=pipeline('grayscale'); p['steps']*=2
        with self.assertRaises(ValueError):engine.validate(p)
    def test_crop_bounds(self):
        with self.assertRaises(ValueError):engine.run(np.zeros((10,10,3),np.uint8),pipeline('crop'))
    def test_cancel(self):
        with self.assertRaises(InterruptedError):engine.run(self.image,pipeline('grayscale'),cancel=lambda:True)
    def test_no_mutation(self):
        original=self.image.copy(); p=pipeline('clahe'); engine.run(self.image,p); np.testing.assert_array_equal(self.image,original)
    def test_history_is_configuration(self):
        d=Document(); p=pipeline('gaussian_blur'); d.commit(p); changed=copy.deepcopy(p); changed['steps'][0]['params']['kernel']=9; d.commit(changed)
        d.undo(); self.assertEqual(d.pipeline,p); d.redo(); self.assertEqual(d.pipeline,changed)
        d.undo(); d.commit(pipeline('grayscale')); self.assertFalse(d.redo_stack)
    def test_rgb_unicode_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tést image.png'; engine.write_image(path,self.image)
            np.testing.assert_array_equal(engine.read_image(path),self.image)
    def test_pipeline_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            p=pipeline('gamma'); path=Path(folder)/'pipeline.json'; engine.save_pipeline(path,p); self.assertEqual(engine.load_pipeline(path),p)
    def test_export_all_operations_exact_pixels(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'input.png'; engine.write_image(source,self.image)
            for kind in engine.OPERATIONS:
                with self.subTest(kind=kind):
                    p=pipeline(kind); script=root/'export.py'; output=root/'output.png'; export_script(script,p)
                    result=subprocess.run([sys.executable,str(script),str(source),str(output),'--overwrite'],capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,result.stderr)
                    np.testing.assert_array_equal(engine.read_image(output),engine.run(self.image,p)[0])
    def test_export_batch_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'inputs'; source.mkdir(); (source/'nested').mkdir()
            engine.write_image(source/'a.png',self.image); engine.write_image(source/'nested'/'a.png',self.image)
            script=root/'export.py'; export_script(script,pipeline('grayscale'))
            args=[sys.executable,str(script),str(source),str(root/'outputs')]
            self.assertEqual(subprocess.run(args,capture_output=True).returncode,0)
            self.assertTrue((root/'outputs'/'nested'/'a.png.png').exists())
            self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
    def test_input_output_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); script=root/'export.py'; export_script(script,pipeline())
            result=subprocess.run([sys.executable,str(script),str(root),str(root/'out')],capture_output=True)
            self.assertNotEqual(result.returncode,0)

if __name__=='__main__':unittest.main()
