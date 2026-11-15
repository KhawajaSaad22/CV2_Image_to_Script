"""Image canvases with explicit pixel scale and user-view change notifications."""
import math
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


def qimage(array):
    array = np.ascontiguousarray(array)
    fmt = QImage.Format.Format_RGB888 if array.ndim == 3 else QImage.Format.Format_Grayscale8
    return QImage(array.data, array.shape[1], array.shape[0], array.strides[0], fmt).copy()


class Canvas(QGraphicsView):
    pixel = Signal(str)
    view_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.image = None
        self.reset_next = True
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.horizontalScrollBar().valueChanged.connect(self._changed)
        self.verticalScrollBar().valueChanged.connect(self._changed)

    def _changed(self, *args):
        self.view_changed.emit()

    def show_array(self, array):
        preserve = not self.reset_next and self.image is not None and self.image.shape[:2] == array.shape[:2]
        transform = self.transform()
        center = self.mapToScene(self.viewport().rect().center())
        blocked = self.blockSignals(True)
        try:
            self.image = array
            self.scene().clear()
            self.scene().addPixmap(QPixmap.fromImage(qimage(array)))
            self.scene().setSceneRect(0, 0, array.shape[1], array.shape[0])
            if preserve:
                self.setTransform(transform)
                self.centerOn(center)
            else:
                self.fit()
            self.reset_next = False
        finally:
            self.blockSignals(blocked)

    def fit(self):
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.view_changed.emit()

    def actual_size(self):
        center = self.mapToScene(self.viewport().rect().center())
        self.resetTransform()
        self.centerOn(center)
        self.view_changed.emit()

    def zoom(self, factor):
        if .02 < self.transform().m11() * factor < 64:
            self.scale(factor, factor)
            self.view_changed.emit()

    def wheelEvent(self, event):
        if event.angleDelta().y():
            self.zoom(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.image is not None:
            point = self.mapToScene(event.position().toPoint())
            x, y = math.floor(point.x()), math.floor(point.y())
            if 0 <= y < self.image.shape[0] and 0 <= x < self.image.shape[1]:
                self.pixel.emit(f"Pixel ({x}, {y}): {self.image[y, x].tolist()}")
        super().mouseMoveEvent(event)
