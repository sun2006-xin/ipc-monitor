from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout, QComboBox, QLabel, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
import os
import csv
from datetime import datetime

class EventHistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("事件历史记录")
        self.setGeometry(200, 200, 800, 400)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.setLayout(layout)

        # ================================================================
        # A5：事件过滤栏（按类型 + 按通道） + 导出 CSV 按钮
        #   - 过滤器：顶部一行，下拉选类型/通道，切换立刻刷新表格（不重建数据）
        #   - 导出 CSV：按当前过滤条件导出当前可见行到 UTF-8-BOM 的 csv（Excel 双击不乱码）
        # ================================================================
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        filter_row.addWidget(QLabel("类型:"))
        self.filter_type = QComboBox()
        self.filter_type.addItem("全部", "")
        # 扩展：新增 B4 上下线(online/offline) + C2 聚集(crowd) + C3 离岗(absence) 共 4 个新事件类型（原有 5 个保持不变）
        for _t in ["face", "motion", "stranger", "snapshot", "record", "online", "offline", "crowd", "absence"]:
            self.filter_type.addItem(_t, _t)
        self.filter_type.currentIndexChanged.connect(self.refresh_table)
        filter_row.addWidget(self.filter_type)

        filter_row.addWidget(QLabel("通道:"))
        self.filter_channel = QComboBox()
        self.filter_channel.addItem("全部", "")
        self.filter_channel.setMinimumWidth(140)
        self.filter_channel.currentIndexChanged.connect(self.refresh_table)
        filter_row.addWidget(self.filter_channel)

        filter_row.addStretch()

        self.export_btn = QPushButton("⬇ 导出CSV")
        self.export_btn.clicked.connect(self.export_csv)
        filter_row.addWidget(self.export_btn)

        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "通道", "类型", "文件路径"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.table, stretch=1)

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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.events.append((timestamp, channel, event_type, filepath))
        # A5：通道下拉自动收集已出现过的通道名，保持顺序去重（新通道追加到末尾）
        if hasattr(self, 'filter_channel'):
            existing = {self.filter_channel.itemData(i) for i in range(self.filter_channel.count())}
            if channel not in existing:
                self.filter_channel.addItem(channel, channel)
        self.refresh_table()

    def _filtered_events(self):
        """A5：当前过滤条件下的可见行（全部事件不变，只在 refresh/export 时拿过滤子集）"""
        ftype = self.filter_type.currentData() if hasattr(self, 'filter_type') else ""
        fch = self.filter_channel.currentData() if hasattr(self, 'filter_channel') else ""
        return [e for e in self.events
                if (not ftype or e[2] == ftype) and (not fch or e[1] == fch)]

    def refresh_table(self):
        rows = self._filtered_events()
        self.table.setRowCount(len(rows))
        for row, (ts, channel, etype, path) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(ts))
            self.table.setItem(row, 1, QTableWidgetItem(channel))
            self.table.setItem(row, 2, QTableWidgetItem(etype))
            self.table.setItem(row, 3, QTableWidgetItem(path))

    def clear_history(self):
        self.events.clear()
        # A5：清空后通道下拉回收（"全部" + 之前加过的通道都没用了），留空不重复展示历史已删通道
        if hasattr(self, 'filter_channel'):
            self.filter_channel.blockSignals(True)
            self.filter_channel.clear()
            self.filter_channel.addItem("全部", "")
            self.filter_channel.blockSignals(False)
        self.refresh_table()

    def export_csv(self):
        """A5：把当前过滤后的事件表导出 CSV（UTF-8-SIG，Excel 双击中文不乱码）"""
        rows = self._filtered_events()
        default = f"events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "导出事件记录为CSV", default, "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            ftype = self.filter_type.currentData() if hasattr(self, 'filter_type') else ""
            fch = self.filter_channel.currentData() if hasattr(self, 'filter_channel') else ""
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f)
                w.writerow(["时间", "通道", "类型", "文件路径"])
                w.writerow([
                    f"筛选条件: 类型={ftype or '全部'}, 通道={fch or '全部'}; 共{len(rows)}条（全部事件{len(self.events)}条）"
                ])
                w.writerow([])
                for ts, channel, etype, filepath in rows:
                    w.writerow([ts, channel, etype, filepath])
            QMessageBox.information(self, "导出成功",
                                    f"已按当前过滤条件导出 {len(rows)} 条记录\n(全部共 {len(self.events)} 条)\n路径: {path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"写入 CSV 失败: {e}")

    def on_item_double_clicked(self, item):
        row = item.row()
        # A5：当前表格是过滤后的行视图，用 _filtered_events() 拿路径，避免"表格显示A但打开B"的错位
        rows = self._filtered_events()
        if row < 0 or row >= len(rows):
            return
        filepath = rows[row][3]
        if os.path.exists(filepath):
            from PyQt5.QtGui import QDesktopServices
            from PyQt5.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
        else:
            QMessageBox.warning(self, "文件不存在", f"文件 {filepath} 不存在")