# IPC-Monitor

IPC-Monitor 是一个面向 Windows 的多路 RTSP 摄像头监控与本地人脸分析工具。它提供可视化摄像头管理、自动网格布局、录像回放、事件历史、人脸注册与识别、陌生人告警、人员聚集检测、值守状态检测和低照度增强。

当前开发版本：`1.2.0-dev`。`main` 是 `v1.1.0` 之后的持续开发主线，下一次正式版本将在固定视频性能基准和发布工程收口后再发布。

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4.svg)](#)

## 主要功能

- 多路 RTSP 视频接入，支持 1×1、2×2、3×3、4×4 自动布局。
- OpenCV DNN + ONNX 人脸检测，默认运行不依赖 PyTorch。
- dlib 128 维人脸特征注册、识别和多帧平均注册。
- 陌生人、人员聚集、设备上下线和离岗事件提醒。
- 手动录像、定时录像、截图、录像回放和事件 CSV 导出。
- 夜间低照度增强、通道全屏和告警静音。
- 源码运行与 PyInstaller 单文件 EXE 两种使用方式。
- 配置、人脸库、日志、截图和录像均保存在本机，不上传外部服务。
- 提供帧处理耗时、P95 延迟、处理帧数、丢帧数和窗口 FPS 的性能诊断指标，为多路线程化优化提供基线。
- 提供 `tools/run_runtime_soak.py`，在真实摄像头验收时只记录进程内存、线程数和 CPU 趋势，不保存视频或摄像头配置。
- 提供 `tools/analyze_runtime_soak.py data/logs/runtime_soak.csv`，汇总起止 RSS、最大 RSS、线程变化和平均 CPU。
- 分析器会对明显 RSS/线程增长给出 `REVIEW` 提示；这是复查信号，不是自动泄漏结论。
- 采集线程与 UI 定时器分离，使用最新帧缓冲，降低 RTSP 读取和推理对界面响应的影响。
- 人脸检测、运动检测和 dlib 人脸识别在后台分析线程执行，结果通过 Qt 信号回到界面；告警、截图、画框和录像仍由 UI 线程统一处理。
- 可运行 `python tools/run_performance_benchmark.py --frames 30` 生成 1/4/9 路合成基线；报告包含 P95、FPS、队列丢弃和结果帧号，仅用于验证线程边界与指标链路，不代替真实摄像头压测。
- 多路共享 OpenCV DNN 时，检测器的 `setInput/forward` 已串行保护，并过滤 NaN/Infinity 输出，避免并发下坐标异常导致崩溃；真实吞吐仍需按设备复测。
- 可运行 `python tools/run_performance_benchmark.py --queue-pressure --frames 12 --delay-ms 5` 验证最新请求优先：12 次提交只处理最后帧，丢弃数为 11。
- 固定视频真实模型基准支持 `--camera-counts 1 --workers 1` 分批运行，适合内存有限的 Windows 环境。
- GitHub Actions 会在 `main` 和 Pull Request 上自动执行测试、源码编译和空白检查。
- 主界面底部诊断栏每秒汇总实际占用通道的分析丢弃数、最近分析帧和最近告警帧，便于排查“告警截图是否落后”。

## 验证方式

- 没有摄像头时，可使用仓库中的固定录像和 fake capture 验证线程、录像、告警证据和资源释放；这类结果不替代真实 RTSP 验收。
- 固定视频真实模型基准建议从单路、少帧数开始，再逐步扩展到 1/4/9 路；如果 Windows 可用虚拟内存不足，应记录为环境阻断并分批运行。

## 后续路线

1. 固定视频 + 真实 ONNX/dlib 的可重复性能报告。
2. 将检测、识别和运动分析继续从 `VideoWidget` 拆成独立服务对象。
3. 将测试、隐私扫描、打包自检和版本信息固化到 GitHub Actions。
4. 接入真实摄像头后，再补 RTSP 断线恢复、30 分钟 EXE 运行和误报/漏报记录。

## 直接运行 EXE

1. 打开仓库的 [Releases](https://github.com/sun2006-xin/ipc-monitor/releases) 页面。
2. 下载最新的 `IPC-Monitor-windows-x64.zip`。
3. 解压到可写目录，不要直接在压缩包内运行。
4. 双击 `IPC-Monitor.exe`。
5. 首次启动后通过“添加设备”填写自己的摄像头连接信息。

程序不会附带任何默认摄像头、IP 地址或登录凭据。运行时数据会写入 EXE 同级的 `data/` 目录。

## 从源码运行

环境要求：Windows 10/11、Python 3.11。

```powershell
git clone https://github.com/sun2006-xin/ipc-monitor.git
cd ipc-monitor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Windows 用户也可以在安装依赖后双击 `run.bat`。

默认检测后端使用 `best.onnx` 和 OpenCV DNN。只有需要实验 PyTorch/Ultralytics 后端时，才安装可选依赖：

```powershell
python -m pip install -r requirements-optional-yolo.txt
```

## 摄像头配置

程序首次启动时设备列表为空。请在界面中添加设备，并填写：

- 设备名称
- 摄像头主机地址
- RTSP 端口
- 用户名与密码
- 视频流路径

真实配置保存在 `data/config.json`，该文件已被 `.gitignore` 排除。请勿将真实配置、人脸数据、截图、录像或日志提交到公开仓库。

## 项目结构

```text
ipc-monitor/
├─ main.py                       程序入口与崩溃日志保护
├─ run.bat                       源码双击启动器
├─ build_exe.ps1                 Windows EXE 构建与自测
├─ build_exe.bat                 构建脚本入口
├─ core/
│  ├─ app_paths.py               源码/EXE 资源与用户数据路径
│  ├─ config_manager.py          本地配置和 RTSP 地址构造
│  ├─ face_engine.py             ONNX 人脸检测
│  ├─ face_recognizer.py         dlib 人脸特征与识别
│  ├─ motion_engine.py            运动检测
│  ├─ reconnect_policy.py         非阻塞重连退避策略
│  ├─ capture_thread.py           采集线程与最新帧缓冲
│  ├─ analysis_thread.py          人脸/运动分析线程
│  └─ video_manager.py            兼容旧名称的线程入口
├─ ui/
│  ├─ video_widget.py             单路采集、检测、录像与事件显示
│  └─ event_history_dialog.py     事件历史与 CSV 导出
├─ models/                       dlib 模型
├─ best.onnx                     默认人脸检测模型
├─ best.pt                       可选 PyTorch 检测模型
├─ resources/                    翻译与告警音资源
├─ data/                         本地运行数据目录
└─ tests/                        路径、ONNX 和发布隐私测试
```

架构、数据流和后续拆分边界见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 构建 Windows EXE

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_exe.ps1
```

构建流程会：

1. 生成控制台版并执行启动自测。
2. 检查 ONNX 后端是否成功加载且没有致命错误。
3. 生成最终无控制台窗口版 `dist\IPC-Monitor.exe`。

构建脚本不会打包 `data/` 中的用户配置、人脸数据、截图、录像或日志。

## 本地测试

```powershell
python -m unittest discover -s tests -v
python -m compileall -q core ui main.py tests
```

## 常见问题

### 程序无法连接摄像头

- 确认摄像头已启用 RTSP。
- 确认主机地址、端口、账号、密码和流路径正确。
- 确认电脑可以访问摄像头所在网络。
- 查看 `data/logs/` 中的日志，但不要公开包含设备信息的日志文件。
- 程序会按 0.5、1、2、4 秒逐步退避重连，恢复连接后自动清零；这段时间界面保持响应。

### 配置文件损坏

程序会优先从 `data/backups/` 恢复最近备份；没有可用备份时，会在同一数据目录生成隐私安全的默认配置。配置写入采用临时文件替换，避免断电留下半个 JSON 文件。

### EXE 启动后没有设备

这是预期行为。为保护隐私，发布包不包含默认摄像头配置，请手动添加设备。

### dlib 安装失败

请使用 Python 3.11，并优先安装与当前 Python 版本和系统架构匹配的预编译 wheel。源码编译 dlib 需要 Visual Studio C++ Build Tools 和 CMake。

## 隐私与安全

- 仓库和发布包不包含真实摄像头地址、密码或作者本机配置。
- RTSP 地址写入日志前会隐藏密码。
- 用户数据只保存在本地 `data/` 目录。
- 发布前会检查暂存文件中的私网地址、带凭据 URL、密钥和令牌模式。
- 如果敏感信息曾经进入公开提交，仅删除当前文件并不足够；应立即更换凭据，并单独处理 Git 历史。

## License

本项目采用 [Apache License 2.0](LICENSE)。第三方模型和依赖仍受其各自许可证约束。

## 致谢

- [OpenCV](https://opencv.org/)
- [dlib](http://dlib.net/)
- [PyQt](https://www.riverbankcomputing.com/software/pyqt/)
- [Ultralytics](https://github.com/ultralytics/ultralytics)
