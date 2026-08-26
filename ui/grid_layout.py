from PyQt5.QtWidgets import QWidget, QGridLayout
from PyQt5.QtCore import Qt
from ui.video_widget import VideoWidget

class GridLayoutWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = 1
        self.cols = 1
        self.channels = []
        self.grid = QGridLayout()
        # UI 紧凑化：通道与通道之间不要肉眼可见大空隙（默认 4/4 仍有明显缝，降到 2/2）
        self.grid.setContentsMargins(2, 2, 2, 2)
        self.grid.setSpacing(2)
        self.setLayout(self.grid)

    def set_grid(self, rows, cols):
        # ✅ 布局切换前先安全清理旧通道：
        #    1) clear() → 标记 _destroying=True + 停 timer + 释放资源 + 断开信号
        #    2) removeWidget → 从布局树脱钩
        #    3) setParent(None) → 解除父子关系，防止父对象析构时重复 delete
        #    4) deleteLater → 让事件循环安全销毁
        # 若直接 deleteLater，timer 的 timeout 信号可能已在事件队列中，
        # 会在 widget 半析构状态时调用 update_frame → SIGSEGV 闪退
        old_channels = list(self.channels)
        self.channels.clear()
        for ch in old_channels:
            try:
                # 先断开，避免任何外部槽继续回调
                try:
                    ch.event_triggered.disconnect()
                except (TypeError, RuntimeError):
                    pass
                try:
                    ch.double_clicked.disconnect()
                except (TypeError, RuntimeError):
                    pass
                # 停 timer、释放 VideoCapture，让对象进入"静止"状态
                ch.clear()
                # 从布局和父子关系脱钩
                self.grid.removeWidget(ch)
                ch.setParent(None)
                # 最后再调度延迟删除
                ch.deleteLater()
            except Exception as e:
                # 即使清理失败也不能让 set_grid 抛异常 → 闪退
                print(f"[GridLayoutWidget] 清理旧通道异常: {e}")
                try:
                    self.grid.removeWidget(ch)
                    ch.deleteLater()
                except Exception:
                    pass

        self.rows = rows
        self.cols = cols
        for r in range(rows):
            for c in range(cols):
                ch = VideoWidget(f"通道 {r*cols+c+1}")
                self.grid.addWidget(ch, r, c)
                self.channels.append(ch)

    def get_channel(self, index):
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return None

    def count(self):
        return len(self.channels)