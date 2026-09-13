# IPC-Monitor 当前架构

## 运行链路

```text
PyQt 主窗口
  └─ GridLayoutWidget
      └─ VideoWidget（每路摄像头一个）
          ├─ CaptureThread：后台读取 RTSP/本地摄像头帧
          │   └─ LatestFrameBuffer：只保留最新帧，避免推理延迟堆积
          ├─ reconnect_policy：按单调时钟做指数退避重连
          ├─ face_engine：OpenCV DNN + best.onnx 人脸检测
          ├─ face_recognizer：可选 dlib 特征提取与本地人脸库匹配
          ├─ motion_engine：MOG2 运动区域检测
          ├─ event_logger：记录事件并发出 UI 信号
          └─ snapshots/records：写入用户数据目录
          └─ performance_metrics：记录处理耗时、P95、丢帧与窗口 FPS
```

## 路径与隐私边界

- 只读资源使用 `core.app_paths.R()`，兼容源码目录和 PyInstaller 临时目录。
- 配置、人脸库、截图、录像和日志使用 `core.app_paths.U()`，写入程序目录下的 `data/`。
- 发布仓库不包含真实摄像头地址、账号、密码、人脸样本或运行日志。

## 稳定性说明

当前 `VideoWidget` 使用 Qt 定时器轮询 `LatestFrameBuffer`，而 `CaptureThread` 在后台读取视频；检测、识别、绘制和录像仍在 UI 定时器中执行。`core/video_manager.py` 的 `VideoThread` 仅保留兼容别名，避免重复维护两套线程实现。下一阶段再评估是否把 AI 推理也拆到工作线程。

配置保存使用临时文件加 `os.replace`，重连使用 `core/reconnect_policy.py` 的单调时间退避；这两部分都不在 UI 线程中阻塞等待。

性能指标目前只做观测，不宣称已经完成线程化优化。后续比较采集线程方案时，必须在相同视频、路数和检测频率下对比 `get_performance_snapshot()` 的结果。

## 下一阶段迭代入口

1. 为断流重连、录像文件轮转和事件冷却增加可重复测试。
2. 用采集线程 + 有界帧队列替代同步检测，测量 4/9/16 路 CPU、延迟和丢帧率。
3. 将检测、识别、运动分析抽成独立服务对象，保持 `VideoWidget` 只负责显示和信号。
