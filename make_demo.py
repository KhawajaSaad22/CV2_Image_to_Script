"""Create original demo images without downloading private or third-party photos."""
from pathlib import Path
import cv2
import numpy as np
import engine

def main():
    root=Path('data/demo'); root.mkdir(parents=True,exist_ok=True)
    for n in range(3):
        image=np.zeros((560,840,3),np.uint8); image[:]=[30,42,58]
        ramp=np.linspace(0,100,840,dtype=np.uint8); image[:,:,0]+=ramp
        cv2.rectangle(image,(70,130),(290,370),(230,130,45),-1)
        cv2.circle(image,(490,270),115,(60,170,220),-1)
        cv2.line(image,(60,460),(770,460),(240,240,240),3)
        cv2.putText(image,'CV2 PIPELINE WORKBENCH',(55,75),cv2.FONT_HERSHEY_SIMPLEX,.9,(245,245,245),2)
        cv2.putText(image,f'Representative image {n+1}',(65,515),cv2.FONT_HERSHEY_SIMPLEX,.7,(220,220,220),1)
        image=np.clip(image.astype(np.int16)+np.random.default_rng(n).integers(-12,13,image.shape),0,255).astype(np.uint8)
        path=root/f'example-{n+1}.png'
        if not path.exists():engine.write_image(path,image)
    print(root)
if __name__=='__main__':main()
