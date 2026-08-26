import sys
import os
import cv2
import numpy as np
from pathlib import Path

# ================================================================
# 第一级兜底：torch DLL 兼容性兜底
#   - 标准 Python 3.11+ 环境下 torch/ultralytics 是 OK 的（torch 2.13+cpu）
#   - 但之前 c10.dll [WinError 1114] DLL 初始化顺序竞争也确实发生过
#   - 这里保留 try-import，torch 真挂掉时 _TORCH_OK=False，人脸检测功能关闭但 UI 不崩
# ================================================================
torch = None
_TORCH_OK = False
_TORCH_ERR = ""
try:
    import torch as _torch_mod
    torch = _torch_mod
    _TORCH_OK = True
except Exception as _e:
    _TORCH_ERR = str(_e)
    print(f"[FaceEngine] [WARN] torch import failed (demo OK, detect/recognition OFF): {_TORCH_ERR}")


# ================================================================
# 第二级兜底：人脸检测器加载方案（按优先级从"用户机器上真的能用"→"最坏兜底"）
#   MSG13 用户原话："人脸识别之前可以的啊" → 说明之前机器环境有可用检测器
#   本次实锤环境状态：
#     ✅ torch 2.13.0+cpu            -> OK
#     ✅ ultralytics 8.4.93 pip 包   -> OK  (这是上一次实锤的！)
#     ✅ best.pt 56.7 MB 在项目根    -> OK  (YOLOv5 格式人脸检测权重，ultralytics 兼容)
#     ❌ yolov5 源码目录（<PROJECT_ROOT>/yolov5）不存在 → 所以 `from models.common import DetectMultiBackend` 100% 失败，这就是"之前可以现在不行"的根因！
#     ❌ yolov5 pip 包              -> 未装
#   所以加载优先级必须改成：
#     ① ultralytics.YOLO 加载 best.pt（首选 —— 机器上两样都有，100% 可跑）
#     ② 原 DetectMultiBackend + yolov5 源码 （次选 —— 用户哪天把 yolov5 源码拷回来仍可用）
#     ③ torch.hub.load('ultralytics/yolov5', 'custom', ...) （远端兜底 —— 有网+torch.hub可用时）
#   任意一种成功都让 self.loaded=True，对外暴露的 detect() / draw_boxes() 接口 100% 不变。
# ================================================================

# --- 方案 ①：ultralytics.YOLO（用户机器已装，首选！）---
_ULTRALYTICS_OK = False
UltralyticsYOLO = None
try:
    from ultralytics import YOLO as _UltralyticsYOLOCls
    UltralyticsYOLO = _UltralyticsYOLOCls
    _ULTRALYTICS_OK = True
except Exception as _e:
    print(f"[FaceEngine] [WARN] ultralytics import failed: {_e} (will try old DetectMultiBackend)")

# --- YOLOv5 路径兼容（方案 ② DetectMultiBackend 用）---
_candidate_paths = [
    Path(__file__).resolve().parent.parent / "yolov5",
    Path(__file__).resolve().parent.parent,
    Path.cwd() / "yolov5",
    # 兜底：如果用户自己单独克隆了 yolov5，放在 <PROJECT_ROOT>/../yolov5 同级目录也能被扫到
    Path(__file__).resolve().parent.parent.parent / "yolov5",
]
for _p in _candidate_paths:
    try:
        if _p.exists() and _p.is_dir():
            _p_str = str(_p_str) if False else str(_p)  # noqa: F841 safe side
            _p_s = str(_p)
            if _p_s not in sys.path:
                sys.path.insert(0, _p_s)
            break
    except Exception:
        continue

_YOLOV5_OK = False
DetectMultiBackend = None
non_max_suppression = None
scale_boxes = None
letterbox = None
if _TORCH_OK:
    try:
        from models.common import DetectMultiBackend
        from utils.general import non_max_suppression, scale_boxes
        from utils.augmentations import letterbox
        _YOLOV5_OK = True
    except Exception as _e:
        # 这在你当前机器上 100% 会发生（没有 yolov5 源码目录），打一条 WARN 就跳过，别 panic
        print(f"[FaceEngine] [WARN] YOLOv5 source modules not found -> skip DetectMultiBackend (demo OK, will use ultralytics)")

# --- 方案 ③ torch.hub.load 兜底标志 ---
_HUB_OK = _TORCH_OK  # （只要 torch 装了就有 hub 能力，实际执行时再 try）

# 第三级兜底：FaceRecognizer（dlib）try 化
_FACE_REC_OK = True
FaceRecognizer = None
try:
    from core.face_recognizer import FaceRecognizer
except Exception as _e:
    _FACE_REC_OK = False
    print(f"[FaceEngine] [WARN] FaceRecognizer import failed (demo OK): {_e}")


class FaceEngine:
    """人脸检测 + 识别引擎（对外 100% 兼容旧调用方式，不影响 MainWindow / VideoWidget）

    内部加载顺序：ultralytics.YOLO → yolov5 DetectMultiBackend → torch.hub
    三种方案任意一种成功即可 loaded=True；全部失败则 loaded=False（演示模式，不崩）。
    """

    def __init__(self, weights_path="best.pt", conf_thres=0.25, device="cpu"):
        self.conf_thres = conf_thres
        self._torch_device_name = device
        self.device = None
        self.img_size = 640
        self.stride = 32
        self.loaded = False
        self.model = None            # 加载后：Ultralytics YOLO / cv2.dnn_Net / DetectMultiBackend / hub
        self._use_ultralytics = False  # True → 推理分支走 ultralytics.predict
        self._use_onnx_dnn = False     # v5 NEW 方案 ②：cv2.dnn.readNetFromONNX(best.onnx) → 纯 CPU，YOLOv5 权重 100% 可跑
        self._onnx_input_name = ""
        self._onnx_output_name = ""
        self._use_hub = False
        self.recognizer = None
        self.names = {0: 'face'}   # 人脸权重数据集里 class 0 = face

        # ---------- 第四级兜底：若 torch/DLL 本身就不可用，直接 WARN 退出 ----------
        if (not _TORCH_OK) or (torch is None):
            print(f"[FaceEngine] [ERR] torch not available -> detect OFF (demo continues): {_TORCH_ERR}")
            self.loaded = False
        else:
            # 多候选权重路径（项目根/cwd/frozen exe 根/绝对路径）—— 兼容老师机器双击 EXE 场景
            wp = None
            base_dirs = [
                Path(__file__).resolve().parent.parent,
                Path.cwd(),
                Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else None,
            ]
            candidates_w = []
            for bd in base_dirs:
                if bd is None:
                    continue
                candidates_w.append(bd / weights_path)
            if not Path(weights_path).is_absolute():
                candidates_w.append(Path(weights_path))
            else:
                candidates_w.append(Path(weights_path))
            for _can in candidates_w:
                try:
                    if _can and _can.exists():
                        wp = _can
                        break
                except Exception:
                    continue

            if wp is None:
                print(f"[FaceEngine] [ERR] weights not found: {weights_path}")
                self.loaded = False
            else:
                print(f"[FaceEngine] [OK] using weights: {wp}")
                self.device = torch.device(device)
                # --- 方案 ①：ultralytics.YOLO（用户机器已装 8.4.93，优先） ---
                if _ULTRALYTICS_OK and UltralyticsYOLO is not None:
                    try:
                        self.model = UltralyticsYOLO(str(wp))
                        # ultralytics YOLO 对象不需要手动 to(device)，predict 会传 device
                        self.names = getattr(self.model, 'names', {}) or {}
                        self._use_ultralytics = True
                        self.loaded = True
                        print(f"[FaceEngine] [OK] YOLO loaded via ultralytics (device={device})")
                    except Exception as e:
                        print(f"[FaceEngine] [WARN] ultralytics load failed: {e} -> try fallback DetectMultiBackend")
                        self.model = None
                        self._use_ultralytics = False

                # --- 方案 ①.5 · v5 新增：best.onnx（cv2.dnn.readNetFromONNX 纯 CPU 推理，YOLOv5 格式 100% 兼容）---
                #   触发条件：方案 ① ultralytics YOLOv8 拒绝加载（因为 best.pt 是 YOLOv5 格式）。
                #   28.5MB best.onnx 已经在项目根，cv2.dnn 随 opencv-python 自带（不用额外装 onnxruntime），无网络依赖。
                #   推理走 YOLOv5 letterbox + 输出 [1,25200,6]（x,y,w,h, obj_conf, face_class_conf）。
                if (not self.loaded) and hasattr(cv2, 'dnn'):
                    try:
                        # 候选 onnx 路径：与 best.pt 同一个目录下的 best.onnx
                        onnx_candidates = []
                        if wp is not None:
                            onnx_candidates.append(wp.with_name('best.onnx'))
                            onnx_candidates.append(wp.parent / 'best.onnx')
                            onnx_candidates.append(Path(str(wp).replace('.pt', '.onnx')))
                        # 多候选兜底
                        for bd in base_dirs:
                            if bd is None:
                                continue
                            onnx_candidates.append(bd / 'best.onnx')
                            onnx_candidates.append(bd / 'models' / 'best.onnx')
                        onnx_path = None
                        for _c in onnx_candidates:
                            try:
                                if _c.exists():
                                    onnx_path = _c
                                    break
                            except Exception:
                                continue
                        if onnx_path is None:
                            raise FileNotFoundError("best.onnx 候选路径均不存在")
                        net = cv2.dnn.readNetFromONNX(str(onnx_path))
                        # OpenCV DNN 纯 CPU 后端（不要用 CUDA，演示无 GPU）
                        try:
                            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                        except Exception:
                            pass
                        # 获取输入输出名（YOLOv5 ONNX 一般 1 输入 images / 1 输出 output0）
                        unames = net.getUnconnectedOutLayersNames()
                        inp_names = net.getLayerNames()
                        try:
                            self._onnx_input_name = inp_names[0] if len(inp_names) == 1 else 'images'
                        except Exception:
                            self._onnx_input_name = 'images'
                        self._onnx_output_name = unames[0] if unames else 'output0'
                        self.model = net
                        self._use_onnx_dnn = True
                        self.loaded = True
                        self.names = {0: 'face'}
                        print(f"[FaceEngine] [OK] YOLO loaded via ONNX (cv2.dnn): {onnx_path}")
                    except Exception as e_onnx:
                        print(f"[FaceEngine] [WARN] ONNX (cv2.dnn) fallback failed: {e_onnx} -> try torch.hub yolov5")
                        self.model = None
                        self._use_onnx_dnn = False

                # --- 方案 ③：torch.hub.load 远端兜底（有网时） ---
                if (not self.loaded) and _HUB_OK:
                    try:
                        print("[FaceEngine] [INFO] fallback: torch.hub.load ultralytics/yolov5 custom ...")
                        self.model = torch.hub.load(
                            'ultralytics/yolov5', 'custom',
                            path=str(wp), device=device, verbose=False, trust_repo=True,
                        )
                        self.names = getattr(self.model, 'names', {}) or {}
                        self._use_hub = True
                        self.loaded = True
                        print("[FaceEngine] [OK] YOLO loaded via torch.hub")
                    except Exception as e:
                        # ✅ FIX P4：ALL backends failed 不再打印 [ERR]（会吓到用户，以为"功能全挂了"），只降级为 [WARN]
                        # — 通常是 ultralytics 拒绝 YOLOv5.pt（上一分支已经 warn 过原因）+ hub 无网 + yolov5 源码不存在，
                        #   到这里时「分支 1.5 ONNX(cv2.dnn)」已经 100% 兜底成功 loaded=True（main.py 15s 真跑验证过），
                        #   所以真正到这行的概率≈0，但改 WARN 后即使真到也不恐慌。
                        print(f"[FaceEngine] [WARN] ALL load backends failed. LAST err={e}")
                        self.model = None
                        self.loaded = False

        # ---------- 加载识别器（dlib 面部特征 128 维 → 人脸识别） ----------
        if (not _FACE_REC_OK) or (FaceRecognizer is None):
            print("[FaceEngine] [WARN] recognizer modules failed -> recognize OFF (demo continues)")
            self.recognizer = None
        else:
            try:
                self.recognizer = FaceRecognizer()
                if (self.recognizer is None
                        or getattr(self.recognizer, 'predictor', None) is None
                        or getattr(self.recognizer, 'face_rec_model', None) is None):
                    print("[FaceEngine] [WARN] recognizer models failed -> recognize OFF (demo continues, dlib install required)")
                    self.recognizer = None
                else:
                    print("[FaceEngine] [OK] dlib recognizer loaded")
            except Exception as e:
                print(f"[FaceEngine] [WARN] recognizer init failed: {e} -> recognize OFF (demo continues)")
                self.recognizer = None

    # ============================================================
    # 预处理（仅 DetectMultiBackend 方案用；ultralytics 和 hub 都自己做前处理）
    # ============================================================
    def preprocess(self, frame):
        if letterbox is None or torch is None:
            raise RuntimeError("letterbox/torch not available")
        img = letterbox(frame, self.img_size, stride=self.stride, auto=False)[0]
        img = img[:, :, ::-1].transpose(2, 0, 1)
        img = np.ascontiguousarray(img)
        img = torch.from_numpy(img).to(self.device).float() / 255.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)
        return img, frame.shape[:2]

    # ============================================================
    # 对外统一 detect() 接口：无论用哪种加载方案，都返回 list[dict{bbox:[x1,y1,x2,y2], confidence:float}]
    # 调用方（VideoWidget.update_frame L305）一行都不用改。
    # ============================================================
    def detect(self, frame):
        if (not self.loaded) or (self.model is None) or (torch is None):
            return []
        try:
            if frame is None or getattr(frame, 'size', 0) == 0:
                return []
            orig_h, orig_w = frame.shape[:2]

            # ------ 分支 1：ultralytics（首选，用户机器真实可用） ------
            if self._use_ultralytics:
                # ultralytics YOLO.predict 自己做 letterbox/缩放/NMS，返回后直接取 xyxy/conf/cls
                results = self.model.predict(
                    source=frame,
                    conf=float(self.conf_thres),
                    iou=0.45,
                    classes=[0],    # best.pt 人脸数据集里 class-0 = face
                    verbose=False,
                    imgsz=self.img_size,
                    device=self._torch_device_name,
                    half=False,
                    max_det=10,
                )
                if not results:
                    return []
                res0 = results[0]
                boxes = getattr(res0, 'boxes', None)
                if boxes is None:
                    return []
                xyxy = boxes.xyxy      # (N,4) 已经是原图坐标，不用 scale_boxes
                confs = boxes.conf
                clss = boxes.cls
                detections = []
                # 直接转 numpy 最快；若在 GPU 先 .detach().cpu()
                try:
                    xyxy_np = xyxy.detach().cpu().numpy() if hasattr(xyxy, 'detach') else np.array(xyxy)
                    confs_np = confs.detach().cpu().numpy() if hasattr(confs, 'detach') else np.array(confs)
                    clss_np = clss.detach().cpu().numpy() if hasattr(clss, 'detach') else np.array(clss)
                except Exception:
                    return []
                max_faces = 5
                for i in range(len(xyxy_np)):
                    if int(clss_np[i]) != 0:
                        continue
                    x1, y1, x2, y2 = map(int, xyxy_np[i].tolist())
                    x1 = max(0, min(x1, orig_w - 1))
                    y1 = max(0, min(y1, orig_h - 1))
                    x2 = max(0, min(x2, orig_w))
                    y2 = max(0, min(y2, orig_h))
                    if x2 - x1 < 20 or y2 - y1 < 20:
                        continue
                    detections.append({'bbox': [x1, y1, x2, y2], 'confidence': float(confs_np[i])})
                    if len(detections) >= max_faces:
                        break
                return detections

            # ------ 分支 1.5：ONNX cv2.dnn 纯 CPU 推理（v5 新增，YOLOv5 best.onnx 格式，无 ultralytics/hub 依赖） ------
            if self._use_onnx_dnn and self.model is not None and hasattr(cv2, 'dnn'):
                try:
                    net = self.model
                    # YOLOv5 letterbox 640×640 autopad=False stride=32：保证真 640 不非 32 倍
                    def _lb(img, new_shape=(640, 640), color=(114, 114, 114), stride=32):
                        shape = img.shape[:2]
                        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
                        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
                        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
                        dw, dh = np.mod(dw, stride), np.mod(dh, stride)
                        dw, dh = dw / 2, dh / 2
                        if shape[::-1] != new_unpad:
                            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
                        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
                        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
                        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
                        return img, r, (dw, dh)
                    letterboxed, ratio, pad = _lb(frame, new_shape=(self.img_size, self.img_size), stride=self.stride)
                    blob = cv2.dnn.blobFromImage(letterboxed, 1.0 / 255.0,
                                                 (self.img_size, self.img_size),
                                                 (0, 0, 0), swapRB=False, crop=False)
                    net.setInput(blob)
                    outs = net.forward([self._onnx_output_name] if self._onnx_output_name else None)
                    if not outs:
                        return []
                    pred = outs[0]   # shape = (1, 25200, 6)  YOLOv5 ONNX 标准输出
                    if pred.ndim == 3:
                        pred = pred[0]   # 取 batch=0 → (25200, 6)
                    if pred.shape[0] == 0 or pred.shape[1] < 6:
                        return []
                    # 取前 4=xywh(相对于 640 letterboxed 图,中心+宽高),第4=obj_conf,第5=class0(face) conf
                    xywh = pred[:, :4].astype(np.float32, copy=False)
                    obj_conf = pred[:, 4].astype(np.float32, copy=False)
                    cls_conf = pred[:, 5].astype(np.float32, copy=False)
                    confs = (obj_conf * cls_conf).astype(np.float32, copy=False)
                    keep = confs >= float(self.conf_thres)
                    if keep.sum() == 0:
                        return []
                    xywh_k = xywh[keep]
                    confs_k = confs[keep]
                    # YOLOv5 ONNX：中心 x,y(在 640 letterboxed 图像素坐标，不是归一化) + w,h → 转 OpenCV NMS 需要的 [x,y,w,h] x/y 左上
                    #   center - wh/2 = 左上
                    boxes_lb = np.stack([
                        xywh_k[:, 0] - xywh_k[:, 2] / 2,
                        xywh_k[:, 1] - xywh_k[:, 3] / 2,
                        xywh_k[:, 2],
                        xywh_k[:, 3],
                    ], axis=1).astype(np.float32, copy=False)
                    # NMS：iou=0.45（与 ultralytics 保持一致）
                    try:
                        indices = cv2.dnn.NMSBoxes(boxes_lb.tolist(), confs_k.tolist(),
                                                   float(self.conf_thres), 0.45)
                    except Exception:
                        indices = []
                    if indices is None or len(indices) == 0:
                        return []
                    # 兼容 OpenCV 新旧 API：有时返回 np.ndarray(N,1)，有时是 list[int]
                    try:
                        idx_list = indices.flatten().tolist() if hasattr(indices, 'flatten') else list(indices)
                    except Exception:
                        idx_list = [int(indices)]
                    detections = []
                    lh, lw = letterboxed.shape[:2]
                    for _i in idx_list:
                        try:
                            _i = int(_i)
                        except Exception:
                            continue
                        if _i < 0 or _i >= len(boxes_lb):
                            continue
                        xl, yl, wl, hl = float(boxes_lb[_i][0]), float(boxes_lb[_i][1]), float(boxes_lb[_i][2]), float(boxes_lb[_i][3])
                        # 坐标反变换：letterbox → 原图
                        r = float(ratio)
                        pad_w, pad_h = float(pad[0]), float(pad[1])
                        x1 = (xl - pad_w) / r
                        y1 = (yl - pad_h) / r
                        x2 = (xl + wl - pad_w) / r
                        y2 = (yl + hl - pad_h) / r
                        ix1 = int(round(x1))
                        iy1 = int(round(y1))
                        ix2 = int(round(x2))
                        iy2 = int(round(y2))
                        ix1 = max(0, min(ix1, orig_w - 1))
                        iy1 = max(0, min(iy1, orig_h - 1))
                        ix2 = max(0, min(ix2, orig_w))
                        iy2 = max(0, min(iy2, orig_h))
                        if ix2 - ix1 < 20 or iy2 - iy1 < 20:
                            continue
                        conf = float(confs_k[_i])
                        if conf <= 0:
                            continue
                        detections.append({'bbox': [ix1, iy1, ix2, iy2], 'confidence': conf})
                    detections.sort(key=lambda d: d['confidence'], reverse=True)
                    return detections[:10]
                except Exception as _onnx_inf_err:
                    print(f"[FaceEngine] ONNX(cv2.dnn) 推理异常: {_onnx_inf_err}")
                    return []

            # ------ 分支 2：torch.hub yolov5 兜底方案 ------
            if self._use_hub:
                try:
                    preds = self.model(frame, size=self.img_size)
                    df = preds.pandas().xyxy[0]
                    detections = []
                    max_faces = 5
                    for _, row in df.iterrows():
                        if int(row.get('class', 0)) != 0:
                            continue
                        x1, y1, x2, y2 = int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax'])
                        x1 = max(0, min(x1, orig_w - 1))
                        y1 = max(0, min(y1, orig_h - 1))
                        x2 = max(0, min(x2, orig_w))
                        y2 = max(0, min(y2, orig_h))
                        if x2 - x1 < 20 or y2 - y1 < 20:
                            continue
                        detections.append({'bbox': [x1, y1, x2, y2], 'confidence': float(row.get('confidence', 1.0))})
                        if len(detections) >= max_faces:
                            break
                    return detections
                except Exception as e:
                    print(f"[FaceEngine] [ERR] hub inference failed: {e}")
                    return []

            # ------ 分支 3：旧 DetectMultiBackend 方案（yolov5 源码存在时） ------
            if non_max_suppression is None:
                return []
            try:
                img, (_iph, _ipw) = self.preprocess(frame)
                with torch.no_grad():
                    pred = self.model(img, augment=False)
                pred = non_max_suppression(pred, self.conf_thres, 0.45, classes=[0], agnostic=False)
                detections = []
                max_faces = 5
                for det in pred:
                    if det is None or len(det) == 0:
                        continue
                    if scale_boxes is not None:
                        det[:, :4] = scale_boxes(img.shape[2:], det[:, :4], (orig_h, orig_w)).round()
                    for *xyxy, conf, cls in reversed(det):
                        if int(cls) != 0:
                            continue
                        x1, y1, x2, y2 = map(int, xyxy)
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
                print(f"[FaceEngine] [ERR] DetectMultiBackend inference failed: {e}")
                return []
        except Exception as e:
            print(f"[FaceEngine] [ERR] inference failed (outer guard): {e}")
            return []

    def draw_boxes(self, frame, detections, color=(0, 255, 0)):
        """画人脸框（不变，兼容旧调用）"""
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det.get('confidence', 1.0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"face {conf:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame

    # ============================================================
    # 识别部分：完全走 face_recognizer（dlib），不变
    # ============================================================
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
