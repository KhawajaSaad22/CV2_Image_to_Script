"""Pure OpenCV/NumPy pipeline engine. RGB uint8 internally; grayscale stays 2-D.

This file is embedded unchanged in standalone exports. It has no Qt dependency.
"""
import argparse
import copy
import json
import math
import hashlib
from pathlib import Path
import time
import uuid
import cv2
import numpy as np

VERSION = 1
EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'}


def number(default, minimum, maximum, integer=False, step=1):
    return dict(default=default, minimum=minimum, maximum=maximum, integer=integer, step=step)


def choice(default, options): return dict(default=default, choices=options)


OPERATIONS = {
    'resize': dict(width=number(640,1,16384,True), height=number(480,1,16384,True), interpolation=choice('area',['area','linear','nearest','cubic'])),
    'crop': dict(x=number(0,0,16384,True), y=number(0,0,16384,True), width=number(100,1,16384,True), height=number(100,1,16384,True)),
    'rotate': dict(angle=number(0,-180,180,False,.1), border=choice('black',['reflect','black','white']), canvas=choice('expand',['expand','keep'])),
    'flip': dict(direction=choice('horizontal',['horizontal','vertical','both'])),
    'grayscale': {},
    'brightness_contrast': dict(brightness=number(0,-255,255,True), contrast=number(1,0,4,False,.01)),
    'gamma': dict(gamma=number(1,.05,5,False,.05)),
    'gaussian_blur': dict(kernel=number(5,1,99,True,2), sigma=number(0,0,30,False,.1)),
    'median_blur': dict(kernel=number(5,3,99,True,2)),
    'threshold': dict(mode=choice('fixed',['fixed','otsu','adaptive']), value=number(127,0,255,True), block=number(11,3,99,True,2), c=number(2,-50,50,False,.5)),
    'canny': dict(low=number(50,0,255,True), high=number(150,0,255,True)),
    'morphology': dict(mode=choice('open',['erode','dilate','open','close']), kernel=number(3,1,99,True,2), iterations=number(1,1,10,True)),
    'equalize': {},
    'clahe': dict(clip=number(2,.1,20,False,.1), tiles=number(8,1,32,True)),
}


def new_step(kind):
    if kind not in OPERATIONS: raise ValueError('Unknown operation: '+kind)
    return dict(id=uuid.uuid4().hex, type=kind, enabled=True,
                params={k:s['default'] for k,s in OPERATIONS[kind].items()})


def validate(pipeline):
    pipeline=copy.deepcopy(pipeline)
    if not isinstance(pipeline,dict) or pipeline.get('version')!=VERSION: raise ValueError('Unsupported pipeline version')
    if not isinstance(pipeline.get('steps'),list) or len(pipeline['steps'])>100: raise ValueError('Expected up to 100 steps')
    ids=set()
    for step in pipeline['steps']:
        if not isinstance(step,dict): raise ValueError('Invalid step')
        identity=step.get('id')
        if not isinstance(identity,str) or not identity or identity in ids: raise ValueError('Step IDs must be unique nonempty strings')
        ids.add(identity)
        if type(step.get('enabled')) is not bool: raise ValueError('Enabled must be boolean')
        kind=step.get('type')
        if kind not in OPERATIONS: raise ValueError('Unknown operation: '+str(kind))
        params=step.get('params')
        if kind=='rotate' and isinstance(params,dict):params.setdefault('canvas','expand')
        if not isinstance(params,dict) or set(params)!=set(OPERATIONS[kind]): raise ValueError('Unexpected parameters for '+kind)
        for key,spec in OPERATIONS[kind].items():
            value=params[key]
            if 'choices' in spec:
                if value not in spec['choices']: raise ValueError('Invalid '+key)
            else:
                if type(value) not in (float,int) or not math.isfinite(value): raise ValueError('Expected finite number: '+key)
                if spec['integer'] and type(value) is not int: raise ValueError('Expected integer: '+key)
                if not spec['minimum']<=value<=spec['maximum']: raise ValueError('Out of range: '+key)
                if key in ('kernel','block') and value%2!=1: raise ValueError(key+' must be odd')
        if kind=='canny' and params['low']>params['high']: raise ValueError('Canny low must not exceed high')
        if 'random' in step:
            settings=step['random']
            if not isinstance(settings,dict) or set(settings)-{'probability','params'}: raise ValueError('Invalid random settings')
            probability=settings.get('probability',1)
            if type(probability) not in (int,float) or not math.isfinite(probability) or not 0<=probability<=1: raise ValueError('Probability must be between 0 and 1')
            rules=settings.get('params',{})
            if not isinstance(rules,dict) or set(rules)-set(OPERATIONS[kind]): raise ValueError('Unknown randomized parameter')
            for key,rule in rules.items():
                if not isinstance(rule,dict): raise ValueError('Random rule must be an object')
                spec=OPERATIONS[kind][key]
                if set(rule)=={'choices'}:
                    values=rule['choices']
                    if not isinstance(values,list) or not values or len(values)>1000: raise ValueError('Provide 1–1000 choices')
                elif set(rule)=={'min','max'} and 'choices' not in spec:
                    lo,hi=rule['min'],rule['max']
                    if type(lo) not in (int,float) or type(hi) not in (int,float) or not math.isfinite(lo) or not math.isfinite(hi) or lo>hi: raise ValueError('Invalid random range')
                    if spec['integer'] and (type(lo)!=int or type(hi)!=int): raise ValueError('Integer ranges require integer endpoints')
                    values=[lo,hi]
                    if key in ('kernel','block') and not any(n%2 for n in range(lo,hi+1)): raise ValueError('Range has no odd values')
                else: raise ValueError('Use choices or min/max for each random rule')
                for value in values:
                    if 'choices' in spec:
                        if value not in spec['choices']: raise ValueError('Unsupported randomized choice')
                    else:
                        if type(value) not in (int,float) or not math.isfinite(value) or not spec['minimum']<=value<=spec['maximum']: raise ValueError('Random value out of bounds')
                        if spec['integer'] and type(value)!=int: raise ValueError('Expected integer random value')
                        if 'choices' in rule and key in ('kernel','block') and value%2!=1: raise ValueError('Kernel choices must be odd')
    return copy.deepcopy(pipeline)


def gray(image): return cv2.cvtColor(image,cv2.COLOR_RGB2GRAY) if image.ndim==3 else image

def rotation_geometry(w,h,p):
    matrix=cv2.getRotationMatrix2D(((w-1)/2,(h-1)/2),p['angle'],1)
    nw,nh=w,h
    if p.get('canvas','expand')=='expand':
        cosine,sine=abs(matrix[0,0]),abs(matrix[0,1])
        nw=max(1,math.ceil(w*cosine+h*sine-1e-10));nh=max(1,math.ceil(h*cosine+w*sine-1e-10))
        matrix[0,2]+=(nw-w)/2;matrix[1,2]+=(nh-h)/2
    return matrix,nw,nh


def apply_operation(image,kind,p):
    if kind=='resize':
        modes={'area':cv2.INTER_AREA,'linear':cv2.INTER_LINEAR,'nearest':cv2.INTER_NEAREST,'cubic':cv2.INTER_CUBIC}
        return cv2.resize(image,(p['width'],p['height']),interpolation=modes[p['interpolation']])
    if kind=='crop':
        x,y,w,h=(p[k] for k in ('x','y','width','height'))
        if x+w>image.shape[1] or y+h>image.shape[0]: raise ValueError('Crop extends outside image; adjust its bounds')
        return image[y:y+h,x:x+w].copy()
    if kind=='rotate':
        h,w=image.shape[:2];matrix,nw,nh=rotation_geometry(w,h,p)
        return cv2.warpAffine(image,matrix,(nw,nh),borderMode=cv2.BORDER_REFLECT_101 if p['border']=='reflect' else cv2.BORDER_CONSTANT,borderValue=(255,255,255) if p['border']=='white' else 0)
    if kind=='flip': return cv2.flip(image,{'horizontal':1,'vertical':0,'both':-1}[p['direction']])
    if kind=='grayscale': return gray(image)
    if kind=='brightness_contrast': return np.clip(image.astype(np.float32)*p['contrast']+p['brightness'],0,255).astype(np.uint8)
    if kind=='gamma':
        lut=np.clip(255*(np.arange(256,dtype=np.float32)/255)**(1/p['gamma']),0,255).astype(np.uint8)
        return cv2.LUT(image,lut)
    if kind=='gaussian_blur': return cv2.GaussianBlur(image,(p['kernel'],p['kernel']),p['sigma'])
    if kind=='median_blur': return cv2.medianBlur(image,p['kernel'])
    if kind=='threshold':
        x=gray(image)
        if p['mode']=='adaptive': return cv2.adaptiveThreshold(x,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,p['block'],p['c'])
        return cv2.threshold(x,p['value'],255,cv2.THRESH_BINARY|(cv2.THRESH_OTSU if p['mode']=='otsu' else 0))[1]
    if kind=='canny': return cv2.Canny(gray(image),p['low'],p['high'])
    if kind=='morphology':
        kernel=np.ones((p['kernel'],p['kernel']),np.uint8)
        return cv2.morphologyEx(image,{'erode':cv2.MORPH_ERODE,'dilate':cv2.MORPH_DILATE,'open':cv2.MORPH_OPEN,'close':cv2.MORPH_CLOSE}[p['mode']],kernel,iterations=p['iterations'])
    if kind in ('clahe','equalize'):
        fn=cv2.equalizeHist if kind=='equalize' else cv2.createCLAHE(p['clip'],(p['tiles'],p['tiles'])).apply
        if image.ndim==2: return fn(image)
        lab=cv2.cvtColor(image,cv2.COLOR_RGB2LAB); lab[:,:,0]=fn(lab[:,:,0])
        return cv2.cvtColor(lab,cv2.COLOR_LAB2RGB)
    raise ValueError('Unknown operation: '+kind)


def run(image,pipeline,cache=None,cancel=None,retain_intermediates=True):
    pipeline=validate(pipeline)
    if image.dtype!=np.uint8 or image.ndim not in (2,3) or min(image.shape[:2])<1 or (image.ndim==3 and image.shape[2]!=3): raise ValueError('Expected nonempty 8-bit grayscale or RGB image')
    current=image.copy(); outputs=[]; timings=[]; prefix=[]
    source_key=hashlib.sha256(image.tobytes()).hexdigest()+str(image.shape)
    for step in pipeline['steps']:
        if cancel and cancel(): raise InterruptedError('Superseded preview')
        prefix.append(step); key=source_key+json.dumps(prefix,sort_keys=True); start=time.perf_counter()
        if cache is not None and key in cache: current=cache[key].copy()
        else:
            if step['enabled']:
                try: current=apply_operation(current,step['type'],step['params'])
                except (cv2.error,ValueError) as exc: raise ValueError(f"{step['type']}: {exc}") from exc
            if cache is not None: cache[key]=current.copy()
        if retain_intermediates:
            if sum(x.nbytes for x in outputs)+current.nbytes>512*1024*1024: raise ValueError('Intermediate preview exceeds 512 MiB; use fast mode or export the pipeline')
            outputs.append(current.copy())
        timings.append((time.perf_counter()-start)*1000)
    return current,outputs,timings


def read_image(path):
    image=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),cv2.IMREAD_UNCHANGED)
    if image is None: raise ValueError('Cannot decode image: '+str(path))
    if image.dtype!=np.uint8: raise ValueError('Only 8-bit images are supported')
    if image.ndim==3:
        if image.shape[2]==4:
            alpha=image[:,:,3:4].astype(np.float32)/255
            image=np.clip(image[:,:,:3]*alpha+255*(1-alpha),0,255).astype(np.uint8)
        image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
    return image


def write_image(path,image):
    path=Path(path)
    bgr=cv2.cvtColor(image,cv2.COLOR_RGB2BGR) if image.ndim==3 else image
    ok,encoded=cv2.imencode(path.suffix,bgr)
    if not ok: raise ValueError('Cannot encode output')
    path.parent.mkdir(parents=True,exist_ok=True); encoded.tofile(str(path))


def save_pipeline(path,pipeline): Path(path).write_text(json.dumps(validate(pipeline),indent=2),encoding='utf-8')
def load_pipeline(path): return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def run_cli(pipeline):
    parser=argparse.ArgumentParser(description='Run an exported OpenCV pipeline. Output images are lossless PNG.')
    parser.add_argument('input',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('--overwrite',action='store_true'); args=parser.parse_args()
    validate(pipeline)
    if not args.input.exists(): parser.error('Input does not exist')
    if args.input.resolve()==args.output.resolve(): parser.error('Input and output must differ')
    batch=args.input.is_dir()
    if batch and args.input.resolve() in args.output.resolve().parents: parser.error('Batch output must be outside the input folder')
    inputs=sorted(p for p in args.input.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS) if batch else [args.input]
    if not inputs: parser.error('No supported images found')
    for source in inputs:
        target=args.output/source.relative_to(args.input).with_name(source.name+'.png') if batch else args.output
        if target.suffix.lower()!='.png': parser.error('Use .png for single-image output')
        if target.exists() and not args.overwrite: parser.error('Output exists: '+str(target))
        output,_,_=run(read_image(source),pipeline,retain_intermediates=False); write_image(target,output)
        print(str(target))
