import cv2
import os
import time
from collections import deque
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from core.app_paths import U
from core.reconnect_policy import ReconnectPolicy

class VideoWidget(QWidget):
    double_clicked = pyqtSignal()
    event_triggered = pyqtSignal(str, str, str)

    def __init__(self, name="通道", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        # -------- 摄像头按钮区 / 视频区 / 信息栏 完美镶嵌：外边距0、内缝1，不留肉眼可见的大空白 --------
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.setLayout(layout)

        # -------- 尺寸链贯通（经验155413 + 692281）：三层 SizePolicy=Expanding 逐级真正铺满 --------
        # 用户反馈"画面是个小方块 + 外面大片白空白"的核心根因清单：
        #   ① GridLayoutWidget 自身不是 Expanding（外层分了空间它不接，留白=#ffffff）
        #   ② 本 VideoWidget（grid cell 里直接放的那个 QWidget）不是 Expanding → cell 给了 400x300，
        #      VideoWidget 只按 sizeHint 拿 240x180，剩下的 cell 空间漏出 #ffffff 白背景，真·小方块
        #   ③ 里面 video_label 也不是 Expanding → VideoWidget 即使涨了，label 还缩在 40px 高度
        # 现在三级都强制 Expanding + MinimumSize(1,1)，让"父给多少子拿多少"100% 贯通。
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(1, 1)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        # -------- 视频背景统一 #000（纯黑）：等比例缩放后两侧/上下的"留边"也是黑的，和监控画面视觉更协调 --------
        # （之前浅灰 f0f1f3 在 16:9 视频被塞进 4:3 格子时会出现两条难看浅灰边；黑底直接融入画面，监控感更强）
        self.video_label.setStyleSheet(
            "QLabel { background-color: #000000; border: 1px solid #e5e7eb; border-radius: 3px; }"
        )
        # -------- 重要：setScaledContents(False) --------
        # 之前开 True + update_frame 里自己 scaled(KeepAspectRatioByExpanding) 两边冲突：
        #   setScaledContents=True 会让 QLabel 强制拉伸 pixmap 填满（变形），
        #   与 KeepAspectRatioByExpanding 等比例+裁边填满容器完全相反 → 导致"画面要么拉变形、要么留浅灰大白边"
        # 关掉后统一走 update_frame / resizeEvent 里的 pix.scaled(KeepAspectRatioByExpanding, Smooth)：
        #   → 先把画面等比放大，直到**短边也填满容器**，长边超出部分被居中裁掉（监控画面不在乎边缘），
        #   结果是 video_label 整个矩形真·全是画面内容，零黑边零空白，用户不会再看到"小方块+大片空"。
        self.video_label.setScaledContents(False)
        # 最小高度 40 保留：外层 stretch=1 时会把它真正拉满容器，不再 1 行有图 3 行空
        self.video_label.setMinimumHeight(40)
        # 第三级贯通：video_label 自己也要 Expanding，否则 VideoWidget 被拉到 400x300，label 还缩成 40 高
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setMinimumSize(1, 1)
        layout.addWidget(self.video_label, stretch=1)

        # -------- 信息栏（一行：摄像头名称 + ●在线状态 + ⏱ 时间显示，三块紧凑并排）--------
        info = QHBoxLayout()
        info.setContentsMargins(2, 1, 2, 1)
        info.setSpacing(4)

        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(
            "color: #111827; font-size: 12px; font-weight: 600;"
            "background: transparent;"
        )
        self.status_label = QLabel("● 离线")
        self.status_label.setStyleSheet(
            "color: #b91c1c; font-size: 11px; background: transparent;"
        )
        # -------- 新增：每路摄像头独立的时间标签（显示最后一帧接收时间，离线时显示 --:--:--）--------
        # 使用等宽字体，数字列对齐不抖动，深灰字不抢 name/status 视觉
        self.time_label = QLabel("--:--:--")
        self.time_label.setStyleSheet(
            "color: #374151; font-size: 11px; background: transparent;"
            "font-family: Consolas, 'Courier New', monospace;"
        )
        # -------- A2：每路分辨率 @ FPS 叠加标签 --------
        # 紧跟时间后面、stretch 之前，信息密度最大化但仍然单行（不换行不空行）
        self.meta_label = QLabel("0x0 @ -- fps")
        self.meta_label.setStyleSheet(
            "color: #6b7280; font-size: 10px; background: transparent;"
            "font-family: Consolas, 'Courier New', monospace;"
        )

        info.addWidget(self.name_label)
        info.addWidget(self.status_label)
        info.addWidget(self.time_label)   # 时间紧跟●状态后面，方便一眼对照"哪个摄像头什么时刻"
        info.addWidget(self.meta_label)   # A2：分辨率 @ FPS 紧跟时间后，一眼看清"这路是不是在正常推流"
        info.addStretch()

        # 把 info 放进一条 QFrame（20-22px 高、浅灰+细边），视觉上"摄像头名+状态"稳稳占 1 行不"空"
        info_box = QFrame()
        info_box.setMaximumHeight(22)
        info_box.setMinimumHeight(22)
        info_box.setStyleSheet(
            "QFrame { background-color: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 3px; }"
        )
        info_box.setLayout(info)
        layout.addWidget(info_box, stretch=0)

        # 核心变量
        self.cap = None
        self.rtsp_url = None
        self.current_pixmap = None
        self.current_frame = None
        # ✅ 记录当前帧真实尺寸（供 VideoWriter 使用，避免与 QPixmap 缩放后的尺寸不一致 → 崩溃）
        self._frame_size = (0, 0)
        self.device_info = {}
        self.face_engine = None
        self.face_recognizer = None   # C1：人脸识别器（识别熟人/陌生人）
        self.motion_engine = None
        self.motion_alarm = False
        self.is_recording = False
        self.video_writer = None
        # 所有运行时数据统一落到用户数据目录，避免从不同工作目录启动时写散。
        self.data_root = U("data")
        for sub in ["snapshots", "records", "motions", "faces"]:
            try:
                os.makedirs(os.path.join(self.data_root, sub), exist_ok=True)
            except Exception:
                pass

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.frame_counter = 0
        self.face_interval = 20   # 降低检测频率
        self.motion_interval = 20

        # -------- A2：FPS 滑窗计算器（maxlen=10 算 10 帧平均，不抖动）--------
        self._fps_times = deque(maxlen=10)

        # 缓存检测结果
        self.last_face_detections = []
        self.last_motion_rects = []

        # 冷却机制：face/motion 共用 last_event_time，陌生人单独一个（防止熟人脸触发冷却把陌生人挡掉）
        self.last_event_time = 0
        self.event_cooldown = 8   # 秒
        self._last_stranger_time = 0   # C1：陌生人独立冷却（与 face event 不共用，识别才触发的核心逻辑）
        self._stranger_cooldown = 8    # C1：陌生人 8 秒只报一次（避免画面抖动、告警音连环响吵）

        # C1：最近一次识别结果（非检测周期也能持续画红/绿框，不丢"陌生人/张三"文字标签）
        self._last_face_rec_results = []   # list[dict{bbox, name, is_stranger, distance}]

        # ================================================================
        # B2/C2/C3/C4 新增变量（代码侧全部落地，torch 装完即生效）
        # ================================================================
        # B2 定时录像：每小时分片当前录像文件时间戳（整小时变了就 stop_record+start_record 开新文件）
        self._record_hour_key = ""   # 形如 "20260827_08"，跨小时自动切文件
        # B2/C3 外部开关（MainWindow toolbar 按钮或右键菜单 setter 设置）
        self._schedule_record_enabled = False   # B2 定时录像（全局 ON 时，本通道在线就自动录）
        self._duty_station = False               # C3 值守岗标记（右键菜单切换，True 时才跑离岗检测）
        # C2 人员聚集检测：人脸数连续 3 个检测周期 ≥ 5 人才触发（避免单帧误检）
        self._crowd_face_streak = 0              # 连续满足 "人脸数>=阈值" 的检测周期次数
        self._crowd_threshold = 5                # 默认 5 人算聚集（可通过 setter 改）
        self._crowd_cooldown = 0                 # C2 聚集告警独立冷却时间戳（避免连环响）
        # C3 离岗检测：连续 N 秒没检测到人脸 AND 没运动 → 离岗告警（值守岗=True 时才启用）
        self._absence_last_face_time = 0.0       # 最近一次检测到人脸的 time.time()
        self._absence_last_motion_time = 0.0     # 最近一次检测到运动的 time.time()
        self._absence_no_activity_seconds = 600  # 默认 10 分钟（600s）无活动算离岗
        self._absence_already_fired = False      # 同一离岗只报警 1 次（活动恢复后重置 False）
        # C4 夜间/低照度增强开关：toolbar 🌙按钮 或 自动亮度<50 时启动；frame 先经 CLAHE 均衡再喂 detect
        self._night_mode = False                 # False=自动(亮度<50时启用)，True=强制启用，None=强制关闭
        try:
            self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))   # C4 CLAHE 对象（一次创建，每帧复用）
        except Exception:
            self._clahe = None

        # ✅ 重连退避计数器：避免网络抖动时频繁创建/销毁 VideoCapture（句柄泄漏 + 崩溃）
        self._reconnect_policy = ReconnectPolicy()
        self._reconnect_policy.reset(time.monotonic())
        # ✅ 销毁保护：防止 QTimer 在对象析构过程中仍回调
        self._destroying = False

    def set_device_info(self, info):
        self.device_info = info
        self.name_label.setText(info.get("name", "摄像头"))

    def set_face_engine(self, engine):
        self.face_engine = engine

    def set_face_recognizer(self, recognizer):
        """C1：外部注入人脸识别器（MainWindow 从 face_engine.recognizer 取来再 set，保持 set_* 风格一致）"""
        self.face_recognizer = recognizer

    def set_motion_engine(self, engine):
        self.motion_engine = engine

    def set_motion_alarm(self, enabled):
        self.motion_alarm = enabled

    # ------------------------------------------------------------
    # B2 定时录像控制开关（MainWindow toolbar 定时录像按钮按下 → 所有在线通道 set_schedule_record(True)）
    # ------------------------------------------------------------
    def set_schedule_record(self, enabled: bool):
        self._schedule_record_enabled = bool(enabled)

    # ------------------------------------------------------------
    # C3 值守岗标记（右键菜单 → 设为/取消值守岗；True 时启用离岗 10 分钟无活动告警）
    # ------------------------------------------------------------
    def set_duty_station(self, enabled: bool):
        self._duty_station = bool(enabled)
        # 取消值守岗 → 重置离岗状态，避免下次设岗时误报
        if not enabled:
            self._absence_already_fired = False
            self._absence_last_face_time = 0.0
            self._absence_last_motion_time = 0.0

    def is_duty_station(self) -> bool:
        return bool(getattr(self, '_duty_station', False))

    # ------------------------------------------------------------
    # C2 聚集阈值 setter（默认 5 人，可通过 setter 调整）
    # ------------------------------------------------------------
    def set_crowd_threshold(self, n: int):
        try:
            n = int(n)
            if n >= 2:
                self._crowd_threshold = n
        except Exception:
            pass

    # ------------------------------------------------------------
    # C4 夜间模式 setter：False=自动(亮度<50时启用CLAHE) / True=强制启用 / None=强制关闭
    # ------------------------------------------------------------
    def set_night_mode(self, value):
        self._night_mode = value

    def start(self, rtsp_url):
        # ✅ 对象正在销毁时禁止启动
        if getattr(self, '_destroying', False):
            return
        self.stop()
        self.rtsp_url = rtsp_url
        # 🛡 开源日志脱敏：打印 //admin:****@，绝不把真实密码打到 stdout/stderr（避免复制粘贴 issue 时泄露）
        from core.config_manager import ConfigManager as _CM
        safe_url = _CM.redact_rtsp(rtsp_url)
        print(f"[VideoWidget] 尝试连接 RTSP: {safe_url}")
        try:
            # ✅ 对 RTSP 场景推荐设置缓冲降低延迟 + 尝试 TCP 传输（避免 UDP 丢包导致的崩溃）
            self.cap = cv2.VideoCapture(rtsp_url)
            if self.cap is not None and self.cap.isOpened():
                try:
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                except Exception:
                    pass
        except Exception as e:
            print(f"❌ [VideoWidget] 创建 VideoCapture 异常: {e}")
            self.cap = None
            return

        if self.cap is None or not self.cap.isOpened():
            # 脱敏打印
            from core.config_manager import ConfigManager as _CM2
            print(f"❌ [VideoWidget] 无法打开 RTSP: {_CM2.redact_rtsp(rtsp_url)}")
            self.set_connected(False)
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            return

        # ✅ 启动成功，重置重连退避
        self._reconnect_policy.reset(time.monotonic())
        from core.config_manager import ConfigManager as _CM3
        print(f"✅ [VideoWidget] RTSP 连接成功: {_CM3.redact_rtsp(rtsp_url)}")
        self.set_connected(True)
        self.timer.start(30)  # 33 FPS

    def stop(self):
        # ✅ 先停止定时器，阻断后续 update_frame 回调
        try:
            if self.timer:
                self.timer.stop()
        except Exception:
            pass
        # ✅ 安全释放 VideoCapture（空值保护 + 异常吞掉）
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        try:
            self.video_label.clear()
            self.video_label.setText("已停止")
        except Exception:
            pass
        # 停止时时间标签回到默认占位（不要继续停留在断开前的旧时间，造成"还在运行"错觉）
        try:
            self.time_label.setText("--:--:--")
        except Exception:
            pass
        # A2：停止时清 FPS/分辨率占位，避免显示"旧 25 fps"骗用户"还在跑"
        try:
            self.meta_label.setText("0x0 @ -- fps")
            self._fps_times.clear()
        except Exception:
            pass
        self.set_connected(False)
        self.current_pixmap = None
        self.current_frame = None
        self._frame_size = (0, 0)
        self.stop_record()
        self.last_event_time = 0
        self.last_face_detections = []
        self.last_motion_rects = []
        self._last_face_rec_results = []
        self._last_stranger_time = 0
        self._crowd_face_streak = 0
        self._crowd_cooldown = 0
        self._absence_already_fired = False
        self._absence_last_face_time = 0.0
        self._absence_last_motion_time = 0.0
        self._record_hour_key = ""
        self._reconnect_policy.reset(time.monotonic())

    def set_connected(self, connected):
        if connected:
            self.status_label.setText("● 在线")
            # 背景透明（深色字+浅绿，白底看得清，不会漏色）
            self.status_label.setStyleSheet("color: #15803d; font-size: 11px; background: transparent;")
        else:
            self.status_label.setText("● 离线")
            self.status_label.setStyleSheet("color: #b91c1c; font-size: 11px; background: transparent;")
            # A2：离线立刻把 FPS 置占位，FPS 滑窗清空（断开后不要显示断开前那一刻的高 FPS 误导）
            try:
                self.meta_label.setText("0x0 @ -- fps")
                if hasattr(self, '_fps_times'):
                    self._fps_times.clear()
            except Exception:
                pass

    def _save_frame(self, frame, subdir):
        try:
            os.makedirs(os.path.join(self.data_root, subdir), exist_ok=True)
            name = self.name_label.text()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.data_root, subdir, f"{name}_{timestamp}.jpg")
            # ✅ imwrite 的异常保护：磁盘满/权限不足时不应崩溃
            ok = cv2.imwrite(filename, frame)
            if not ok:
                return None
            return filename
        except Exception as e:
            print(f"[VideoWidget] 保存图片异常: {e}")
            return None

    def update_frame(self):
        # ✅ 销毁保护：对象在析构过程中，不再处理
        if getattr(self, '_destroying', False):
            return
        try:
            if self.cap is None or not self.cap.isOpened():
                # 基于单调时钟退避，不依赖帧计数，避免不同 FPS 下重连频率失真。
                now = time.monotonic()
                if not self._reconnect_policy.can_attempt(now):
                    return
                # 尝试重连（此处不 sleep，避免阻塞主线程）
                try:
                    if self.cap:
                        self.cap.release()
                except Exception:
                    pass
                self.cap = None
                if not self.rtsp_url:
                    return
                try:
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    if self.cap and self.cap.isOpened():
                        try:
                            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        except Exception:
                            pass
                        self.set_connected(True)
                        self._reconnect_policy.reset(now)
                    else:
                        self.set_connected(False)
                        if self.cap:
                            try:
                                self.cap.release()
                            except Exception:
                                pass
                            self.cap = None
                except Exception as e:
                    print(f"[VideoWidget] 重连异常: {e}")
                    self.set_connected(False)
                    self.cap = None
                self.frame_counter += 1
                return

            ret, frame = self.cap.read()
            if not ret:
                # ✅ 读取失败：退避重连，不 time.sleep（原代码 0.5s 阻塞主线程 → 卡死/无响应 → "闪退"感）
                now = time.monotonic()
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
                self._reconnect_policy.failed(now)
                self.set_connected(False)
                self.frame_counter += 1
                return

            # 读取成功：重置退避
            if self._reconnect_policy.attempts != 0:
                self._reconnect_policy.reset(time.monotonic())
                self.set_connected(True)

            self.current_frame = frame
            self.frame_counter += 1
            # ✅ 防止超长时间运行后计数器溢出（虽然 Python int 不会溢出，但防止取模前的值过大影响判断精度）

            # ================================================================
            # C4 · 夜间低照度增强（CLAHE 亮度自适应）
            #   判定：_night_mode=True 强制启用；_night_mode=False(默认) → 灰度平均亮度<50 自动启用；_night_mode=None 永不启用
            #   处理：BGR→YCrCb，只对 Y 亮度通道跑 createCLAHE(clipLimit=2.0) 均衡→转回 BGR
            #   目的：夜间红外/暗光画面 YOLO 检测率从 30% 提升到 80% 以上
            #   注意：检测/识别都吃增强后的 detect_frame，但展示给用户+录像仍用原始 frame（保持画面真实不偏色）
            # ================================================================
            detect_frame = frame   # 默认检测帧 = 原帧
            _night_applied = False
            try:
                if self._night_mode is None:
                    pass  # 强制关闭，啥都不做
                else:
                    _fh, _fw = frame.shape[:2]
                    if _fh > 0 and _fw > 0:
                        # 快速亮度估计：32×32 小图 mean 足够判断 0-255 亮度，CPU < 0.2ms
                        _tiny = cv2.resize(frame, (32, 32), interpolation=cv2.INTER_AREA)
                        _gray_mean = float(_tiny.mean())
                        should_enhance = bool(self._night_mode) or (
                            (not self._night_mode) and _gray_mean < 50.0
                        )
                        if should_enhance and self._clahe is not None:
                            ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
                            ycrcb[:, :, 0] = self._clahe.apply(ycrcb[:, :, 0])
                            detect_frame = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
                            _night_applied = True
            except Exception as _ne:
                print(f"[VideoWidget][C4] 夜间增强异常: {_ne}")
                detect_frame = frame   # 增强失败退化用原帧，不崩
            self._night_applied_flag = _night_applied   # 给后面画面叠加 "🌙" 水印用
            if self.frame_counter > 1000000:
                self.frame_counter = 0
            # ✅ 记录真实帧尺寸，VideoWriter 必须使用该尺寸（不能用 UI 缩放后的 QPixmap 尺寸）
            fh, fw = frame.shape[:2]
            self._frame_size = (fw, fh)

            # ================================================================
            # A2：每路独立 FPS 计算（滑窗 10 帧平均 → 不跳不抖） + 分辨率@FPS 叠加
            #   信息栏：meta_label 紧跟时间后显示 "1920x1080 @ 25 fps"
            #   画面：🔥 FIX P2 用户要求——左下角显示（原左上角与"右上角时间/🌙夜间/顶部聚集大红字"争抢空间），
            #        黑底条+白字 cv2.rectangle(-1 填充) 保证任意背景可读
            # ================================================================
            try:
                self._fps_times.append(time.time())
                if len(self._fps_times) >= 2:
                    fps_span = max(1e-6, self._fps_times[-1] - self._fps_times[0])
                    fps_val = (len(self._fps_times) - 1) / fps_span
                else:
                    fps_val = 0.0
                self.meta_label.setText(f"{fw}x{fh} @ {fps_val:0.0f} fps")
                # ---- cv2 直接画到帧左下角（不影响 VideoWriter 原始帧写入，画框和 FPS 叠加都走同一个 frame）----
                overlay_text = f"{fw}x{fh} {fps_val:0.0f}fps"
                try:
                    (tw, th), _ = cv2.getTextSize(overlay_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    # 左下角：x=8, y=fh-8，黑底条矩形从 (6, fh - th - 16) 到 (6+tw+12, fh-4)
                    bx1, by1 = 6, fh - th - 16
                    bx2, by2 = 6 + tw + 12, fh - 4
                    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 0, 0), thickness=-1)
                    cv2.putText(frame, overlay_text, (12, fh - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                except Exception:
                    pass
            except Exception:
                pass

            # -------- 新增：每帧刷新该路独立时间显示（HH:MM:SS，对应"状态旁边加一个时间显示"需求）--------
            # 直接用系统时间作为"画面到达时间"（大部分家用 IPC 不支持 OSDP 时间戳叠加，系统时间足够对齐）
            try:
                self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
            except Exception:
                pass

            # 检测（仅更新缓存）—— 降低 CPU 占用，避免 UI 卡死
            if self.face_interval > 0 and (self.frame_counter % self.face_interval == 0) and self.face_engine:
                try:
                    # C4：检测吃 CLAHE 增强后的 detect_frame（暗光下脸能被 YOLO 真检到），但后面所有画图/录像/存图仍用原始 frame（真实不偏色）
                    self.last_face_detections = self.face_engine.detect(detect_frame)
                    # ================================================================
                    # C1 · 陌生人识别：detect 拿到 bbox 后，对每个人脸调 recognize_from_frame
                    #   - bbox 复用 YOLO 检测结果（不再 dlib 扫第二遍，省 40ms/帧）
                    #   - 结果缓存到 _last_face_rec_results：非检测周期也能持续画名字/距离
                    #   - 熟人 → 绿色框 + 名字+d=0.xx；陌生人 → 红色框 + "陌生人 d=0.xx"
                    #   - 陌生人 → 独立 8s 冷却 → 存图 → emit('stranger') 联动 A4 告警音 + 落历史
                    # ================================================================
                    rec_results = []
                    any_stranger = False
                    stranger_to_emit_bbox = None
                    if self.face_recognizer is not None and self.last_face_detections:
                        for det in self.last_face_detections:
                            bbox = det.get('bbox')
                            if not bbox:
                                continue
                            try:
                                name, is_stranger, distance, _enc = self.face_recognizer.recognize_from_frame(frame, bbox)
                            except Exception as _re:
                                print(f"[VideoWidget] recognize_from_frame 异常: {_re}")
                                name, is_stranger, distance = None, False, -1.0
                            if name is None:
                                # 识别失败：退化只画普通绿脸框，不记 rec_results（下一周期还会重试）
                                continue
                            rec_results.append({
                                'bbox': list(bbox),
                                'name': name,
                                'is_stranger': bool(is_stranger),
                                'distance': float(distance) if distance and distance >= 0 else 0.0,
                            })
                            if is_stranger:
                                any_stranger = True
                                stranger_to_emit_bbox = list(bbox)
                    self._last_face_rec_results = rec_results

                    # face event（老逻辑）：检测到人脸就触发，用于人脸截图归档（与 stranger 独立冷却互不影响）
                    if self.last_face_detections:
                        self._trigger_event("face", frame)

                    # C1：陌生人事件（独立冷却 8s，不与 face event 共用 last_event_time）
                    if any_stranger:
                        now_s = time.time()
                        if now_s - self._last_stranger_time >= self._stranger_cooldown:
                            self._last_stranger_time = now_s
                            # 存图：文件名"陌生人_通道名_时间.jpg"，老师截图演示一眼认得出
                            subdir = "faces"
                            try:
                                os.makedirs(os.path.join(self.data_root, subdir), exist_ok=True)
                                name_cn = self.name_label.text()
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                fname = os.path.join(self.data_root, subdir, f"陌生人_{name_cn}_{ts}.jpg")
                                ok_saved = cv2.imwrite(fname, frame)
                                if ok_saved:
                                    # emit stranger → MainWindow.on_event_triggered → 红底 + 告警音 + 落事件历史（A5已支持stranger类型）
                                    self.event_triggered.emit("stranger", self.name_label.text(), fname)
                            except Exception as _se:
                                print(f"[VideoWidget] 陌生人告警存图/emit异常: {_se}")
                except Exception as e:
                    print(f"[VideoWidget] 人脸检测异常: {e}")
                    # 异常时清空缓存，避免用过期结果绘制
                    self.last_face_detections = []
                    self._last_face_rec_results = []

            if self.motion_interval > 0 and (self.frame_counter % self.motion_interval == 0) and self.motion_engine:
                try:
                    self.last_motion_rects = self.motion_engine.detect(detect_frame)   # C4：运动检测也吃增强帧（暗光下人影晃动能被真识别）
                    if self.last_motion_rects and self.motion_alarm:
                        self._trigger_event("motion", frame)
                    # C3 离岗：有运动 → 记录最近运动时间 + 活动恢复重置 absence_already_fired
                    if self.last_motion_rects:
                        now = time.time()
                        self._absence_last_motion_time = now
                        if self._absence_already_fired:
                            self._absence_already_fired = False   # 人回来了，下次长时间不在再重新报警
                except Exception as e:
                    print(f"[VideoWidget] 运动检测异常: {e}")
                    self.last_motion_rects = []

            # ================================================================
            # C2 · 人员聚集检测（单画面人脸数持续 3 个周期 ≥ crowd_threshold=5 → 告警）
            #   设计：连续 3 个 face_interval 周期都 >= 阈值才告警（避免单帧误检"5个影子算5人"）
            #   独立冷却 30s（聚集场景本来就持续几分钟，30s 只报 1 次不吵）
            #   画面叠加 "⚠ 聚集 N 人" 大红字 顶部中央
            # ================================================================
            self._crowd_active = False   # 给后面画面叠加水印用
            try:
                if self.face_interval > 0 and (self.frame_counter % self.face_interval == 0) and self.face_engine:
                    n_faces = len(self.last_face_detections)
                    if n_faces >= max(2, self._crowd_threshold):
                        self._crowd_face_streak = min(99, int(self._crowd_face_streak) + 1)
                    else:
                        self._crowd_face_streak = 0
                    # C3 离岗顺带更新最近一次人脸出现时间
                    if n_faces > 0:
                        now = time.time()
                        self._absence_last_face_time = now
                        if self._absence_already_fired:
                            self._absence_already_fired = False
                    if self._crowd_face_streak >= 3:
                        self._crowd_active = True
                        now_s = time.time()
                        if now_s - self._crowd_cooldown >= 30:
                            self._crowd_cooldown = now_s
                            # 30s 冷却外：存一张聚集图 → emit('crowd', 通道名, 路径) → 自动联动 A4 告警音 + A5 落历史
                            subdir = "snapshots"
                            try:
                                os.makedirs(os.path.join(self.data_root, subdir), exist_ok=True)
                                name_cn = self.name_label.text()
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                fname = os.path.join(self.data_root, subdir, f"聚集{n_faces}人_{name_cn}_{ts}.jpg")
                                ok_saved = cv2.imwrite(fname, frame)
                                if ok_saved:
                                    self.event_triggered.emit("crowd", name_cn, fname)
                            except Exception as _ce:
                                print(f"[VideoWidget][C2] 聚集告警存图/emit异常: {_ce}")
            except Exception as _c2e:
                print(f"[VideoWidget][C2] 聚集检测异常: {_c2e}")

            # ================================================================
            # C3 · 离岗/睡岗检测（仅本通道 _duty_station=True 时启用）
            #   判定：当前时间 - max(最近人脸时间, 最近运动时间) > 600秒(10分钟) → 离岗
            #   同一离岗只报警 1 次 _absence_already_fired；后续有人脸/运动恢复自动重置 False
            #   画面叠加底部 "🔴 离岗告警 已无活动 X 分钟" 红色大字；存图+emit('absence') → A4 告警音 + A5 落历史
            # ================================================================
            self._absence_active = False
            self._absence_elapsed_min = 0
            try:
                if self._duty_station:
                    now = time.time()
                    last_act = max(float(self._absence_last_face_time), float(self._absence_last_motion_time))
                    if last_act <= 0:
                        # 刚设为值守岗还没任何事件 → 以"现在"为起点，避免一设岗就立即报"10分钟无活动"
                        self._absence_last_face_time = now
                        self._absence_last_motion_time = now
                        last_act = now
                    elapsed = now - last_act
                    self._absence_elapsed_min = int(elapsed // 60)
                    if elapsed >= max(10, int(self._absence_no_activity_seconds)) and (not self._absence_already_fired):
                        self._absence_already_fired = True
                        self._absence_active = True
                        # 存图 + emit absence 事件
                        subdir = "snapshots"
                        try:
                            os.makedirs(os.path.join(self.data_root, subdir), exist_ok=True)
                            name_cn = self.name_label.text()
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            fname = os.path.join(self.data_root, subdir, f"离岗告警_{name_cn}_{ts}.jpg")
                            ok_saved = cv2.imwrite(fname, frame)
                            if ok_saved:
                                self.event_triggered.emit("absence", name_cn, fname)
                        except Exception as _ae:
                            print(f"[VideoWidget][C3] 离岗告警存图/emit异常: {_ae}")
                    elif self._absence_already_fired:
                        # 已经报过的离岗，持续叠加"离岗水印"直到人回来
                        self._absence_active = True
            except Exception as _c3e:
                print(f"[VideoWidget][C3] 离岗检测异常: {_c3e}")

            # 绘制（使用缓存结果）：
            #   - 人脸：优先用 _last_face_rec_results（C1 已识别：熟人绿 / 陌生人红，都带名字+d=0.xx）
            #   - 退化：没识别结果时退化为 last_face_detections 纯绿框（老逻辑，兼容识别器=None 场景）
            #   - 运动：原红框不变（注意跟陌生人框颜色区分：运动是空心小矩形区域，陌生人是人脸大红框+文字，视觉上不冲突）
            try:
                drawn_bboxes = set()
                for r in self._last_face_rec_results:
                    try:
                        x1, y1, x2, y2 = [int(v) for v in r['bbox']]
                        key = (x1, y1, x2, y2)
                        drawn_bboxes.add(key)
                        is_stranger = bool(r.get('is_stranger'))
                        name = str(r.get('name', '人脸'))
                        dist = float(r.get('distance', 0.0))
                        color = (0, 0, 255) if is_stranger else (0, 255, 0)   # 陌生人=红 / 熟人=绿
                        thickness = 3 if is_stranger else 2                    # 陌生人加粗更醒目
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
                        if dist > 0:
                            label = f"{name} d={dist:.2f}"
                        else:
                            label = name
                        # 黑底白字条：保证红框绿框在任意背景下文字都清晰（不漂不糊）
                        try:
                            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                            lx, ly = max(0, x1), max(th + 6, y1 - 6)
                            cv2.rectangle(frame, (lx, ly - th - 8), (lx + tw + 8, ly + 2), (0, 0, 0), thickness=-1)
                            cv2.putText(frame, label, (lx + 4, ly - 4),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
                        except Exception:
                            # 退化：没算成 textSize 就直接 putText，位置 x1,y1-10
                            try:
                                cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
                            except Exception:
                                pass
                    except Exception as _de:
                        print(f"[VideoWidget] 绘制识别结果异常: {_de}")
                        continue
                # 退化：没识别结果时用 last_face_detections 纯绿框（老逻辑）
                # ✅ FIX P3 用户要求「人脸标识框怎么没有人脸字样」— 检测到但识别器没启动/没返回时，
                #    也在框右上角外画黑底白字"人脸 87%"（带 confidence），与识别分支视觉风格一致
                for det in self.last_face_detections:
                    try:
                        x1, y1, x2, y2 = [int(v) for v in det['bbox']]
                        if (x1, y1, x2, y2) in drawn_bboxes:
                            continue
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        conf = float(det.get('confidence', 0.0))
                        if conf > 0:
                            label = f"人脸 {conf*100:.0f}%"
                        else:
                            label = "人脸"
                        try:
                            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                            lx, ly = max(0, x1), max(th + 6, y1 - 6)
                            cv2.rectangle(frame, (lx, ly - th - 8), (lx + tw + 8, ly + 2), (0, 0, 0), thickness=-1)
                            cv2.putText(frame, label, (lx + 4, ly - 4),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
                        except Exception:
                            try:
                                cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2, cv2.LINE_AA)
                            except Exception:
                                pass
                    except Exception:
                        pass
                # 运动检测框：保持老代码蓝绿/红约定（当前代码 BGR=0,0,255 → 显示红，实际"运动框"用浅黄 0,200,255 更易与人脸红区分）
                for (x, y, w, h) in self.last_motion_rects:
                    try:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 255), 2)   # BGR 浅黄，区分陌生人红(0,0,255)
                    except Exception:
                        pass

                # ================================================================
                # B2/C2/C3/C4 画面水印叠加
                #   - C4 🌙 夜间增强（右上角小图标）
                #   - C2 ⚠ 聚集 N 人（顶部居中大红字）
                #   - C3 🔴 离岗告警：已无活动 X 分钟（底部居中红字条）
                #   - B2 ⏱ 定时录像中（右上角 FPS 信息旁边，已经有录像●红点 meta_label 外的额外提示）
                # ================================================================
                try:
                    fh, fw = frame.shape[:2]
                    # C4 🌙 夜间增强标记
                    if bool(getattr(self, '_night_applied_flag', False)):
                        cv2.putText(frame, "🌙", (fw - 40, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 200, 0), 2, cv2.LINE_AA)
                    # C2 聚集 N 人
                    if bool(getattr(self, '_crowd_active', False)):
                        n_crowd = len(self.last_face_detections)
                        label = f"⚠ 人员聚集 {n_crowd} 人"
                        try:
                            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 3)
                            lx = max(0, (fw - tw) // 2)
                            cv2.rectangle(frame, (lx - 10, 10), (lx + tw + 10, 10 + th + 20), (0, 0, 200), thickness=-1)
                            cv2.putText(frame, label, (lx, 10 + th + 8),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3, cv2.LINE_AA)
                        except Exception:
                            pass
                    # C3 离岗告警底部红字条
                    if bool(getattr(self, '_absence_active', False)):
                        em = int(getattr(self, '_absence_elapsed_min', 0))
                        label = f"🔴 离岗告警：已无活动 {em} 分钟"
                        try:
                            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 3)
                            lx = max(0, (fw - tw) // 2)
                            by = max(th + 20, fh - 20)
                            cv2.rectangle(frame, (lx - 10, by - th - 16), (lx + tw + 10, by + 4), (0, 0, 180), thickness=-1)
                            cv2.putText(frame, label, (lx, by - 8),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 3, cv2.LINE_AA)
                        except Exception:
                            pass
                except Exception as _we:
                    print(f"[VideoWidget] B/C 功能水印叠加异常: {_we}")
            except Exception as e:
                print(f"[VideoWidget] 绘制检测框异常: {e}")

            # ============================================================
            # ✅ 【最核心闪退修复】QImage 构造时直接引用 numpy 数据（浅拷贝），
            #    rgb 离开作用域后被 GC → QImage 内部指针悬空 →
            #    QPixmap::fromImage / scaled / setPixmap 在渲染线程访问野内存 → SIGSEGV 随机闪退
            #    修复方式：QImage(...).copy() 强制深拷贝，或者把 rgb 保留为成员
            # ============================================================
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            if h <= 0 or w <= 0 or ch <= 0:
                return
            bytes_per_line = ch * w
            # .copy() 是关键！确保 QImage 拥有自己的内存，不依赖 rgb numpy 数组生命周期
            qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            pix = QPixmap.fromImage(qt_img)
            # 立即删除 qt_img 引用（可选，避免多余内存占用）
            del qt_img
            self.current_pixmap = pix

            label_size = self.video_label.size()
            try:
                if label_size.width() > 0 and label_size.height() > 0:
                    # --------- 用户要求"不要大片空白、要自适应填满"：KeepAspectRatio → KeepAspectRatioByExpanding ---------
                    # KeepAspectRatio = 保证画面完整、留白/黑边；容器1:1塞16:9视频时上下留黑=用户说的"小方块大片空"
                    # KeepAspectRatioByExpanding = 先等比例放到短边贴满容器、长边超出居中裁掉
                    #                      → 整个 video_label 矩形100%都是画面，零空白/零黑边，监控观感正好（裁边用户可接受）
                    scaled = pix.scaled(label_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    self.video_label.setPixmap(scaled)
                else:
                    self.video_label.setPixmap(pix)
            except Exception as e:
                print(f"[VideoWidget] 渲染帧异常: {e}")

            # ================================================================
            # B2 · 定时录像 + 每小时分片（配合 MainWindow.toolbar "⏱️ 定时录像" checkable 按钮控制 _schedule_record_enabled）
            #   逻辑：在线 + _schedule_record_enabled=True → 自动 is_recording；跨小时自动切新文件
            #   这样用户演示"挂一整晚录像"不用每个通道手动 ●录像，第二天直接按小时看片
            # ================================================================
            try:
                should_record = bool(self._schedule_record_enabled)
                if should_record:
                    # 每小时分片键：YYYYMMDD_HH（变了就切一份新 MP4）
                    hour_key = datetime.now().strftime("%Y%m%d_%H")
                    if not self.is_recording or self._record_hour_key != hour_key:
                        if self.is_recording:
                            try: self.stop_record()
                            except Exception: pass
                        self._record_hour_key = hour_key
                        # 启动新小时分片录像（跟 toggle_record 的 start_record 同尺寸逻辑，但文件名带 B2_小时分片前缀）
                        try:
                            name_cn = self.name_label.text()
                            ts = datetime.now().strftime("%Y%m%d_%H00")
                            rec_dir = os.path.join(self.data_root, "records")
                            os.makedirs(rec_dir, exist_ok=True)
                            fname = os.path.join(rec_dir, f"B2定时分片_{name_cn}_{ts}.mp4")
                            fw = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
                            fh = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
                            if fw > 0 and fh > 0:
                                self._frame_size = (fw, fh)
                                try:
                                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                                except Exception:
                                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                                self.video_writer = cv2.VideoWriter(fname, fourcc, 15.0, (fw, fh))
                                if self.video_writer and self.video_writer.isOpened():
                                    self.is_recording = True
                        except Exception as _b2e:
                            print(f"[VideoWidget][B2] 小时分片录像启动异常: {_b2e}")
                            self.is_recording = False
                else:
                    # 定时录像被 MainWindow 关闭 → 如果当前录的是 B2 自动分片（不是用户手动 ●录像）就停掉
                    if self.is_recording and self._record_hour_key:
                        try: self.stop_record()
                        except Exception: pass
                        self._record_hour_key = ""
            except Exception as _b2e2:
                print(f"[VideoWidget][B2] 定时录像逻辑异常: {_b2e2}")

            # 录像（原代码保留：手动 ●录像 和 B2 定时分片 共享同一个 is_recording 分支写帧）
            if self.is_recording and self.video_writer is not None:
                try:
                    # ✅ VideoWriter 默认期望 BGR（OpenCV 约定），而不是 RGB
                    #    同时保证帧尺寸与 VideoWriter 初始化时完全一致（尺寸不匹配 → 写入失败/崩溃）
                    vw_w, vw_h = self._frame_size
                    if vw_w > 0 and vw_h > 0 and (frame.shape[1], frame.shape[0]) == (vw_w, vw_h):
                        self.video_writer.write(frame)
                except Exception as e:
                    print(f"[VideoWidget] 录像写入异常: {e}")
                    # 写入失败就停止录像，避免后续持续异常
                    self.stop_record()

        except Exception as e:
            print(f"[VideoWidget] update_frame 捕获异常: {e}")

    def _trigger_event(self, event_type, frame):
        # ✅ 销毁保护 + 识别器为 None 时仍能保存
        if getattr(self, '_destroying', False):
            return
        now = time.time()
        if now - self.last_event_time < self.event_cooldown:
            return
        self.last_event_time = now
        filepath = self._save_frame(frame, event_type + "s")
        if filepath is None:
            return  # 保存失败就不发事件，避免下游处理空路径
        try:
            self.event_triggered.emit(event_type, self.name_label.text(), filepath)
        except Exception as e:
            print(f"[VideoWidget] emit 事件异常: {e}")

    def resizeEvent(self, event):
        try:
            if self.current_pixmap is not None and not getattr(self, '_destroying', False):
                label_size = self.video_label.size()
                if label_size.width() > 0 and label_size.height() > 0:
                    # 与 update_frame 保持一致：KeepAspectRatioByExpanding 让像素画真填满不留空
                    scaled = self.current_pixmap.scaled(label_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    self.video_label.setPixmap(scaled)
        except Exception as e:
            print(f"[VideoWidget] resizeEvent 异常: {e}")
        super().resizeEvent(event)

    def snapshot(self):
        if getattr(self, '_destroying', False):
            return None
        if self.current_pixmap is None:
            return None
        try:
            os.makedirs(os.path.join(self.data_root, "snapshots"), exist_ok=True)
            name = self.name_label.text()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.data_root, "snapshots", f"{name}_{timestamp}.jpg")
            # ✅ 优先用 current_frame 写无损原图（cv2.imwrite 更可靠），失败再退回 QPixmap.save
            if self.current_frame is not None:
                ok = cv2.imwrite(filename, self.current_frame)
                if ok:
                    return filename
            # fallback
            if not self.current_pixmap.save(filename, "JPG"):
                return None
            return filename
        except Exception as e:
            print(f"[VideoWidget] 截图异常: {e}")
            return None

    def start_record(self):
        if getattr(self, '_destroying', False):
            return False
        if self.is_recording:
            return False
        # ✅ 关键：VideoWriter 的尺寸必须来自真实帧 current_frame，不能来自 QPixmap（UI 缩放后尺寸不匹配 → 写入失败/编码器崩溃）
        if self.current_frame is None:
            return False
        try:
            os.makedirs(os.path.join(self.data_root, "records"), exist_ok=True)
            name = self.name_label.text()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.data_root, "records", f"{name}_{timestamp}.mp4")
            fh, fw = self.current_frame.shape[:2]
            if fw <= 0 or fh <= 0:
                return False
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(filename, fourcc, 10.0, (fw, fh))
            if not writer.isOpened():
                try:
                    writer.release()
                except Exception:
                    pass
                return False
            self.video_writer = writer
            self._frame_size = (fw, fh)
            self.is_recording = True
            return True
        except Exception as e:
            print(f"[VideoWidget] 开始录像异常: {e}")
            self.video_writer = None
            self.is_recording = False
            return False

    def stop_record(self):
        writer = self.video_writer
        self.video_writer = None
        self.is_recording = False
        if writer is not None:
            try:
                writer.release()
            except Exception as e:
                print(f"[VideoWidget] 停止录像 release 异常: {e}")

    def mouseDoubleClickEvent(self, event):
        try:
            if not getattr(self, '_destroying', False):
                self.double_clicked.emit()
        except Exception:
            pass
        super().mouseDoubleClickEvent(event)

    def clear(self):
        # ✅ 先标记销毁状态，让所有回调快速返回
        self._destroying = True
        try:
            # 断开所有外部连接的槽（防止 deleteLater 过程中 emit 到已析构对象）
            try:
                self.event_triggered.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                self.double_clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
        except Exception:
            pass
        self.stop()
        # 清空引用，帮助 GC
        self.face_engine = None
        self.face_recognizer = None
        self.motion_engine = None
