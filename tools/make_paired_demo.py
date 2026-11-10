"""Create a tiny train/validation/test fixture with masks, boxes, and keypoints."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import cv2
import numpy as np
import engine

def main():
    root=Path('data/paired-demo')
    if root.exists():raise ValueError('Demo exists; reuse it rather than overwriting')
    root.mkdir(parents=True);records=[]
    for n,split in enumerate(('train','validation','test')):
        image=np.random.default_rng(n).integers(0,30,(64,80,3),dtype=np.uint8);image[10:30,20:40]=[220,130,50]
        mask=np.zeros((64,80),np.uint16);mask[10:30,20:40]=300
        engine.write_image(root/(split+'.png'),image);cv2.imencode('.png',mask)[1].tofile(str(root/(split+'-mask.png')))
        records.append(dict(id=split+'-part',image=split+'.png',mask=split+'-mask.png',split=split,
                            boxes=[dict(xyxy=[20,10,40,30],label='part')],keypoints=[dict(x=25,y=20,visibility=2,label='center')]))
    (root/'inputs.json').write_text(json.dumps(records,indent=2));print(root/'inputs.json')
if __name__=='__main__':main()
