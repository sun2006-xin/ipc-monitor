import cv2
import os
import time
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage

class VideoWidget(QWidget):
    double_clicked = pyqtSignal()
    event_triggered = pyqtSignal(str, str, str)

    def __init__(self, name="通道", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        # UI 紧凑化：内部边距全归零（通道间的"缝"交给外层 GridLayout 控制），视频栏与信息栏的垂直间距缩到 1
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.setLayout(layout)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #0d1117; border-radius: 4px;")
        # 把 120 -> 40：原先 4 通道模式时，minHeight=120 会让每个通道"最小高度 120 + 标题栏"，
        # 导致一行 2 个也塞不下，下半截全是空白空隙（截图里"camera ● 在线"下面一整行浅灰空的罪魁祸首）
        # 现在把最小高度砍到 40，由外层布局拉伸决定实际尺寸——画面会把所有空间"填满"，不再留大空。
        self.video_label.setMinimumHeight(40)
        layout.addWidget(self.video_label)

        # 信息栏（紧凑布局）
        info = QHBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)  # 4 -> 2：通道名 / 状态点更贴近，视觉不空旷
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("color: #a0aec0; font-size: 12px; font-weight: bold;")
        self.status_label = QLabel("● 离线")
        self.status_label.setStyleSheet("color: #fc8181; font-size: 11px;")
        info.addWidget(self.name_label)
        info.addWidget(self.status_label)
        info.addStretch()  # 将标签推到左侧，右侧留空
        layout.addLayout(info)

        # 核心变量
        self.cap = None
        self.rtsp_url = None
        self.current_pixmap = None
        self.current_frame = None
        # ✅ 记录当前帧真实尺寸（供 VideoWriter 使用，避免与 QPixmap 缩放后的尺寸不一致 → 崩溃）
        self._frame_size = (0, 0)
        self.device_info = {}
        self.face_engine = None
        self.motion_engine = None
        self.motion_alarm = False
        self.is_recording = False
        self.video_writer = None
        self.data_root = "data"
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

        # 缓存检测结果
        self.last_face_detections = []
        self.last_motion_rects = []

        # 冷却机制
        self.last_event_time = 0
        self.event_cooldown = 8   # 秒

        # ✅ 重连退避计数器：避免网络抖动时频繁创建/销毁 VideoCapture（句柄泄漏 + 崩溃）
        self._reconnect_backoff = 0
        # ✅ 销毁保护：防止 QTimer 在对象析构过程中仍回调
        self._destroying = False

    def set_device_info(self, info):
        self.device_info = info
        self.name_label.setText(info.get("name", "摄像头"))

    def set_face_engine(self, engine):
        self.face_engine = engine

    def set_motion_engine(self, engine):
        self.motion_engine = engine

    def set_motion_alarm(self, enabled):
        self.motion_alarm = enabled

    def start(self, rtsp_url):
        # ✅ 对象正在销毁时禁止启动
        if getattr(self, '_destroying', False):
            return
        self.stop()
        self.rtsp_url = rtsp_url
        print(f"[VideoWidget] 尝试连接 RTSP: {rtsp_url}")
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
            print(f"❌ [VideoWidget] 无法打开 RTSP: {rtsp_url}")
            self.set_connected(False)
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            return

        # ✅ 启动成功，重置重连退避
        self._reconnect_backoff = 0
        print(f"✅ [VideoWidget] RTSP 连接成功: {rtsp_url}")
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
        self.set_connected(False)
        self.current_pixmap = None
        self.current_frame = None
        self._frame_size = (0, 0)
        self.stop_record()
        self.last_event_time = 0
        self.last_face_detections = []
        self.last_motion_rects = []
        self._reconnect_backoff = 0

    def set_connected(self, connected):
        if connected:
            self.status_label.setText("● 在线")
            self.status_label.setStyleSheet("color: #48bb78; font-size: 11px;")
        else:
            self.status_label.setText("● 离线")
            self.status_label.setStyleSheet("color: #fc8181; font-size: 11px;")

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
                # 退避重连：每 2^(backoff) 次回调尝试一次，避免网络断开时暴力 33Hz 重连
                self._reconnect_backoff = min(self._reconnect_backoff + 1, 8)
                if (self.frame_counter & ((1 << self._reconnect_backoff) - 1)) != 0:
                    self.frame_counter += 1
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
                        self._reconnect_backoff = 0
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
                self._reconnect_backoff = min(self._reconnect_backoff + 1, 8)
                if self._reconnect_backoff <= 1:
                    try:
                        if self.cap:
                            self.cap.release()
                    except Exception:
                        pass
                    self.cap = None
                self.set_connected(False)
                self.frame_counter += 1
                return

            # 读取成功：重置退避
            if self._reconnect_backoff != 0:
                self._reconnect_backoff = 0
                self.set_connected(True)

            self.current_frame = frame
            self.frame_counter += 1
            # ✅ 防止超长时间运行后计数器溢出（虽然 Python int 不会溢出，但防止取模前的值过大影响判断精度）
            if self.frame_counter > 1000000:
                self.frame_counter = 0
            # ✅ 记录真实帧尺寸，VideoWriter 必须使用该尺寸（不能用 UI 缩放后的 QPixmap 尺寸）
            fh, fw = frame.shape[:2]
            self._frame_size = (fw, fh)

            # 检测（仅更新缓存）—— 降低 CPU 占用，避免 UI 卡死
            if self.face_interval > 0 and (self.frame_counter % self.face_interval == 0) and self.face_engine:
                try:
                    self.last_face_detections = self.face_engine.detect(frame)
                    if self.last_face_detections:
                        self._trigger_event("face", frame)
                except Exception as e:
                    print(f"[VideoWidget] 人脸检测异常: {e}")
                    # 异常时清空缓存，避免用过期结果绘制
                    self.last_face_detections = []

            if self.motion_interval > 0 and (self.frame_counter % self.motion_interval == 0) and self.motion_engine:
                try:
                    self.last_motion_rects = self.motion_engine.detect(frame)
                    if self.last_motion_rects and self.motion_alarm:
                        self._trigger_event("motion", frame)
                except Exception as e:
                    print(f"[VideoWidget] 运动检测异常: {e}")
                    self.last_motion_rects = []

            # 绘制（使用缓存结果）
            try:
                for det in self.last_face_detections:
                    x1, y1, x2, y2 = det['bbox']
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                for (x, y, w, h) in self.last_motion_rects:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
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
                    scaled = pix.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.video_label.setPixmap(scaled)
                else:
                    self.video_label.setPixmap(pix)
            except Exception as e:
                print(f"[VideoWidget] 渲染帧异常: {e}")

            # 录像
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
                    scaled = self.current_pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
        self.motion_engine = None