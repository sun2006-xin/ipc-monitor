from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QFileDialog, QComboBox, QLabel, QMessageBox,
    QWidget  # 添加缺失的导入
)
from PyQt5.QtCore import Qt
from core.config_manager import ConfigManager
from core.logger import Logger

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统设置")
        self.setGeometry(300, 200, 600, 400)
        self.config = ConfigManager()
        self.logger = Logger()

        layout = QVBoxLayout()
        self.setLayout(layout)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 检测设置
        detect_tab = QWidget()
        detect_layout = QFormLayout()
        detect_tab.setLayout(detect_layout)

        self.face_interval_spin = QSpinBox()
        self.face_interval_spin.setRange(1, 30)
        self.face_interval_spin.setValue(self.config.get('detection.face_interval', 5))
        detect_layout.addRow("人脸检测帧间隔:", self.face_interval_spin)

        self.motion_interval_spin = QSpinBox()
        self.motion_interval_spin.setRange(1, 30)
        self.motion_interval_spin.setValue(self.config.get('detection.motion_interval', 5))
        detect_layout.addRow("运动检测帧间隔:", self.motion_interval_spin)

        self.face_threshold_spin = QDoubleSpinBox()
        self.face_threshold_spin.setRange(0.1, 0.9)
        self.face_threshold_spin.setSingleStep(0.05)
        self.face_threshold_spin.setValue(self.config.get('detection.face_threshold', 0.25))
        detect_layout.addRow("人脸置信度阈值:", self.face_threshold_spin)

        self.motion_area_spin = QSpinBox()
        self.motion_area_spin.setRange(500, 5000)
        self.motion_area_spin.setSingleStep(100)
        self.motion_area_spin.setValue(self.config.get('detection.motion_min_area', 1500))
        detect_layout.addRow("运动最小面积:", self.motion_area_spin)

        tabs.addTab(detect_tab, "检测")

        # 报警设置
        alarm_tab = QWidget()
        alarm_layout = QFormLayout()
        alarm_tab.setLayout(alarm_layout)

        self.sound_enabled = QCheckBox()
        self.sound_enabled.setChecked(self.config.get('alarm.sound_enabled', True))
        alarm_layout.addRow("启用报警音:", self.sound_enabled)

        self.sound_file_edit = QLabel(self.config.get('alarm.sound_file', 'resources/sounds/alarm.wav'))
        sound_btn = QPushButton("选择声音文件")
        sound_btn.clicked.connect(self.select_sound_file)
        sound_layout = QHBoxLayout()
        sound_layout.addWidget(self.sound_file_edit)
        sound_layout.addWidget(sound_btn)
        alarm_layout.addRow("报警声音文件:", sound_layout)

        tabs.addTab(alarm_tab, "报警")

        # 语言
        lang_tab = QWidget()
        lang_layout = QFormLayout()
        lang_tab.setLayout(lang_layout)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["zh", "en"])
        self.lang_combo.setCurrentText(self.config.get('language', 'zh'))
        lang_layout.addRow("语言:", self.lang_combo)

        tabs.addTab(lang_tab, "语言")

        # 日志
        log_tab = QWidget()
        log_layout = QFormLayout()
        log_tab.setLayout(log_layout)

        self.export_log_btn = QPushButton("导出日志 (TXT)")
        self.export_log_btn.clicked.connect(lambda: self.export_log("txt"))
        self.export_log_json_btn = QPushButton("导出日志 (JSON)")
        self.export_log_json_btn.clicked.connect(lambda: self.export_log("json"))
        log_layout.addRow(self.export_log_btn, self.export_log_json_btn)

        tabs.addTab(log_tab, "日志")

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def select_sound_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "选择报警声音文件", "", "WAV Files (*.wav)")
        if filepath:
            self.sound_file_edit.setText(filepath)

    def export_log(self, format):
        filepath, _ = QFileDialog.getSaveFileName(self, "导出日志", f"ipc_log.{format}", f"{format.upper()} Files (*.{format})")
        if filepath:
            from core.logger import Logger
            Logger().export(filepath, format)
            QMessageBox.information(self, "成功", f"日志已导出到 {filepath}")

    def save_settings(self):
        self.config.set('detection.face_interval', self.face_interval_spin.value())
        self.config.set('detection.motion_interval', self.motion_interval_spin.value())
        self.config.set('detection.face_threshold', self.face_threshold_spin.value())
        self.config.set('detection.motion_min_area', self.motion_area_spin.value())
        self.config.set('alarm.sound_enabled', self.sound_enabled.isChecked())
        self.config.set('alarm.sound_file', self.sound_file_edit.text())
        self.config.set('language', self.lang_combo.currentText())
        self.config.save()
        QMessageBox.information(self, "成功", "设置已保存")
        self.close()