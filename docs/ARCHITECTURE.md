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

在内存恢复后，使用真实 ONNX/dlib 固定视频、每路 3 帧、单 worker 的低内存烟测为：1 路 P95 168.26 ms / 6.95 FPS，4 路 P95 139.75 ms / 7.31 FPS，9 路 P95 134.75 ms / 7.61 FPS；三组均完整处理且 `queue_dropped=0`。这是可重复的本机样本基线，不是跨设备性能承诺。

队列压力可用 `python tools/run_performance_benchmark.py --queue-pressure --frames 12 --delay-ms 5` 单独验证：12 次快速提交只处理最后的帧 11，丢弃 11 次。这证明“最新请求优先”是有界策略，但不代表实时画面完全不丢帧。

主窗口底部诊断栏每秒读取实际占用通道的 `get_performance_snapshot()`，显示分析丢弃总数、最近分析帧和最近告警帧。它是只读观测层，不参与告警决策；空的网格槽位不会计入在线通道。

事件冷却从截图证据成功落盘后开始计时；如果 `_save_frame()` 失败，不会更新冷却时间，也不会发出空路径事件。

录像生命周期同样遵循“真实帧才启动、停止时只释放一次”的边界：`VideoWriter` 使用原始帧尺寸，`stop_record()` 先清空引用再调用 `release()`，窗口关闭和断流路径都可以安全重复调用。

定时录像的小时轮转已抽成 `_ensure_scheduled_recording(frame, now)`：小时键变化时先停止旧 writer，再创建新 writer，测试可注入时间而不依赖真实时钟。

采集线程的 soak 边界也已覆盖：正常停止和读帧失败都会释放 `VideoCapture`，重复启动/停止不会累积旧句柄；这些测试使用 fake capture，不需要真实摄像头。

真实设备的长时间验收使用 `python tools/run_runtime_soak.py --pid <PID> --duration-minutes 30 --interval-seconds 10`，输出 CSV 只包含 UTC 时间、PID、RSS 内存、线程数和 CPU 百分比。它不能替代摄像头画面正确性测试，但能帮助判断运行期间是否持续增长。

验收结束后运行 `python tools/analyze_runtime_soak.py data/logs/runtime_soak.csv`，重点看 `rss_delta_mb`、`max_rss_mb` 和 `thread_delta`；这些指标只描述进程健康趋势，不自动判定业务正确性。

分析器默认只做保守提示：RSS 增量达到 50 MB 或线程增加达到 2 时输出 `REVIEW`，否则输出 `PASS`。阈值用于决定是否复查，不等于已经证明存在泄漏。

## 下一阶段迭代入口

当前稳定性主线已完成源码级和确定性测试闭环，后续不再重复建设同类测试。剩余工作按依赖分为：

1. **无需摄像头**：继续完善固定视频 + 真实 ONNX/dlib 的可重复基准，把 CPU、P95、FPS、丢帧和识别延迟写入版本化报告；再逐步把检测、识别、运动分析从 `VideoWidget` 抽成独立服务对象。
2. **需要摄像头**：用真实 EXE 做 30 分钟运行记录，观察 RSS、线程数、重连次数，并验证真实 RTSP 断流恢复、画面正确性和告警误报/漏报。这些证据不能由 fake capture 或合成视频替代。
3. **发布工程**：将源码测试、隐私扫描、打包自检和版本信息固化到 GitHub Actions；发布前继续核对模型清单、依赖和用户数据目录边界。
