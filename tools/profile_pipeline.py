"""Reproducible CPU timing/RSS report; not a cross-machine performance guarantee."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import json
import platform
import statistics
import time
import cv2
import engine

def main():
    p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('pipeline');p.add_argument('--runs',type=int,default=10);p.add_argument('--output',default='profile.json');a=p.parse_args()
    if a.runs<1:p.error('Positive run count required')
    image=engine.read_image(a.image);pipeline=engine.load_pipeline(a.pipeline);engine.run(image,pipeline,retain_intermediates=False);times=[]
    for _ in range(a.runs):
        start=time.perf_counter();engine.run(image,pipeline,retain_intermediates=False);times.append((time.perf_counter()-start)*1000)
    result=dict(platform=platform.platform(),opencv=cv2.__version__,shape=list(image.shape),runs=a.runs,median_ms=statistics.median(times),min_ms=min(times),max_ms=max(times),note='One warmup; no prefix cache. Memory usage not measured.')
    Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
