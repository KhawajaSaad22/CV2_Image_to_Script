"""Seeded sampling and paired mask/box/keypoint geometry. No GUI dependency."""
import copy
import hashlib
import json
import cv2
import numpy as np
import engine

SAMPLER_VERSION=1
GEOMETRIC={'resize','crop','rotate','flip'}

def sample(recipe,seed,source_id,variant):
    recipe=engine.validate(recipe)
    if type(seed)!=int or type(variant)!=int or variant<0: raise ValueError('Integer seed and nonnegative variant required')
    result=copy.deepcopy(recipe)
    for step in result['steps']:
        settings=step.pop('random',{})
        def rng(key):
            token=json.dumps([SAMPLER_VERSION,seed,source_id,variant,step['id'],key],ensure_ascii=False)
            return np.random.default_rng(int.from_bytes(hashlib.sha256(token.encode()).digest()[:16],'big'))
        step['enabled']=step['enabled'] and bool(rng('probability').random()<settings.get('probability',1))
        for key,rule in sorted(settings.get('params',{}).items()):
            generator=rng(key); spec=engine.OPERATIONS[step['type']][key]
            if 'choices' in rule: value=rule['choices'][int(generator.integers(len(rule['choices'])))]
            elif spec['integer']:
                lo,hi=rule['min'],rule['max']
                if key in ('kernel','block'):
                    lo+=int(lo%2==0); value=int(generator.integers(0,(hi-lo)//2+1))*2+lo
                else:value=int(generator.integers(lo,hi+1))
            else:value=float(generator.uniform(rule['min'],rule['max']))
            step['params'][key]=value
    # Joint constraints are not silently sorted or resampled (e.g. sampled Canny low > high).
    return engine.validate(result)

def validate_targets(image,targets):
    targets=copy.deepcopy(targets or {}); h,w=image.shape[:2]
    if set(targets)-{'boxes','keypoints','mask'}: raise ValueError('Unsupported target type')
    if targets.get('mask') is not None:
        mask=targets['mask']
        if mask.ndim!=2 or mask.shape!=(h,w) or mask.dtype not in (np.uint8,np.uint16): raise ValueError('Mask must be matching 2-D uint8/uint16 class IDs')
    for box in targets.get('boxes',[]):
        values=box.get('xyxy',[])
        if len(values)!=4 or not np.isfinite(values).all(): raise ValueError('Box needs finite xyxy coordinates')
        x1,y1,x2,y2=values
        if not 0<=x1<x2<=w or not 0<=y1<y2<=h: raise ValueError('Box outside source bounds')
    for point in targets.get('keypoints',[]):
        if not all(k in point for k in ('x','y','visibility')) or not np.isfinite([point['x'],point['y']]).all() or point['visibility'] not in (0,1,2): raise ValueError('Keypoint needs x, y, visibility (0/1/2)')
        if point['visibility'] and not (0<=point['x']<w and 0<=point['y']<h): raise ValueError('Visible keypoint outside image')
    return targets

def geometry(kind,p,w,h):
    """Return pixel-center and half-open box-edge matrices, plus output dimensions."""
    if kind=='resize':
        nw,nh=p['width'],p['height']; sx,sy=nw/w,nh/h
        center=np.array([[sx,0,(sx-1)/2],[0,sy,(sy-1)/2],[0,0,1]],float)
    elif kind=='crop':
        nw,nh=p['width'],p['height']; center=np.array([[1,0,-p['x']],[0,1,-p['y']],[0,0,1]],float)
    elif kind=='flip':
        nw,nh=w,h; sx=-1 if p['direction'] in ('horizontal','both') else 1; sy=-1 if p['direction'] in ('vertical','both') else 1
        center=np.array([[sx,0,w-1 if sx<0 else 0],[0,sy,h-1 if sy<0 else 0],[0,0,1]],float)
    else:
        nw,nh=w,h; center=np.eye(3); center[:2]=cv2.getRotationMatrix2D(((w-1)/2,(h-1)/2),p['angle'],1)
    plus=np.array([[1,0,.5],[0,1,.5],[0,0,1.]])
    minus=np.array([[1,0,-.5],[0,1,-.5],[0,0,1.]])
    return center,plus@center@minus,nw,nh

def transform_points(points,matrix):
    points=np.asarray(points,dtype=float); return (np.column_stack([points,np.ones(len(points))])@matrix.T)[:,:2]

def run_paired(image,pipeline,targets=None,min_visibility=0):
    if not 0<=min_visibility<=1: raise ValueError('Visibility must be between 0 and 1')
    pipeline=engine.validate(pipeline); targets=validate_targets(image,targets); current=image.copy(); dropped=[]
    for step in pipeline['steps']:
        if not step['enabled']:continue
        kind,p=step['type'],step['params']; h,w=current.shape[:2]
        if kind=='rotate' and p['border']=='reflect' and targets:
            raise ValueError('Paired rotation requires black/white borders; reflection can create unlabeled objects')
        result=engine.apply_operation(current,kind,p)
        if kind in GEOMETRIC:
            center,edge,nw,nh=geometry(kind,p,w,h)
            if targets.get('mask') is not None:
                mask=targets['mask']
                if kind=='resize':mask=cv2.resize(mask,(nw,nh),interpolation=cv2.INTER_NEAREST)
                elif kind=='crop':mask=mask[p['y']:p['y']+nh,p['x']:p['x']+nw].copy()
                elif kind=='flip':mask=cv2.flip(mask,{'horizontal':1,'vertical':0,'both':-1}[p['direction']])
                else:mask=cv2.warpAffine(mask,center[:2],(nw,nh),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
                targets['mask']=mask
            boxes=[]
            for box in targets.get('boxes',[]):
                x1,y1,x2,y2=box['xyxy']; corners=transform_points([[x1,y1],[x2,y1],[x2,y2],[x1,y2]],edge)
                low=corners.min(0); high=corners.max(0); before=float(np.prod(high-low))
                clipped_low=np.clip(low,[0,0],[nw,nh]); clipped_high=np.clip(high,[0,0],[nw,nh]); area=float(np.prod(np.maximum(0,clipped_high-clipped_low)))
                if area>0 and area/max(before,1e-12)>=min_visibility:boxes.append({**box,'xyxy':[*clipped_low.tolist(),*clipped_high.tolist()]})
                else:dropped.append(copy.deepcopy(box))
            if 'boxes' in targets:targets['boxes']=boxes
            for point in targets.get('keypoints',[]):
                point['x'],point['y']=map(float,transform_points([[point['x'],point['y']]],center)[0])
                if not (0<=point['x']<nw and 0<=point['y']<nh):point['visibility']=0
        current=result
    return current,targets,dropped
