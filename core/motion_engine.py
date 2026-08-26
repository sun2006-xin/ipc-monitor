import cv2
import numpy as np

class MotionEngine:
    def __init__(self, min_area=1500):
        self.min_area = min_area
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)
        self.kernel = np.ones((7,7), np.uint8)

    def detect(self, frame):
        fgmask = self.bg_subtractor.apply(frame)
        fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, self.kernel)
        contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rects = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > self.min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                if w>20 and h>20:
                    rects.append((x,y,w,h))
        return rects

    def draw_rects(self, frame, rects, color=(0,0,255)):
        for (x,y,w,h) in rects:
            cv2.rectangle(frame, (x,y), (x+w, y+h), color, 2)
        return frame