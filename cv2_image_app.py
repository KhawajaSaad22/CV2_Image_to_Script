import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QSlider, QGroupBox, QMainWindow, QAction, QMenuBar,
    QComboBox, QListWidget, QListWidgetItem, QSplitter, QCheckBox
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt


class ImageEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini Photoshop with OpenCV")
        self.original_image = None
        self.layers = []
        self.current_image = None
        self.current_filter = None
        self.current_filter_params = {}
        self.current_path = None
        self.undo_stack = []
        self.redo_stack = []
        self.preview_temp_image = None

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        top_panel = QHBoxLayout()
        content_splitter = QSplitter(Qt.Horizontal)

        menu_bar = QMenuBar(self)
        file_menu = menu_bar.addMenu("File")

        load_action = QAction("Load Image", self)
        load_action.triggered.connect(self.load_image)
        file_menu.addAction(load_action)

        export_action = QAction("Export Script", self)
        export_action.triggered.connect(self.export_script)
        file_menu.addAction(export_action)

        self.setMenuBar(menu_bar)

        image_panel = QWidget()
        image_layout = QHBoxLayout()
        image_panel.setLayout(image_layout)

        self.original_label = QLabel("Original Image")
        self.edited_label = QLabel("Edited Image")
        self.original_label.setFixedSize(300, 300)
        self.edited_label.setFixedSize(300, 300)
        image_layout.addWidget(self.original_label)
        image_layout.addWidget(self.edited_label)

        self.filter_dropdown = QComboBox()
        self.filter_dropdown.addItems(["Select Filter", "Grayscale", "Blur", "Canny", "Brightness", "Contrast", "Sepia"])
        self.filter_dropdown.setEnabled(False)
        self.filter_dropdown.currentIndexChanged.connect(self.prepare_filter)

        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setRange(1, 31)
        self.blur_slider.setSingleStep(2)
        self.blur_slider.setValue(5)
        self.blur_slider.valueChanged.connect(self.preview_filter)

        self.canny_slider = QSlider(Qt.Horizontal)
        self.canny_slider.setRange(50, 200)
        self.canny_slider.setValue(100)
        self.canny_slider.valueChanged.connect(self.preview_filter)

        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.preview_filter)

        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(1, 300)
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self.preview_filter)

        self.hide_all_sliders()

        apply_button = QPushButton("Apply Filter")
        apply_button.clicked.connect(self.apply_filter)

        undo_button = QPushButton("Undo")
        undo_button.clicked.connect(self.undo)

        redo_button = QPushButton("Redo")
        redo_button.clicked.connect(self.redo)

        self.layer_list = QListWidget()
        self.layer_list_label = QLabel("Layers")
        self.layer_list.itemChanged.connect(self.toggle_layer_visibility)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        right_layout.addWidget(self.layer_list_label)
        right_layout.addWidget(self.layer_list)

        top_panel.addWidget(self.filter_dropdown)
        top_panel.addWidget(self.blur_slider)
        top_panel.addWidget(self.canny_slider)
        top_panel.addWidget(self.brightness_slider)
        top_panel.addWidget(self.contrast_slider)
        top_panel.addWidget(apply_button)
        top_panel.addWidget(undo_button)
        top_panel.addWidget(redo_button)

        content_splitter.addWidget(image_panel)
        content_splitter.addWidget(right_panel)
        content_splitter.setSizes([700, 200])

        main_layout.addLayout(top_panel)
        main_layout.addWidget(content_splitter)
        central_widget.setLayout(main_layout)

    def hide_all_sliders(self):
        self.blur_slider.setVisible(False)
        self.canny_slider.setVisible(False)
        self.brightness_slider.setVisible(False)
        self.contrast_slider.setVisible(False)

    def load_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if file_name:
            self.original_image = cv2.imread(file_name)
            self.current_path = file_name
            self.current_image = self.original_image.copy()
            self.layers = [(self.original_image.copy(), "Original Image", True)]
            self.layer_list.clear()
            self.add_layer_item("Original Image")
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.filter_dropdown.setEnabled(True)
            self.display_images()

    def add_layer_item(self, name):
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.layer_list.addItem(item)

    def toggle_layer_visibility(self, item):
        index = self.layer_list.row(item)
        self.layers[index] = (self.layers[index][0], self.layers[index][1], item.checkState() == Qt.Checked)
        self.rebuild_current_image()

    def rebuild_current_image(self):
        img = self.layers[0][0].copy()
        for layer, name, visible in self.layers[1:]:
            if visible:
                img = layer
        self.current_image = img
        self.display_images()

    def display_images(self):
        if self.original_image is not None:
            self.original_label.setPixmap(self.convert_cv_to_pixmap(self.original_image))
            self.edited_label.setPixmap(self.convert_cv_to_pixmap(self.current_image))

    def prepare_filter(self, index):
        if index == 0 or self.original_image is None:
            self.current_filter = None
            self.hide_all_sliders()
            return

        filter_name = self.filter_dropdown.currentText()
        self.current_filter = filter_name.lower()
        self.hide_all_sliders()

        if filter_name == "Blur":
            self.blur_slider.setVisible(True)
        elif filter_name == "Canny":
            self.canny_slider.setVisible(True)
        elif filter_name == "Brightness":
            self.brightness_slider.setVisible(True)
        elif filter_name == "Contrast":
            self.contrast_slider.setVisible(True)

        self.preview_filter()

    def preview_filter(self):
        if self.original_image is None or not self.current_filter:
            return

        img = self.current_image.copy()
        if self.current_filter == "grayscale":
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif self.current_filter == "blur":
            k = self.blur_slider.value()
            if k % 2 == 0:
                k += 1
            img = cv2.GaussianBlur(img, (k, k), 0)
        elif self.current_filter == "canny":
            t = self.canny_slider.value()
            edges = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), t, t * 2)
            img = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        elif self.current_filter == "brightness":
            v = self.brightness_slider.value()
            img = cv2.convertScaleAbs(img, alpha=1, beta=v)
        elif self.current_filter == "contrast":
            alpha = self.contrast_slider.value() / 100.0
            img = cv2.convertScaleAbs(img, alpha=alpha, beta=0)
        elif self.current_filter == "sepia":
            kernel = np.array([[0.272, 0.534, 0.131],
                               [0.349, 0.686, 0.168],
                               [0.393, 0.769, 0.189]])
            img = cv2.transform(img, kernel)
            img = np.clip(img, 0, 255).astype(np.uint8)

        self.preview_temp_image = img.copy()
        self.edited_label.setPixmap(self.convert_cv_to_pixmap(img))

    def apply_filter(self):
        if self.preview_temp_image is None:
            return

        self.undo_stack.append(self.current_image.copy())
        self.current_image = self.preview_temp_image.copy()
        self.layers.append((self.current_image.copy(), self.current_filter.title(), True))
        self.add_layer_item(f"Layer {len(self.layers) - 1}: {self.current_filter.title()}")
        self.redo_stack.clear()
        self.display_images()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.current_image.copy())
            self.current_image = self.undo_stack.pop()
            if len(self.layers) > 1:
                self.layer_list.takeItem(self.layer_list.count() - 1)
                self.layers.pop()
            self.display_images()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.current_image.copy())
            redone = self.redo_stack.pop()
            self.current_image = redone
            self.layers.append((redone.copy(), "Redo", True))
            self.add_layer_item(f"Layer {len(self.layers) - 1}: Redo")
            self.display_images()

    def convert_cv_to_pixmap(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        return QPixmap.fromImage(QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).scaled(300, 300, Qt.KeepAspectRatio))

    def export_script(self):
        lines = [
            "import cv2",
            f"img = cv2.imread('{self.current_path or 'your_image.jpg'}')"
        ]
        for _, name, visible in self.layers[1:]:
            if visible:
                lines.append(f"# Apply: {name} (manual implementation needed)")
        lines.append("cv2.imwrite('edited_output.jpg', img)")
        with open("exported_script.py", "w") as f:
            f.write("\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = ImageEditor()
    editor.show()
    sys.exit(app.exec_())
