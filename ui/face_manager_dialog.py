import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QMessageBox,
    QHeaderView, QInputDialog, QProgressDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
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
        self.btn_add = QPushButton("添加（从当前画面抓取）")
        self.btn_add.clicked.connect(self.add_from_video)
        self.btn_delete = QPushButton("删除选中")
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh_table)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        # ✅ recognizer 为 None 时直接禁用相关按钮，防止后续操作崩溃
        if self.recognizer is None:
            self.btn_add.setEnabled(False)
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
        if self.recognizer is None:
            QMessageBox.warning(self, "提示", "人脸识别模块未加载，无法注册")
            return
        if not self.video_widget:
            QMessageBox.warning(self, "提示", "请先连接摄像头")
            return
        # ✅ 如果 video_widget 已经在销毁流程中，直接返回
        if getattr(self.video_widget, '_destroying', False):
            QMessageBox.warning(self, "提示", "当前视频源已断开")
            return
        frame = self.video_widget.current_frame
        if frame is None:
            QMessageBox.warning(self, "提示", "没有视频帧")
            return
        if self.video_widget.face_engine is None:
            QMessageBox.warning(self, "提示", "人脸检测引擎未加载")
            return

        try:
            detections = self.video_widget.face_engine.detect(frame)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"人脸检测失败: {e}")
            return
        if not detections:
            QMessageBox.warning(self, "提示", "未检测到人脸")
            return
        x1, y1, x2, y2 = detections[0]['bbox']
        # ✅ 防止坐标越界（负坐标/超过图尺寸 → 切片空图 → 后续注册流程崩溃）
        fh, fw = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(fw, x2), min(fh, y2)
        if x2 <= x1 or y2 <= y1:
            QMessageBox.warning(self, "提示", "人脸区域无效")
            return
        face_img = frame[y1:y2, x1:x2]
        if face_img.size == 0:
            QMessageBox.warning(self, "提示", "人脸区域为空")
            return
        # 转换为 RGB
        try:
            face_img_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"图像转换失败: {e}")
            return

        progress = QProgressDialog("正在提取人脸特征...", "取消", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)  # dlib 提取时无法中断，避免点取消后留下 thread
        progress.show()
        QApplication.processEvents()

        # ✅ 如果已有 extract_thread，先断开旧连接避免 lambda 重复
        if self.extract_thread is not None:
            try:
                self.extract_thread.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.extract_thread = None

        self.extract_thread = ExtractThread(self.recognizer, face_img_rgb)
        self.extract_thread.finished.connect(
            lambda enc, err, prog=progress: self.on_extract_finished(enc, err, prog)
        )
        self.extract_thread.start()

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
            QMessageBox.warning(self, "错误", "识别器未加载")
            return
        if error:
            QMessageBox.warning(self, "错误", f"特征提取失败: {error}")
            return
        if encoding is None:
            QMessageBox.warning(self, "提示", "无法提取人脸特征")
            return

        name, ok = QInputDialog.getText(self, "输入姓名", "请输入该人脸对应的姓名：")
        if ok and name.strip():
            try:
                all_names = self.recognizer.get_all_names()
            except Exception:
                all_names = []
            if name.strip() in all_names:
                QMessageBox.warning(self, "提示", "该姓名已注册")
                return
            try:
                self.recognizer.register_face(name.strip(), encoding)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"注册失败: {e}")
                return
            self.refresh_table()
            QMessageBox.information(self, "成功", f"已注册 {name.strip()}")

    def delete_selected(self):
        if self.recognizer is None:
            QMessageBox.warning(self, "提示", "识别器未加载，无法删除")
            return
        selected = self.table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "提示", "请先选择一行")
            return
        # ✅ item 可能为 None（例如 recognizer 为 None 时的提示行没有第 0 列 item）
        item = self.table.item(selected, 0)
        if item is None:
            QMessageBox.warning(self, "提示", "该行不可操作")
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
                QMessageBox.warning(self, "错误", f"删除失败: {e}")
                return
            self.refresh_table()

    def closeEvent(self, event):
        self._closing = True
        # ✅ 关闭前如果 extract 线程仍在跑，等一下避免残留线程引用 UI 对象
        if self.extract_thread is not None and self.extract_thread.isRunning():
            try:
                self.extract_thread.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            # 不强制 terminate（dlib 不安全），只把引用置空由系统回收
            self.extract_thread = None
        event.accept()