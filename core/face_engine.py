import sys
import os
import cv2
import torch
import numpy as np
from pathlib import Path

# ================================================================
# ✅ YOLOv5 路径兼容策略（原代码硬编码 D:\\ 是闪退隐患之一：用户若没 D 盘或没 yolov5 项目会直接 ImportError）
#    1) 优先使用项目内 yolov5 子目录
#    2) 其次使用当前 main.py 同级目录
#    3) 再退回到硬编码路径 D:\yolov5_project\yolov5
#    路径存在才加入 sys.path，否则 DetectMultiBackend 导入失败 → loaded=False 但不崩溃
# ================================================================
_candidate_paths = [
    Path(__file__).resolve().parent.parent / "yolov5",          # 项目根/yolov5
    Path(__file__).resolve().parent.parent,                     # 项目根（若 yolov5 包直接在项目根内）
    Path.cwd() / "yolov5",
    Path(r"D:\yolov5_project\yolov5"),
]
for _p in _candidate_paths:
    try:
        if _p.exists() and _p.is_dir():
            _p_str = str(_p)
            if _p_str not in sys.path:
                sys.path.insert(0, _p_str)
            break
    except Exception:
        continue

# ✅ 导入也必须 try 保护：就算路径加了，若缺失模块也不能崩
try:
    from models.common import DetectMultiBackend
    from utils.general import non_max_suppression, scale_boxes
    from utils.augmentations import letterbox
    _YOLOV5_OK = True
except Exception as _e:
    print(f"[FaceEngine] ⚠️ YOLOv5 模块导入失败: {_e}")
    DetectMultiBackend = None
    non_max_suppression = None
    scale_boxes = None
    letterbox = None
    _YOLOV5_OK = False

from core.face_recognizer import FaceRecognizer

class FaceEngine:
    def __init__(self, weights_path="best.pt", conf_thres=0.25, device="cpu"):
        self.conf_thres = conf_thres
        self.device = torch.device(device)
        self.img_size = 640
        self.stride = 32
        self.loaded = False
        self.model = None
        self.recognizer = None
        self.names = {}

        # 加载 YOLOv5
        if not _YOLOV5_OK or DetectMultiBackend is None:
            print("[FaceEngine] ❌ YOLOv5 模块不可用，检测功能关闭")
            self.loaded = False
        else:
            try:
                print(f"[FaceEngine] 加载 YOLOv5 模型 ({self.device})...")
                # ✅ weights_path 允许相对路径：以项目根为基准
                wp = Path(weights_path)
                if not wp.is_absolute():
                    base = Path(__file__).resolve().parent.parent
                    wp = base / weights_path
                if not wp.exists():
                    # 再尝试当前工作目录下的相对路径
                    wp2 = Path(weights_path)
                    if not wp2.exists():
                        print(f"[FaceEngine] ❌ 权重文件不存在: {wp}")
                        self.loaded = False
                    else:
                        wp = wp2
                if wp.exists():
                    self.model = DetectMultiBackend(str(wp), device=self.device)
                    self.stride = int(getattr(self.model, 'stride', 32))
                    self.names = getattr(self.model, 'names', {}) or {}
                    self.loaded = True
                    print("[FaceEngine] ✅ YOLOv5 加载成功")
                else:
                    self.loaded = False
            except Exception as e:
                print(f"[FaceEngine] ❌ YOLOv5 加载失败: {e}")
                self.model = None
                self.loaded = False

        # 加载识别器
        try:
            self.recognizer = FaceRecognizer()
            if (self.recognizer is None
                    or getattr(self.recognizer, 'predictor', None) is None
                    or getattr(self.recognizer, 'face_rec_model', None) is None):
                print("[FaceEngine] ⚠️ 识别器模型加载失败，将仅使用检测功能")
                self.recognizer = None
            else:
                print("[FaceEngine] ✅ 识别器（dlib）加载成功")
        except Exception as e:
            print(f"[FaceEngine] ⚠️ 识别器初始化失败: {e}，将仅使用检测功能")
            self.recognizer = None

    def preprocess(self, frame):
        if letterbox is None:
            raise RuntimeError("letterbox not available")
        img = letterbox(frame, self.img_size, stride=self.stride, auto=False)[0]
        img = img[:, :, ::-1].transpose(2, 0, 1)
        img = np.ascontiguousarray(img)
        img = torch.from_numpy(img).to(self.device).float() / 255.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)
        return img, frame.shape[:2]

    def detect(self, frame):
        if not self.loaded or self.model is None or non_max_suppression is None:
            return []
        try:
            # ✅ 空帧保护
            if frame is None or frame.size == 0:
                return []
            img, (orig_h, orig_w) = self.preprocess(frame)
            with torch.no_grad():
                pred = self.model(img, augment=False)
            pred = non_max_suppression(pred, self.conf_thres, 0.45, classes=[0], agnostic=False)
            detections = []
            max_faces = 5  # 限制最多5个人脸
            for det in pred:
                if det is None or len(det) == 0:
                    continue
                if scale_boxes is not None:
                    det[:, :4] = scale_boxes(img.shape[2:], det[:, :4], (orig_h, orig_w)).round()
                for *xyxy, conf, cls in reversed(det):
                    if int(cls) != 0:
                        continue
                    x1, y1, x2, y2 = map(int, xyxy)
                    # ✅ 输出坐标裁剪到图像内，防止下游绘制/切片越界崩溃
                    x1 = max(0, min(x1, orig_w - 1))
                    y1 = max(0, min(y1, orig_h - 1))
                    x2 = max(0, min(x2, orig_w))
                    y2 = max(0, min(y2, orig_h))
                    if x2 - x1 < 20 or y2 - y1 < 20:
                        continue
                    detections.append({'bbox': [x1, y1, x2, y2], 'confidence': float(conf)})
                    if len(detections) >= max_faces:
                        break
            return detections
        except Exception as e:
            print(f"[FaceEngine] 推理失败: {e}")
            return []

    def draw_boxes(self, frame, detections, color=(0,255,0)):
        for det in detections:
            x1,y1,x2,y2 = det['bbox']
            conf = det.get('confidence', 1.0)
            cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
            cv2.putText(frame, f"face {conf:.2f}", (x1, y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame

    def get_face_encoding(self, face_img):
        if self.recognizer:
            return self.recognizer.get_face_encoding(face_img)
        return None

    def recognize(self, encoding):
        if self.recognizer:
            return self.recognizer.recognize(encoding)
        return None, False

    def get_all_known_names(self):
        if self.recognizer:
            return self.recognizer.get_all_names()
        return []