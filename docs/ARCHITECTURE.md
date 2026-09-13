# IPC-Monitor 当前架构

## 运行链路

```text
PyQt 主窗口
  └─ GridLayoutWidget
      └─ VideoWidget（每路摄像头一个）
          ├─ CaptureThread：后台读取 RTSP/本地摄像头帧
          │   └─ LatestFrameBuffer：只保留最新帧，避免推理延迟堆积
          ├─ AnalysisThread：后台执行人脸检测、运动检测和 dlib 识别
          │   └─ result_ready：把纯数据结果发回 UI 线程
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

当前 `VideoWidget` 使用 Qt 定时器轮询 `LatestFrameBuffer`，而 `CaptureThread` 在后台读取视频；`AnalysisThread` 负责检测、运动分析和 dlib 识别，UI 线程只消费普通结果并负责告警、截图、绘制和录像。`core/video_manager.py` 的 `VideoThread` 仅保留兼容别名，避免重复维护两套线程实现。

配置保存使用临时文件加 `os.replace`，重连使用 `core/reconnect_policy.py` 的单调时间退避；这两部分都不在 UI 线程中阻塞等待。

性能指标目前只做观测，不宣称已经完成全部性能优化。下一步必须在相同视频、路数和检测频率下对比 `get_performance_snapshot()` 的结果，并额外记录分析队列丢弃数、识别延迟和告警时序。

本地可先运行 `python tools/run_performance_benchmark.py --frames 30`，得到 1/4/9 路合成基线。该工具使用 fake engine，不加载摄像头或模型，目的是真实验证结果帧号是否按路保持、指标是否可采集；真实性能结论仍需用固定视频或摄像头输入复测。

固定视频实测曾暴露共享 `cv2.dnn_Net` 并发时的 NaN/Infinity 输出；现在 `FaceEngine` 串行保护 ONNX 的 `setInput/forward`，并在坐标变换前过滤非有限预测。修复后同一 640×480 本地样本、每路 5 帧的 P95 约为 1 路 164 ms、4 路 643 ms、9 路 1467 ms，说明稳定性恢复但共享 CPU 检测器成为瓶颈。该基准直接调用分析函数，`queue_dropped=0` 只表示本次没有模拟提交队列压力。

队列压力可用 `python tools/run_performance_benchmark.py --queue-pressure --frames 12 --delay-ms 5` 单独验证：12 次快速提交只处理最后的帧 11，丢弃 11 次。这证明“最新请求优先”是有界策略，但不代表实时画面完全不丢帧。

## 下一阶段迭代入口

1. 为断流重连、录像文件轮转和事件冷却增加可重复测试。
2. 用采集线程 + 有界帧队列替代同步检测，测量 4/9/16 路 CPU、延迟和丢帧率。
3. 将检测、识别、运动分析抽成独立服务对象，继续缩小 `VideoWidget` 的业务边界。
