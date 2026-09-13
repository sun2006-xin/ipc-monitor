import sys
import os
import csv
import datetime as _dt
from datetime import datetime   # B4 上下线占位文件写 datetime.now()；与 import datetime as _dt 不冲突
from functools import partial
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QDialog, QAction, QMenu, QMessageBox, QCheckBox, QComboBox,
    QFileDialog, QApplication,
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
        self.face_recognizer = getattr(self.face_engine, 'recognizer', None)   # C1：统一从 face_engine 拿 recognizer，FaceEngine 兜底为 None
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
        # -------- 用户明确要求"白的好"：回退所有深色背景，改为干净白色（或跟随系统默认浅灰）--------
        # 不再用 #0f151d，整屏不会一片黑
        central.setStyleSheet("background-color: #f5f6f8;")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout()
        # 外层容器用"最小但不挤"的统一值：外边距 2 px、左右区水平缝 2 px
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        central.setLayout(main_layout)

        # 左侧设备列表
        left = QWidget()
        # 左栏给 250 px（既放得下"📹 设备列表"，也不挤压右边视频区）
        left.setFixedWidth(250)
        left_layout = QVBoxLayout()
        # 左栏内部：外边距 6 → 2；子控件之间垂直距离统一 2
        left_layout.setContentsMargins(2, 2, 2, 2)
        left_layout.setSpacing(2)
        left.setLayout(left_layout)

        title = QLabel("📹 设备列表")
        # 深色文字（因为背景现在是浅色！）
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f2937;")
        left_layout.addWidget(title)

        self.device_list = QListWidget()
        self.device_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.device_list.customContextMenuRequested.connect(self.show_context_menu)
        self.device_list.itemClicked.connect(self.on_device_clicked)
        # -------- QListWidget 整体改回浅色风格：白底灰边，文字黑色 --------
        # 列表项之间的上下缝隙压缩到 0，让"两个文字（camera + ●在线）"不占一大块空
        self.device_list.setStyleSheet(
            "QListWidget { background: #ffffff; border: 1px solid #d1d5db; border-radius: 4px;"
            " padding: 0px; color: #111827; outline: none; }"
            "QListWidget::item { border-radius: 3px; padding: 0px; margin: 0px 0px 1px 0px; }"
            "QListWidget::item:selected { background-color: #dbeafe; color: #111827; }"
        )
        left_layout.addWidget(self.device_list)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)
        self.btn_add = QPushButton("＋ 添加")
        self.btn_add.clicked.connect(self.add_device)
        self.btn_refresh = QPushButton("⟳ 刷新")
        self.btn_refresh.clicked.connect(self.on_refresh)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_refresh)
        left_layout.addLayout(btn_layout)

        self.stats_label = QLabel("设备总数: 0 | 在线: 0")
        # 背景白所以用深灰文字
        self.stats_label.setStyleSheet("color: #4b5563; font-size: 11px;")
        self.stats_label.setMaximumHeight(18)
        left_layout.addWidget(self.stats_label)

        main_layout.addWidget(left, stretch=0)  # stretch=0：左栏永远 250，宽度多出来的只给右视频区

        # 右侧视频区域
        right = QWidget()
        right_layout = QVBoxLayout()
        # -------- 右区"完美镶嵌不留空白难看"的核心：margin 归零，三段(toolbar/grid/status)间距 1 px --------
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(1)
        right.setLayout(right_layout)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(2, 2, 2, 2)
        toolbar.setSpacing(4)
        layout_label = QLabel("布局:")
        layout_label.setStyleSheet("color: #1f2937;")
        toolbar.addWidget(layout_label)

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["1x1", "1x2", "2x2", "2x3", "3x3", "4x4"])  # A1：补 1x2 / 2x3，覆盖 2 路/6 路手动场景
        self.layout_combo.setFixedWidth(72)
        self.layout_combo.currentTextChanged.connect(self.on_layout_changed)
        toolbar.addWidget(self.layout_combo)

        # ================================================================
        # A1：自动布局切换按钮（按在线通道数自动切布局）
        #   - 用户最新反馈"4×4切回单个摄像头会卡主不放大"→ 修好 stretch 残留 BUG 后自动切换更顺手
        #   - 自动切规则：1路→1x1 / 2路→1x2 / 3-4路→2x2 / 5-6路→2x3 / 7-9路→3x3 / 10-16路→4x4
        #   - 用户手动从 combo 切布局 → 自动关闭"自动"按钮（尊重手动优先级）
        # ================================================================
        self.auto_layout_toggle = QPushButton("自动")
        self.auto_layout_toggle.setCheckable(True)
        self.auto_layout_toggle.setChecked(False)
        self.auto_layout_toggle.setToolTip("按在线通道数自动切布局：1/2/3-4/5-6/7-9/10-16 路 → 1x1/1x2/2x2/2x3/3x3/4x4")
        self.auto_layout_toggle.clicked.connect(self._on_auto_layout_toggled)
        toolbar.addWidget(self.auto_layout_toggle)

        # ================================================================
        # A4：告警音 + 静音开关（不依赖 torch，用系统 winsound.MessageBeep，Windows 自带无需音频文件）
        #   - 任何事件（face/motion/后续 stranger）触发时响一声系统告警音
        #   - 按下"🔇 已静音"→ 后续告警静默，适合夜间静默运行
        # ================================================================
        self.alarm_mute_btn = QPushButton("🔔 告警音")
        self.alarm_mute_btn.setCheckable(True)
        self.alarm_mute_btn.setChecked(False)
        self.alarm_mute_btn.toggled.connect(self._on_alarm_mute_toggled)
        toolbar.addWidget(self.alarm_mute_btn)
        self._alarm_muted = False

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

        # ================================================================
        # B2：⏱ 定时录像（checkable 三态 25px 高度，紧贴 toolbar 不撑高）
        #   - 按下：所有在线通道自动开始按小时分片录像（跨小时自动切新文件）
        #   - 弹起：停止自动录像（用户手动 ●录像 不受影响）
        # ================================================================
        self.btn_schedule_rec = QPushButton("⏱ 定时录像")
        self.btn_schedule_rec.setCheckable(True)
        self.btn_schedule_rec.setChecked(False)
        self.btn_schedule_rec.setToolTip("自动为所有在线通道录像，并按小时自动分片（挂一整晚回放不找大文件）")
        self.btn_schedule_rec.toggled.connect(self._on_schedule_record_toggled)
        toolbar.addWidget(self.btn_schedule_rec)
        # ================================================================
        # B4：📡 设备上下线告警（checkable）
        #   - 按下：on_refresh 中对比 online 前后状态，翻转时 emit online/offline 事件 → A4 告警音 + A5 落历史
        #   - 弹起：只做静默上下线，不写事件不吵
        # ================================================================
        self.btn_device_alarm = QPushButton("📡 上下线告警")
        self.btn_device_alarm.setCheckable(True)
        self.btn_device_alarm.setChecked(True)   # 默认开启设备上下线提醒
        self.btn_device_alarm.setToolTip("设备从在线→离线或离线→在线时，自动写一条事件历史 + 响告警音")
        toolbar.addWidget(self.btn_device_alarm)
        # ================================================================
        # C4：🌙 夜间模式（checkable 三态）
        #   - 未选中（默认）：自动亮度 < 50 → CLAHE 均衡后检测
        #   - 选中：强制启用 CLAHE（白天也跑，演示"增强前后"对比）
        #   - 右键：强制关闭
        # ================================================================
        self.btn_night_mode = QPushButton("🌙 夜间")
        self.btn_night_mode.setCheckable(True)
        self.btn_night_mode.setChecked(False)
        self.btn_night_mode.setToolTip("夜间/暗光 CLAHE 对比度增强：未选中=自动(亮度<50启用)，选中=强制启用")
        self.btn_night_mode.toggled.connect(self._on_night_mode_toggled)
        toolbar.addWidget(self.btn_night_mode)

        # 把 toolbar 塞进一个 QFrame，这样按钮不会"悬空"，视觉上紧接上
        toolbar_box = QFrame()
        toolbar_box.setStyleSheet(
            "QFrame { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 4px; }"
        )
        toolbar_box.setMaximumHeight(40)
        toolbar_box.setLayout(toolbar)
        right_layout.addWidget(toolbar_box, stretch=0)

        self.grid_widget = GridLayoutWidget()
        # -------- 视频网格：白色背景 + 细边框，按钮→网格→状态栏 像"三块拼图"紧贴在一起 --------
        self.grid_widget.setStyleSheet(
            "GridLayoutWidget { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 4px; }"
        )
        right_layout.addWidget(self.grid_widget, stretch=1)  # stretch=1：视频网格拿所有多余高度（彻底消除底部大空）

        # 底部状态栏：高度压缩到 22，背景浅灰，文字深灰 —— 紧贴 grid 不留缝
        self.status_bar = QLabel("就绪")
        self.status_bar.setMaximumHeight(22)
        self.status_bar.setMinimumHeight(22)
        self.status_bar.setStyleSheet(
            "padding: 0 8px; background-color: #e5e7eb; border-radius: 4px;"
            "color: #111827; font-size: 12px;"
        )
        right_layout.addWidget(self.status_bar, stretch=0)

        main_layout.addWidget(right, stretch=1)  # stretch=1：右区拿到一切横向上多余空间，左栏再变不会挤压视频

        rows = self.config.get('layout.rows', 2)
        cols = self.config.get('layout.cols', 2)
        self.grid_widget.set_grid(rows, cols)
        self.active_ids = [None] * self.grid_widget.count()

        # ================================================================
        # B4：初始化前后 online 对照字典（id → bool），on_refresh 每轮执行完写一次新快照
        #   避免第一次启动时所有设备"离线→在线"被误判成变了导致一堆 online 事件（首次只采集不触发）
        # ================================================================
        try:
            self._last_device_online_map = {}
            for d in self.config.get_devices():
                self._last_device_online_map[str(d.get("id", ""))] = bool(d.get("online", False))
        except Exception:
            self._last_device_online_map = {}

        # ================================================================
        # C3：每个 VideoWidget 右键菜单切换"设为/取消 值守岗"（离岗 10 分钟告警）
        #   CustomContextMenu 策略 = 右键 VideoWidget 任何空白处弹菜单，不破坏原双击全屏逻辑
        # ================================================================
        try:
            for idx, ch in enumerate(self.grid_widget.channels):
                try:
                    ch.setContextMenuPolicy(Qt.CustomContextMenu)
                    ch.customContextMenuRequested.connect(
                        lambda pos, _ch=ch, _idx=idx: self._show_channel_context_menu(_ch, _idx, pos)
                    )
                except Exception:
                    pass
        except Exception:
            pass

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
            # -------- 严格按用户要求：不要一个大地方就放两个文字（camera + ●在线），空那么多 --------
            # 方案：把"名字●在线IP"三行改成"一行水平布局"（名字 + ●状态 左，IP 右），高度直接砍 2/3
            layout = QHBoxLayout()
            # 边距压缩到极致(左右4上下0)，列表项不会上下再拉出大空
            layout.setContentsMargins(4, 0, 4, 0)
            layout.setSpacing(6)

            name = QLabel(d.get("name", "未知"))
            # 白底黑字（之前深灰 #e0e0e0 改成纯黑系，不会"看不清"）
            name.setStyleSheet(
                "font-size: 12px; font-weight: 600; color: #111827;"
                "background: transparent;"
            )

            status = QLabel("● 在线" if d.get("online", False) else "○ 离线")
            # 在线绿/离线红，字号缩小不会显空
            status.setStyleSheet(
                f"font-size: 11px; color: {'#15803d' if d.get('online', False) else '#b91c1c'};"
                "background: transparent;"
            )

            ip = QLabel(d.get("ip", ""))
            ip.setStyleSheet("font-size: 10px; color: #4b5563; background: transparent;")
            ip.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            left_box = QVBoxLayout()
            left_box.setContentsMargins(0, 0, 0, 0)
            left_box.setSpacing(0)
            # 关键：第 1 行 = 名字 + ●状态 并排（把"两个字"放进同一行，不再上下两"空"叠放）
            row1 = QHBoxLayout()
            row1.setContentsMargins(0, 0, 0, 0)
            row1.setSpacing(6)
            row1.addWidget(name)
            row1.addWidget(status)
            row1.addStretch()
            left_box.addLayout(row1)
            # 第 2 行 = IP（如果 IP 为空就不放，避免空行占位）
            if d.get("ip", ""):
                row2 = QLabel(d.get("ip", ""))
                row2.setStyleSheet("font-size: 10px; color: #6b7280; background: transparent;")
                row2.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                left_box.addWidget(row2)

            layout.addLayout(left_box, stretch=1)

            widget.setLayout(layout)
            # sizeHint 也压一下：一行时 22 px，两行 IP 时 34 px，绝不再"空一大块"
            hint = widget.sizeHint()
            hint.setHeight(max(22, hint.height()))
            item.setSizeHint(hint)
            item.setData(Qt.UserRole, d["id"])
            self.device_list.addItem(item)
            self.device_list.setItemWidget(item, widget)

        online = sum(1 for d in devices if d.get("online", False))
        self.stats_label.setText(f"设备总数: {len(devices)} | 在线: {online}")
        # A1：设备清单刷新后（加/删/初始化都走这里），若自动布局 ON → 重新按新在线数切布局
        self._apply_auto_layout()

    def auto_connect(self):
        devices = self.config.get_devices()
        online = [d for d in devices if d.get("online", False)]
        self.active_ids = [None] * self.grid_widget.count()
        for i, d in enumerate(online):
            if i < self.grid_widget.count():
                ch = self.grid_widget.channels[i]
                ch.set_device_info(d)
                ch.set_face_engine(self.face_engine)
                ch.set_face_recognizer(self.face_recognizer)   # C1：注入人脸识别器，陌生人识别才能跑
                ch.set_motion_engine(self.motion_engine)
                ch.set_motion_alarm(self.motion_alarm_check.isChecked())
                # B2/C4 全局开关：toolbar 按钮状态 → 传给每路 VideoWidget（新增通道立即继承）
                try:
                    ch.set_schedule_record(self.btn_schedule_rec.isChecked())
                except Exception:
                    pass
                night_value = True if self.btn_night_mode.isChecked() else False
                try:
                    ch.set_night_mode(night_value)
                except Exception:
                    pass
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
                ch.set_face_recognizer(self.face_recognizer)   # C1：注入人脸识别器，陌生人识别才能跑
                ch.set_motion_engine(self.motion_engine)
                ch.set_motion_alarm(self.motion_alarm_check.isChecked())
                # B2/C4 全局开关：toolbar 按钮状态 → 传给每路 VideoWidget（新增通道立即继承）
                try:
                    ch.set_schedule_record(self.btn_schedule_rec.isChecked())
                except Exception:
                    pass
                night_value = True if self.btn_night_mode.isChecked() else False
                try:
                    ch.set_night_mode(night_value)
                except Exception:
                    pass
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
            # A1：加设备后 → 自动布局按新在线数重算（新设备在线可能从 1×1→1×2/2×2）
            self._apply_auto_layout()

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
            # A1：删设备后（在线数可能从 3→2、9→6）→ 重新按新在线数切布局，正好验证"多格切回 1 格不卡"
            self._apply_auto_layout()

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
        # A1：刷新（设备上下线变了）后若自动布局 ON → 按新在线数重切
        self._apply_auto_layout()

        # ================================================================
        # B4 · 设备上下线告警：对比 _last_device_online_map 前后 online 值
        #   仅 btn_device_alarm 按下时才 emit 事件；A5 已支持 online/offline/crowd/absence 类型
        #   存图：用 _save_simple_placeholder 生成一张 纯色文字占位 jpg（没有画面帧就不保存空文件，下游都能拿到 filepath 继续走）
        # ================================================================
        try:
            if getattr(self, 'btn_device_alarm', None) and self.btn_device_alarm.isChecked():
                prev_map = dict(getattr(self, '_last_device_online_map', {}) or {})
                now_map = {}
                for d in self.config.get_devices():
                    did = str(d.get("id", ""))
                    now_on = bool(d.get("online", False))
                    now_map[did] = now_on
                    old_on = prev_map.get(did, None)
                    if old_on is None:
                        continue   # 第一次出现的新设备：跳过（避免误判成变化）
                    if old_on != now_on:
                        dev_name = str(d.get("name", did))
                        evt_type = "online" if now_on else "offline"
                        # 写事件：文件路径给 data/faces 占位（A5 双击时如果文件不存在会 QMessageBox 提示，不崩）
                        placeholder = os.path.join(self.config.get_data_root(), "snapshots", f"{evt_type}_{dev_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                        try:
                            os.makedirs(os.path.dirname(placeholder), exist_ok=True)
                            with open(placeholder, 'w', encoding='utf-8') as f:
                                f.write(f"[{evt_type.upper()}] {dev_name} {'上线' if now_on else '离线'} @ {datetime.now().isoformat(timespec='seconds')}\n")
                        except Exception:
                            placeholder = ""
                        try:
                            self.on_event_triggered(evt_type, dev_name, placeholder)
                        except Exception as _b4e:
                            self.logger.error(f"B4 上下线 emit 异常: {_b4e}")
                self._last_device_online_map = now_map
        except Exception as _b4_total:
            self.logger.error(f"B4 上下线告警整体异常: {_b4_total}")

    # ================================================================
    # A1：自动布局核心方法（经验 147363：布局变化入口统一走单一函数，不散落多处各自算）
    # ================================================================
    @staticmethod
    def _auto_layout_rows_cols(n: int):
        """按在线通道数 n → (rows, cols)，保证 cols>=rows 或方正（4:3 IPC显示更友好）"""
        if n <= 1:  return (1, 1)
        if n <= 2:  return (1, 2)
        if n <= 4:  return (2, 2)
        if n <= 6:  return (2, 3)
        if n <= 9:  return (3, 3)
        return (4, 4)

    def _apply_auto_layout(self):
        """自动布局 ON 时，按当前在线设备数重算行列并切换（若当前已是目标布局→直接跳过不重建不闪）"""
        if not getattr(self, 'auto_layout_toggle', None):
            return
        if not self.auto_layout_toggle.isChecked():
            return
        devices = self.config.get_devices()
        online = max(1, sum(1 for d in devices if d.get('online', False)))
        rows, cols = self._auto_layout_rows_cols(online)
        want = f"{rows}x{cols}"
        cur = self.layout_combo.currentText()
        if cur == want:
            # 已经是目标布局：不重建通道不闪，只写状态
            self.status_bar.setText(f"🤖 自动布局: {want}（在线 {online} 路）")
            self._restore_style_later()
            return
        # block combo 信号避免 on_layout_changed 把"自动"按钮关掉（手动切才关）
        self.layout_combo.blockSignals(True)
        self.layout_combo.setCurrentText(want)
        self.layout_combo.blockSignals(False)
        self.on_layout_changed(want)
        self.status_bar.setText(f"🤖 自动布局切换为: {want}（在线 {online} 路）")
        self._restore_style_later()

    def _on_auto_layout_toggled(self, checked: bool):
        if checked:
            self.layout_combo.setEnabled(False)
            self.status_bar.setText("🤖 自动布局 ON（按在线通道数自动切）")
            self._apply_auto_layout()
        else:
            self.layout_combo.setEnabled(True)
            self.status_bar.setText("🤖 自动布局 OFF（手动选择布局）")
        self._restore_style_later()

    # ================================================================
    # A4：告警音（Windows winsound.MessageBeep 无需音频文件，失败静默不闪退）
    # ================================================================
    def _on_alarm_mute_toggled(self, muted: bool):
        self._alarm_muted = bool(muted)
        self.alarm_mute_btn.setText("🔇 已静音" if self._alarm_muted else "🔔 告警音")

    def _play_alarm_sound(self):
        if getattr(self, '_alarm_muted', False):
            return
        try:
            import winsound  # Windows 自带，无 pip 依赖
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            # 非 Windows / 权限 / 无音频设备 → 静默降级，不因为告警音导致主线程异常
            pass

    def _restore_style_later(self):
        """公共 helper：3 秒后把 status_bar 样式还原为浅色主题（避免事件结束后还维持红底/黑块）"""
        def _restore():
            try:
                if not getattr(self, '_destroyed', False) and not getattr(self.status_bar, 'deleted', False):
                    self.status_bar.setStyleSheet(
                        "padding: 0 8px; background-color: #e5e7eb; border-radius: 4px;"
                        "color: #111827; font-size: 12px;"
                    )
            except Exception:
                pass
        QTimer.singleShot(3000, _restore)

    def on_layout_changed(self, layout_text):
        # A1：用户直接从 combo 选了布局 → 视为"手动覆盖"，把自动布局按钮关掉（尊重手动优先级）
        if getattr(self, 'auto_layout_toggle', None) and self.auto_layout_toggle.isChecked():
            self.auto_layout_toggle.blockSignals(True)
            self.auto_layout_toggle.setChecked(False)
            self.auto_layout_toggle.blockSignals(False)
            self.layout_combo.setEnabled(True)

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

        # A1/A4 通用 helper：3 秒后把 status_bar 还原浅色（与 auto_layout 触发时的还原逻辑共用，不再重复写 QTimer.singleShot 闭包）
        self._restore_style_later()

        # A4：事件触发响告警音（与 🔔/🔇 静音开关联动，静默时不响）
        #     原来的 QApplication.beep() 没有静音能力，持续运行时可能打扰用户；改为统一走 _play_alarm_sound，失败静默降级
        self._play_alarm_sound()

        self.logger.info(f"事件触发: {channel} - {event_type}")

    def on_motion_alarm_toggle(self):
        enabled = self.motion_alarm_check.isChecked()
        for ch in self.grid_widget.channels:
            ch.set_motion_alarm(enabled)
        self.status_bar.setText(f"运动报警 {'开启' if enabled else '关闭'}")

    # ================================================================
    # B2 · 定时录像按钮槽（Toolbar ⏱）：三档广播所有通道 set_schedule_record
    # ================================================================
    def _on_schedule_record_toggled(self, checked: bool):
        try:
            for ch in self.grid_widget.channels:
                try:
                    ch.set_schedule_record(bool(checked))
                except Exception:
                    pass
            self.status_bar.setText(f"⏱ 定时录像 {'已开启（所有在线通道将按小时分片自动录像）' if checked else '已关闭（不影响手动●录像）'}")
            self._restore_style_later()
        except Exception as _b2s:
            self.logger.error(f"B2 定时录像切换异常: {_b2s}")

    # ================================================================
    # C4 · 夜间模式按钮槽（Toolbar 🌙）：未选中=自动(亮度<50启用)，选中=强制启用
    #   三档广播：True/False → 每个 VideoWidget.set_night_mode（None=强制关闭 由右键再扩展，暂不做）
    # ================================================================
    def _on_night_mode_toggled(self, checked: bool):
        try:
            night_value = True if checked else False
            for ch in self.grid_widget.channels:
                try:
                    ch.set_night_mode(night_value)
                except Exception:
                    pass
            self.status_bar.setText(f"🌙 夜间{'强制启用 CLAHE 对比度增强' if checked else '自动（亮度<50 自动启用增强）'}")
            self._restore_style_later()
        except Exception as _c4s:
            self.logger.error(f"C4 夜间模式切换异常: {_c4s}")

    # ================================================================
    # C3 · 通道右键菜单：切换「设为/取消 值守岗」（离岗 10 分钟无活动告警）
    #   右键点 VideoWidget 任何位置弹菜单，打勾表示当前是值守岗
    # ================================================================
    def _show_channel_context_menu(self, channel_widget, channel_idx, pos):
        try:
            if channel_widget is None or getattr(channel_widget, '_destroying', False):
                return
            is_duty = bool(getattr(channel_widget, 'is_duty_station', lambda: False)())
            menu = QMenu(self)
            duty_act = QAction("设为值守岗（离岗 10 分钟告警）", self)
            duty_act.setCheckable(True)
            duty_act.setChecked(is_duty)
            duty_act.triggered.connect(lambda _c, _ch=channel_widget: self._toggle_duty_station(_ch))
            menu.addAction(duty_act)
            menu.addSeparator()
            # 顺手加一个"全屏显示"小便捷入口（双击原本也能进，右键多一条）
            full_act = QAction("全屏显示", self)
            full_act.triggered.connect(lambda _c, _ch=channel_widget: self._quick_fullscreen(_ch))
            menu.addAction(full_act)
            menu.exec_(channel_widget.mapToGlobal(pos))
        except Exception as _c3m:
            self.logger.error(f"C3 通道右键菜单异常: {_c3m}")

    def _toggle_duty_station(self, ch):
        try:
            now_is = bool(ch.is_duty_station()) if hasattr(ch, 'is_duty_station') else False
            ch.set_duty_station(not now_is)
            msg = f"【{ch.name_label.text()}】已{'设为值守岗（10分钟无活动将触发离岗告警）' if not now_is else '取消值守岗'}"
            self.status_bar.setText(msg)
            self._restore_style_later()
            self.logger.info(f"C3 值守岗切换: {msg}")
        except Exception as _c3t:
            self.logger.error(f"C3 值守岗切换异常: {_c3t}")

    def _quick_fullscreen(self, ch):
        try:
            if ch is None or ch.current_frame is None:
                QMessageBox.information(self, "提示", "当前通道无画面")
                return
            # 复用现有 FullscreenDialog（与双击全屏一致），不新建类保持模块划分硬约束
            dialog = FullscreenDialog(ch, self)
            dialog.exec_()
        except Exception as _qfse:
            self.logger.error(f"快捷全屏异常: {_qfse}")

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
            # 🔥 FIX P4：不再显示"模块未加载"恐慌警告 → 友好操作提示，错误细节只打 stdout
            #（如果真没加载 dlib 模型，人脸管理表格已经有"识别器未加载"行，按钮全灰，不用再额外弹警告）
            QMessageBox.information(self, "提示", "人脸库还在初始化中，请等摄像头画面出现后再试一下")
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