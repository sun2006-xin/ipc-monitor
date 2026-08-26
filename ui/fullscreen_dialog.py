from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
import weakref

class FullscreenDialog(QDialog):
    def __init__(self, video_widget, parent=None):
        super().__init__(parent)
        # 构造时安全地读取标题，避免 widget 已被销毁
        title = "全屏预览"
        try:
            title = "全屏预览 - " + video_widget.name_label.text()
        except Exception:
            pass
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(800, 600)

        # ✅ 使用弱引用保存 video_widget，避免对方已被销毁时仍持有强引用 → 野指针闪退
        #    当外部布局切换/删除设备导致 VideoWidget 被 deleteLater 时，弱引用会自动返回 None
        self._video_widget_ref = weakref.ref(video_widget)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #0d1117;")
        layout.addWidget(self.image_label)

        # 信息栏：在构造时一次性读取快照，避免后续每次刷新访问可能已销毁的对象
        try:
            info_text = (
                f"名称: {video_widget.device_info.get('name', '未知')} | "
                f"IP: {video_widget.device_info.get('ip', 'N/A')} | "
                f"状态: {'在线' if video_widget.device_info.get('online') else '离线'}"
            )
        except Exception:
            info_text = "信息不可用"
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #a0aec0; padding: 5px;")
        layout.addWidget(info_label)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_image)
        self.timer.start(30)
        self._closing = False

    def update_image(self):
        # ✅ 关闭或销毁过程中不再更新
        if getattr(self, '_closing', False):
            return
        # ✅ 从弱引用取对象，如果对象已被销毁 → video_widget is None
        video_widget = self._video_widget_ref()
        if video_widget is None:
            # 引用对象已被销毁，停止刷新并提示用户
            self.timer.stop()
            self.image_label.clear()
            self.image_label.setText("⚠️ 视频源已断开，请关闭窗口")
            return
        # ✅ VideoWidget 自身标记了 destroying（在 clear/析构中）
        if getattr(video_widget, '_destroying', False):
            self.timer.stop()
            self.image_label.clear()
            self.image_label.setText("⚠️ 视频源正在关闭，请关闭窗口")
            return
        try:
            pixmap = video_widget.current_pixmap
        except Exception:
            pixmap = None
        if pixmap is None:
            return
        try:
            label_size = self.image_label.size()
            if label_size.width() <= 0 or label_size.height() <= 0:
                return
            # ✅ 深拷贝一份 pixmap 再缩放，避免和原 widget 的 current_pixmap 有隐式共享冲突
            scaled = QPixmap(pixmap).scaled(
                label_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        except Exception as e:
            # UI 渲染任何异常都不能让对话框崩溃
            print(f"[FullscreenDialog] 更新画面异常: {e}")

    def resizeEvent(self, event):
        try:
            self.update_image()
        except Exception:
            pass
        super().resizeEvent(event)

    def closeEvent(self, event):
        self._closing = True
        try:
            if self.timer:
                self.timer.stop()
        except Exception:
            pass
        # 断开弱引用，帮助 GC
        self._video_widget_ref = None
        event.accept()