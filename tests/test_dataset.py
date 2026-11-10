import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import cv2
import numpy as np
import engine
from augmentation import sample,run_paired
from dataset import generate,replay_record,read_manifest,contact_sheet
from project import export_bundle

def pipeline(*kinds):return {'version':1,'steps':[engine.new_step(k) for k in kinds]}

class RandomTests(unittest.TestCase):
    def recipe(self):
        p=pipeline('brightness_contrast','gaussian_blur')
        p['steps'][0]['random']={'probability':.75,'params':{'brightness':{'min':-20,'max':20}}}
        p['steps'][1]['random']={'params':{'kernel':{'min':2,'max':12}}}
        return p
    def test_reproducible_and_odd(self):
        p=self.recipe();original=copy.deepcopy(p)
        self.assertEqual(sample(p,42,'a',1),sample(p,42,'a',1));self.assertEqual(p,original)
        for n in range(30):self.assertEqual(sample(p,42,'a',n)['steps'][1]['params']['kernel']%2,1)
    def test_independent_of_source_order(self):
        p=self.recipe();a={s:sample(p,42,s,0) for s in ['a','b']};b={s:sample(p,42,s,0) for s in ['b','a']};self.assertEqual(a,b)
    def test_probability_zero(self):
        p=pipeline('grayscale');p['steps'][0]['random']={'probability':0};self.assertFalse(sample(p,1,'a',0)['steps'][0]['enabled'])
    def test_choices(self):
        p=pipeline('flip');p['steps'][0]['random']={'params':{'direction':{'choices':['both','vertical']}}}
        self.assertIn(sample(p,2,'a',0)['steps'][0]['params']['direction'],['both','vertical'])
    def test_invalid_rules(self):
        for rule in [{'min':10,'max':2},{'choices':[2,4]},{'min':2,'max':2}]:
            p=pipeline('gaussian_blur');p['steps'][0]['random']={'params':{'kernel':rule}}
            with self.assertRaises(ValueError):engine.validate(p)

class PairedTests(unittest.TestCase):
    def setUp(self):
        self.image=np.zeros((8,10,3),np.uint8);self.image[2:6,1:4]=255
        self.mask=np.zeros((8,10),np.uint16);self.mask[2:6,1:4]=300
        self.targets={'mask':self.mask,'boxes':[{'xyxy':[1,2,4,6],'label':'part'}],'keypoints':[{'x':2,'y':3,'visibility':2}]}
    def test_flip_alignment(self):
        p=pipeline('flip');image,t,d=run_paired(self.image,p,self.targets)
        np.testing.assert_array_equal(image[:,:,0]>0,t['mask']>0)
        self.assertEqual(t['boxes'][0]['xyxy'],[6.,2.,9.,6.]);self.assertEqual(t['keypoints'][0]['x'],7)
        self.assertEqual(t['mask'].dtype,np.uint16);self.assertEqual(set(np.unique(t['mask'])),{0,300})
    def test_crop_and_drop(self):
        p=pipeline('crop');p['steps'][0]['params']={'x':3,'y':0,'width':7,'height':8}
        image,t,d=run_paired(self.image,p,self.targets,min_visibility=.5)
        self.assertFalse(t['boxes']);self.assertEqual(len(d),1);self.assertEqual(t['keypoints'][0]['visibility'],0)
        np.testing.assert_array_equal(image[:,:,0]>0,t['mask']>0)
    def test_resize_preserves_ids(self):
        p=pipeline('resize');p['steps'][0]['params']={'width':20,'height':16,'interpolation':'nearest'}
        image,t,_=run_paired(self.image,p,self.targets)
        self.assertEqual(t['boxes'][0]['xyxy'],[2.,4.,8.,12.]);self.assertEqual(t['keypoints'][0]['x'],4.5)
        np.testing.assert_array_equal(image[:,:,0]>0,t['mask']>0)
    def test_rotation_and_no_reflection(self):
        p=pipeline('rotate');p['steps'][0]['params']={'angle':180,'border':'black'}
        image,t,_=run_paired(self.image,p,self.targets)
        np.testing.assert_array_equal(image[:,:,0]>127,t['mask']>0)
        np.testing.assert_allclose(t['boxes'][0]['xyxy'],[6,2,9,6],atol=1e-8)
        p['steps'][0]['params']['border']='reflect'
        with self.assertRaises(ValueError):run_paired(self.image,p,self.targets)
    def test_photometric_keeps_labels(self):
        _,t,_=run_paired(self.image,pipeline('gamma','threshold'),self.targets)
        np.testing.assert_array_equal(t['mask'],self.mask);self.assertEqual(t['boxes'],self.targets['boxes'])
    def test_bad_mask(self):
        with self.assertRaises(ValueError):run_paired(self.image,pipeline(),{'mask':np.zeros((2,2),np.uint8)})

class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        image=np.random.default_rng(9).integers(0,256,(32,40,3),dtype=np.uint8)
        engine.write_image(self.root/'input.png',image)
        self.records=[{'id':'sample','image':str(self.root/'input.png'),'split':'train'}]
        self.recipe=pipeline('brightness_contrast');self.recipe['steps'][0]['random']={'params':{'brightness':{'min':-20,'max':20}}}
    def tearDown(self):self.temp.cleanup()
    def test_generate_replay_and_guards(self):
        out=self.root/'generated';result=generate(self.records,self.recipe,out,variants=3)
        self.assertEqual(result['generated'],3);self.assertEqual(result['status'],'complete')
        records=[json.loads(line) for line in (out/'replay.jsonl').read_text().splitlines()]
        self.assertTrue(replay_record(records[1],self.root/'replay.png')['pixel_encoding_match'])
        with self.assertRaises(ValueError):generate(self.records,self.recipe,out)
        engine.write_image(self.root/'input.png',np.zeros((32,40,3),np.uint8))
        with self.assertRaises(ValueError):replay_record(records[0],self.root/'changed.png')
    def test_no_test_augmentation(self):
        self.records[0]['split']='test'
        with self.assertRaises(ValueError):generate(self.records,self.recipe,self.root/'out')
    def test_content_split_leakage(self):
        manifest=[dict(id='a',image='input.png',split='train'),dict(id='b',image='input.png',split='test')]
        path=self.root/'manifest.json';path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):read_manifest(path)
    def test_cancel_status(self):
        out=self.root/'cancel'
        with self.assertRaises(InterruptedError):generate(self.records,self.recipe,out,cancel=lambda:True)
        self.assertEqual(json.loads((out/'run.json').read_text())['status'],'cancelled')
    def test_bundle_runs_without_app(self):
        bundle=self.root/'bundle.zip';export_bundle(bundle,self.recipe);folder=self.root/'extracted'
        with zipfile.ZipFile(bundle) as archive:archive.extractall(folder)
        manifest=self.root/'inputs.json';manifest.write_text(json.dumps(self.records))
        result=subprocess.run([sys.executable,'generate.py','generate',str(manifest),'--output',str(self.root/'portable'),'--variants','2'],cwd=folder,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads((self.root/'portable'/'manifest.json').read_text())),2)
    def test_contact_sheet(self):self.assertEqual(contact_sheet([np.zeros((20,40),np.uint8)]).shape,(328,900,3))
    def test_paired_generation_replay(self):
        mask=np.zeros((32,40),np.uint16);mask[4:12,3:10]=300
        cv2.imencode('.png',mask)[1].tofile(str(self.root/'mask.png'))
        record={**self.records[0],'mask':str(self.root/'mask.png'),'boxes':[{'xyxy':[3,4,10,12],'label':'object'}],'keypoints':[{'x':4,'y':5,'visibility':2}]}
        out=self.root/'paired';generate([record],pipeline('flip'),out,variants=1)
        replay=json.loads((out/'replay.jsonl').read_text());replay_record(replay,self.root/'paired-replay.png')
        np.testing.assert_array_equal(cv2.imread(str(self.root/'paired-replay-mask.png'),cv2.IMREAD_UNCHANGED),cv2.flip(mask,1))
        self.assertEqual(replay['output']['boxes'][0]['xyxy'],[30.,4.,37.,12.])

if __name__=='__main__':unittest.main()
