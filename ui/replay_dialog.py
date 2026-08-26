import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QPixmap, QDesktopServices

class ReplayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("录像回放 - 浏览截图与录像")
        self.setGeometry(150, 100, 1000, 600)

        layout = QVBoxLayout()
        self.setLayout(layout)

        splitter = QSplitter(Qt.Horizontal)
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_item_clicked)
        splitter.addWidget(self.file_list)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #0d1117; border: 1px solid #2d3748;")
        self.preview_label.setMinimumWidth(400)
        splitter.addWidget(self.preview_label)

        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.scan_files)
        open_btn = QPushButton("打开文件")
        open_btn.clicked.connect(self.open_selected)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(open_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.scan_files()

    def scan_files(self):
        self.file_list.clear()
        self.preview_label.clear()
        self.preview_label.setText("选择文件预览")

        base_dirs = [
            ("data/snapshots", "截图"),
            ("data/records", "录像"),
            ("data/motions", "运动触发"),
            ("data/faces", "人脸触发")
        ]

        for subdir, label in base_dirs:
            if os.path.exists(subdir):
                for fname in os.listdir(subdir):
                    if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.avi', '.mkv')):
                        full_path = os.path.join(subdir, fname)
                        item = QListWidgetItem(f"[{label}] {fname}")
                        item.setData(Qt.UserRole, full_path)
                        self.file_list.addItem(item)

        if self.file_list.count() == 0:
            self.file_list.addItem("没有找到任何文件")

    def on_item_clicked(self, item):
        filepath = item.data(Qt.UserRole)
        if not filepath or not os.path.exists(filepath):
            return
        if filepath.lower().endswith(('.jpg', '.jpeg', '.png')):
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.preview_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled)
            else:
                self.preview_label.setText("无法加载图片")
        else:
            self.preview_label.setText(f"视频文件:\n{os.path.basename(filepath)}\n点击下方「打开文件」播放")

    def open_selected(self):
        current = self.file_list.currentItem()
        if not current:
            return
        filepath = current.data(Qt.UserRole)
        if filepath and os.path.exists(filepath):
            QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
        else:
            QMessageBox.warning(self, "错误", "文件不存在")