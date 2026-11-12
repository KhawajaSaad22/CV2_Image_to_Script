"""Warm CPU timings and sampled process RSS; not a cross-machine guarantee."""
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
import threading
import psutil

def main():
    p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('pipeline');p.add_argument('--runs',type=int,default=10);p.add_argument('--output',default='profile.json');a=p.parse_args()
    if a.runs<1:p.error('Positive run count required')
    process=psutil.Process(); baseline=process.memory_info().rss; peak=[baseline]; stop=threading.Event()
    def sample():
        while not stop.wait(.01): peak[0]=max(peak[0],process.memory_info().rss)
    worker=threading.Thread(target=sample,daemon=True); worker.start()
    try:
        image=engine.read_image(a.image);pipeline=engine.load_pipeline(a.pipeline);engine.run(image,pipeline,retain_intermediates=False);times=[]
        for _ in range(a.runs):
            start=time.perf_counter();engine.run(image,pipeline,retain_intermediates=False);times.append((time.perf_counter()-start)*1000)
        peak[0]=max(peak[0],process.memory_info().rss)
    finally:
        stop.set(); worker.join()
    result=dict(platform=platform.platform(),opencv=cv2.__version__,shape=list(image.shape),runs=a.runs,median_ms=statistics.median(times),min_ms=min(times),max_ms=max(times),rss_baseline_bytes=baseline,rss_sampled_peak_bytes=peak[0],note='One warmup; no prefix cache. RSS sampled every 10ms from before image loading; short peaks may be missed. Includes process overhead; no GPU memory measured.')
    Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
