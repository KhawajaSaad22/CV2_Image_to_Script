"""Guided random controls and asynchronous dataset generation."""
import copy
import json
from pathlib import Path
import threading
import secrets
import cv2
from PySide6.QtCore import QObject,Signal,QRunnable,QThreadPool,Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QDoubleSpinBox,
 QSpinBox,QPlainTextEdit,QDialogButtonBox,QFileDialog,QLineEdit,QProgressBar,QScrollArea,QMessageBox,QTabWidget,QWidget,QComboBox)
import engine
from augmentation import sample,variation_summary
from dataset import contact_sheet,generate,read_manifest
from project import export_script,export_bundle

class RandomSettings(QDialog):
    def __init__(self,step,parent=None):
        super().__init__(parent); self.setWindowTitle('Randomize selected operation'); self.resize(600,450); self.step=copy.deepcopy(step)
        layout=QVBoxLayout(self); self.probability=QDoubleSpinBox();self.probability.setRange(0,1);self.probability.setSingleStep(.05);self.probability.setValue(step.get('random',{}).get('probability',1))
        form=QFormLayout();form.addRow('Apply probability',self.probability);layout.addLayout(form)
        layout.addWidget(QLabel('Choose Fixed, Range or Choices for each parameter. Kernels sample valid odd values.'))
        self.tabs=QTabWidget(); layout.addWidget(self.tabs)
        guided=QWidget(); self.guided_form=QFormLayout(guided); self.tabs.addTab(guided,'Guided controls')
        self.editor=QPlainTextEdit();self.editor.setPlainText(json.dumps(step.get('random',{}).get('params',{}),indent=2));self.tabs.addTab(self.editor,'Advanced JSON')
        self.advanced_dirty=False; self.building=False; self.rule_widgets={}
        self.build_guided(step.get('random',{}).get('params',{}))
        self.editor.textChanged.connect(self.advanced_changed)
        self.tabs.currentChanged.connect(self.tab_changed)
        defaults={key:({'choices':spec['choices']} if 'choices' in spec else {'min':step['params'][key],'max':step['params'][key]}) for key,spec in engine.OPERATIONS[step['type']].items()}
        suggestions={
            'rotate':{'angle':{'min':-15,'max':15}},
            'brightness_contrast':{'brightness':{'min':-25,'max':25},'contrast':{'min':.8,'max':1.2}},
            'gamma':{'gamma':{'min':.8,'max':1.2}},
            'gaussian_blur':{'kernel':{'choices':[3,5,7]}},'median_blur':{'kernel':{'choices':[3,5,7]}},
            'clahe':{'clip':{'min':1.,'max':4.}},'flip':{'direction':{'choices':['horizontal','vertical','both']}},
            'canny':{'low':{'min':30,'max':80},'high':{'min':120,'max':200}},
            'threshold':{'value':{'min':80,'max':180}},'morphology':{'kernel':{'choices':[3,5,7]}}
        }
        fill=QPushButton('Insert example random ranges (review before applying)');fill.clicked.connect(lambda:self.load_rules(suggestions.get(step['type'],defaults)));layout.addWidget(fill)
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        if self.guided_lossy:self.error.setText('This rule needs extra decimal precision. Use Advanced JSON to preserve its values.')
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept_checked);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def accept_checked(self):
        try:
            candidate=copy.deepcopy(self.step)
            rules=json.loads(self.editor.toPlainText()) if self.advanced_dirty or self.guided_lossy else self.guided_rules()
            candidate['random']={'probability':self.probability.value(),'params':rules}
            engine.validate({'version':1,'steps':[candidate]});self.step=candidate;self.accept()
        except Exception as exc:self.error.setText(str(exc))

    def build_guided(self,rules):
        self.building=True
        self.guided_lossy=False
        while self.guided_form.rowCount(): self.guided_form.removeRow(0)
        self.rule_widgets={}
        for key,spec in engine.OPERATIONS[self.step['type']].items():
            row=QWidget(); line=QHBoxLayout(row); line.setContentsMargins(0,0,0,0)
            mode=QComboBox();mode.addItems(['Fixed','Choices'] if 'choices' in spec else ['Fixed','Range','Choices']);line.addWidget(mode)
            fixed=QLabel('Value: '+str(self.step['params'][key]));line.addWidget(fixed)
            low=high=None
            if 'choices' not in spec:
                low=QSpinBox() if spec['integer'] else QDoubleSpinBox()
                high=QSpinBox() if spec['integer'] else QDoubleSpinBox()
                for field in (low,high):
                    if isinstance(field,QDoubleSpinBox):field.setDecimals(4)
                    field.setRange(spec['minimum'],spec['maximum']);field.setSingleStep(spec['step']);field.setValue(self.step['params'][key])
                    field.valueChanged.connect(self.guided_changed);line.addWidget(field)
                low.setToolTip('Minimum');high.setToolTip('Maximum');low.setPrefix('Min: ');high.setPrefix('Max: ')
            choices=QLineEdit(); choices.setPlaceholderText('Comma-separated choices');line.addWidget(choices)
            rule=rules.get(key)
            if rule:
                if 'choices' in rule:
                    mode.setCurrentText('Choices');choices.setText(', '.join(map(str,rule['choices'])))
                else:
                    mode.setCurrentText('Range');low.setValue(rule['min']);high.setValue(rule['max'])
                    if low.value()!=rule['min'] or high.value()!=rule['max']:self.guided_lossy=True
            else:choices.setText(str(self.step['params'][key]))
            self.rule_widgets[key]=(mode,low,high,choices,spec)
            fixed.setVisible(mode.currentText()=='Fixed')
            mode.currentTextChanged.connect(lambda value,label=fixed:label.setVisible(value=='Fixed'))
            mode.currentTextChanged.connect(self.guided_changed);choices.textChanged.connect(self.guided_changed)
            self.guided_form.addRow(key,row)
        self.building=False;self.update_visibility()
        self.tabs.widget(0).setEnabled(not self.guided_lossy)
        if self.guided_lossy:self.tabs.setCurrentIndex(1)

    def update_visibility(self):
        for mode,low,high,choices,spec in self.rule_widgets.values():
            if low is not None:low.setVisible(mode.currentText()=='Range');high.setVisible(mode.currentText()=='Range')
            choices.setVisible(mode.currentText()=='Choices')

    def guided_rules(self):
        result={}
        for key,(mode,low,high,choices,spec) in self.rule_widgets.items():
            if mode.currentText()=='Range':result[key]={'min':low.value(),'max':high.value()}
            elif mode.currentText()=='Choices':
                values=[v.strip() for v in choices.text().split(',') if v.strip()]
                if 'choices' not in spec:values=[int(v) if spec['integer'] else float(v) for v in values]
                result[key]={'choices':values}
        return result

    def advanced_changed(self):self.advanced_dirty=True

    def load_rules(self,rules):
        self.build_guided(rules);self.editor.blockSignals(True)
        self.editor.setPlainText(json.dumps(rules,indent=2));self.editor.blockSignals(False);self.advanced_dirty=False

    def guided_changed(self,*args):
        if self.building:return
        self.update_visibility();self.advanced_dirty=False
        try:
            rules=self.guided_rules();self.editor.blockSignals(True)
            self.editor.setPlainText(json.dumps(rules,indent=2));self.editor.blockSignals(False)
            self.error.clear()
        except ValueError as exc:self.error.setText(str(exc))

    def tab_changed(self,index):
        if index==0 and self.advanced_dirty:
            try:
                rules=json.loads(self.editor.toPlainText());candidate=copy.deepcopy(self.step)
                candidate['random']={'probability':self.probability.value(),'params':rules}
                engine.validate({'version':1,'steps':[candidate]});self.load_rules(rules)
                self.error.setText('Use Advanced JSON to preserve extra decimal precision.' if self.guided_lossy else '')
            except Exception as exc:
                self.error.setText(str(exc));self.tabs.blockSignals(True);self.tabs.setCurrentIndex(1);self.tabs.blockSignals(False)

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
        new_seed=QPushButton('New seed — get a different reproducible batch');new_seed.clicked.connect(lambda:self.seed.setValue(secrets.randbelow(2147483648)));form.addRow(new_seed)
        seed_help=QLabel('The same seed reproduces a batch; each variant still samples separately. A seed cannot add variation to fixed settings.');seed_help.setWordWrap(True);form.addRow(seed_help)
        self.count=QSpinBox();self.count.setRange(1,1000);self.count.setValue(5);form.addRow('Variants per training image',self.count)
        self.visibility=QDoubleSpinBox();self.visibility.setRange(0,1);self.visibility.setSingleStep(.1);form.addRow('Minimum retained box visibility',self.visibility)
        self.manifest=QLineEdit();row=QHBoxLayout();row.addWidget(self.manifest);browse=QPushButton('Browse manifest');row.addWidget(browse);browse.clicked.connect(self.pick_manifest);form.addRow('Paired manifest (optional)',row)
        self.output=QLineEdit('generated/run-1');form.addRow('New output folder',self.output)
        rules=variation_summary(self.recipe)
        summary=QLabel('Active variation:\n'+('\n'.join(rules) if rules else 'NONE — outputs per source will be identical. Close this dialog and configure Random settings for a step.'))
        summary.setWordWrap(True);form.addRow(summary)
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
                unique=len({(im.shape,im.tobytes()) for im in images})
                return contact_sheet(images),samples,unique
            def show(result):
                from workbench import qimage
                image,self.samples,unique=result;self.sheet.setPixmap(QPixmap.fromImage(qimage(image)));self.message.setText(f'{unique} distinct preview thumbnails out of {len(self.samples)}. Sampled settings stay frozen until you sample again. Repeated pixels can occur even with random parameters.')
            self.start(work,show)
        except Exception as exc:self.failed(str(exc))
    def generate(self):
        try:
            records=self.sources();recipe=copy.deepcopy(self.recipe);out=self.output.text();variants=self.count.value();seed=self.seed.value();visibility=self.visibility.value()
            if variants>1 and not variation_summary(recipe):
                answer=QMessageBox.question(self,'No random variation configured','All settings are fixed. This will make repeated copies for each source. Continue anyway?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
                if answer!=QMessageBox.StandardButton.Yes:return
            self.start(lambda progress:generate(records,recipe,out,variants,seed,visibility,progress,self.cancel.is_set),lambda result:self.message.setText(f"Finished: {result['generated']} images; {result['unique_images']} distinct within their sources, {result['duplicate_images']} repeats. Replay and target records saved."))
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
