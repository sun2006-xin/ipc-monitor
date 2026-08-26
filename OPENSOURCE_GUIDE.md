# 开源到 GitHub · 10 步手搓完全指南（毕设新手零失败版）

> **开源协议：Apache-2.0**（A 系列主流许可，附带贡献者专利授权 + 专利反诉公平终止条款，比 MIT 多一层专利保护。详见同目录 LICENSE 文件或 <https://www.apache.org/licenses/LICENSE-2.0>）
>
> 本指南配合作者桌面文件夹 `Desktop\ipc_monitor_open` 使用。  
> ❗ 全程 **不要手动复制** 真实数据/账号/密码/大权重文件，严格按下面第 4 步的「git status 安全检查」。
> 配套视频教程（自己搜）：B 站 "GitHub 新手上传项目"。

---

## 🔴 开源前必做 2 件事（5 分钟）
### ① 确认桌面副本是「纯净版」
```
桌面 ipc_monitor_open 目录必须：
  data/config.json                 = 不存在 ✅（.gitignore 已忽略 + 只有 sample）
  data/face_db.json                = 不存在 ✅（.gitignore 已忽略 + 只有 sample）
  data/faces/ 下                   = 只有 .gitkeep，没有 jpg ✅
  data/motions/ snapshots/ records = 只有 .gitkeep ✅
  best.pt / best.onnx / models/*.dat = 不存在 ✅（.gitignore 排除，另放 Release Assets）
```

### ② 确认本机装了 Git + 有 GitHub 账号
- Git 下载：<https://git-scm.com/download/win> 一路 Next（安装时勾 "Git from the command line and also from 3rd-party software"）
- 打开 PowerShell / CMD：`git --version` 输出版本 = 成功
- 有 GitHub 账号：<https://github.com/join>

---

## 🛠 STEP 1～10（照抄就能成功）

### STEP 1：配置 Git 身份（第一次使用 Git 才需要）
打开 PowerShell，粘贴两行（把 `你的GitHub用户名`、`你的邮箱` 改成你自己的）：
```powershell
git config --global user.name  "你的GitHub用户名"
git config --global user.email "你注册GitHub用的邮箱@xx.com"
# 验证
git config --global --list
```
如果显示上面两行 = 通过。

### STEP 2：进入桌面纯净副本目录
```powershell
cd "$env:USERPROFILE\Desktop\ipc_monitor_open"
```

### STEP 3：初始化 Git 仓库 + 第一次 commit
```powershell
git init -b main
git add -A
git status               # 🔴 必须停下来看一眼输出：
                         #   不能有 "new file: data/config.json"
                         #   不能有 "new file: data/face_db.json"
                         #   不能有 "new file: best.pt / best.onnx / models/*.dat"
                         #   不能有 "new file: data/logs/xxx.log / data/faces/xxx.jpg"
                         # 只要出现任何上面 4 类 = 立刻停止！回到「🔴 开源前必做 2 件事」
git commit -m "chore: first commit · 毕设 IPC-Monitor 源码 (Apache-2.0)"
```
> 如果 `git status` 显示的 list 跟你 README 的目录结构一样（17 源 py 文件 + README/LICENSE/.gitignore/requirements/bat/samples + 6 个 .gitkeep）= 安全 ✅

### STEP 4：安装并登录 GitHub CLI `gh`（推荐，比网页新建 repo 复制 URL 稳 10 倍）
GitHub CLI 下载：<https://cli.github.com/> → Windows MSI 64-bit 装完重启 PowerShell。
```powershell
gh --version          # 验证
gh auth login         # 登录（一步一步选：GitHub.com → HTTPS → Login with a web browser → 回车 → 浏览器打开贴 8 位码 → 授权）
gh auth status        # 显示 Logged in to github.com as <你的用户名> (OAuth) = OK
```

### STEP 5：创建远程仓库并推送到 GitHub
```powershell
# 仓库名就叫 ipc-monitor（全小写短横线，符合 GitHub 习惯）
gh repo create ipc-monitor --public --source=. --remote=origin --push
```
看到 `✓ Created repository 你的用户名/ipc-monitor on GitHub` + `✓ Pushed commits to origin/main` = 成功 ✅

> **网页建仓库备选方案（不想装 gh）**：  
> 打开 <https://github.com/new>，Repository name 填 `ipc-monitor` → Public → ⚠ **三个 Initialize 勾全不勾（Don't add README / LICENSE / .gitignore）** → Create Repository。  
> 然后把页面给出的两行 "…or push an existing repository from the command line" 复制粘贴执行，就是：
> ```powershell
> git remote add origin https://github.com/你的用户名/ipc-monitor.git
> git branch -M main
> git push -u origin main
> ```

### STEP 6：刷新仓库主页 → （可选）Release v1.0.0 发布 EXE 演示包
> 🎉 **好消息：4 个权重模型全部 ≤100MB，已直接内置在 Git 仓库里**（best.pt 54MB / best.onnx 27MB / dlib landmarks.dat 95MB / recognition.dat 21MB，合计 ≈198MB）。别人 git clone 下来**直接就能用**，不需要再手动下载权重到 Release！
>
> 下面 STEP 6 是「锦上添花」：把 Windows 免安装 EXE 也打包发 Release，让完全不会用 Python 的老师同学也能双击打开。
1. 网页打开自己仓库主页 → 右边栏 **Releases → Create a new release**
2. Tag version：填 `v1.0.0`；Release title：填 `毕设答辩版 v1.0.0 · Apache-2.0 开源 · 4 权重已内置`
3. 下面 Attach binaries：**（可选）打包好的 IPC-Monitor.exe 拖拽上传**（README 写了 build_exe.bat 双击打包）
   - 权重文件**不需要再传了**，已经在 Git 里 clone 就有
4. 点 **Publish release**（公开发布）
5. 把发布页 URL 复制到 README.md 最底部 "Windows 免安装版下载"那一节（可选锦上添花）。

### STEP 7：上传 3 张宣传图 + 把 demo 截图替换占位
1. 去 `docs/image_prompts.md` 抄 3 套提示词 → 喂给 Midjourney / DALL·E / SD / 豆包画图，生成 3 张 PNG 存到：
   - docs/poster_overview.png   （大字报 · 1920×1080 横版）
   - docs/structure_diagram.png （系统结构图 · 1600×900 横版）
   - docs/algorithm_detail.png  （算法细节图 · 1600×1200 竖版）
2. `docs/screenshots/home_placeholder.png`、`c_demo_placeholder.png`、`face_db_placeholder.png` 用你自己 demo 时按 Win+Shift+S 截图替换。
3. 提交并 push：
   ```powershell
   git add -A && git commit -m "docs: 更新宣传图 + 替换 demo 截图占位" && git push
   ```

### STEP 8：写 GitHub 简介（仓库顶部 About）
打开仓库主页 → 齿轮 ⚙ About，按下面填：
- **Description**：  
  毕设多路 RTSP 智能监控 · PyQt5 + YOLOv5 人脸检测 + dlib 人脸识别 · 13 功能 A/B/C 三档分级演示 · Apache-2.0
- **Website**：空
- **Topics**（标签，打勾这几个能大大提高被搜中概率）：
  `graduation-project` `ip-camera` `rtsp` `pyqt5` `face-detection` `face-recognition` `yolov5` `dlib` `opencv-dnn` `onnx` `windows-desktop` `surveillance` `chinese-readme`
- ⚠ 勾选 **Include in the home page recommendations**

### STEP 9：打包 EXE（可选，你说可选可不选；答辩给老师演示用方便）
1. 在**你自己的开发工作目录**（桌面纯净副本没装依赖、缺权重，打包会失败；就用你平时写代码的那个 `ipc_monitor` 文件夹）：
   ```powershell
   cd <你本机存放代码的任意目录，例如 X:\project\ipc_monitor>
   .\build_exe.bat
   ```
2. 等 3-5 分钟，成功后生成 `dist\IPC-Monitor.exe`（约 400MB）
3. 把它也拖到刚才 Release v1.0.0 页面的 Attach binaries 一起上传（Update release）。
4. README 最底部可以加一句 "Windows 免安装版：Release v1.0.0 下载 IPC-Monitor.exe + 4 个权重 → 双击 run"。

### STEP 10：Star 自己的仓库 + 朋友圈 + 毕设 PPT 挂仓库地址
- 浏览器打开仓库 → 右上角 Star 按钮（⭐ + 1）
- PPT 最后一页加「GitHub：https://github.com/<你的用户名>/ipc-monitor」二维码（用 <https://cli.im/> 生成 QR）
- 朋友圈/同学群分享 → 10 ⭐ 以上答辩老师会觉得你做的很专业 🎓

---

## 🆘 常见错误 + 一次性修好

| 错误 | 原因 | 一步修好 |
|------|------|---------|
| `git: 'credential-manager' is not a git command` | Git 旧版没装 GCM | 去 <https://git-scm.com/download/win> 重装最新版（带 Git Credential Manager 勾上）|
| `fatal: Authentication failed` | GitHub 2021 后不再支持密码登录 | ① 用 `gh auth login`（推荐）② 或者 GitHub Settings → Developer settings → Personal access tokens (classic) 生成 1 个 token 当密码贴 |
| `error: failed to push some refs to` | 远程有初始 README 本地没有 | `git pull origin main --rebase --allow-unrelated-histories` → 再 `git push` |
| `remote: error: File best.pt is 56.79 MB; this exceeds GitHub's file size limit of 50.00 MB` / `GH001` | 大文件被 .gitignore 漏掉了 | 立刻 `git rm --cached best.pt best.onnx models/*.dat data/config.json data/face_db.json` → 检查 .gitignore 是否正确 → 重新 commit |
| `warning: LF will be replaced by CRLF` | Windows 换行符 CRLF ≠ Linux LF | 不管也行，强迫症执行 `git config --global core.autocrlf true` |
| 仓库 About 看不到中文 / 中文乱码 | README 是 UTF-8 BOM 才会让 GBK 编辑器乱码，但 GitHub 默认 UTF-8 | 我们所有 md 文件都是 UTF-8（无 BOM），不会乱码。如果乱码了：用 VS Code 打开 → 右下 UTF-8 → Save with Encoding → UTF-8 |
| `The filename or extension is too long` when cloning | Windows 长路径关了 | 管理员 PowerShell 跑：`New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force`，重启电脑 |

---

## ⚠ 安全底线 Checklist（每一项都确认 ✅ 才能对外开源）
- [ ] 我没有 **泄露自己的摄像头账号密码**（config.json 在 .gitignore，sample.json 只有 your_password_here 占位）
- [ ] 我没有 **泄露个人真实人脸快照**（data/faces/ / snapshots/ / records/ / motions/ 只有 .gitkeep）
- [ ] 我没有 **泄露人脸特征 128D 向量**（face_db.json 在 .gitignore，只有 sample 全 0）
- [ ] 我没有 **泄露内网 IP**（代码默认值是 192.168.1.100 占位，redact_rtsp 不会把真 IP 密码打 stdout）
- [ ] 我没有 **超过 100MB 的单文件在 Git 里**（已验证 4 个权重 best.pt 54MB / onnx 27MB / landmarks 95MB / recognition 21MB 全部 < 100MB 直接内置 Git，clone 即用）
- [ ] 我把 **LICENSE Apache-2.0 文件** 放进了 Git（本指南同目录有 LICENSE，Apache License Version 2.0 官方全文，附带专利授权 + 公平反诉终止条款）
- [ ] 我知道 `.gitignore` 里写的 **不会被提交** 的东西；如果不确定 `git status -u` 一看就知道

如果有任何一项没勾上 —— **先别急着 push**，告诉我缺什么，我帮你修完再开源 🚀
