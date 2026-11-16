"""Render the application's own demo window for visual QA, without external UI automation."""
import os
import argparse
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import engine
from workbench import Workbench
from make_demo import main

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--comparison',action='store_true',help='Show absolute difference and linked views')
parser.add_argument('--output',type=Path,default=Path('artifacts/workbench.png'))
args=parser.parse_args()
main(); app=QApplication([]); app.setStyle('Fusion'); window=Workbench(session_dir=Path('artifacts/render-recovery')); window.show()
window.load_paths([str(p) for p in sorted(Path('data/demo').glob('*.png'))])
window.commit(engine.load_pipeline('examples/edge_inspection.json'),2)
def capture():
    if window.final is None:QTimer.singleShot(100,capture); return
    if args.comparison:
        window.view_mode.setCurrentText('Absolute difference');window.link_views.setChecked(True)
    args.output.parent.mkdir(parents=True,exist_ok=True); window.grab().save(str(args.output))
    window.document.mark_saved(); window.close(); app.quit()
QTimer.singleShot(500,capture); QTimer.singleShot(15000,app.quit); app.exec()
