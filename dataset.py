"""Dataset generation/replay CLI and portable bundle runtime. No Qt required."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import cv2
import numpy as np
import engine
from augmentation import sample,run_paired,variation_summary

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read_manifest(path):
    path=Path(path).resolve(); records=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(records,list) or not records:raise ValueError('Manifest must be a nonempty JSON list')
    ids=set(); content_splits={}; result=[]
    for source in records:
        r=dict(source)
        if not isinstance(r.get('id'),str) or not r['id'] or r['id'] in ids:raise ValueError('Unique nonempty source IDs required')
        ids.add(r['id'])
        for key in ('image','mask'):
            if r.get(key):r[key]=str((path.parent/r[key]).resolve())
        if not r.get('image'):raise ValueError('Missing image')
        r.setdefault('split','train')
        if r['split'] not in ('train','validation','test'):raise ValueError('Unsupported split')
        fingerprint=digest(r['image'])
        if fingerprint in content_splits and content_splits[fingerprint]!=r['split']:raise ValueError('Source image content overlaps train/validation/test')
        content_splits[fingerprint]=r['split']; r['source_sha256']=fingerprint; result.append(r)
    return result

def load_targets(record):
    targets={k:record[k] for k in ('boxes','keypoints') if k in record}
    if record.get('mask'):
        mask=cv2.imdecode(np.fromfile(record['mask'],dtype=np.uint8),cv2.IMREAD_UNCHANGED)
        if mask is None:raise ValueError('Cannot decode target mask')
        targets['mask']=mask
    return targets

def write_mask(path,mask):
    ok,data=cv2.imencode('.png',mask)
    if not ok:raise ValueError('Cannot encode target mask')
    data.tofile(str(path))

def generate(records,recipe,output,variants=5,seed=42,min_visibility=0,progress=None,cancel=None):
    recipe=engine.validate(recipe); output=Path(output).resolve()
    if type(variants)!=int or not 1<=variants<=1000:raise ValueError('Variants must be 1–1000')
    if type(seed)!=int:raise ValueError('Seed must be integer')
    if output.exists():raise ValueError('Choose a new output folder; generation never overwrites')
    if not records:raise ValueError('No training records')
    if any(r.get('split','train')!='train' for r in records):raise ValueError('Augment training sources only; split original data first')
    for r in records:
        for key in ('image','mask'):
            if r.get(key) and Path(r[key]).resolve().is_relative_to(output):raise ValueError('Output cannot contain input sources')
    if len({r['id'] for r in records})!=len(records):raise ValueError('Duplicate source IDs')
    output.mkdir(parents=True); (output/'images').mkdir(); (output/'masks').mkdir()
    variation=variation_summary(recipe)
    status={'status':'running','generated':0,'requested':len(records)*variants,'recipe':recipe,'seed':seed,
            'variation_rules':variation,'unique_images':0,'duplicate_images':0,
            'warnings':[] if variation or variants==1 else ['No variable random settings: each source will produce identical copies. Configure min/max ranges, multiple choices, or an apply probability.'],
            'versions':{'python':platform.python_version(),'numpy':np.__version__,'opencv':cv2.__version__}}
    def checkpoint(): (output/'run.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    checkpoint(); generated=[]
    try:
        with (output/'replay.jsonl').open('w',encoding='utf-8') as replay:
            for record in records:
                seen=set()
                image=engine.read_image(record['image']); targets=load_targets(record)
                source_hash=digest(record['image'])
                mask_hash=digest(record['mask']) if record.get('mask') else None
                for variant in range(variants):
                    if cancel and cancel():raise InterruptedError('Generation cancelled')
                    resolved=sample(recipe,seed,record['id'],variant)
                    result,transformed,dropped=run_paired(image,resolved,targets,min_visibility)
                    pixel_hash=hashlib.sha256(str(result.shape).encode()+result.tobytes()).hexdigest()
                    duplicate=pixel_hash in seen;seen.add(pixel_hash)
                    status['duplicate_images' if duplicate else 'unique_images']+=1
                    name=hashlib.sha256(json.dumps([record['id'],source_hash,variant]).encode()).hexdigest()[:24]
                    image_path=Path('images')/(name+'.png'); engine.write_image(output/image_path,result)
                    entry={'id':name,'source_id':record['id'],'variant':variant,'split':'train','image':image_path.as_posix(),'duplicate_pixels_within_source':duplicate}
                    if transformed.get('mask') is not None:
                        mask_path=Path('masks')/(name+'.png'); write_mask(output/mask_path,transformed.pop('mask')); entry['mask']=mask_path.as_posix()
                    entry.update(transformed); generated.append(entry)
                    replay_entry=dict(source=record,source_sha256=source_hash,mask_sha256=mask_hash,variant=variant,seed=seed,
                                      sampled_pipeline=resolved,min_visibility=min_visibility,output=entry,
                                      dropped_boxes=dropped,output_sha256=digest(output/image_path),versions=status['versions'])
                    replay.write(json.dumps(replay_entry)+'\n'); replay.flush()
                    status['generated']+=1; checkpoint()
                    if progress:progress(status['generated'],status['requested'])
        status['status']='complete'
    except Exception as exc:
        status['status']='cancelled' if isinstance(exc,InterruptedError) else 'failed'; status['error']=str(exc); raise
    finally:
        checkpoint(); (output/'manifest.json').write_text(json.dumps(generated,indent=2),encoding='utf-8')
    return status

def replay_record(record,output):
    output=Path(output)
    if output.suffix.lower()!='.png':raise ValueError('Replay output must be lossless PNG')
    if output.exists():raise ValueError('Replay output already exists')
    metadata=output.with_suffix('.targets.json');mask_path=output.with_name(output.stem+'-mask.png')
    if metadata.exists() or mask_path.exists():raise ValueError('Replay companion output already exists')
    source=record['source']
    if digest(source['image'])!=record['source_sha256']:raise ValueError('Source image changed')
    if source.get('mask') and digest(source['mask'])!=record['mask_sha256']:raise ValueError('Source mask changed')
    import copy
    pipeline=copy.deepcopy(record['sampled_pipeline'])
    for step in pipeline['steps']:
        if step['type']=='rotate':step['params'].setdefault('canvas','keep')
    image,targets,dropped=run_paired(engine.read_image(source['image']),pipeline,load_targets(source),record['min_visibility'])
    engine.write_image(output,image)
    if targets.get('mask') is not None:
        write_mask(mask_path,targets.pop('mask'))
    metadata.write_text(json.dumps({'targets':targets,'dropped_boxes':dropped},indent=2))
    return {'pixel_encoding_match':digest(output)==record['output_sha256'],'output':str(output)}

def contact_sheet(images,columns=3,thumb=300):
    if not images:raise ValueError('No contact-sheet samples')
    sheet=np.full((((len(images)+columns-1)//columns)*(thumb+28),columns*thumb,3),30,np.uint8)
    for n,image in enumerate(images):
        if image.ndim==2:image=cv2.cvtColor(image,cv2.COLOR_GRAY2RGB)
        scale=min(thumb/image.shape[1],thumb/image.shape[0]); im=cv2.resize(image,(max(1,round(image.shape[1]*scale)),max(1,round(image.shape[0]*scale))))
        y=(n//columns)*(thumb+28); x=(n%columns)*thumb
        sheet[y:y+im.shape[0],x:x+im.shape[1]]=im
        cv2.putText(sheet,f'Variant {n}',(x+8,y+thumb+20),cv2.FONT_HERSHEY_SIMPLEX,.45,(230,230,230),1)
    return sheet

def main(default_recipe=None):
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    g=sub.add_parser('generate');g.add_argument('manifest');g.add_argument('--recipe',default=default_recipe,required=default_recipe is None);g.add_argument('--output',required=True)
    g.add_argument('--variants',type=int,default=5);g.add_argument('--seed',type=int,default=42);g.add_argument('--min-visibility',type=float,default=0)
    r=sub.add_parser('replay');r.add_argument('records');r.add_argument('--row',type=int,default=0);r.add_argument('--output',required=True)
    a=p.parse_args()
    if a.command=='generate':
        records=read_manifest(a.manifest); records=[r for r in records if r['split']=='train']
        print(json.dumps(generate(records,engine.load_pipeline(a.recipe),a.output,a.variants,a.seed,a.min_visibility),indent=2))
    else:
        with open(a.records,encoding='utf-8') as f:records=[json.loads(line) for line in f if line.strip()]
        if not 0<=a.row<len(records):p.error('Replay row out of range')
        print(json.dumps(replay_record(records[a.row],a.output),indent=2))

if __name__=='__main__':main()
