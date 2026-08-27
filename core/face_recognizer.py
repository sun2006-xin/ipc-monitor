import os
import json
import sys
import numpy as np
import cv2
from datetime import datetime
import urllib.request
import bz2
from pathlib import Path
from core.app_paths import R, U, BUNDLE_ROOT


# ================================================================
# 第一级兜底：dlib 顶层 import 必须 try 化
# 若 dlib 没装 / 缺 VC++ runtime → 旧代码会在 import 阶段 NameError 连 DB 读写都进不去
# 这里失败时 dlib=None、_DLIB_OK=False、recognize 功能全关但 DB 读写仍保留、UI 不崩
# ================================================================
dlib = None
_DLIB_OK = False
_DLIB_ERR = ""
try:
    import dlib as _dlib_mod
    dlib = _dlib_mod
    _DLIB_OK = True
except Exception as _e:
    _DLIB_ERR = str(_e)
    print(f"[FaceRecognizer] [WARN] dlib import failed (recognize OFF, demo continues): {_DLIB_ERR}")


class FaceRecognizer:
    def __init__(self, db_path=None, tolerance=0.6):
        self.db_path = db_path if db_path else U("data/face_db.json")
        self.tolerance = tolerance
        self.known_faces = []
        # dlib 不可用时 detector/predictor/face_rec_model 全置 None，绝不使用未定义名
        self.detector = None
        self.predictor = None
        self.face_rec_model = None
        if _DLIB_OK and dlib is not None:
            try:
                self.detector = dlib.get_frontal_face_detector()
            except Exception as _e:
                print(f"[FaceRecognizer] [ERR] dlib.get_frontal_face_detector failed: {_e}")
                self.detector = None
        else:
            print("[FaceRecognizer] dlib not available -> only face DB read/write kept (demo continues)")
        self._load_models()
        self.load_db()

    # ------------------------------------------------------------
    # 模型路径多候选：优先 BUNDLE_ROOT/_MEIPASS（打包已内置 2 个 dlib 权重）→ EXE 同级/models → cwd
    #   下载兜底：仅当所有候选都不存在时，下载到「用户写目录 / USER_DATA_ROOT/models」（不然写到 _MEIPASS 下次又重下）
    # ------------------------------------------------------------
    @staticmethod
    def _resolve_model(filename: str):
        exe_dir = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else None
        base_dirs = [
            BUNDLE_ROOT / "models",                         # 首选：源码 / EXE _MEIPASS 内置
            exe_dir / "models" if exe_dir else None,         # 用户把权重放到 EXE 同级 / models
            Path.cwd() / "models",                           # cwd / models
        ]
        for bd in base_dirs:
            if bd is None:
                continue
            try:
                p = bd / filename
                if p.exists():
                    return str(p)
            except Exception:
                continue
        # fallback：下载写入「用户可写目录/models」，而不是写到 NUL _MEIPASS
        download_dir = Path(U("models"))
        try:
            os.makedirs(str(download_dir), exist_ok=True)
        except Exception:
            pass
        return str(download_dir / filename)

    def _load_models(self):
        predictor_path = FaceRecognizer._resolve_model("shape_predictor_68_face_landmarks.dat")
        rec_model_path = FaceRecognizer._resolve_model("dlib_face_recognition_resnet_model_v1.dat")
        model_dir = os.path.dirname(predictor_path) or "models"
        try:
            os.makedirs(model_dir, exist_ok=True)
        except Exception:
            pass

        if (not _DLIB_OK) or (dlib is None):
            # 没装 dlib 不下载大文件（下载了解压了也加载不了，纯浪费）
            if not os.path.exists(predictor_path):
                print(f"[FaceRecognizer] [WARN] skip predictor download -> dlib unavailable")
            if not os.path.exists(rec_model_path):
                print(f"[FaceRecognizer] [WARN] skip rec_model download -> dlib unavailable")
            return

        if not os.path.exists(predictor_path):
            print("[FaceRecognizer] downloading shape_predictor_68_face_landmarks.dat (about 99MB)...")
            try:
                url = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
                bz2_path = predictor_path + ".bz2"
                urllib.request.urlretrieve(url, bz2_path)
                with open(bz2_path, 'rb') as f:
                    data = bz2.decompress(f.read())
                with open(predictor_path, 'wb') as f:
                    f.write(data)
                try:
                    os.remove(bz2_path)
                except OSError:
                    pass
                print("[FaceRecognizer] [OK] shape predictor downloaded")
            except Exception as e:
                print(f"[FaceRecognizer] [WARN] shape predictor download failed: {e}. please manually place in models/")
                return

        if not os.path.exists(rec_model_path):
            print("[FaceRecognizer] downloading dlib_face_recognition_resnet_model_v1.dat (about 96MB)...")
            try:
                url = "http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2"
                bz2_path = rec_model_path + ".bz2"
                urllib.request.urlretrieve(url, bz2_path)
                with open(bz2_path, 'rb') as f:
                    data = bz2.decompress(f.read())
                with open(rec_model_path, 'wb') as f:
                    f.write(data)
                try:
                    os.remove(bz2_path)
                except OSError:
                    pass
                print("[FaceRecognizer] [OK] face rec model downloaded")
            except Exception as e:
                print(f"[FaceRecognizer] [WARN] rec model download failed: {e}. please manually place in models/")
                return

        try:
            self.predictor = dlib.shape_predictor(predictor_path)
            self.face_rec_model = dlib.face_recognition_model_v1(rec_model_path)
            print("[FaceRecognizer] [OK] dlib models loaded")
        except Exception as e:
            print(f"[FaceRecognizer] [ERR] dlib models load failed: {e}")
            self.predictor = None
            self.face_rec_model = None

    def load_db(self):
        try:
            db_dir = os.path.dirname(self.db_path) or "."
            os.makedirs(db_dir, exist_ok=True)
        except Exception:
            pass
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        self.known_faces = json.loads(content)
                    else:
                        self.known_faces = []
            except json.JSONDecodeError:
                print("[FaceRecognizer] [WARN] face_db.json invalid -> reset to empty DB")
                self.known_faces = []
            except Exception as e:
                print(f"[FaceRecognizer] [WARN] face_db.json read failed: {e}")
                self.known_faces = []
        else:
            self.known_faces = []
            self.save_db()

    def save_db(self):
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.known_faces, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[FaceRecognizer] [ERR] save face_db failed: {e}")

    def register_face(self, name, face_encoding):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "name": name,
            "encoding": face_encoding.tolist() if isinstance(face_encoding, np.ndarray) else face_encoding,
            "registered": now,
            "last_seen": now,
        }
        self.known_faces.append(entry)
        self.save_db()
        return True

    def delete_face(self, name):
        before = len(self.known_faces)
        self.known_faces = [f for f in self.known_faces if f["name"] != name]
        if len(self.known_faces) != before:
            self.save_db()
            return True
        return False

    def get_all_names(self):
        return [f["name"] for f in self.known_faces]

    def get_face_encoding(self, face_image):
        if self.detector is None or self.predictor is None or self.face_rec_model is None:
            return None
        if face_image is None or getattr(face_image, "size", 0) == 0:
            return None
        if face_image.dtype != np.uint8:
            face_image = face_image.astype(np.uint8)
        if len(face_image.shape) == 3 and face_image.shape[2] == 3:
            rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
        else:
            rgb = face_image
        try:
            faces = self.detector(rgb, 1)
        except Exception as e:
            print(f"[FaceRecognizer] [ERR] dlib detector failed: {e}")
            return None
        if len(faces) == 0:
            return None
        try:
            shape = self.predictor(rgb, faces[0])
            face_descriptor = self.face_rec_model.compute_face_descriptor(rgb, shape)
        except Exception as e:
            print(f"[FaceRecognizer] [ERR] predictor/rec_model failed: {e}")
            return None
        return np.array(face_descriptor)

    def recognize(self, face_encoding):
        if not self.known_faces or face_encoding is None:
            return None, False
        try:
            encodings = [np.array(f["encoding"]) for f in self.known_faces]
            distances = np.linalg.norm(encodings - face_encoding, axis=1)
            best_idx = int(np.argmin(distances))
            if distances[best_idx] < self.tolerance:
                name = self.known_faces[best_idx]["name"]
                self.known_faces[best_idx]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_db()
                return name, True
        except Exception as e:
            print(f"[FaceRecognizer] [ERR] recognize failed: {e}")
        return None, False

    # ================================================================
    # 辅助：直接在 原视频帧 + (x1,y1,x2,y2) bbox 上算人脸 descriptor（给 B1 多帧注册 / C1 陌生人识别复用）
    #   - 为什么不用 detector 再扫一遍？detect 已经在 VideoWidget 里用 YOLO 拿过 bbox 了，再扫一遍浪费 CPU；
    #     直接把 bbox 转成 dlib.rectangle 喂 shape_predictor/rec_model 即可，0.6ms 一张 vs detector 要 40ms+。
    #   - 兼容 3 通道 BGR/RGB：内部再做一次颜色转换，调用方不用管。
    # ================================================================
    def encode_from_frame(self, frame_bgr, bbox_xyxy=None):
        if self.detector is None or self.predictor is None or self.face_rec_model is None:
            return None
        if frame_bgr is None or getattr(frame_bgr, "size", 0) == 0:
            return None
        try:
            if not isinstance(frame_bgr, np.ndarray):
                frame_bgr = np.asarray(frame_bgr)
            if frame_bgr.dtype != np.uint8:
                frame_bgr = frame_bgr.astype(np.uint8)
            # 颜色统一转 RGB（dlib landmark/rec 都期望 RGB，与 get_face_encoding 保持一致）
            if len(frame_bgr.shape) == 3 and frame_bgr.shape[2] == 3:
                rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            else:
                rgb = frame_bgr
            fh, fw = rgb.shape[:2]

            rect = None
            if bbox_xyxy is not None:
                try:
                    x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(fw - 1, x2), min(fh - 1, y2)
                    if x2 > x1 and y2 > y1:
                        rect = dlib.rectangle(x1, y1, x2, y2)
                except Exception:
                    rect = None
            if rect is None:
                # bbox 无效或未传 → 回退 dlib detector 扫一遍（与 get_face_encoding 原逻辑一致）
                try:
                    faces = self.detector(rgb, 1)
                except Exception as e:
                    print(f"[FaceRecognizer] [ERR] dlib detector fallback failed: {e}")
                    return None
                if not faces:
                    return None
                rect = faces[0]

            shape = self.predictor(rgb, rect)
            descriptor = self.face_rec_model.compute_face_descriptor(rgb, shape)
            return np.array(descriptor, dtype=np.float64)
        except Exception as e:
            print(f"[FaceRecognizer] [ERR] encode_from_frame failed: {e}")
            return None

    # ------------------------------------------------------------
    # B1 · 多帧平均人脸注册（减少单帧误判）
    # 用法：register_face_multi("张三", frames_list, num_frames=10, min_frames=5)
    #   frames 可以是 list[np.ndarray(BGR帧)], 也可以是 list[bbox + frame 的 tuple(frame, bbox)]
    #   内部逐帧算 descriptor → 至少 min_frames 个成功 → np.mean 取 128 维均值 → 写入 face_db.json
    #   返回 (ok, used_frames_count, error_msg)，调用方（FaceManagerDialog UI）直接展示"采集成功 x/10 帧"
    # ------------------------------------------------------------
    def register_face_multi(self, name, frames, num_frames=10, min_frames=5, bbox_list=None):
        if not _DLIB_OK or self.face_rec_model is None:
            return False, 0, "dlib 识别模型未加载，无法注册"
        if not name or not str(name).strip():
            return False, 0, "姓名不能为空"
        name = str(name).strip()
        try:
            if name in self.get_all_names():
                return False, 0, f"姓名 {name} 已注册"
        except Exception:
            pass
        if not frames:
            return False, 0, "未提供任何帧"
        # 限制最多处理 num_frames，超过取前 N
        frames = list(frames[:num_frames]) if hasattr(frames, '__getitem__') else list(frames)

        encs = []
        for idx, fr in enumerate(frames):
            bbox = None
            if bbox_list is not None and idx < len(bbox_list):
                bbox = bbox_list[idx]
            enc = self.encode_from_frame(fr, bbox)
            if enc is not None and getattr(enc, 'size', 0) > 0:
                encs.append(np.asarray(enc, dtype=np.float64))
            # 提前达成 num_frames 就停，不要继续白跑 CPU
            if len(encs) >= num_frames:
                break
        if len(encs) < max(1, min_frames):
            return False, len(encs), (f"仅成功提取 {len(encs)} 帧人脸特征，不足最低 {min_frames} 帧。"
                                       "请正对摄像头、保持光照充足、无大角度侧脸后重试。")

        # 多帧均值：逐帧异常大的特征通过"取均值 + 重新单位范数归一化"拉回 dlib 128D 期望分布
        # dlib 原 descriptor 是 L2 归一化的，取均值后再归一一次，保证后续 compare distance 阈值 0.6 还是可靠
        mean_enc = np.mean(np.stack(encs, axis=0), axis=0)
        norm = float(np.linalg.norm(mean_enc))
        if norm > 1e-6:
            mean_enc = mean_enc / norm
        ok = self.register_face(name, mean_enc)
        if not ok:
            return False, len(encs), "写入人脸库失败"
        return True, len(encs), ""

    # ------------------------------------------------------------
    # C1 · 陌生人识别统一入口（返回 name / is_stranger / distance / encoding）
    #   - 如果 distance < tolerance → 熟人，返回 (name, False, distance, encoding)
    #   - 如果 distance >= tolerance 或 DB 为空 → 陌生人，返回 ("陌生人", True, distance, encoding or None)
    #   - 失败时返回 (None, False, -1.0, None)
    # ------------------------------------------------------------
    def recognize_from_frame(self, frame_bgr, bbox_xyxy=None):
        enc = self.encode_from_frame(frame_bgr, bbox_xyxy)
        if enc is None:
            return None, False, -1.0, None
        if not self.known_faces:
            return "陌生人", True, -1.0, enc
        try:
            encodings = [np.array(f["encoding"]) for f in self.known_faces]
            distances = np.linalg.norm(encodings - enc, axis=1)
            best_idx = int(np.argmin(distances))
            dist = float(distances[best_idx])
            if dist < self.tolerance:
                name = self.known_faces[best_idx]["name"]
                try:
                    self.known_faces[best_idx]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_db()
                except Exception:
                    pass
                return name, False, dist, enc
            return "陌生人", True, dist, enc
        except Exception as e:
            print(f"[FaceRecognizer] [ERR] recognize_from_frame failed: {e}")
        return None, False, -1.0, enc
