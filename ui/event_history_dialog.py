from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt
import os

class EventHistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("事件历史记录")
        self.setGeometry(200, 200, 800, 400)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "通道", "类型", "文件路径"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("清空记录")
        clear_btn.clicked.connect(self.clear_history)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.events = []

    def add_event(self, event_type, channel, filepath):
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.events.append((timestamp, channel, event_type, filepath))
        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(len(self.events))
        for row, (ts, channel, etype, path) in enumerate(self.events):
            self.table.setItem(row, 0, QTableWidgetItem(ts))
            self.table.setItem(row, 1, QTableWidgetItem(channel))
            self.table.setItem(row, 2, QTableWidgetItem(etype))
            self.table.setItem(row, 3, QTableWidgetItem(path))

    def clear_history(self):
        self.events.clear()
        self.refresh_table()

    def on_item_double_clicked(self, item):
        row = item.row()
        filepath = self.events[row][3]
        if os.path.exists(filepath):
            from PyQt5.QtGui import QDesktopServices
            from PyQt5.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "文件不存在", f"文件 {filepath} 不存在")