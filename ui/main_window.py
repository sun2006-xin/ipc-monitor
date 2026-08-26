import sys
import os
from functools import partial
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QFrame, QComboBox, QMenu, QAction,
    QMessageBox, QDialog, QApplication, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap

from core.config_manager import ConfigManager
from core.logger import Logger
from core.recovery import RecoveryManager
from core.face_engine import FaceEngine
from core.motion_engine import MotionEngine

from ui.video_widget import VideoWidget
from ui.grid_layout import GridLayoutWidget
from ui.device_dialog import DeviceDialog
from ui.fullscreen_dialog import FullscreenDialog
from ui.event_history_dialog import EventHistoryDialog
from ui.replay_dialog import ReplayDialog
from ui.settings_dialog import SettingsDialog
from ui.i18n import I18nManager
from ui.face_manager_dialog import FaceManagerDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPC 智能监控系统")
        self.setGeometry(100, 50, 1280, 780)

        # 窗口销毁保护：防止 QTimer.singleShot 等在析构后仍回调
        self._destroyed = False

        self.config = ConfigManager()
        self.logger = Logger()
        self.recovery = RecoveryManager()
        try:
            self.recovery.auto_repair(lambda d: True)
        except Exception as e:
            self.logger.error(f"RecoveryManager 自动修复异常: {e}")

        self.face_engine = FaceEngine(weights_path="best.pt", conf_thres=self.config.get('detection.face_threshold', 0.25), device="cpu")
        self.motion_engine = MotionEngine(min_area=self.config.get('detection.motion_min_area', 1500))

        self.active_ids = []
        self.recording = False
        self.event_history_dialog = None
        self.replay_dialog = None

        self.init_ui()
        self.load_devices()
        self.auto_connect()

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.on_refresh)
        self.refresh_timer.start(15000)

        self.i18n = I18nManager()
        try:
            self.i18n.load_language(self.config.get('language', 'zh'), QApplication.instance())
        except Exception as e:
            self.logger.error(f"语言加载异常: {e}")

    def init_ui(self):
        central = QWidget()
        # 让 central widget 背景跟随主题深色，不留白边（外层浅色大空块来自 central 默认浅灰）
        central.setStyleSheet("background-color: #0f151d;")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout()
        # UI 紧凑化：外层布局默认 margin ~11 / spacing ~6 会叠加出"大边框感"，压缩到 4/3
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(3)
        central.setLayout(main_layout)

        # 左侧设备列表
        left = QWidget()
        left.setFixedWidth(260)   # 280 -> 260：多挤 20 px 给视频区
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(4)   # 标题 / 列表 / 按钮 / 统计 四行之间的垂直缝从默认 6 -> 4
        left.setLayout(left_layout)

        title = QLabel("📹 设备列表")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        left_layout.addWidget(title)

        self.device_list = QListWidget()
        self.device_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.device_list.customContextMenuRequested.connect(self.show_context_menu)
        self.device_list.itemClicked.connect(self.on_device_clicked)
        # 设备列表项的垂直间距：把列表自己的上下内边距也压一下，列表项本身再拉不出来大块空
        self.device_list.setStyleSheet(
            "QListWidget { background-color: #111823; border-radius: 6px; padding: 2px; color: #e2e8f0; }"
            "QListWidget::item { border-radius: 4px; margin: 1px 0; }"
            "QListWidget::item:selected { background-color: #1f6feb; }"
        )
        left_layout.addWidget(self.device_list)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        self.btn_add = QPushButton("＋ 添加")
        self.btn_add.clicked.connect(self.add_device)
        self.btn_refresh = QPushButton("⟳ 刷新")
        self.btn_refresh.clicked.connect(self.on_refresh)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_refresh)
        left_layout.addLayout(btn_layout)

        self.stats_label = QLabel("设备总数: 0 | 在线: 0")
        self.stats_label.setStyleSheet("color: #a0aec0;")
        left_layout.addWidget(self.stats_label)

        main_layout.addWidget(left)

        # 右侧视频区域
        right = QWidget()
        right_layout = QVBoxLayout()
        # 右区本身也是外层容器之一，默认 11+11 的 margin 叠起来会让视频区"四边大空隙"——截图右边白大边、底部大空都来自这里
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(3)   # toolbar / grid / status 三段垂直间距从 ~6 -> 3
        right.setLayout(right_layout)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)       # 工具按钮间的水平距离从默认 6+ 收紧到明确 6
        layout_label = QLabel("布局:")
        layout_label.setStyleSheet("color: #a0aec0;")
        toolbar.addWidget(layout_label)

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["1x1", "2x2", "3x3", "4x4"])
        self.layout_combo.setFixedWidth(80)
        self.layout_combo.currentTextChanged.connect(self.on_layout_changed)
        toolbar.addWidget(self.layout_combo)

        toolbar.addStretch()

        self.btn_snapshot = QPushButton("📷 截图")
        self.btn_snapshot.clicked.connect(self.on_snapshot)
        toolbar.addWidget(self.btn_snapshot)

        self.btn_record = QPushButton("● 录像")
        self.btn_record.clicked.connect(self.toggle_record)
        toolbar.addWidget(self.btn_record)

        self.btn_event = QPushButton("📋 事件日志")
        self.btn_event.clicked.connect(self.show_event_history)
        toolbar.addWidget(self.btn_event)

        self.btn_replay = QPushButton("📁 回放")
        self.btn_replay.clicked.connect(self.show_replay)
        toolbar.addWidget(self.btn_replay)

        self.btn_face_mgr = QPushButton("👤 人脸管理")
        self.btn_face_mgr.clicked.connect(self.show_face_manager)
        toolbar.addWidget(self.btn_face_mgr)

        self.motion_alarm_check = QCheckBox("运动报警")
        self.motion_alarm_check.setChecked(False)
        self.motion_alarm_check.stateChanged.connect(self.on_motion_alarm_toggle)
        toolbar.addWidget(self.motion_alarm_check)

        right_layout.addLayout(toolbar)

        self.grid_widget = GridLayoutWidget()
        self.grid_widget.setStyleSheet("background-color: #0d1117; border-radius: 6px;")
        right_layout.addWidget(self.grid_widget, stretch=1)  # stretch=1 把所有剩余高度都给视频网格（之前没给→底部一大块浅灰空白）

        self.status_bar = QLabel("就绪")
        self.status_bar.setMaximumHeight(28)
        self.status_bar.setStyleSheet("padding: 2px 12px; background-color: #0d1117; border-radius: 4px; color: #a0aec0; font-size: 12px;")
        right_layout.addWidget(self.status_bar)

        main_layout.addWidget(right)

        rows = self.config.get('layout.rows', 2)
        cols = self.config.get('layout.cols', 2)
        self.grid_widget.set_grid(rows, cols)
        self.active_ids = [None] * self.grid_widget.count()

        menubar = self.menuBar()
        settings_menu = menubar.addMenu("设置")
        lang_action = QAction("语言切换", self)
        lang_action.triggered.connect(self.switch_language)
        settings_menu.addAction(lang_action)
        settings_action = QAction("系统设置", self)
        settings_action.triggered.connect(self.show_settings)
        settings_menu.addAction(settings_action)

    def load_devices(self):
        self.device_list.clear()
        devices = self.config.get_devices()
        for d in devices:
            item = QListWidgetItem()
            widget = QWidget()
            layout = QVBoxLayout()
            # UI 紧凑化：(8,6) -> (5,4)；原代码每一项上下 12px 留白叠加成列表项大空隙（截图里"camera 在线"上面一大条黑空、下面又一大条就是它）
            layout.setContentsMargins(5, 4, 5, 4)
            layout.setSpacing(1)   # 名/状态/IP 三行之间垂直距离
            name = QLabel(d.get("name", "未知"))
            name.setStyleSheet("font-weight: bold; color: #e0e0e0;")
            status = QLabel("● 在线" if d.get("online", False) else "○ 离线")
            status.setStyleSheet(f"color: {'#48bb78' if d.get('online', False) else '#fc8181'}; font-size: 11px;")
            ip = QLabel(d.get("ip", ""))
            ip.setStyleSheet("color: #718096; font-size: 10px;")
            layout.addWidget(name)
            layout.addWidget(status)
            layout.addWidget(ip)
            widget.setLayout(layout)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.UserRole, d["id"])
            self.device_list.addItem(item)
            self.device_list.setItemWidget(item, widget)

        online = sum(1 for d in devices if d.get("online", False))
        self.stats_label.setText(f"设备总数: {len(devices)} | 在线: {online}")

    def auto_connect(self):
        devices = self.config.get_devices()
        online = [d for d in devices if d.get("online", False)]
        self.active_ids = [None] * self.grid_widget.count()
        for i, d in enumerate(online):
            if i < self.grid_widget.count():
                ch = self.grid_widget.channels[i]
                ch.set_device_info(d)
                ch.set_face_engine(self.face_engine)
                ch.set_motion_engine(self.motion_engine)
                ch.set_motion_alarm(self.motion_alarm_check.isChecked())
                # ✅ 防止重复连接信号：先断开再连接，保证唯一连接
                try:
                    ch.event_triggered.disconnect(self.on_event_triggered)
                except (TypeError, RuntimeError):
                    pass  # 未连接过则忽略
                ch.event_triggered.connect(self.on_event_triggered)
                ch.start(self.config.get_rtsp_url(d))
                self.active_ids[i] = d["id"]

    def connect_device(self, device):
        rtsp = self.config.get_rtsp_url(device)
        for i, ch in enumerate(self.grid_widget.channels):
            if self.active_ids[i] is None:
                ch.set_device_info(device)
                ch.set_face_engine(self.face_engine)
                ch.set_motion_engine(self.motion_engine)
                ch.set_motion_alarm(self.motion_alarm_check.isChecked())
                # ✅ 防止重复连接信号
                try:
                    ch.event_triggered.disconnect(self.on_event_triggered)
                except (TypeError, RuntimeError):
                    pass
                ch.event_triggered.connect(self.on_event_triggered)
                ch.start(rtsp)
                self.active_ids[i] = device["id"]
                self.status_bar.setText(f"✅ 已连接: {device.get('name')}")
                return True
        self.status_bar.setText("⚠️ 所有通道已占用")
        return False

    def on_device_clicked(self, item):
        idx = self.device_list.row(item)
        devices = self.config.get_devices()
        if idx < len(devices):
            d = devices[idx]
            if d.get("online"):
                self.connect_device(d)

    def show_context_menu(self, pos):
        item = self.device_list.itemAt(pos)
        if not item:
            return
        idx = self.device_list.row(item)
        devices = self.config.get_devices()
        if idx >= len(devices):
            return
        device = devices[idx]
        menu = QMenu()
        edit_action = QAction("编辑", self)
        edit_action.triggered.connect(lambda: self.edit_device(device["id"]))
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self.delete_device(device["id"]))
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec_(self.device_list.mapToGlobal(pos))

    def add_device(self):
        dialog = DeviceDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_device()
            self.config.add_device(data)
            self.load_devices()
            for d in self.config.get_devices():
                if d["id"] == data["id"] and d.get("online"):
                    self.connect_device(d)
                    break
            self.logger.info(f"添加设备: {data.get('name')}")

    def edit_device(self, device_id):
        devices = self.config.get_devices()
        device = next((d for d in devices if d["id"] == device_id), None)
        if not device:
            return
        dialog = DeviceDialog(device, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_device()
            self.config.update_device(device_id, data)
            self.load_devices()
            for i, ch in enumerate(self.grid_widget.channels):
                if self.active_ids[i] == device_id:
                    # ✅ 先断开信号，再清理（避免 clear 内部 emit 到已被逻辑移除的槽）
                    try:
                        ch.event_triggered.disconnect(self.on_event_triggered)
                    except (TypeError, RuntimeError):
                        pass
                    ch.clear()
                    self.active_ids[i] = None
            for d in self.config.get_devices():
                if d["id"] == device_id and d.get("online"):
                    self.connect_device(d)
                    break
            self.logger.info(f"编辑设备: {data.get('name')}")

    def delete_device(self, device_id):
        reply = QMessageBox.question(self, "确认删除", "确定删除此设备吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for i, ch in enumerate(self.grid_widget.channels):
                if self.active_ids[i] == device_id:
                    # ✅ 断开信号 + 清理通道
                    try:
                        ch.event_triggered.disconnect(self.on_event_triggered)
                    except (TypeError, RuntimeError):
                        pass
                    ch.clear()
                    self.active_ids[i] = None
            self.config.remove_device(device_id)
            self.load_devices()
            self.logger.info(f"删除设备: {device_id}")

    def on_refresh(self):
        try:
            self.load_devices()
        except Exception as e:
            self.logger.error(f"刷新设备列表异常: {e}")
        for i, ch in enumerate(self.grid_widget.channels):
            if not self.active_ids[i]:
                continue
            # ✅ VideoWidget 使用 QTimer（非 QThread），用 timer 是否激活 + cap 是否有效来判断是否"在运行"
            #    原代码 ch.thread 不存在，必然抛 AttributeError → 闪退
            try:
                timer_running = ch.timer is not None and ch.timer.isActive()
                cap_valid = ch.cap is not None and ch.cap.isOpened()
                need_restart = (not timer_running) or (not cap_valid)
            except Exception as e:
                self.logger.error(f"检查通道{i}状态异常: {e}")
                need_restart = True
            if need_restart:
                devices = self.config.get_devices()
                for d in devices:
                    if d["id"] == self.active_ids[i] and d.get("online"):
                        try:
                            ch.start(self.config.get_rtsp_url(d))
                        except Exception as e:
                            self.logger.error(f"通道{i}重连失败: {e}")
                        break

    def on_layout_changed(self, layout_text):
        rows, cols = map(int, layout_text.split('x'))
        # ✅ 布局切换前先断开所有通道信号并清理，避免 deleteLater 后仍有回调
        for i, ch in enumerate(self.grid_widget.channels):
            try:
                ch.event_triggered.disconnect(self.on_event_triggered)
            except (TypeError, RuntimeError):
                pass
            try:
                ch.clear()
            except Exception as e:
                self.logger.error(f"清理通道{i}异常: {e}")
        self.active_ids = [None] * self.grid_widget.count()

        self.grid_widget.set_grid(rows, cols)
        self.config.set('layout.rows', rows)
        self.config.set('layout.cols', cols)
        self.active_ids = [None] * self.grid_widget.count()
        self.auto_connect()

    def on_snapshot(self):
        count = 0
        for ch in self.grid_widget.channels:
            if ch.current_pixmap:
                if ch.snapshot():
                    count += 1
        self.status_bar.setText(f"📷 截图已保存 ({count} 张)")

    def toggle_record(self):
        if not self.recording:
            count = 0
            for ch in self.grid_widget.channels:
                if ch.current_pixmap and ch.start_record():
                    count += 1
            if count > 0:
                self.recording = True
                self.btn_record.setText("⏹ 停止录像")
                self.status_bar.setText(f"🎥 录像中 ({count} 通道)")
            else:
                QMessageBox.information(self, "提示", "没有视频流，无法录像")
        else:
            for ch in self.grid_widget.channels:
                ch.stop_record()
            self.recording = False
            self.btn_record.setText("● 录像")
            self.status_bar.setText("⏹ 录像已停止")

    def on_event_triggered(self, event_type, channel, filepath):
        # ✅ 销毁保护：如果窗口已在关闭流程中，直接忽略
        if getattr(self, '_destroyed', False):
            return
        if self.event_history_dialog is None:
            self.event_history_dialog = EventHistoryDialog(self)
        try:
            self.event_history_dialog.add_event(event_type, channel, filepath)
        except Exception as e:
            self.logger.error(f"写入事件历史异常: {e}")

        try:
            self.status_bar.setText(f"🚨 [{channel}] {event_type} 触发")
            self.status_bar.setStyleSheet("padding: 2px 12px; background-color: #c0392b; border-radius: 4px; color: white; font-weight: bold; font-size: 12px;")
        except Exception:
            pass

        # ✅ 防止窗口销毁后 QTimer.singleShot 仍回调访问已析构对象（野指针 → 闪退）
        def _restore_style():
            try:
                if not getattr(self, '_destroyed', False) and not getattr(self.status_bar, 'deleted', False):
                    self.status_bar.setStyleSheet(
                        "padding: 2px 12px; background-color: #0d1117; border-radius: 4px; color: #a0aec0; font-size: 12px;"
                    )
            except Exception:
                pass
        QTimer.singleShot(3000, _restore_style)

        try:
            QApplication.beep()
        except Exception:
            pass
        self.logger.info(f"事件触发: {channel} - {event_type}")

    def on_motion_alarm_toggle(self):
        enabled = self.motion_alarm_check.isChecked()
        for ch in self.grid_widget.channels:
            ch.set_motion_alarm(enabled)
        self.status_bar.setText(f"运动报警 {'开启' if enabled else '关闭'}")

    def show_event_history(self):
        if self.event_history_dialog is None:
            self.event_history_dialog = EventHistoryDialog(self)
        self.event_history_dialog.show()
        self.event_history_dialog.raise_()

    def show_replay(self):
        if self.replay_dialog is None:
            self.replay_dialog = ReplayDialog(self)
        self.replay_dialog.show()
        self.replay_dialog.raise_()

    def show_face_manager(self):
        video_widget = None
        for ch in self.grid_widget.channels:
            if ch.current_frame is not None:
                video_widget = ch
                break
        if not video_widget:
            QMessageBox.information(self, "提示", "请先连接摄像头")
            return
        if self.face_engine.recognizer is None:
            QMessageBox.warning(self, "错误", "人脸识别模块未加载")
            return
        dialog = FaceManagerDialog(self.face_engine.recognizer, video_widget, self)
        dialog.exec_()

    def show_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec_()

    def switch_language(self):
        current = self.config.get('language', 'zh')
        new_lang = 'en' if current == 'zh' else 'zh'
        self.config.set('language', new_lang)
        self.i18n.load_language(new_lang, QApplication.instance())
        self.status_bar.setText(f"语言切换到 {new_lang}")

    def closeEvent(self, event):
        # ✅ 标记销毁状态，防止后续回调访问已析构对象
        self._destroyed = True
        # 1) 先停止全局刷新定时器，防止销毁过程中继续触发 on_refresh
        try:
            if getattr(self, 'refresh_timer', None):
                self.refresh_timer.stop()
        except Exception:
            pass
        # 2) 先断开所有通道的事件信号，再逐一清理
        for i, ch in enumerate(getattr(self.grid_widget, 'channels', [])):
            try:
                ch.event_triggered.disconnect(self.on_event_triggered)
            except (TypeError, RuntimeError):
                pass
            try:
                ch.clear()
            except Exception as e:
                try:
                    self.logger.error(f"关闭时清理通道{i}异常: {e}")
                except Exception:
                    pass
        # 3) 对话框引用清理
        self.event_history_dialog = None
        self.replay_dialog = None
        # 4) 保存配置 + 日志
        try:
            self.config.save()
        except Exception as e:
            try:
                self.logger.error(f"保存配置异常: {e}")
            except Exception:
                pass
        try:
            self.logger.info("程序退出")
        except Exception:
            pass
        event.accept()