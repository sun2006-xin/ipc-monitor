import threading
import time
import cv2
from queue import Queue
from PyQt5.QtCore import QThread, pyqtSignal

class VideoThread(QThread):
    frame_ready = pyqtSignal(object)
    status_changed = pyqtSignal(bool)

    def __init__(self, rtsp_url, fps=15):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.fps = fps
        self.interval = 1.0 / fps
        self.running = False
        self.cap = None
        self.lock = threading.Lock()
        self.frame_queue = Queue(maxsize=5)

    def run(self):
        self.running = True
        self.cap = cv2.VideoCapture(self.rtsp_url)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if not self.cap.isOpened():
            self.status_changed.emit(False)
            self.running = False
            return
        self.status_changed.emit(True)

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                self.cap.release()
                self.cap = cv2.VideoCapture(self.rtsp_url)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                if not self.cap.isOpened():
                    self.status_changed.emit(False)
                    time.sleep(1)
                    continue
                else:
                    self.status_changed.emit(True)
                continue
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass
            self.frame_queue.put(frame)
            time.sleep(self.interval)

    def stop(self):
        self.running = False
        with self.lock:
            if self.cap:
                self.cap.release()
                self.cap = None
        self.wait()

    def get_frame(self, timeout=0.03):
        try:
            return self.frame_queue.get(timeout=timeout)
        except:
            return None

    def __del__(self):
        self.stop()