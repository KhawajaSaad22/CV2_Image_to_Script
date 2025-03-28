import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QListWidget, QListWidgetItem
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt


class ImageEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini Photoshop with OpenCV")
        self.original_image = None
        self.edited_image = None
        self.applied_filters = []  # Track applied filters

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
        right_panel.addWidget(load_button)
        right_panel.addWidget(export_button)

        main_layout.addLayout(image_layout)
        main_layout.addLayout(right_panel)

        self.setLayout(main_layout)

    def load_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if file_name:
            self.original_image = cv2.imread(file_name)
            self.edited_image = self.original_image.copy()
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
        if self.edited_image is None:
            return
        filter_name = item.text()
        self.applied_filters.append(filter_name)

        if filter_name == "Grayscale":
            self.edited_image = cv2.cvtColor(self.edited_image, cv2.COLOR_BGR2GRAY)
            self.edited_image = cv2.cvtColor(self.edited_image, cv2.COLOR_GRAY2BGR)  # Convert back for display
        elif filter_name == "Blur":
            self.edited_image = cv2.GaussianBlur(self.edited_image, (5, 5), 0)
        elif filter_name == "Canny":
            gray = cv2.cvtColor(self.edited_image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            self.edited_image = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        self.display_images()

    def export_script(self):
        script_lines = [
            "import cv2\n",
            "img = cv2.imread('your_image.jpg')\n"
        ]
        for filt in self.applied_filters:
            if filt == "Grayscale":
                script_lines.append("img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)\n")
            elif filt == "Blur":
                script_lines.append("img = cv2.GaussianBlur(img, (5, 5), 0)\n")
            elif filt == "Canny":
                script_lines.append("img = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 100, 200)\n")

        script_lines.append("cv2.imwrite('edited_image.jpg', img)\n")

        with open("exported_script.py", "w") as f:
            f.writelines(script_lines)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageEditor()
    window.show()
    sys.exit(app.exec_())
