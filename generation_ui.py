"""Functional generation controls; visual redesign is intentionally deferred."""
import copy
import json
from pathlib import Path
import threading
import cv2
from PySide6.QtCore import QObject,Signal,QRunnable,QThreadPool,Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QDoubleSpinBox,
 QSpinBox,QPlainTextEdit,QDialogButtonBox,QFileDialog,QLineEdit,QProgressBar,QScrollArea,QMessageBox)
import engine
from augmentation import sample
from dataset import contact_sheet,generate,read_manifest
from project import export_script,export_bundle

class RandomSettings(QDialog):
    def __init__(self,step,parent=None):
        super().__init__(parent); self.setWindowTitle('Randomize selected operation'); self.resize(600,450); self.step=copy.deepcopy(step)
        layout=QVBoxLayout(self); self.probability=QDoubleSpinBox();self.probability.setRange(0,1);self.probability.setSingleStep(.05);self.probability.setValue(step.get('random',{}).get('probability',1))
        form=QFormLayout();form.addRow('Apply probability',self.probability);layout.addLayout(form)
        layout.addWidget(QLabel('Parameter rules (JSON): use {"min": value, "max": value} or {"choices": [...]}.\nLeave {} to keep every parameter fixed. Numeric kernels sample odd values only.'))
        self.editor=QPlainTextEdit();self.editor.setPlainText(json.dumps(step.get('random',{}).get('params',{}),indent=2));layout.addWidget(self.editor)
        defaults={key:({'choices':spec['choices']} if 'choices' in spec else {'min':step['params'][key],'max':step['params'][key]}) for key,spec in engine.OPERATIONS[step['type']].items()}
        fill=QPushButton('Insert fixed-value rules as a starting point');fill.clicked.connect(lambda:self.editor.setPlainText(json.dumps(defaults,indent=2)));layout.addWidget(fill)
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept_checked);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def accept_checked(self):
        try:
            self.step['random']={'probability':self.probability.value(),'params':json.loads(self.editor.toPlainText())}
            engine.validate({'version':1,'steps':[self.step]});self.accept()
        except Exception as exc:self.error.setText(str(exc))

class Signals(QObject):
    done=Signal(object); failed=Signal(str); progress=Signal(int,int)

class Task(QRunnable):
    def __init__(self,fn):super().__init__();self.fn=fn;self.signals=Signals()
    def run(self):
        try:self.signals.done.emit(self.fn(self.signals.progress.emit))
        except Exception as exc:self.signals.failed.emit(str(exc))

class GenerationDialog(QDialog):
    def __init__(self,recipe,paths,parent=None):
        super().__init__(parent); self.setWindowTitle('Dataset generation and replay');self.resize(980,700)
        self.recipe=copy.deepcopy(recipe);self.paths=list(paths);self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1);self.task=None;self.cancel=threading.Event();self.samples=[]
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.seed=QSpinBox();self.seed.setRange(0,2147483647);self.seed.setValue(42);form.addRow('Seed',self.seed)
        self.count=QSpinBox();self.count.setRange(1,1000);self.count.setValue(5);form.addRow('Variants per training image',self.count)
        self.visibility=QDoubleSpinBox();self.visibility.setRange(0,1);self.visibility.setSingleStep(.1);form.addRow('Minimum retained box visibility',self.visibility)
        self.manifest=QLineEdit();row=QHBoxLayout();row.addWidget(self.manifest);browse=QPushButton('Browse manifest');row.addWidget(browse);browse.clicked.connect(self.pick_manifest);form.addRow('Paired manifest (optional)',row)
        self.output=QLineEdit('generated/run-1');form.addRow('New output folder',self.output)
        layout.addWidget(QLabel('Without a manifest, loaded gallery images are treated as unlabeled training sources.\nWith a manifest, only train records are generated; cross-split duplicate content is rejected.'))
        buttons=QHBoxLayout();layout.addLayout(buttons)
        self.preview_button=QPushButton('Sample contact sheet (up to 9)');self.preview_button.clicked.connect(self.preview);buttons.addWidget(self.preview_button)
        self.generate_button=QPushButton('Generate dataset');self.generate_button.clicked.connect(self.generate);buttons.addWidget(self.generate_button)
        bundle=QPushButton('Export generation bundle');bundle.clicked.connect(self.bundle);buttons.addWidget(bundle)
        self.cancel_button=QPushButton('Cancel current job');self.cancel_button.clicked.connect(self.cancel.set);buttons.addWidget(self.cancel_button)
        sampled=QPushButton('Export first sampled pipeline');sampled.clicked.connect(self.export_sample);buttons.addWidget(sampled)
        self.progress=QProgressBar();layout.addWidget(self.progress);self.message=QLabel();self.message.setWordWrap(True);layout.addWidget(self.message)
        scroll=QScrollArea();scroll.setWidgetResizable(True);self.sheet=QLabel('Sample once, then inspect or export those sampled settings.');self.sheet.setAlignment(Qt.AlignmentFlag.AlignCenter);scroll.setWidget(self.sheet);layout.addWidget(scroll,1)
    def pick_manifest(self):
        path,_=QFileDialog.getOpenFileName(self,'Dataset manifest','','JSON (*.json)')
        if path:self.manifest.setText(path)
    def sources(self):
        if self.manifest.text().strip():return [r for r in read_manifest(self.manifest.text()) if r['split']=='train']
        return [{'id':str(Path(p).resolve()),'image':str(Path(p).resolve()),'split':'train'} for p in self.paths]
    def start(self,fn,callback):
        if self.task:return
        self.cancel.clear();self.preview_button.setEnabled(False);self.generate_button.setEnabled(False);self.message.setText('Working…')
        self.task=Task(fn);self.task.signals.progress.connect(self.update_progress)
        self.task.signals.done.connect(lambda result:self.finished(result,callback));self.task.signals.failed.connect(self.failed);self.pool.start(self.task)
    def update_progress(self,done,total):self.progress.setMaximum(total);self.progress.setValue(done)
    def finished(self,result,callback):
        self.task=None;self.preview_button.setEnabled(True);self.generate_button.setEnabled(True);callback(result)
    def failed(self,message):
        self.task=None;self.preview_button.setEnabled(True);self.generate_button.setEnabled(True);self.message.setText('Stopped: '+message)
    def preview(self):
        try:
            records=self.sources()
            if not records:raise ValueError('Load images or a training manifest first')
            recipe=copy.deepcopy(self.recipe);seed=self.seed.value();count=min(9,self.count.value());record=records[0]
            self.samples=[]
            def work(progress):
                source=engine.read_image(record['image']);samples=[];images=[]
                for n in range(count):
                    if self.cancel.is_set():raise InterruptedError('Preview cancelled')
                    resolved=sample(recipe,seed,record['id'],n);result=engine.run(source,resolved,retain_intermediates=False)[0]
                    scale=min(1,300/max(result.shape[:2]));images.append(cv2.resize(result,(max(1,round(result.shape[1]*scale)),max(1,round(result.shape[0]*scale)))));samples.append(resolved);progress(n+1,count)
                return contact_sheet(images),samples
            def show(result):
                from workbench import qimage
                image,self.samples=result;self.sheet.setPixmap(QPixmap.fromImage(qimage(image)));self.message.setText('Sampled settings frozen until you sample again. Contact sheet uses the first source at original resolution.')
            self.start(work,show)
        except Exception as exc:self.failed(str(exc))
    def generate(self):
        try:
            records=self.sources();recipe=copy.deepcopy(self.recipe);out=self.output.text();variants=self.count.value();seed=self.seed.value();visibility=self.visibility.value()
            self.start(lambda progress:generate(records,recipe,out,variants,seed,visibility,progress,self.cancel.is_set),lambda result:self.message.setText(f"Finished: {result['generated']} images. Replay and target records saved."))
        except Exception as exc:self.failed(str(exc))
    def bundle(self):
        path,_=QFileDialog.getSaveFileName(self,'Export portable generation bundle','generation.zip','ZIP (*.zip)')
        if path:
            try:export_bundle(path,self.recipe);self.message.setText('Exported code, recipe, requirements, and instructions; no private source images included.')
            except Exception as exc:self.failed(str(exc))
    def export_sample(self):
        if not self.samples:self.message.setText('Sample a contact sheet first.');return
        path,_=QFileDialog.getSaveFileName(self,'Export sampled pipeline','sampled.py','Python (*.py);;JSON (*.json)')
        if path:
            if Path(path).suffix.lower()=='.py':export_script(path,self.samples[0])
            else:engine.save_pipeline(path,self.samples[0])
            self.message.setText('Saved the exact first sampled pipeline, not the randomized recipe.')
    def closeEvent(self,event):
        if self.task:self.cancel.set();self.message.setText('Cancelling; close again after the job stops.');event.ignore()
        else:super().closeEvent(event)
    def reject(self):
        if self.task:self.cancel.set();self.message.setText('Cancelling; wait for the current sample to finish.')
        else:super().reject()
