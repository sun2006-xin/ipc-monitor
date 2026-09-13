from PyQt5.QtWidgets import QWidget, QGridLayout, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from ui.video_widget import VideoWidget

# 允许的最大行列（10×10 足够未来扩展，清理旧 stretch 时遍历到这里保证不留残留）
_MAX_GRID_DIM = 10

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
        # -------- 尺寸链贯通（经验155413 + 692281）：容器自身必须 Expanding --------
        # 用户反馈"画面是一个小方块、外面大片白空白"的真凶之一就是外层 GridLayoutWidget 不是 Expanding，
        # 即使 main_window right_layout 给了 stretch=1，Qt 默认 QWidget 的 sizePolicy 是 Preferred/Fixed，
        # 会按最小 sizeHint 收缩，剩下的区域是 GridLayoutWidget 的白色背景 (#ffffff)。
        # 这里强制双向 Expanding，让外层分多少就吞多少。
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(1, 1)   # 防止 Qt 认为"最小尺寸0"直接把整区压扁（防御性）

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

        # ================================================================
        # BUG FIX（Msg "4×4切回单个摄像头会卡主位置不放大沾满" —— 根因已实锤）：
        #   前一次布局 4×4 时 setRowStretch(0..3,1) / setColumnStretch(0..3,1) 写入 QGridLayout 内部缓存，
        #   切回 1×1 只设 rowStretch(0,1)，而 rows>=1、cols>=1 的 3 行3列 stretch=1 "残留还在"，
        #   Qt 的布局算法会按"4行4列都要 1:1 分配比例"来做，1×1 只拿到 1/4×1/4 的左上角，
        #   剩下 3/4 区域被"虚拟的旧行列"占住当空白 → 视觉上就是"卡主位置、放大不了、外面一大片空"。
        # 修法：对 0.._MAX_GRID_DIM 全部行列先 reset stretch=0，再把当前 rows/cols 设成 1，
        #       保证旧布局的 stretch 彻底不参与任何比例分配。
        # ================================================================
        for r in range(_MAX_GRID_DIM):
            self.grid.setRowStretch(r, 0)
        for c in range(_MAX_GRID_DIM):
            self.grid.setColumnStretch(c, 0)
        for r in range(rows):
            self.grid.setRowStretch(r, 1)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

        for r in range(rows):
            for c in range(cols):
                ch = VideoWidget(f"通道 {r*cols+c+1}")
                self.grid.addWidget(ch, r, c)
                self.channels.append(ch)

        # ================================================================
        # 第二道防线（经验 147363：不能靠事件循环"碰运气"刷新，必须在 set_grid 尾部强制重算几何）：
        #   ① grid.activate() 让 QGridLayout 立刻按新 stretch 重新分配几何
        #   ② self.updateGeometry() + 每个 channel updateGeometry()：通知 Qt 父子尺寸链全部失效重算
        #      （经验 939755：子控件不调用 updateGeometry，外层 minSizeHint 可能不更新→看起来卡死）
        #   ③ QTimer.singleShot(0, ...) 下一轮事件循环再补一次 updateGeometry + repaint()，
        #      对付"新建 VideoWidget 的 sizeHint 要等下一轮事件循环才稳定"的 Qt 内部时序坑
        #      （经验 147363 失败经验 3：不要堆 processEvents，挂到确定的 singleShot 一次就够）
        # ================================================================
        self.grid.activate()
        self.updateGeometry()
        for ch in self.channels:
            ch.updateGeometry()
        # 触发外层（main_window right_layout/centralWidget）也重新算几何，避免"主窗口还按旧的 4×4 sizeHint 留空白"
        parent = self.parentWidget()
        while parent is not None:
            try:
                parent.updateGeometry()
            except Exception:
                break
            parent = parent.parentWidget()

        QTimer.singleShot(0, self._post_set_grid_refresh)

    def get_channel(self, index):
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return None

    def count(self):
        return len(self.channels)

    def _post_set_grid_refresh(self):
        """set_grid 后下一轮事件循环的最终几何刷新（经验 147363：避免新建 widget sizeHint 时序导致的"卡死不放大"）"""
        try:
            self.grid.activate()
            self.updateGeometry()
            for ch in self.channels:
                try:
                    ch.updateGeometry()
                    # 经验 847351：video_label 的 pixmap 会影响 sizeHint，让它重新触发 resizeEvent → 重新 scaled(ByExpanding)
                    if hasattr(ch, 'video_label') and ch.video_label is not None:
                        ch.video_label.updateGeometry()
                        # 手动触发一次 resizeEvent（内部带 current_pixmap None 保护），确保切回 1×1 时那一张图立刻占满
                        if hasattr(ch, 'resizeEvent'):
                            from PyQt5.QtGui import QResizeEvent
                            ev = QResizeEvent(ch.size(), ch.size())
                            ch.resizeEvent(ev)
                except Exception:
                    pass
            # 外层父级也统一重算，避免 main_window centralWidget/right_layout 还缓存旧几何
            parent = self.parentWidget()
            while parent is not None:
                try:
                    parent.updateGeometry()
                except Exception:
                    break
                parent = parent.parentWidget()
            self.repaint()
        except Exception as e:
            print(f"[GridLayoutWidget] _post_set_grid_refresh 异常: {e}")