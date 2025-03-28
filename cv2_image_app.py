import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QListWidget, QListWidgetItem, QSlider, QGroupBox, QGridLayout
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt


class ImageEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini Photoshop with OpenCV")
        self.original_image = None
        self.edited_image = None
        self.applied_filters = []  # Track applied filters and params
        self.current_path = None

        self.init_ui()

    def init_ui(self):
        # Layouts
        main_layout = QHBoxLayout()
        image_layout = QHBoxLayout()
        right_panel = QVBoxLayout()

        # Original and Edited Image Labels
        self.original_label = QLabel("Original Image")
        self.edited_label = QLabel("Edited Image")
        self.original_label.setFixedSize(300, 300)
        self.edited_label.setFixedSize(300, 300)

        # Filter Panel
        self.filter_list = QListWidget()
        self.filter_list.addItems(["Grayscale", "Blur", "Canny"])
        self.filter_list.itemClicked.connect(self.apply_filter)

        # Sliders for dynamic filters
        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setMinimum(1)
        self.blur_slider.setMaximum(31)
        self.blur_slider.setValue(5)
        self.blur_slider.setSingleStep(2)
        self.blur_slider.setTickInterval(2)
        self.blur_slider.valueChanged.connect(self.update_blur)
        self.blur_slider.setVisible(False)

        self.canny_slider = QSlider(Qt.Horizontal)
        self.canny_slider.setMinimum(50)
        self.canny_slider.setMaximum(200)
        self.canny_slider.setValue(100)
        self.canny_slider.setTickInterval(10)
        self.canny_slider.valueChanged.connect(self.update_canny)
        self.canny_slider.setVisible(False)

        slider_group = QGroupBox("Filter Settings")
        slider_layout = QVBoxLayout()
        slider_layout.addWidget(self.blur_slider)
        slider_layout.addWidget(self.canny_slider)
        slider_group.setLayout(slider_layout)

        # Buttons
        load_button = QPushButton("Load Image")
        load_button.clicked.connect(self.load_image)

        export_button = QPushButton("Export Filter Script")
        export_button.clicked.connect(self.export_script)

        # Assemble Layout
        image_layout.addWidget(self.original_label)
        image_layout.addWidget(self.edited_label)

        right_panel.addWidget(QLabel("Filter Panel"))
        right_panel.addWidget(self.filter_list)
        right_panel.addWidget(slider_group)
        right_panel.addWidget(load_button)
        right_panel.addWidget(export_button)

        main_layout.addLayout(image_layout)
        main_layout.addLayout(right_panel)

        self.setLayout(main_layout)

    def load_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if file_name:
            self.original_image = cv2.imread(file_name)
            self.current_path = file_name
            self.edited_image = self.original_image.copy()
            self.applied_filters = []
            self.display_images()

    def display_images(self):
        def convert_cv_to_pixmap(cv_img):
            rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            return QPixmap.fromImage(QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).scaled(300, 300, Qt.KeepAspectRatio))

        if self.original_image is not None:
            self.original_label.setPixmap(convert_cv_to_pixmap(self.original_image))
            self.edited_label.setPixmap(convert_cv_to_pixmap(self.edited_image))

    def apply_filter(self, item: QListWidgetItem):
        if self.original_image is None:
            return

        self.edited_image = self.original_image.copy()
        selected_filter = item.text()

        if selected_filter == "Grayscale":
            self.edited_image = cv2.cvtColor(self.edited_image, cv2.COLOR_BGR2GRAY)
            self.edited_image = cv2.cvtColor(self.edited_image, cv2.COLOR_GRAY2BGR)
            self.applied_filters.append(("grayscale", {}))
            self.blur_slider.setVisible(False)
            self.canny_slider.setVisible(False)

        elif selected_filter == "Blur":
            k = self.blur_slider.value()
            if k % 2 == 0:
                k += 1
            self.edited_image = cv2.GaussianBlur(self.edited_image, (k, k), 0)
            self.applied_filters.append(("blur", {"kernel": k}))
            self.blur_slider.setVisible(True)
            self.canny_slider.setVisible(False)

        elif selected_filter == "Canny":
            t = self.canny_slider.value()
            gray = cv2.cvtColor(self.edited_image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, t, t * 2)
            self.edited_image = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            self.applied_filters.append(("canny", {"threshold": t}))
            self.blur_slider.setVisible(False)
            self.canny_slider.setVisible(True)

        self.display_images()

    def update_blur(self):
        self.apply_filter(QListWidgetItem("Blur"))

    def update_canny(self):
        self.apply_filter(QListWidgetItem("Canny"))

    def export_script(self):
        lines = [
            "import cv2",
            f"img = cv2.imread('{self.current_path or 'your_image.jpg'}')"
        ]
        for filt, params in self.applied_filters:
            if filt == "grayscale":
                lines.append("img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)")
            elif filt == "blur":
                k = params.get("kernel", 5)
                lines.append(f"img = cv2.GaussianBlur(img, ({k}, {k}), 0)")
            elif filt == "canny":
                t = params.get("threshold", 100)
                lines.append(f"img = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), {t}, {t * 2})")

        lines.append("cv2.imwrite('edited_output.jpg', img)")
        with open("exported_script.py", "w") as f:
            f.write("\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = ImageEditor()
    editor.show()
    sys.exit(app.exec_())
