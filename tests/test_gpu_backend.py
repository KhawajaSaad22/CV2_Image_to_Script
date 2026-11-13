import unittest
import numpy as np
import engine
from gpu_backend import run
try:
    import torch
    CUDA=torch.cuda.is_available()
except ImportError:CUDA=False


class GPUBackendTests(unittest.TestCase):
    def recipe(self):
        steps=[engine.new_step(k) for k in ('resize','flip','brightness_contrast','gamma','crop')]
        steps[0]['params'].update(width=37,height=29,interpolation='nearest')
        steps[2]['params'].update(contrast=1.2,brightness=-10)
        steps[-1]['params'].update(x=2,y=3,width=20,height=16)
        return {'version':1,'steps':steps}

    def test_cpu_path_preserves_engine_results(self):
        image=np.random.default_rng(9).integers(0,256,(31,43,3),np.uint8);recipe=self.recipe()
        expected=engine.run(image,recipe)[0];actual,_,_,info=run(image,recipe,'cpu')
        np.testing.assert_array_equal(actual,expected);self.assertEqual(info['device'],'cpu')

    def test_auto_fallback_without_torch(self):
        from unittest.mock import patch
        image=np.ones((8,8),np.uint8)
        with patch.dict('sys.modules',{'torch':None}):
            result,_,_,info=run(image,{'version':1,'steps':[]},'auto')
            self.assertEqual(info['device'],'cpu')
            with self.assertRaisesRegex(ValueError,'PyTorch'):run(image,{'version':1,'steps':[]},'cuda')

    def test_auto_cpu_fallback_retains_preview_cache(self):
        from unittest.mock import patch
        image=np.ones((8,8),np.uint8);cache={}
        recipe={'version':1,'steps':[engine.new_step('flip')]}
        with patch.dict('sys.modules',{'torch':None}):
            run(image,recipe,'auto',cache=cache)
            self.assertTrue(cache)
            with patch('engine.apply_operation',side_effect=AssertionError('Cache miss')):
                actual,_,_,info=run(image,recipe,'auto',cache=cache)
        np.testing.assert_array_equal(actual,image);self.assertEqual(info['device'],'cpu')

    @unittest.skipUnless(CUDA,'Needs a visible CUDA device')
    def test_cuda_supported_pipeline_and_mixed_fallback(self):
        image=np.random.default_rng(9).integers(0,256,(31,43,3),np.uint8);recipe=self.recipe()
        expected=engine.run(image,recipe)[0]
        actual,_,_,info=run(image,recipe,'cuda',strict=True)
        np.testing.assert_allclose(actual,expected,atol=1,rtol=0)
        self.assertTrue(all(s=='cuda' for s in info['steps']))
        recipe['steps'].append(engine.new_step('grayscale'))
        mixed,_,_,info=run(image,recipe,'cuda');self.assertEqual(info['device'],'mixed')
        self.assertEqual(mixed.ndim,2)
        with self.assertRaisesRegex(ValueError,'No CUDA'):run(image,recipe,'cuda',strict=True)
