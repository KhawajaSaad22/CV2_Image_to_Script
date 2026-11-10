"""Desktop entry point: python workbench.py"""
import copy
import json
import os
from pathlib import Path
import sys
import threading
import time
import cv2
import numpy as np
from PySide6.QtCore import Qt,QObject,Signal,QTimer,QRunnable,QThreadPool
from PySide6.QtGui import QAction,QImage,QPixmap,QPainter,QFont,QFontDatabase,QPalette,QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
    QPushButton,QComboBox,QListWidget,QListWidgetItem,QSplitter,QFileDialog,QCheckBox,
    QFormLayout,QSpinBox,QDoubleSpinBox,QSlider,QScrollArea,QGraphicsView,QGraphicsScene,QMessageBox)
import engine
from project import Document,export_script

def configure_app():
    app=QApplication.instance(); app.setStyle('Fusion')
    if not QFontDatabase.families() and os.name=='nt':
        QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeui.ttf'))
    families=QFontDatabase.families()
    app.setFont(QFont('Segoe UI' if 'Segoe UI' in families else 'DejaVu Sans',10))
    palette=QPalette()
    for role,color in [(QPalette.ColorRole.Window,'#171c24'),(QPalette.ColorRole.WindowText,'#e3edf7'),
        (QPalette.ColorRole.Base,'#0e1621'),(QPalette.ColorRole.AlternateBase,'#202c3b'),
        (QPalette.ColorRole.Text,'#e3edf7'),(QPalette.ColorRole.Button,'#283a50'),
        (QPalette.ColorRole.ButtonText,'#e3edf7'),(QPalette.ColorRole.Highlight,'#247f9b'),
        (QPalette.ColorRole.HighlightedText,'#ffffff'),(QPalette.ColorRole.ToolTipBase,'#283a50'),
        (QPalette.ColorRole.ToolTipText,'#ffffff')]:palette.setColor(role,QColor(color))
    app.setPalette(palette)

def qimage(array):
    array=np.ascontiguousarray(array)
    fmt=QImage.Format.Format_RGB888 if array.ndim==3 else QImage.Format.Format_Grayscale8
    return QImage(array.data,array.shape[1],array.shape[0],array.strides[0],fmt).copy()

class Canvas(QGraphicsView):
    pixel=Signal(str)
    def __init__(self):
        super().__init__(); self.setScene(QGraphicsScene(self)); self.image=None; self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    def show_array(self,array):
        self.image=array; self.scene().clear(); self.scene().addPixmap(QPixmap.fromImage(qimage(array)))
        self.scene().setSceneRect(0,0,array.shape[1],array.shape[0]); self.fit()
    def fit(self): self.fitInView(self.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        scale=self.transform().m11()
        if .02<scale*factor<64:self.scale(factor,factor)
    def mouseMoveEvent(self,event):
        if self.image is not None:
            point=self.mapToScene(event.position().toPoint()); x,y=int(point.x()),int(point.y())
            if 0<=y<self.image.shape[0] and 0<=x<self.image.shape[1]: self.pixel.emit(f'Pixel ({x}, {y}): {self.image[y,x].tolist()}')
        super().mouseMoveEvent(event)

class Signals(QObject):
    done=Signal(int,object)
    failed=Signal(int,str)
    finished=Signal(int)

class Preview(QRunnable):
    def __init__(self,revision,image,pipeline,fast,cache,cancel):
        super().__init__(); self.revision=revision; self.image=image; self.pipeline=pipeline
        self.fast=fast; self.cache=cache; self.cancel=cancel; self.signals=Signals()
    def run(self):
        try:
            if self.cancel.is_set():return
            image=self.image
            if self.fast and max(image.shape[:2])>1000:
                factor=1000/max(image.shape[:2]); image=cv2.resize(image,(max(1,round(image.shape[1]*factor)),max(1,round(image.shape[0]*factor))),interpolation=cv2.INTER_AREA)
            start=time.perf_counter(); final,outputs,timings=engine.run(image,self.pipeline,self.cache,self.cancel.is_set)
            # Limit retained prefix cache to 96 MiB. Intermediates of current preview remain selectable.
            while sum(x.nbytes for x in self.cache.values())>96*1024*1024:self.cache.pop(next(iter(self.cache)))
            self.signals.done.emit(self.revision,(image,final,outputs,timings,(time.perf_counter()-start)*1000,self.cache))
        except InterruptedError:pass
        except Exception as exc:self.signals.failed.emit(self.revision,str(exc))
        finally:self.signals.finished.emit(self.revision)

class Workbench(QMainWindow):
    def __init__(self):
        super().__init__(); configure_app(); self.setWindowTitle('CV2 Image to Script — Pipeline Workbench'); self.resize(1500,900)
        self.document=Document(); self.paths=[]; self.original=None; self.outputs=[]; self.final=None
        self.revision=0; self.cancel=threading.Event(); self.cache={}; self.cache_scope=None; self.worker_refs={}
        self.pool=QThreadPool(self); self.pool.setMaxThreadCount(1)
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(160); self.timer.timeout.connect(self.start_preview)
        root=QWidget(); self.setCentralWidget(root); main=QVBoxLayout(root)
        toolbar=QHBoxLayout(); main.addLayout(toolbar)
        for text,callback in [('Add images',self.open_images),('Open pipeline',self.open_pipeline),('Save pipeline',self.save_pipeline),('Export fixed Python',self.export),('Save processed PNG',self.save_output),('Undo',self.undo),('Redo',self.redo)]:
            button=QPushButton(text); button.clicked.connect(callback); toolbar.addWidget(button)
        self.exact=QCheckBox('Exact full resolution'); self.exact.toggled.connect(self.request_preview); toolbar.addWidget(self.exact)
        random_bar=QHBoxLayout();main.addLayout(random_bar)
        for text,callback in [('Random settings for selected step',self.random_settings),('Dataset / random preview',self.generation),('Replay generated record',self.replay_generated)]:
            button=QPushButton(text);button.clicked.connect(callback);random_bar.addWidget(button)
        body=QSplitter(); main.addWidget(body,1)
        self.gallery=QListWidget(); self.gallery.setMaximumWidth(220); self.gallery.currentRowChanged.connect(self.select_image); body.addWidget(self.gallery)
        middle=QWidget(); layout=QVBoxLayout(middle); canvases=QSplitter()
        self.before=Canvas(); self.after=Canvas()
        for title,canvas in [('Original / preview input',self.before),('Processed / selected stage',self.after)]:
            pane=QWidget(); col=QVBoxLayout(pane); col.addWidget(QLabel(title)); col.addWidget(canvas); canvases.addWidget(pane)
            canvas.pixel.connect(self.statusBar().showMessage)
        layout.addWidget(canvases,1)
        controls=QHBoxLayout(); self.stage=QComboBox(); self.stage.addItem('Final output'); self.stage.currentIndexChanged.connect(self.display_stage)
        controls.addWidget(QLabel('Inspect stage:')); controls.addWidget(self.stage,1)
        fit=QPushButton('Fit both views'); fit.clicked.connect(lambda:(self.before.fit(),self.after.fit())); controls.addWidget(fit); layout.addLayout(controls)
        self.metadata=QLabel('Load images to start. Wheel: zoom. Drag: pan.'); self.metadata.setWordWrap(True); layout.addWidget(self.metadata); body.addWidget(middle)
        panel=QWidget(); right=QVBoxLayout(panel); panel.setMinimumWidth(320)
        right.addWidget(QLabel('Ordered processing pipeline'))
        add=QHBoxLayout(); self.kind=QComboBox(); self.kind.addItems(engine.OPERATIONS); add.addWidget(self.kind)
        button=QPushButton('Add'); button.clicked.connect(self.add_step); add.addWidget(button); right.addLayout(add)
        self.steps=QListWidget(); self.steps.currentRowChanged.connect(self.build_settings); self.steps.itemChanged.connect(self.toggle_step); right.addWidget(self.steps)
        actions=QHBoxLayout()
        for text,fn in [('Up',lambda:self.move(-1)),('Down',lambda:self.move(1)),('Duplicate',self.duplicate),('Remove',self.remove)]:
            b=QPushButton(text); b.clicked.connect(fn); actions.addWidget(b)
        right.addLayout(actions)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); self.settings=QWidget(); self.form=QFormLayout(self.settings); scroll.setWidget(self.settings); right.addWidget(scroll,1)
        body.addWidget(panel); body.setSizes([180,970,350])
        for shortcut,callback in [('Ctrl+Z',self.undo),('Ctrl+Y',self.redo),('Ctrl+O',self.open_images),('Ctrl+S',self.save_pipeline)]:
            action=QAction(self); action.setShortcut(shortcut); action.triggered.connect(callback); self.addAction(action)
        self.setStyleSheet('QMainWindow {background:#171c24;} QWidget {font-size:12px;} QPushButton {padding:6px;} QListWidget {min-height:100px;}')

    def error(self,message): self.statusBar().showMessage(message); self.metadata.setText('Error: '+message)
    def random_settings(self):
        from generation_ui import RandomSettings
        i=self.steps.currentRow()
        if i<0:self.error('Select a pipeline step first');return
        dialog=RandomSettings(self.document.pipeline['steps'][i],self)
        if dialog.exec():
            p=copy.deepcopy(self.document.pipeline);p['steps'][i]=dialog.step;self.commit(p,i)
    def generation(self):
        from generation_ui import GenerationDialog
        dialog=GenerationDialog(self.document.pipeline,self.paths,self);dialog.exec()
    def replay_generated(self):
        from dataset import replay_record
        from PySide6.QtWidgets import QInputDialog
        path,_=QFileDialog.getOpenFileName(self,'Replay records','','JSON lines (*.jsonl)')
        if not path:return
        try:
            records=[json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
            if not records:raise ValueError('No replay records')
            row,ok=QInputDialog.getInt(self,'Replay sample','Zero-based record row',0,0,len(records)-1)
            if not ok:return
            out,_=QFileDialog.getSaveFileName(self,'Replay output','replay.png','PNG (*.png)')
            if out:self.statusBar().showMessage(str(replay_record(records[row],out)))
        except Exception as exc:QMessageBox.warning(self,'Replay failed',str(exc))
    def open_images(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Add representative images','','Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)')
        if paths:self.load_paths(paths)
    def load_paths(self,paths):
        for path in paths:
            if path not in self.paths:self.paths.append(path); self.gallery.addItem(Path(path).name)
        if self.gallery.currentRow()<0:self.gallery.setCurrentRow(0)
    def select_image(self,index):
        if index<0:return
        self.invalidate(); self.cache={}; self.final=None; self.outputs=[]
        try:self.original=engine.read_image(self.paths[index]); self.request_preview()
        except Exception as exc:self.original=None; self.error(str(exc))
    def invalidate(self):
        self.cancel.set(); self.cancel=threading.Event(); self.revision+=1; self.final=None
    def request_preview(self,*args):
        self.invalidate(); self.timer.start()
    def start_preview(self):
        if self.original is None:return
        scope=(self.gallery.currentRow(),self.exact.isChecked())
        if scope!=self.cache_scope:self.cache={}; self.cache_scope=scope
        revision=self.revision
        worker=Preview(revision,self.original,self.document.pipeline,self.exact.isChecked()==False,dict(self.cache),self.cancel)
        worker.signals.done.connect(self.preview_done); worker.signals.failed.connect(self.preview_failed)
        worker.signals.finished.connect(self.worker_finished)
        self.worker_refs[revision]=worker; self.metadata.setText('Processing…'); self.pool.start(worker)
    def worker_finished(self,revision):self.worker_refs.pop(revision,None)
    def preview_failed(self,revision,message):
        self.worker_refs.pop(revision,None)
        if revision==self.revision:self.error(message)
    def preview_done(self,revision,result):
        self.worker_refs.pop(revision,None)
        if revision!=self.revision:return
        image,self.final,self.outputs,times,elapsed,self.cache=result
        self.before.show_array(image)
        selected=self.stage.currentIndex(); self.stage.blockSignals(True); self.stage.clear(); self.stage.addItem('Final output')
        for i,step in enumerate(self.document.pipeline['steps']):self.stage.addItem(f"{i+1}. {step['type']} ({times[i]:.1f} ms)")
        self.stage.setCurrentIndex(min(max(selected,0),self.stage.count()-1)); self.stage.blockSignals(False); self.display_stage()
        mode='EXACT — original pixels' if self.exact.isChecked() else 'FAST — max 1000 px, settings act on preview pixels'
        h,w=self.final.shape[:2]; channels=1 if self.final.ndim==2 else self.final.shape[2]
        self.metadata.setText(f'{mode} | Output {w} × {h}, {channels} channels, uint8, range {self.final.min()}–{self.final.max()} | {elapsed:.1f} ms. Export and saved PNG always use original resolution.')
    def display_stage(self,*args):
        if self.final is None:return
        i=self.stage.currentIndex(); self.after.show_array(self.outputs[i-1] if 0<i<=len(self.outputs) else self.final)
    def refresh_steps(self,index=None):
        if index is None:index=self.steps.currentRow()
        self.steps.blockSignals(True); self.steps.clear()
        for n,step in enumerate(self.document.pipeline['steps']):
            item=QListWidgetItem(f"{n+1}. {step['type']}"); item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if step['enabled'] else Qt.CheckState.Unchecked); self.steps.addItem(item)
        self.steps.setCurrentRow(min(index,len(self.document.pipeline['steps'])-1)); self.steps.blockSignals(False); self.build_settings(); self.request_preview()
    def commit(self,pipeline,index=None):self.document.commit(pipeline); self.refresh_steps(index)
    def add_step(self):
        p=copy.deepcopy(self.document.pipeline); p['steps'].append(engine.new_step(self.kind.currentText())); self.commit(p,len(p['steps'])-1)
    def remove(self):
        i=self.steps.currentRow()
        if i>=0:p=copy.deepcopy(self.document.pipeline); p['steps'].pop(i); self.commit(p)
    def duplicate(self):
        import uuid
        i=self.steps.currentRow()
        if i>=0:
            p=copy.deepcopy(self.document.pipeline); step=copy.deepcopy(p['steps'][i]); step['id']=uuid.uuid4().hex
            p['steps'].insert(i+1,step); self.commit(p,i+1)
    def move(self,direction):
        i=self.steps.currentRow(); j=i+direction; p=copy.deepcopy(self.document.pipeline)
        if i>=0 and 0<=j<len(p['steps']):p['steps'][i],p['steps'][j]=p['steps'][j],p['steps'][i]; self.commit(p,j)
    def toggle_step(self,item):
        p=copy.deepcopy(self.document.pipeline); p['steps'][self.steps.row(item)]['enabled']=item.checkState()==Qt.CheckState.Checked; self.commit(p)
    def undo(self):self.document.undo(); self.refresh_steps()
    def redo(self):self.document.redo(); self.refresh_steps()
    def build_settings(self,*args):
        while self.form.rowCount():self.form.removeRow(0)
        i=self.steps.currentRow()
        if i<0:return
        step=self.document.pipeline['steps'][i]
        for key,spec in engine.OPERATIONS[step['type']].items():
            if 'choices' in spec or key in ('kernel','block'):
                values=spec['choices'] if 'choices' in spec else [str(n) for n in range(spec['minimum'],spec['maximum']+1,2)]
                field=QComboBox(); field.addItems(values); field.setCurrentText(str(step['params'][key])); field.currentTextChanged.connect(lambda value,k=key:self.change_parameter(k,int(value) if k in ('kernel','block') else value))
                self.form.addRow(key,field)
            else:
                container=QWidget(); line=QHBoxLayout(container); line.setContentsMargins(0,0,0,0)
                field=QSpinBox() if spec['integer'] else QDoubleSpinBox()
                field.setRange(spec['minimum'],spec['maximum']); field.setSingleStep(spec['step']); field.setValue(step['params'][key]); field.setKeyboardTracking(False)
                field.valueChanged.connect(lambda value,k=key:self.change_parameter(k,value)); line.addWidget(field)
                if key not in ('width','height','x','y'):
                    slider=QSlider(Qt.Orientation.Horizontal); factor=1 if spec['integer'] else 100
                    slider.setRange(round(spec['minimum']*factor),round(spec['maximum']*factor)); slider.setValue(round(step['params'][key]*factor))
                    slider.valueChanged.connect(lambda value,f=field,s=spec,factor=factor:f.setValue(int(value) if s['integer'] else value/factor))
                    field.valueChanged.connect(lambda value,s=slider,factor=factor:s.setValue(round(value*factor))); line.addWidget(slider)
                self.form.addRow(key,container)
    def change_parameter(self,key,value):
        i=self.steps.currentRow()
        if i<0:return
        p=copy.deepcopy(self.document.pipeline); spec=engine.OPERATIONS[p['steps'][i]['type']][key]
        if key in ('kernel','block') and value%2==0:value=min(value+1,spec['maximum'])
        p['steps'][i]['params'][key]=value
        try:self.document.commit(p); self.request_preview()
        except ValueError as exc:self.error(str(exc)); QTimer.singleShot(0,self.build_settings)
    def open_pipeline(self):
        path,_=QFileDialog.getOpenFileName(self,'Open pipeline','','Pipeline (*.json)')
        if path:
            try:self.commit(engine.load_pipeline(path),0)
            except Exception as exc:QMessageBox.warning(self,'Cannot load pipeline',str(exc))
    def save_pipeline(self):
        path,_=QFileDialog.getSaveFileName(self,'Save pipeline','pipeline.json','JSON (*.json)')
        if path:
            try:engine.save_pipeline(path,self.document.pipeline)
            except Exception as exc:QMessageBox.warning(self,'Save failed',str(exc))
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Export standalone Python','process_images.py','Python (*.py)')
        if path:
            try:export_script(path,self.document.pipeline); self.statusBar().showMessage('Standalone script exported. Run: python process_images.py INPUT OUTPUT')
            except Exception as exc:QMessageBox.warning(self,'Export failed',str(exc))
    def save_output(self):
        if self.original is None:return
        path,_=QFileDialog.getSaveFileName(self,'Save exact processed image','processed.png','PNG (*.png)')
        if path:
            # Exact save is explicit and synchronous; preview never becomes an export source.
            try:engine.write_image(path,engine.run(self.original,self.document.pipeline,retain_intermediates=False)[0])
            except Exception as exc:QMessageBox.warning(self,'Save failed',str(exc))
    def closeEvent(self,event):self.cancel.set(); self.timer.stop(); self.pool.clear(); self.pool.waitForDone(); super().closeEvent(event)

if __name__=='__main__':
    if '--self-test' in sys.argv:
        from packaging_check import main
        main();sys.exit(0)
    app=QApplication(sys.argv); app.setStyle('Fusion'); window=Workbench(); window.show(); sys.exit(app.exec())
