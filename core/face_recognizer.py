import os
import json
import numpy as np
import cv2
import dlib
from datetime import datetime
import urllib.request
import bz2

class FaceRecognizer:
    def __init__(self, db_path="data/face_db.json", tolerance=0.6):
        self.db_path = db_path
        self.tolerance = tolerance
        self.known_faces = []
        self.detector = dlib.get_frontal_face_detector()
        self.predictor = None
        self.face_rec_model = None
        self._load_models()
        self.load_db()

    def _load_models(self):
        model_dir = "models"
        os.makedirs(model_dir, exist_ok=True)

        predictor_path = os.path.join(model_dir, "shape_predictor_68_face_landmarks.dat")
        rec_model_path = os.path.join(model_dir, "dlib_face_recognition_resnet_model_v1.dat")

        if not os.path.exists(predictor_path):
            print("[FaceRecognizer] 下载 shape_predictor_68_face_landmarks.dat (约 99MB)...")
            try:
                url = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
                bz2_path = predictor_path + ".bz2"
                urllib.request.urlretrieve(url, bz2_path)
                with open(bz2_path, 'rb') as f:
                    data = bz2.decompress(f.read())
                with open(predictor_path, 'wb') as f:
                    f.write(data)
                os.remove(bz2_path)
                print("[FaceRecognizer] ✅ 形状预测器下载完成")
            except Exception as e:
                print(f"[FaceRecognizer] ⚠️ 形状预测器下载失败: {e}，请手动下载放入 models/")
                return

        if not os.path.exists(rec_model_path):
            print("[FaceRecognizer] 下载 dlib_face_recognition_resnet_model_v1.dat (约 96MB)...")
            try:
                url = "http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2"
                bz2_path = rec_model_path + ".bz2"
                urllib.request.urlretrieve(url, bz2_path)
                with open(bz2_path, 'rb') as f:
                    data = bz2.decompress(f.read())
                with open(rec_model_path, 'wb') as f:
                    f.write(data)
                os.remove(bz2_path)
                print("[FaceRecognizer] ✅ 识别模型下载完成")
            except Exception as e:
                print(f"[FaceRecognizer] ⚠️ 识别模型下载失败: {e}，请手动下载放入 models/")
                return

        try:
            self.predictor = dlib.shape_predictor(predictor_path)
            self.face_rec_model = dlib.face_recognition_model_v1(rec_model_path)
            print("[FaceRecognizer] ✅ dlib 模型加载完成")
        except Exception as e:
            print(f"[FaceRecognizer] ❌ 模型加载失败: {e}")
            self.predictor = None
            self.face_rec_model = None

    def load_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        self.known_faces = json.loads(content)
                    else:
                        self.known_faces = []
            except json.JSONDecodeError:
                print("[FaceRecognizer] ⚠️ face_db.json 格式错误，重置为空数据库")
                self.known_faces = []
        else:
            self.known_faces = []
            self.save_db()

    def save_db(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.known_faces, f, indent=2, ensure_ascii=False)

    def register_face(self, name, face_encoding):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "name": name,
            "encoding": face_encoding.tolist() if isinstance(face_encoding, np.ndarray) else face_encoding,
            "registered": now,
            "last_seen": now
        }
        self.known_faces.append(entry)
        self.save_db()
        return True

    def delete_face(self, name):
        self.known_faces = [f for f in self.known_faces if f["name"] != name]
        self.save_db()
        return True

    def get_all_names(self):
        return [f["name"] for f in self.known_faces]

    def get_face_encoding(self, face_image):
        if face_image is None or face_image.size == 0:
            return None
        if face_image.dtype != np.uint8:
            face_image = face_image.astype(np.uint8)
        # 确保是 RGB（dlib 需要 RGB）
        if len(face_image.shape) == 3 and face_image.shape[2] == 3:
            # 假设传入的是 BGR（OpenCV 默认），转换为 RGB
            rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
        else:
            rgb = face_image
        faces = self.detector(rgb, 1)
        if len(faces) == 0:
            return None
        shape = self.predictor(rgb, faces[0])
        face_descriptor = self.face_rec_model.compute_face_descriptor(rgb, shape)
        return np.array(face_descriptor)

    def recognize(self, face_encoding):
        if not self.known_faces:
            return None, False
        encodings = [np.array(f["encoding"]) for f in self.known_faces]
        distances = np.linalg.norm(encodings - face_encoding, axis=1)
        best_idx = np.argmin(distances)
        if distances[best_idx] < self.tolerance:
            name = self.known_faces[best_idx]["name"]
            self.known_faces[best_idx]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_db()
            return name, True
        else:
            return None, False