# 项目宣传图 3 张 · AI 生成提示词（作者本人不画图，直接复制喂 Midjourney / DALL·E 3 / SDXL / 文心一言 / 豆包图像）
> 使用方式：每张图下面都有 【Midjourney Prompt】/ 【中文 AI 通用 Prompt】两种格式 + 【核心元素清单 Checklist】+ 【配色/字体/尺寸要求】。
> 作者只需要把对应 Prompt 复制到画图 AI 就能得到专业成品，不用自己设计。
> 产出后请放到项目 `docs/` 下：`poster_overview.png / structure_diagram.png / algorithm_detail.png`

---

## 🖼 图 1：大字报 Poster（富含总体信息）· 首页头图 / PPT 封面 / 朋友圈

### 📐 技术规格
- 尺寸：**1920×1080 px（横版 16:9）**
- 风格：**科技感深色/浅色渐变 + 卡片玻璃态**（毕设海报风格，正式但不死板）
- 主色调：**蓝 + 青 + 橙 三色点缀**（对应"检测/识别/告警"三层）
- 字体（中文）：**思源黑体 Bold / 阿里巴巴普惠体 Heavy**，英文：**Inter Black / Montserrat Black**
- 右下角 放 **Apache-2.0 License · Graduation Project 2026** 徽章 + 二维码占位（放 GitHub 链接）

### 📝 【Midjourney 英文版 Prompt】直接复制：
```
graduation project poster for a multi-channel RTSP IP smart surveillance system, title at top "IPC-Monitor · IP Camera Intelligent Face Surveillance Platform", 3 main rounded glass card columns under the title: Column A "5 Basic Features A1-A5" with icons (auto grid layout, FPS+timestamp overlay, face registration, alarm sound, csv event export), Column B "4 Medium Features B1-B4" with icons (10-frame average enrollment, scheduled recording hourly split, face appearance history search, device online/offline alarm), Column C "4 Heavy Features C1-C4" with icons (stranger red bbox 3px, crowd detection top red banner, duty station absence alert red, night low-light CLAHE enhance), the background is a dark to light blue tech gradient with subtle CCTV camera silhouette mesh, top right corner shows a small 2x2 preview of 4 surveillance screens each has green face detection boxes, bottom left displays tech stack badges: PyQt5 | YOLOv5 | dlib | OpenCV DNN ONNX fallback | Windows, bottom right displays a GitHub QR code placeholder + "Apache-2.0 License · 2026 Graduation Project". Minimal corporate UI style, clean spacing, no camera gear clutter, 16:9, high resolution, professional, --ar 16:9 --style raw --v 6.0
```

### 📝 【中文 AI 画图通用 Prompt】（给豆包/文心一言/SD 中文模型）
```
毕业设计大字报海报，尺寸 1920×1080 横版 16:9，风格为科技感玻璃态卡片，蓝青色科技渐变背景，上面有半透明的监控摄像头网格剪影。

顶部居中大标题：「IPC-Monitor · IP 摄像头智能人脸监控平台」，副标题小字：「毕业答辩演示 · A5 基础 + B4 中等 + C4 综合 = 13 功能阶梯展示」。

标题下方 3 列并排圆角玻璃卡片（每列内 4 行带图标条目）：
  左列（蓝色 · 标题 A 档·基础 5 项）：
  ✅ A1 多路自动布局 1×1~4×4 不留空白
  ✅ A2 FPS + 分辨率 + 时间叠加左下角
  ✅ A3 人脸管理单帧 + 多帧注册
  ✅ A4 🔔 告警音 + 一键静音
  ✅ A5 9 类型事件历史 + UTF-8 BOM CSV 导出

  中列（橙色 · 标题 B 档·中等 4 项）：
  ➕ B1 10 帧平均注册 QProgressDialog 采集
  ⏱ B2 定时录像 + 每小时自动分片 MP4
  🔍 B3 人脸出现记录检索 QSplitter 缩略图预览
  📡 B4 摄像头上下线告警自动响铃落历史

  右列（红色 · 标题 C 档·综合 4 项）：
  🚨 C1 陌生人加粗 3px 红框 8s 独立冷却
  ⚠ C2 人员聚集 5 人 3 周期 30s 冷却 顶部横幅
  🔴 C3 值守岗右键菜单 10 分钟离岗红字告警
  🌙 C4 夜间低照度 YCrCb CLAHE 对比度增强

右上角画一个 2×2 的缩小监控预览窗口，4 个小屏幕里每个都画绿色的人脸检测矩形框。
左下角贴 4 枚圆形徽章：PyQt5 / YOLOv5 / dlib / OpenCV DNN ONNX 兜底。
右下角放 GitHub 二维码占位 + 一行字"Apache-2.0 License · 2026 毕业设计"。
字体使用思源黑体，排版干净正式，配色统一，不要任何卡通元素，不要多余装饰，不要乱码中文。
```

### ✅ 核心元素 Checklist（出图后对照确认）
- [ ] 标题 「IPC-Monitor」+ 12 字副标题清晰
- [ ] 3 列卡片 A5+B4+C4=13 项条目 **没有缺行**、**图标都对得上**
- [ ] 右上角 2×2 监控小预览 + 绿色框
- [ ] 左下 4 枚技术栈徽章、右下 GitHub 二维码占位、Apache-2.0 徽章
- [ ] 中文无乱码、字体不歪扭、没有"鬼画符"的 AI 假汉字

---

## 🧱 图 2：系统结构图（Mermaid/Drawio）· README 架构章节 / PPT 架构页

> 💡 **推荐导出法（最快最稳）**：我们仓库根 `docs/ARCHITECTURE.mmd` 已经写好 **完全可运行的 Mermaid 源码**！
> 1. 打开 <https://mermaid.live/> → 把 `ARCHITECTURE.mmd` 内容粘贴到左边编辑器 → 右边自动出结构图
> 2. 右上角 Actions → **Export PNG (2x scale)** → 得到 2560×1440 高清 PNG（就是这张图 2），完美对齐模块不会画错
> 3. 想再美化成商业风格？打开 <https://app.diagrams.net/> → Arrange → Insert → Advanced → Mermaid → 粘贴源码 → 换 Drawio 的图标主题再导出 PNG

### 📐 技术规格
- 尺寸：**1600×900 px 横版 16:9**
- 风格：**自顶向下流程图（Top-Down）**，分为「5 大分区」：输入层 📡 / GUI 🖥 / AI 引擎 🧠 / 数据层 💾 / 告警联动 🚨
- 配色：各分区使用同一套 classDef：
  - GUI：青蓝 `#ecfeff → #0891b2`
  - 核心（Core）：橙 `#fff7ed → #ea580c`
  - AI：绿 `#f0fdf4 → #16a34a`
  - 数据：紫 `#faf5ff → #9333ea`
  - 告警：玫红 `#fff1f2 → #e11d48`

### 📝 【中文 AI 画图通用 Prompt】（若你不想用 Mermaid 源码直接画 2 次对比）
```
系统架构流程图，尺寸 1600×900 横版，自顶向下 5 个分区用虚线方框分隔，每分区左上角有 emoji 图标 + 分区名：

① 最上「📡 输入层」：3 个摄像头 1/2/N，每个图标是一个圆形小监控球，标题写多路 RTSP 摄像头，流出箭头连到下一层。

② 第二层「🖥 PyQt5 GUI 主进程」：左侧 MainWindow（大圆角方块）→ 中间 GridLayout（1×1/2×2/3×3/4×4 切换）→ 右侧 N 个 VideoWidget 小方块，MainWindow 上方连 Toolbar 8 个按钮图标（静音/布局/人脸/事件/设备/定时录像/上下线/夜间），下方连 FaceManagerDialog 弹窗 + EventHistoryDialog 弹窗。整个分区用青蓝色圆角大框。

③ 第三层「🧠 核心 AI 引擎」：左侧人脸检测 FaceEngine（写 4 层兜底链），中间人脸识别 FaceRecognizer（dlib 128D + 10 帧均值），右侧运动检测 MotionDetector（MOG2）。上方连 VideoWidget "每帧 30ms 拉取" 虚线。FaceEngine 用 YOLO bbox 复用箭头连 FaceRecognizer，FaceEngine 连 C2 聚集判定（绿色圆角），FaceRecognizer 连 C1 陌生人判定，MotionDetector 连 C3 离岗判定。整个分区用绿色圆角大框。

④ 右下「💾 数据层」：6 个紫色卡片：face_db.json / events.json+CSV / snapshots / records / config.sample.json / models 权重（写 4 个大文件放 Release Assets）。FaceRecognizer 双向连 face_db.json，MainWindow 双向连 config.sample.json，B2 录像连 records，B3 检索连 snapshots+events。

⑤ 最右「🚨 A4/A5 告警联动」：3 个玫红色卡片：🔔 winsound 告警音+静音 / status_bar 3s 红底 / 事件历史 9 类型。C1/C2/C3/B4 所有事件用统一的粗箭头连到 MainWindow，MainWindow 再分 3 条连告警 3 张卡片。

排版干净整齐，箭头不交叉，配色跟分区 classDef 一致，中文用思源黑体，没有 AI 假汉字。
```

### ✅ Checklist
- [ ] 5 个分区齐全、箭头方向正确（自顶向下 + 右联动）
- [ ] **「bbox 复用 0.6ms」** 这条绿色箭头必须能看见（答辩亮点）
- [ ] **「ONNX cv2.dnn 兜底」** 卡片里写在 FaceEngine 第 ①.5 层（答辩亮点）
- [ ] **「密码脱敏 admin:****」** 写在 ConfigManager 旁
- [ ] **「单入口 on_event_triggered」** 从 C1/C2/C3/B4 → MainWindow → 告警三卡片的通路要明显粗一点或用彩色箭头突出

---

## 🧠 图 3：算法链路细节图（Face Detection + Recognition 流水线）· 毕设 PPT "实现细节" 页

### 📐 技术规格
- 尺寸：**1600×1200 px 竖版 A4 比例**（答辩投影上放这张 10 秒不解释，老师就知道你真做了细节）
- 风格：**时序/流水线左→右流向**，上半是 **C1 陌生人检测链路**，下半是 **B1 多帧注册链路**（左右并排对比），中间放 共享组件
- 配色：**深蓝色 流程节点 / 绿色 dlib / 红色判定 / 灰色兜底分支**

### 📝 【中文 AI 画图通用 Prompt】
```
AI 算法链路细节图，1600×1200 竖版 A4，分为上下两条并行流水线，中间是共享模块，整体从左到右流动：

──────── 上半：🛰 C1 陌生人识别 实时链路（箭头向右粗箭头）────────
1. 第 1 块（Input 左）：RTSP 帧 BGR (H×W×3) 图像
2. 第 2 块：C4 夜间增强分支判断框（IF 平均亮度<50 或 🌙按下 → 走 YCrCb Y 通道 CLAHE(clipLimit=2.0 tileGridSize=8×8) → 输出 detect_frame；否则 detect_frame=原frame；画面展示原frame不偏色）
3. 第 3 块：FaceEngine 检测：大号标题写 4 层兜底链，4 个平行分支从上到下写 ①Ultralytics YOLOv8(best.pt) → ①.5 OpenCV DNN(best.onnx) YOLOv5 640×640 NMS ✨兜底推荐 ⭐ → ② Torch Hub → ③ DetectMultiBackend；每分支都出 N 个 bbox xyxy + confidence；最后绿色大框写「合并 clamp · 过滤 <20px小脸 · Top 10」→ 输出 List[bbox, conf]
4. 第 4 块：🚀 复用 YOLO bbox（黄色加粗高亮文字：不再 dlib.detector 二次扫，40ms→0.6ms，毕设亮点）
5. 第 5 块（共享模块，放在整张图中央，上下两分支都连）：FaceRecognizer：① dlib 68 点 shape_predictor 关键点对齐 → ② dlib ResNet v1 提取 128D 单位范数特征 → ③ 与 known_faces 全量欧氏距离 Top1 匹配
6. 第 6 块（右）：判定节点，红绿分叉：Top1 ≤ 0.6 → 绿框 2px + 黑底白字「张三 d=0.45」；Top1 > 0.6 → 红框 3px 加粗 + 黑底白字「陌生人 d=0.78」；陌生人分支再加一个「独立 8s 冷却」灰色沙漏小图标 → 存陌生人_通道_时间.jpg + emit stranger → A4 告警音 + A5 落库

──────── 下半：➕ B1 多帧 10 帧注册链路（箭头向右粗蓝线）────────
1. 第 1 块：人脸管理对话框 → 开始按钮 + QProgressDialog 进度条（写 250ms/帧 共 10 帧）
2. 第 2 块：连续 10 张 RTSP 帧，每帧复用同一条上半流程的 2→3→4→5 块 → 收集 10 条 128D 向量
3. 第 3 块（中间下方）：大号求和符号 → 10 条向量逐元素均值 → 再 L2 归一化使范数=1（写公式：e_final = normalize(mean(e₁..e₁₀))）
4. 第 4 块（右）：查重姓名是否已存在 → 绿色分叉写入 face_db.json → QMessageBox "已注册 张三 (9/10 帧平均)"；红色分叉提示已注册取消

整张图排版对齐上下两个分支，共享模块用半透明绿色大色块放在整张图中间水平方向横跨上下，让读者一眼看出两条链路都复用 FaceEngine + FaceRecognizer。字体是思源黑体，中文不产生错误字符。每个节点圆角矩形，粗细线区分主干和兜底。
```

### ✅ 算法亮点 Checklist（答辩老师一眼能看到的 6 个要点，画出来 +⭐）
- [ ] ⭐ ①.5 ONNX (cv2.dnn) 兜底分支（无外网依赖，28.5MB 单文件推理）
- [ ] ⭐ YOLO bbox 复用 0.6ms（40ms → 0.6ms 性能对比数字要写显眼）
- [ ] ⭐ 多帧 10 帧均值 + L2 再归一化公式（不是只写"均值"两个字）
- [ ] ⭐ 陌生人独立 8s 冷却、聚集 30s 冷却、离岗单次 fire 直到活动恢复（冷却策略分层图）
- [ ] ⭐ CLAHE 只均衡 Y 通道（画面展示仍原帧不偏色不偏绿偏蓝，写"只给检测/运动，展示/录像用原帧"）
- [ ] ⭐ 陌生人/熟人距离阈值 0.6（欧氏距离 dlib 默认阈值，答辩老师都认识）

---

## 📐 推荐导出 & 压缩
- 所有图用 AI 工具导出后，用 <https://tinypng.com/> 在线压缩 PNG（体积减少 70% 不丢清晰度，README 加载秒开）
- Mermaid 导出图片请再压缩一次，Mermaid 原始 PNG 很大
- 如果要做 PPT 打印海报：再加一张 A1 海报就是这张「图 1 大字报」导出 PDF 送打印店彩色铜版纸 ✨
