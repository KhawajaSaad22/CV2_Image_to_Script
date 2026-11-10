import copy
import json
from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
import engine
from augmentation import sample,run_paired,variation_summary
from dataset import generate,replay_record,digest
from operation_help import HELP

def pipeline(kind,**params):
    step=engine.new_step(kind);step['params'].update(params);return {'version':1,'steps':[step]}

class RotationTests(unittest.TestCase):
    def test_hd_quarter_turn_frame(self):
        image=np.zeros((1080,1920,3),np.uint8)
        result=engine.run(image,pipeline('rotate',angle=-90))[0]
        self.assertEqual(result.shape,(1920,1080,3))
    def test_quarter_turns_preserve_pixels(self):
        image=np.random.default_rng(1).integers(0,255,(7,12,3),dtype=np.uint8)
        for angle,k in [(90,1),(-90,-1),(180,2),(0,0)]:
            with self.subTest(angle=angle):np.testing.assert_array_equal(engine.run(image,pipeline('rotate',angle=angle))[0],np.rot90(image,k))
    def test_keep_canvas_option(self):
        result=engine.run(np.zeros((7,12,3),np.uint8),pipeline('rotate',angle=90,canvas='keep'))[0]
        self.assertEqual(result.shape,(7,12,3))
    def test_arbitrary_angle_contains_corners(self):
        p=pipeline('rotate',angle=33)['steps'][0]['params'];matrix,w,h=engine.rotation_geometry(120,70,p)
        from augmentation import geometry,transform_points
        center,edge,nw,nh=geometry('rotate',p,120,70)
        corners=transform_points([[0,0],[120,0],[120,70],[0,70]],edge)
        self.assertTrue((corners>=-1e-8).all());self.assertTrue((corners<=[nw+1e-8,nh+1e-8]).all())
    def test_paired_quarter_turn(self):
        image=np.zeros((8,10,3),np.uint8);image[2:6,1:4]=255;mask=(image[:,:,0]>0).astype(np.uint16)*300
        output,targets,_=run_paired(image,pipeline('rotate',angle=-90),{'mask':mask,'boxes':[{'xyxy':[1,2,4,6]}],'keypoints':[{'x':2,'y':3,'visibility':2}]})
        np.testing.assert_array_equal(output[:,:,0]>0,targets['mask']>0)
        self.assertEqual(output.shape,(10,8,3));np.testing.assert_allclose(targets['boxes'][0]['xyxy'],[2,1,6,4],atol=1e-8)
        self.assertAlmostEqual(targets['keypoints'][0]['x'],4);self.assertAlmostEqual(targets['keypoints'][0]['y'],2)
    def test_legacy_load_expands_without_mutation(self):
        p=pipeline('rotate');del p['steps'][0]['params']['canvas'];before=copy.deepcopy(p)
        self.assertEqual(engine.validate(p)['steps'][0]['params']['canvas'],'expand');self.assertEqual(p,before)

class GenerationIssueTests(unittest.TestCase):
    def test_seed_does_not_repeat_every_variant(self):
        p=pipeline('brightness_contrast');p['steps'][0]['random']={'params':{'brightness':{'min':-80,'max':80}}}
        values=[sample(p,42,'source',i)['steps'][0]['params']['brightness'] for i in range(12)]
        self.assertGreater(len(set(values)),1)
        self.assertEqual(values,[sample(p,42,'source',i)['steps'][0]['params']['brightness'] for i in range(12)])
    def test_single_odd_value_is_not_variable(self):
        p=pipeline('gaussian_blur');p['steps'][0]['random']={'params':{'kernel':{'min':2,'max':4}}}
        self.assertEqual(variation_summary(p),[])
    def test_duplicate_warning_and_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';engine.write_image(source,np.full((8,12,3),100,np.uint8))
            records=[{'id':'s','image':str(source),'split':'train'}]
            status=generate(records,pipeline('grayscale'),root/'fixed',variants=3)
            self.assertTrue(status['warnings']);self.assertEqual(status['unique_images'],1);self.assertEqual(status['duplicate_images'],2)
            p=pipeline('brightness_contrast');p['steps'][0]['random']={'params':{'brightness':{'min':-80,'max':80}}}
            status=generate(records,p,root/'random',variants=12)
            self.assertFalse(status['warnings']);self.assertGreater(status['unique_images'],1)
    def test_old_rotation_replay_keeps_old_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';image=np.arange(240,dtype=np.uint8).reshape(8,10,3);engine.write_image(source,image)
            p=pipeline('rotate',angle=90,canvas='keep');old=engine.run(image,p)[0];expected=root/'old.png';engine.write_image(expected,old)
            del p['steps'][0]['params']['canvas']
            record={'source':{'image':str(source)},'source_sha256':digest(source),'mask_sha256':None,'sampled_pipeline':p,'min_visibility':0,'output_sha256':digest(expected)}
            self.assertTrue(replay_record(record,root/'replayed.png')['pixel_encoding_match'])
    def test_every_operation_has_help(self):
        self.assertEqual(set(HELP),set(engine.OPERATIONS));self.assertIn('Contrast Limited',HELP['clahe'][1]);self.assertIn('cv2.createCLAHE',HELP['clahe'][2])

if __name__=='__main__':unittest.main()
