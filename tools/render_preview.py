"""Render the application's own demo window for visual QA, without external UI automation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import engine
from workbench import Workbench
from make_demo import main

main(); app=QApplication([]); app.setStyle('Fusion'); window=Workbench(); window.show()
window.load_paths([str(p) for p in sorted(Path('data/demo').glob('*.png'))])
window.commit(engine.load_pipeline('examples/edge_inspection.json'),2)
def capture():
    if window.final is None:QTimer.singleShot(100,capture); return
    Path('artifacts').mkdir(exist_ok=True); window.grab().save('artifacts/workbench.png'); window.close(); app.quit()
QTimer.singleShot(500,capture); QTimer.singleShot(15000,app.quit); app.exec()
