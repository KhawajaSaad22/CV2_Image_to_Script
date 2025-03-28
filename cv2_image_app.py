import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QSlider, QGroupBox, QGridLayout, QMainWindow, QAction, QMenuBar,
    QComboBox, QStackedWidget, QListWidget
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt


class ImageEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini Photoshop with OpenCV")
        self.original_image = None
        self.layers = []  # List of applied layers
        self.current_image = None
        self.current_filter = None
        self.current_filter_params = {}
        self.current_path = None

        self.init_ui()

    def init_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layouts
        main_layout = QHBoxLayout()
        image_layout = QHBoxLayout()
        left_panel = QVBoxLayout()
        right_panel = QVBoxLayout()

        # Menu Bar
        menu_bar = QMenuBar(self)
        file_menu = menu_bar.addMenu("File")

        load_action = QAction("Load Image", self)
        load_action.triggered.connect(self.load_image)
        file_menu.addAction(load_action)

        export_action = QAction("Export Script", self)
        export_action.triggered.connect(self.export_script)
        file_menu.addAction(export_action)

        self.setMenuBar(menu_bar)

        # Image Displays
        self.original_label = QLabel("Original Image")
        self.edited_label = QLabel("Edited Image")
        self.original_label.setFixedSize(300, 300)
        self.edited_label.setFixedSize(300, 300)
        image_layout.addWidget(self.original_label)
        image_layout.addWidget(self.edited_label)

        # Filter Dropdown
        self.filter_dropdown = QComboBox()
        self.filter_dropdown.addItems(["Select Filter", "Grayscale", "Blur", "Canny"])
        self.filter_dropdown.currentTextChanged.connect(self.prepare_filter)

        # Sliders for filter settings
        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setMinimum(1)
        self.blur_slider.setMaximum(31)
        self.blur_slider.setValue(5)
        self.blur_slider.setSingleStep(2)
        self.blur_slider.setTickInterval(2)
        self.blur_slider.valueChanged.connect(self.preview_filter)
        self.blur_slider.setVisible(False)

        self.canny_slider = QSlider(Qt.Horizontal)
        self.canny_slider.setMinimum(50)
        self.canny_slider.setMaximum(200)
        self.canny_slider.setValue(100)
        self.canny_slider.setTickInterval(10)
        self.canny_slider.valueChanged.connect(self.preview_filter)
        self.canny_slider.setVisible(False)

        # Apply Filter Button
        apply_button = QPushButton("Apply Filter")
        apply_button.clicked.connect(self.apply_filter)

        # Assemble Panels
        left_panel.addWidget(QLabel("Filter Selection"))
        left_panel.addWidget(self.filter_dropdown)
        left_panel.addWidget(self.blur_slider)
        left_panel.addWidget(self.canny_slider)
        left_panel.addWidget(apply_button)

        main_layout.addLayout(left_panel)
        main_layout.addLayout(image_layout)

        central_widget.setLayout(main_layout)

    def load_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if file_name:
            self.original_image = cv2.imread(file_name)
            self.current_path = file_name
            self.current_image = self.original_image.copy()
            self.layers = [self.original_image.copy()]  # Reset layers
            self.display_images()

    def display_images(self):
        def convert_cv_to_pixmap(cv_img):
            rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            return QPixmap.fromImage(QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).scaled(300, 300, Qt.KeepAspectRatio))

        if self.original_image is not None:
            self.original_label.setPixmap(convert_cv_to_pixmap(self.original_image))
            self.edited_label.setPixmap(convert_cv_to_pixmap(self.current_image))

    def prepare_filter(self, filter_name):
        self.current_filter = filter_name.lower()
        self.current_filter_params = {}

        self.blur_slider.setVisible(False)
        self.canny_slider.setVisible(False)

        if filter_name == "Blur":
            self.blur_slider.setVisible(True)
            self.preview_filter()
        elif filter_name == "Canny":
            self.canny_slider.setVisible(True)
            self.preview_filter()
        elif filter_name == "Grayscale":
            self.preview_filter()

    def preview_filter(self):
        if self.original_image is None or not self.current_filter:
            return

        temp = self.current_image.copy()

        if self.current_filter == "grayscale":
            temp = cv2.cvtColor(temp, cv2.COLOR_BGR2GRAY)
            temp = cv2.cvtColor(temp, cv2.COLOR_GRAY2BGR)

        elif self.current_filter == "blur":
            k = self.blur_slider.value()
            if k % 2 == 0:
                k += 1
            temp = cv2.GaussianBlur(temp, (k, k), 0)
            self.current_filter_params = {"kernel": k}

        elif self.current_filter == "canny":
            t = self.canny_slider.value()
            edges = cv2.Canny(cv2.cvtColor(temp, cv2.COLOR_BGR2GRAY), t, t * 2)
            temp = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            self.current_filter_params = {"threshold": t}

        self.edited_label.setPixmap(self.convert_cv_to_pixmap(temp))

    def apply_filter(self):
        if self.current_filter is None or self.current_image is None:
            return

        temp = self.current_image.copy()

        if self.current_filter == "grayscale":
            temp = cv2.cvtColor(temp, cv2.COLOR_BGR2GRAY)
            temp = cv2.cvtColor(temp, cv2.COLOR_GRAY2BGR)
        elif self.current_filter == "blur":
            k = self.current_filter_params.get("kernel", 5)
            temp = cv2.GaussianBlur(temp, (k, k), 0)
        elif self.current_filter == "canny":
            t = self.current_filter_params.get("threshold", 100)
            edges = cv2.Canny(cv2.cvtColor(temp, cv2.COLOR_BGR2GRAY), t, t * 2)
            temp = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        self.layers.append(temp.copy())
        self.current_image = temp
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

        for layer in self.layers[1:]:
            # Placeholder: More sophisticated tracking of filter stack can be done here.
            lines.append("# Filter applied but operation details not stored. Add manually if needed.")

        lines.append("cv2.imwrite('edited_output.jpg', img)")

        with open("exported_script.py", "w") as f:
            f.write("\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = ImageEditor()
    editor.show()
    sys.exit(app.exec_())
