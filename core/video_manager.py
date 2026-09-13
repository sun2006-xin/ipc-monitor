from .capture_thread import CaptureThread


class VideoThread(CaptureThread):
    """Backward-compatible name for callers using the old video manager."""

    def __init__(self, rtsp_url, fps=15, parent=None):
        super().__init__(rtsp_url, fps=fps, parent=parent)

    def get_frame(self, timeout=0.03):
        # The latest-frame design intentionally does not block the UI.
        return self.get_latest_frame()
