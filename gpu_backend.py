"""Optional CUDA execution for selected operations, with explicit CPU fallback.

The independent OpenCV export engine does not depend on this module or PyTorch.
"""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import engine


def select_device(device):
    if device not in ('auto','cpu','cuda'):raise ValueError('Device must be auto, cpu or cuda')
    if device=='cpu':return None,'CPU selected'
    try:import torch
    except ImportError:
        if device=='cuda':raise ValueError('CUDA needs optional PyTorch; use a CUDA-enabled Python environment')
        return None,'PyTorch unavailable; CPU fallback'
    if not torch.cuda.is_available():
        if device=='cuda':raise ValueError('CUDA requested but no CUDA-enabled runtime/GPU is available')
        return None,'CUDA unavailable; CPU fallback'
    return torch,None


def supported(kind,params,ndim):
    return kind in ('crop','flip','brightness_contrast','gamma') or kind=='resize' and params['interpolation']=='nearest' or kind=='threshold' and params['mode']=='fixed' and ndim==2


def run(image,pipeline,device='auto',cancel=None,retain_intermediates=True,strict=False,cache=None):
    pipeline=engine.validate(pipeline)
    if image.dtype!=np.uint8 or image.ndim not in (2,3) or min(image.shape[:2])<1 or image.ndim==3 and image.shape[2]!=3:
        raise ValueError('Expected nonempty uint8 RGB or grayscale image')
    torch,reason=select_device(device)
    if torch is None:
        final,outputs,timings=engine.run(image,pipeline,cache=cache,cancel=cancel,retain_intermediates=retain_intermediates)
        return final,outputs,timings,{'device':'cpu','reason':reason,'steps':['cpu' if s['enabled'] else 'disabled' for s in pipeline['steps']]}
    current=image.copy();outputs=[];timings=[];executed=[];retained=0
    def cpu(value):return value.detach().cpu().numpy().copy() if isinstance(value,torch.Tensor) else value.copy()
    def cuda(value):return value if isinstance(value,torch.Tensor) else torch.from_numpy(np.ascontiguousarray(value)).to('cuda')
    for step in pipeline['steps']:
        if cancel and cancel():raise InterruptedError('Superseded GPU processing')
        torch.cuda.synchronize();start=time.perf_counter();kind=step['type'];p=step['params'];used='disabled'
        if step['enabled']:
            if supported(kind,p,current.ndim):
                current=cuda(current);used='cuda'
                if kind=='crop':
                    x,y,w,h=(p[k] for k in ('x','y','width','height'))
                    if x+w>current.shape[1] or y+h>current.shape[0]:raise ValueError('Crop extends outside image')
                    current=current[y:y+h,x:x+w].clone()
                elif kind=='flip':current=torch.flip(current,{'horizontal':[1],'vertical':[0],'both':[0,1]}[p['direction']])
                elif kind=='brightness_contrast':current=(current.float()*p['contrast']+p['brightness']).clamp(0,255).to(torch.uint8)
                elif kind=='gamma':
                    lut=np.clip(255*(np.arange(256,dtype=np.float32)/255)**(1/p['gamma']),0,255).astype(np.uint8)
                    current=torch.as_tensor(lut,device='cuda')[current.long()]
                elif kind=='threshold':current=(current>p['value']).to(torch.uint8)*255
                elif kind=='resize':
                    h,w=current.shape[:2]
                    ys=np.minimum(np.floor(np.arange(p['height'])*(h/p['height'])).astype(np.int64),h-1)
                    xs=np.minimum(np.floor(np.arange(p['width'])*(w/p['width'])).astype(np.int64),w-1)
                    current=current.index_select(0,torch.as_tensor(ys,device='cuda')).index_select(1,torch.as_tensor(xs,device='cuda'))
            else:
                if strict:raise ValueError('No CUDA implementation for '+kind+' with these parameters')
                current=engine.apply_operation(cpu(current),kind,p);used='cpu'
        executed.append(used)
        if retain_intermediates:
            snapshot=cpu(current);retained+=snapshot.nbytes
            if retained>512*1024*1024:raise ValueError('Intermediate preview exceeds 512 MiB')
            outputs.append(snapshot)
        torch.cuda.synchronize();timings.append((time.perf_counter()-start)*1000)
    actual='mixed' if 'cuda' in executed and 'cpu' in executed else 'cuda' if 'cuda' in executed else 'cpu'
    return cpu(current),outputs,timings,{'device':actual,'gpu':torch.cuda.get_device_name(0),
        'steps':executed,'reason':'Unsupported operations use OpenCV on CPU; transfers are included'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image');parser.add_argument('recipe');parser.add_argument('--output',required=True)
    parser.add_argument('--device',choices=['auto','cpu','cuda'],default='auto');parser.add_argument('--strict',action='store_true')
    args=parser.parse_args();output=Path(args.output);metadata=Path(str(output)+'.execution.json')
    if output.exists() or metadata.exists():parser.error('Choose a new output path')
    result,_,timings,execution=run(engine.read_image(args.image),engine.load_pipeline(args.recipe),args.device,strict=args.strict,retain_intermediates=False)
    output.parent.mkdir(parents=True,exist_ok=True);engine.write_image(output,result)
    metadata.write_text(json.dumps({**execution,'step_ms':timings},indent=2),encoding='utf-8')


if __name__=='__main__':main()
