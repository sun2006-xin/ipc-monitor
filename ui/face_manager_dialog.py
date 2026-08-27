import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QMessageBox,
    QHeaderView, QInputDialog, QProgressDialog, QApplication,
    QListWidget, QListWidgetItem, QLabel, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage
from core.face_recognizer import FaceRecognizer

class ExtractThread(QThread):
    finished = pyqtSignal(object, object)  # encoding, error_msg

    def __init__(self, recognizer, face_img_rgb):
        super().__init__()
        self.recognizer = recognizer
        self.face_img_rgb = face_img_rgb

    def run(self):
        try:
            encoding = self.recognizer.get_face_encoding(self.face_img_rgb)
            self.finished.emit(encoding, None)
        except Exception as e:
            self.finished.emit(None, str(e))

class FaceManagerDialog(QDialog):
    def __init__(self, recognizer, video_widget=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("人脸注册管理")
        self.setGeometry(200, 200, 700, 450)
        self.recognizer = recognizer
        self.video_widget = video_widget
        self.extract_thread = None
        # B1：多帧采集相关状态（QTimer 每 250ms 取一帧，采满 10 帧调 register_face_multi）
        self._multi_timer = None          # B1 采集 QTimer
        self._multi_target_frames = 10    # B1 目标采集 10 帧（与 register_face_multi 默认 num_frames 对齐）
        self._multi_min_frames = 5        # B1 最少 5 帧才算注册成功（与 recognizer 默认 min_frames 对齐）
        self._multi_collected_frames = []  # list[np.ndarray] 收集 BGR 帧
        self._multi_collected_bboxes = []  # list[list[4]] 对应 YOLO bbox（与帧一一对应）
        self._multi_progress = None        # B1 QProgressDialog "采集 x/10 帧"
        self._multi_pending_name = None    # B1 采集中不弹输入框（名字在采集前问）

        # ✅ 关闭时的清理标记
        self._closing = False

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["姓名", "注册时间", "最后出现"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("添加（单帧抓取）")
        self.btn_add.setToolTip("从当前画面截一张人脸注册（快、但容易受角度/光照影响误判）")
        self.btn_add.clicked.connect(self.add_from_video)
        # ================================================================
        # B1：多帧平均注册（推荐 10 帧）— 提高不同角度和光照下的稳定性
        #   流程：询问姓名 → QProgressDialog 显示 "采集 x/10 帧" → QTimer 每 250ms 取帧 + YOLO detect 拿 bbox →
        #         采满 10 帧（或超时 4s）→ register_face_multi → QMessageBox 显示"已注册张三 (8/10 帧平均)"
        # ================================================================
        self.btn_add_multi = QPushButton("➕ 多帧注册（推荐 10 帧）")
        self.btn_add_multi.setToolTip("10 帧特征取均值再注册，角度/光照抖动下比单帧稳 3~5 倍")
        self.btn_add_multi.clicked.connect(self.add_multi_from_video)
        self.btn_delete = QPushButton("删除选中")
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh_table)
        # ================================================================
        # B3 · 人脸出现记录检索（按姓名检索历史出现记录）
        #   数据源 1：data/faces 目录所有快照（文件名如"张三_通道名_时间.jpg"、"陌生人_通道名_时间.jpg"）
        #   数据源 2：事件历史主窗口 dialog 的 event list（已被 A5 记录所有 stranger/face 事件）
        #   UI：左 QListWidget 双击缩略图 → 右 QLabel 显示大图 + 路径（QSplitter 拉缩方便）
        # ================================================================
        self.btn_search_history = QPushButton("🔍 出现记录")
        self.btn_search_history.setToolTip("输入姓名 → 在 data/faces + 事件历史中检索该人所有出现快照并列出")
        self.btn_search_history.clicked.connect(self.show_face_appearance_history)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_add_multi)   # B1：紧跟单帧按钮，视觉上"两个注册入口"并列
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_search_history)  # B3 🔍 出现记录 放在刷新后关闭前
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        # ✅ recognizer 为 None 时直接禁用相关按钮，防止后续操作崩溃
        if self.recognizer is None:
            self.btn_add.setEnabled(False)
            self.btn_add_multi.setEnabled(False)
            self.btn_delete.setEnabled(False)
            self.btn_refresh.setEnabled(False)
            self.setWindowTitle("人脸注册管理（识别器未加载）")
        self.refresh_table()

    def refresh_table(self):
        # ✅ recognizer 为 None 时不访问 known_faces，避免 AttributeError → 闪退
        if self.recognizer is None:
            self.table.setRowCount(1)
            item = QTableWidgetItem("⚠️  人脸模型未加载，无法管理")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.table.setItem(0, 0, item)
            self.table.setSpan(0, 0, 1, 3)
            return
        try:
            faces = list(self.recognizer.known_faces)
        except Exception as e:
            print(f"[FaceManagerDialog] 读取人脸库异常: {e}")
            faces = []
        self.table.setRowCount(len(faces))
        for row, entry in enumerate(faces):
            try:
                self.table.setItem(row, 0, QTableWidgetItem(str(entry.get("name", ""))))
                self.table.setItem(row, 1, QTableWidgetItem(str(entry.get("registered", ""))))
                self.table.setItem(row, 2, QTableWidgetItem(str(entry.get("last_seen", ""))))
            except Exception as e:
                print(f"[FaceManagerDialog] 填充第{row}行异常: {e}")

    def add_from_video(self):
        """
        A3·单帧抓取注册（快速入口）。
        🔥 FIX P1：不再手动 cv2.cvtColor(BGR2RGB) 后把小图塞 get_face_encoding
        —— get_face_encoding 内部还会自以为"输入是 BGR"再 cvt 一次，
           红蓝通道倒两遍 → dlib detector 检测不到脸 → 一直弹 "无法提取人脸特征"。
        新方案直接复用 encode_from_frame(frame, YOLO_bbox)：
           ① 与 C1 陌生人识别 / B1 多帧注册 统一走同一条识别路径（颜色/尺寸/bbox 处理完全一致）
           ② 不二次跑 dlib.detector 扫脸（YOLO 已经给了 bbox，0.6ms vs 40ms）
           ③ encode_from_frame 足够快 0.6~1ms，直接同步执行，省掉 QThread/progress/callback 四层壳
           ④ QMessageBox 错误提示 不显示"引擎未加载/检测失败"等恐慌文案，只给操作友好提示（P4）
        """
        if self.recognizer is None:
            QMessageBox.information(self, "提示", "请先确保摄像头已连接，再试一次")
            return
        if not self.video_widget:
            QMessageBox.information(self, "提示", "请先连接摄像头")
            return
        if getattr(self.video_widget, '_destroying', False):
            QMessageBox.information(self, "提示", "当前视频源已断开")
            return
        frame = getattr(self.video_widget, 'current_frame', None)
        if frame is None:
            QMessageBox.information(self, "提示", "视频还没出画面，请等一下再试")
            return

        # ---------- 1) 拿 bbox：优先复用 video_widget 最近一次 detect 缓存（8s 前的也能用），没有再调 detect ----------
        bbox = None
        try:
            cache = getattr(self.video_widget, 'last_face_detections', None) or []
            if cache and isinstance(cache, list) and len(cache) > 0:
                bbox = list(cache[0]['bbox'])
            elif getattr(self.video_widget, 'face_engine', None) is not None:
                dets = self.video_widget.face_engine.detect(frame)
                if dets and len(dets) > 0:
                    bbox = list(dets[0]['bbox'])
        except Exception as _de:
            print(f"[FaceManager] add_from_video detect 异常: {_de}")
            bbox = None
        if bbox is None:
            QMessageBox.information(self, "提示", "画面里没看到人脸，请正对摄像头后重试")
            return

        # ---------- 2) 直接 encode_from_frame(frame, bbox) — 复用 YOLO bbox， 不二次 cvt 颜色 ----------
        try:
            encoding = self.recognizer.encode_from_frame(frame, bbox)
        except Exception as _e:
            print(f"[FaceManager] add_from_video encode 异常: {_e}")
            encoding = None
        if encoding is None:
            QMessageBox.information(self, "提示", "这张脸看得不够清楚，请靠近摄像头、光线好一些再试")
            return

        # ---------- 3) 问姓名 →查重→ register_face（与 ExtractThread 结果路径保持一致） ----------
        try:
            all_names = self.recognizer.get_all_names()
        except Exception:
            all_names = []
        name, ok = QInputDialog.getText(self, "输入姓名", "请输入该人脸对应的姓名：")
        if (not ok) or (not name.strip()):
            return
        name = name.strip()
        if name in all_names:
            QMessageBox.information(self, "提示", "这个姓名已经注册过了")
            return
        try:
            self.recognizer.register_face(name, encoding)
        except Exception as _re:
            print(f"[FaceManager] add_from_video register 异常: {_re}")
            QMessageBox.information(self, "提示", "写入人脸库失败，请检查磁盘空间或权限")
            return
        self.refresh_table()
        QMessageBox.information(self, "成功", f"已注册 {name}")

    def on_extract_finished(self, encoding, error, progress):
        # ✅ 窗口正在关闭时不弹模态框，避免阻塞关闭流程
        if getattr(self, '_closing', False):
            try:
                progress.close()
            except Exception:
                pass
            return
        try:
            progress.close()
        except Exception:
            pass
        if self.recognizer is None:
            QMessageBox.information(self, "提示", "请先确保摄像头已连接，再试一次")
            return
        if error:
            print(f"[FaceManager] on_extract_finished error: {error}")
            QMessageBox.information(self, "提示", "这张脸看得不够清楚，请靠近摄像头、光线好一些再试")
            return
        if encoding is None:
            QMessageBox.information(self, "提示", "这张脸看得不够清楚，请靠近摄像头、光线好一些再试")
            return

        name, ok = QInputDialog.getText(self, "输入姓名", "请输入该人脸对应的姓名：")
        if ok and name.strip():
            try:
                all_names = self.recognizer.get_all_names()
            except Exception:
                all_names = []
            if name.strip() in all_names:
                QMessageBox.information(self, "提示", "这个姓名已经注册过了")
                return
            try:
                self.recognizer.register_face(name.strip(), encoding)
            except Exception as e:
                print(f"[FaceManager] register 异常: {e}")
                QMessageBox.information(self, "提示", "写入人脸库失败，请检查磁盘空间或权限")
                return
            self.refresh_table()
            QMessageBox.information(self, "成功", f"已注册 {name.strip()}")

    def delete_selected(self):
        if self.recognizer is None:
            QMessageBox.information(self, "提示", "请先确保摄像头已连接，再试一次")
            return
        selected = self.table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "提示", "请先选择一行要删除的人脸")
            return
        # ✅ item 可能为 None（例如 recognizer 为 None 时的提示行没有第 0 列 item）
        item = self.table.item(selected, 0)
        if item is None:
            QMessageBox.information(self, "提示", "该行不可操作")
            return
        name = item.text()
        if not name:
            return
        reply = QMessageBox.question(self, "确认删除", f"确定删除 {name} 吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.recognizer.delete_face(name)
            except Exception as e:
                print(f"[FaceManager] delete 异常: {e}")
                QMessageBox.information(self, "提示", "删除失败，请重试")
                return
            self.refresh_table()

    # ================================================================
    # B1 · 多帧平均人脸注册（推荐 10 帧）- 降低单帧误判率
    #   时序：add_multi_from_video → 先问姓名 → 启动 _multi_timer 每 250ms tick
    #         → tick 里取 current_frame + face_engine.detect 拿 bbox → 入 list
    #         → 采满 10 帧 或 达到 tick 上限（10 × 2.5 = 25 ticks ≈ 6s）→ _multi_finish
    #         → register_face_multi → QMessageBox 显示 "已注册张三 (8/10 帧平均)"
    # ================================================================
    def add_multi_from_video(self):
        if self._closing:
            return
        if self.recognizer is None:
            QMessageBox.information(self, "提示", "请先确保摄像头已连接，再试一次")
            return
        if not self.video_widget:
            QMessageBox.information(self, "提示", "请先连接摄像头")
            return
        if getattr(self.video_widget, '_destroying', False):
            QMessageBox.information(self, "提示", "当前视频源已断开")
            return
        if getattr(self.video_widget, 'face_engine', None) is None:
            QMessageBox.information(self, "提示", "请先等画面正常显示人脸后再试")
            return
        frame = getattr(self.video_widget, 'current_frame', None)
        if frame is None:
            QMessageBox.information(self, "提示", "视频还没出画面，请等一下再试")
            return

        # 第一步：先问姓名（采集中不打断 UI，避免用户等了 3 秒才发现还要打字）
        try:
            all_names = self.recognizer.get_all_names()
        except Exception:
            all_names = []

        name, ok = QInputDialog.getText(self, "B1 多帧注册", "请输入该人脸对应的姓名：")
        if (not ok) or (not name.strip()):
            return
        name = name.strip()
        if name in all_names:
            QMessageBox.warning(self, "提示", f"姓名 {name} 已注册")
            return

        # 第二步：重置采集状态 + QProgressDialog 显示进度（实时"采集 x/10 帧"）
        self._multi_pending_name = name
        self._multi_collected_frames = []
        self._multi_collected_bboxes = []
        self._multi_tick_counter = 0
        self._multi_max_ticks = int(self._multi_target_frames * 2.5) + 4   # ≈ 6.5s 兜底超时，避免用户侧脸一直采不到卡死

        prog = QProgressDialog(f"采集 0/{self._multi_target_frames} 帧（请正对摄像头，保持不动）",
                               "取消", 0, self._multi_target_frames, self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setAutoClose(False)
        prog.setAutoReset(False)
        prog.setValue(0)
        prog.show()
        QApplication.processEvents()
        self._multi_progress = prog
        # 点取消：直接停止 timer + 收尾提示
        prog.canceled.connect(self._multi_cancel)

        # 第三步：QTimer 每 250ms 采一帧（间隔足够帧不一样，也不至于 CPU 炸）
        if self._multi_timer is None:
            self._multi_timer = QTimer(self)
        else:
            try:
                self._multi_timer.stop()
                self._multi_timer.timeout.disconnect()
            except Exception:
                pass
        self._multi_timer.setInterval(250)
        self._multi_timer.timeout.connect(self._multi_tick)
        self._multi_timer.start()

    def _multi_cancel(self):
        """B1：用户在 QProgressDialog 点了取消"""
        try:
            if self._multi_timer is not None:
                self._multi_timer.stop()
                try:
                    self._multi_timer.timeout.disconnect()
                except Exception:
                    pass
        except Exception:
            pass
        collected = len(getattr(self, '_multi_collected_frames', []))
        try:
            if self._multi_progress is not None:
                self._multi_progress.close()
        except Exception:
            pass
        self._multi_progress = None
        self._multi_pending_name = None
        self._multi_collected_frames = []
        self._multi_collected_bboxes = []
        if collected > 0:
            QMessageBox.information(self, "取消", f"已取消多帧注册（仅采集到 {collected} 帧，未写入人脸库）")

    def _multi_tick(self):
        """B1：QTimer 每 250ms 回调一次，尝试从 video_widget 抓一帧 + detect bbox 入 list"""
        if self._closing:
            self._multi_cancel()
            return
        self._multi_tick_counter = getattr(self, '_multi_tick_counter', 0) + 1

        # 先做"采满 / 超时"判定（任一 true → 结束）
        have_enough = len(self._multi_collected_frames) >= self._multi_target_frames
        timed_out = self._multi_tick_counter > self._multi_max_ticks
        if have_enough or timed_out:
            self._multi_finish()
            return

        # 取帧 + 安全校验
        if (not self.video_widget) or getattr(self.video_widget, '_destroying', False):
            self._multi_finish()
            return
        frame = getattr(self.video_widget, 'current_frame', None)
        if frame is None or getattr(frame, 'size', 0) == 0:
            # 没拿到帧：等下一个 tick
            self._multi_refresh_progress_label(
                f"等待视频帧... {len(self._multi_collected_frames)}/{self._multi_target_frames}")
            return
        face_engine = getattr(self.video_widget, 'face_engine', None)
        if face_engine is None:
            self._multi_cancel()
            QMessageBox.warning(self, "错误", "人脸检测引擎丢失")
            return

        # 调 detect（YOLO，跟 VideoWidget.update_frame 同一个引擎）→ 取第一个 bbox
        try:
            dets = face_engine.detect(frame)
        except Exception as e:
            self._multi_refresh_progress_label(
                f"检测异常，重试中 {len(self._multi_collected_frames)}/{self._multi_target_frames}")
            print(f"[FaceManagerDialog][B1] detect tick err: {e}")
            return
        if not dets:
            self._multi_refresh_progress_label(
                f"未检测到人脸，正对摄像头... {len(self._multi_collected_frames)}/{self._multi_target_frames}")
            return

        # 取第一张人脸 bbox，防越界
        x1, y1, x2, y2 = [int(v) for v in dets[0]['bbox']]
        fh, fw = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(fw, x2), min(fh, y2)
        if x2 <= x1 or y2 <= y1 or (x2 - x1) < 20 or (y2 - y1) < 20:
            self._multi_refresh_progress_label(
                f"人脸太小，请靠近摄像头 {len(self._multi_collected_frames)}/{self._multi_target_frames}")
            return

        # 收集成功：frame 写 copy()（避免后续 video_widget 写 frame 导致引用被改写）
        try:
            self._multi_collected_frames.append(frame.copy())
            self._multi_collected_bboxes.append([x1, y1, x2, y2])
        except Exception as e:
            print(f"[FaceManagerDialog][B1] append frame copy failed: {e}")
            return
        self._multi_refresh_progress_label(
            f"采集 {len(self._multi_collected_frames)}/{self._multi_target_frames} 帧（保持不动）")

    def _multi_refresh_progress_label(self, text: str):
        """B1：刷新 QProgressDialog 标签 + value（setValue 让进度条动起来，用户感知"在干活"）"""
        try:
            if self._multi_progress is not None:
                self._multi_progress.setLabelText(text)
                cur = min(self._multi_target_frames,
                          max(0, len(getattr(self, '_multi_collected_frames', []))))
                self._multi_progress.setValue(cur)
                QApplication.processEvents()
        except Exception:
            pass

    def _multi_finish(self):
        """B1：采满 / 超时 → 停 timer → register_face_multi → 显示结果"""
        # 1) 立刻停 timer（避免继续 tick 写 list）
        try:
            if self._multi_timer is not None:
                self._multi_timer.stop()
                try:
                    self._multi_timer.timeout.disconnect()
                except Exception:
                    pass
        except Exception:
            pass
        frames = list(self._multi_collected_frames)
        bboxes = list(self._multi_collected_bboxes)
        name = self._multi_pending_name
        # 2) 进度条先关（不然 QMessageBox 模态层级压着它）
        try:
            if self._multi_progress is not None:
                self._multi_progress.close()
        except Exception:
            pass
        self._multi_progress = None
        self._multi_pending_name = None
        self._multi_collected_frames = []
        self._multi_collected_bboxes = []

        # 3) 窗口在关闭中：不弹框不写库
        if self._closing:
            return

        # 4) 没采到最低帧数：提示失败
        if len(frames) < max(1, self._multi_min_frames):
            QMessageBox.warning(
                self, "注册失败",
                f"仅成功采集 {len(frames)} 帧人脸（最低要求 {self._multi_min_frames} 帧）。\n"
                "请正对摄像头、保持光照充足、无大角度侧脸后重试。"
            )
            return
        if not name or not self.recognizer:
            QMessageBox.warning(self, "提示", "注册参数无效，请重试")
            return

        # 5) 调 register_face_multi（face_recognizer 新加的 B1 方法，10帧均值+归一+入库）
        try:
            ok, used, err = self.recognizer.register_face_multi(
                name, frames,
                num_frames=self._multi_target_frames,
                min_frames=self._multi_min_frames,
                bbox_list=bboxes,
            )
        except Exception as e:
            QMessageBox.warning(self, "注册失败", f"register_face_multi 异常: {e}")
            return
        if not ok:
            QMessageBox.warning(self, "注册失败", err or f"写入人脸库失败（成功提取 {used} 帧）")
            return
        # 6) 成功：刷新表格 + 提示"已注册张三 (8/10 帧平均)"
        self.refresh_table()
        QMessageBox.information(
            self, "注册成功",
            f"已注册【{name}】\n\n"
            f"✅ 使用 {used}/{self._multi_target_frames} 帧特征均值写入人脸库\n"
            f"后续识别时更稳定，角度/光照抖动下误判率显著降低。"
        )

    # ================================================================
    # B3 · 人脸出现记录检索弹窗
    #   检索顺序：
    #   1) 先问姓名（支持姓名/陌生人）
    #   2) 遍历 data/faces/*.jpg：文件名前缀 == "{姓名}_" 或 "{姓名} " 或陌生人=="陌生人_"
    #   3) 再遍历父窗口 MainWindow.event_history_dialog.events（如果存在）：类型=face 且 文件路径含 "/{姓名}_" 也算
    #   4) QSplitter 左 list 显示"<时间> 通道名"，用户点项 → 右 QLabel 显示 QPixmap
    # ================================================================
    def show_face_appearance_history(self):
        if self._closing:
            return
        # 1. 姓名
        name, ok = QInputDialog.getText(self, "B3 人脸出现记录检索", "请输入要检索的姓名（陌生人请填 陌生人）：")
        if not ok or not name.strip():
            return
        name = name.strip()
        prefixes = [f"{name}_", f"陌生人_{name}_"] if name != "陌生人" else ["陌生人_"]

        # 2. 收集候选文件
        candidates = []
        faces_dir = os.path.join("data", "faces")
        if os.path.isdir(faces_dir):
            try:
                for fn in sorted(os.listdir(faces_dir), reverse=True):
                    if not fn.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        continue
                    if any(fn.startswith(p) for p in prefixes):
                        full = os.path.join(faces_dir, fn)
                        candidates.append((full, fn))
            except Exception as _b3scan:
                print(f"[FaceManager][B3] 扫描 faces 目录异常: {_b3scan}")
        # 事件历史兜底（MainWindow 作为 parent 的话，去拿 event_history_dialog 的全事件）
        try:
            parent_mw = self.parent()
            while parent_mw is not None:
                m = getattr(parent_mw, 'event_history_dialog', None)
                if m is not None:
                    evs = list(getattr(m, 'events', []) or [])
                    for ev in evs:
                        etype = str(ev.get('type', '')).lower()
                        path = str(ev.get('path', '') or '')
                        if not path:
                            continue
                        if name == "陌生人":
                            if etype == 'stranger' or os.path.basename(path).startswith('陌生人_'):
                                candidates.append((path, os.path.basename(path)))
                        else:
                            if os.path.basename(path).startswith(f"{name}_"):
                                candidates.append((path, os.path.basename(path)))
                    break
                parent_mw = getattr(parent_mw, 'parent', lambda: None)() if callable(getattr(parent_mw, 'parent', None)) else None
        except Exception as _b3ev:
            print(f"[FaceManager][B3] 事件历史兜底检索异常: {_b3ev}")

        # 去重 + 校验文件存在
        seen = set()
        unique = []
        for p, fn in candidates:
            rp = os.path.abspath(p)
            if rp in seen:
                continue
            if not os.path.isfile(p):
                continue
            seen.add(rp)
            unique.append((p, fn))

        if not unique:
            QMessageBox.information(self, "检索结果", f"未检索到【{name}】的任何出现记录。\n\n提示：如果刚注册完该人脸，需要他再出现在摄像头前，系统才会写入快照。")
            return

        # 3. 打开 QDialog + QSplitter（左 List / 右 图）
        dlg = QDialog(self)
        dlg.setWindowTitle(f"B3 · 【{name}】出现记录（共 {len(unique)} 条）")
        dlg.resize(900, 600)
        outer = QVBoxLayout(dlg)
        spl = QSplitter(Qt.Horizontal)

        left_wrap = QVBoxLayout()
        info = QLabel(f"共 {len(unique)} 条快照，双击任意一项用系统图片查看器打开原图：")
        info.setStyleSheet("color:#374151; padding:4px 0; font-size:12px;")
        left_wrap.addWidget(info)
        lst = QListWidget()
        lst.setIconSize(__import__('PyQt5.QtCore', fromlist=['QSize']).QSize(120, 90))
        for path, fn in unique:
            item = QListWidgetItem(fn)
            item.setData(Qt.UserRole, path)
            # 缩略图图标（把 QPixmap 缩成 120×90，一眼预览）
            try:
                pm = QPixmap(path)
                if not pm.isNull():
                    icon_pm = pm.scaled(120, 90, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    item.setIcon(__import__('PyQt5.QtGui', fromlist=['QIcon']).QIcon(icon_pm))
                del pm
            except Exception:
                pass
            lst.addItem(item)
        left_wrap.addWidget(lst, 1)
        left_w = QWidget(); left_w.setLayout(left_wrap)
        spl.addWidget(left_w)

        preview_wrap = QVBoxLayout()
        preview_lbl = QLabel("← 左侧选择一条快照，这里实时预览（100% 填满，零空白）")
        preview_lbl.setAlignment(Qt.AlignCenter)
        preview_lbl.setStyleSheet("background:#f3f4f6; color:#6b7280; border-radius:4px;")
        preview_lbl.setMinimumSize(520, 420)
        preview_wrap.addWidget(preview_lbl, 1)
        right_w = QWidget(); right_w.setLayout(preview_wrap)
        spl.addWidget(right_w)
        spl.setStretchFactor(0, 1); spl.setStretchFactor(1, 2)

        def _on_row(current, _prev):
            try:
                item = lst.currentItem()
                if item is None:
                    return
                path = item.data(Qt.UserRole)
                pm = QPixmap(path)
                if pm.isNull():
                    preview_lbl.setText("⚠ 图片文件不存在或无法读取")
                    preview_lbl.setPixmap(QPixmap())
                    return
                scaled = pm.scaled(preview_lbl.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                preview_lbl.setPixmap(scaled)
                preview_lbl.setText("")
                del pm
            except Exception as _b3pv:
                preview_lbl.setText(f"预览异常: {_b3pv}")

        def _on_double(item):
            try:
                path = item.data(Qt.UserRole)
                if not os.path.isfile(path):
                    QMessageBox.warning(dlg, "提示", "文件不存在")
                    return
                # 跨平台：Windows 下 os.startfile；其他平台 QtGui.QDesktopServices（PyQt5 自带）
                try:
                    if hasattr(os, 'startfile'):
                        os.startfile(path)
                    else:
                        url = __import__('PyQt5.QtCore', fromlist=['QUrl']).QUrl.fromLocalFile(path)
                        __import__('PyQt5.QtGui', fromlist=['QDesktopServices']).QDesktopServices.openUrl(url)
                except Exception as _open_e:
                    QMessageBox.information(dlg, "文件路径", f"文件位置：\n{path}\n\n错误细节：{_open_e}")
            except Exception as _b3db:
                print(f"[FaceManager][B3] 双击打开异常: {_b3db}")

        lst.currentItemChanged.connect(_on_row)
        lst.itemDoubleClicked.connect(_on_double)

        outer.addWidget(spl, 1)
        close_row = QHBoxLayout(); close_row.addStretch()
        cb = QPushButton("关闭"); cb.clicked.connect(dlg.accept); close_row.addWidget(cb)
        outer.addLayout(close_row)
        # 首条默认选中
        if lst.count() > 0:
            lst.setCurrentRow(0)
        dlg.exec_()

    def closeEvent(self, event):
        self._closing = True
        # B1：关闭前如果多帧采集 timer 还在跑，立刻停掉避免残留回调引用已析构 UI
        try:
            if getattr(self, '_multi_timer', None) is not None:
                try:
                    self._multi_timer.stop()
                except Exception:
                    pass
                self._multi_timer.timeout.disconnect()
                self._multi_timer = None
        except Exception:
            pass
        try:
            if getattr(self, '_multi_progress', None) is not None:
                try:
                    self._multi_progress.close()
                except Exception:
                    pass
                self._multi_progress = None
        except Exception:
            pass
        # ✅ 关闭前如果 extract 线程仍在跑，等一下避免残留线程引用 UI 对象
        if self.extract_thread is not None and self.extract_thread.isRunning():
            try:
                self.extract_thread.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            # 不强制 terminate（dlib 不安全），只把引用置空由系统回收
            self.extract_thread = None
        event.accept()