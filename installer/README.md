# MelodySheet 安装包（Windows + macOS）

把整个产品（FastAPI 后端 + 静态前端 + ffmpeg）封装成原生安装包。安装后用户双击应用，浏览器自动打开 `http://127.0.0.1:8765/`。无需手动安装 Python、Node.js、ffmpeg。

| 平台 | 产物 | 单 tag push 触发 |
|---|---|---|
| **Windows** | `MelodySheet-Setup.exe`（Inno Setup 自解压安装器，~150 MB）| `Build Windows installer` workflow |
| **macOS** (Apple Silicon) | `MelodySheet-macOS.dmg`（拖入 Applications 即可）| `Build macOS installer` workflow |

## 两种构建路径

### A. 推荐：GitHub Actions 自动构建（零本地依赖）

只要把代码 push 到 GitHub：

```bash
git tag v0.1.0
git push origin v0.1.0
```

**两个 workflow 都会被同时触发**（Windows + macOS），各 15-25 分钟产出对应安装包。也可以在 Actions 标签页手动 dispatch 单独某个平台。

工作流定义：
- [`.github/workflows/build-windows-installer.yml`](../.github/workflows/build-windows-installer.yml) → Windows
- [`.github/workflows/build-macos-installer.yml`](../.github/workflows/build-macos-installer.yml) → macOS

### B-macOS. 本地（Mac 机器）构建

**一次性准备**：
```bash
brew install python@3.11 node ffmpeg create-dmg
```

**构建**（在终端，仓库根目录）：

```bash
bash installer/build_macos.sh
```

跑约 10-15 分钟。完成后 `installer/out/MelodySheet-macOS.dmg` 就是发布产物。可选环境变量：

- `SKIP_FFMPEG=1` 复用已下载的 ffmpeg
- `SKIP_WEB=1` 复用已 build 的 `apps/web/out`
- `SKIP_BACKEND=1` 跳过 PyInstaller（只重做 DMG 打包）

**关于 macOS 签名 / 公证**：

未签名的 .app 用户首次打开会被 Gatekeeper 拦：
```
"MelodySheet" 无法打开,因为无法验证开发者。
```
解决方法：右键 → **打开** → 在弹窗里再点一次"打开"。从此就能正常用了。

正式发布建议买 Apple Developer Program (¥688/年) 做 code-sign + notarize，能让用户 Gatekeeper 0 警告启动。流程：
```bash
codesign --deep --force --options runtime --sign 'Developer ID Application: NAME' dist/MelodySheet.app
xcrun notarytool submit installer/out/MelodySheet-macOS.dmg --keychain-profile mynotary --wait
xcrun stapler staple installer/out/MelodySheet-macOS.dmg
```

### B-Windows. 本地（Windows 机器）构建

**一次性准备**：
- Python 3.11 x64（务必 x64）— [python.org](https://www.python.org/downloads/windows/) 装并勾选 "Add to PATH"
- Node.js 20 LTS — [nodejs.org](https://nodejs.org/)
- Inno Setup 6 — [jrsoftware.org](https://jrsoftware.org/isdl.php)，安到默认路径

**构建**（在 PowerShell，仓库根目录）：

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

跑约 10–15 分钟。完成后 `installer\out\MelodySheet-Setup.exe` 就是发布产物。

可选参数：
- `-SkipFfmpegDownload` — 复用已下载的 ffmpeg
- `-SkipWebBuild` — 复用已 build 的 `apps\web\out`
- `-SkipBackendBuild` — 跳过 PyInstaller（只重做 Inno Setup）
- `-IsccPath` — 自定义 ISCC.exe 路径

## 安装包结构

```
MelodySheet-Setup.exe                   ← Inno Setup 自解压安装器（~150 MB）
  └─ 安装到 %LOCALAPPDATA%\Programs\MelodySheet\
       MelodySheet.exe                   ← PyInstaller 启动器
       _internal\                        ← Python 运行时 + 依赖
         web\                            ← 静态前端 (index.html, _next/...)
         ffmpeg\ffmpeg.exe              ← 内嵌 ffmpeg
         apps\api\                       ← 后端源
         librosa\..., music21\..., basic_pitch\..., scipy\..., numpy\...
```

运行时数据（上传的音频 + 生成的乐谱）写在 `%APPDATA%\MelodySheet\storage\`，卸载会保留 — 用户可手动清理。

## 启动流程

1. 用户双击桌面 / 开始菜单的 **小提琴旋律谱** 图标
2. `MelodySheet.exe` (`installer/launcher.py`) 起飞：
   - 探测可用端口（默认 8765，被占用就 +1 / +2 / +3 / 随机）
   - 把 `_internal\ffmpeg` 加到当前进程 `PATH`
   - 把存储目录指向 `%APPDATA%\MelodySheet`
   - 起 uvicorn，单进程同时服务 API + 静态前端
   - 等端口起来后调系统默认浏览器打开 `http://127.0.0.1:<port>/`
3. 一个 console 窗口留着显示日志；关掉窗口就退出

## 已知细节 / 取舍

- **首次启动较慢**（5–10 秒）：PyInstaller 解压 `_internal` + librosa cold load。
- **杀软告警**：未签名的 PyInstaller exe 偶尔被 Windows Defender SmartScreen 标"未知发布商"。生产发布前用 EV code signing 证书签名能消除。
- **占用磁盘 ~500 MB**：numpy + scipy + librosa + music21 + basic-pitch 本身就大；安装包压缩后 ~150 MB。
- **CREPE 默认未装**：体积 +250 MB（TensorFlow）。需要的用户可以在 `apps/api/.venv-build` 里 `pip install crepe` 再重 build。
- **Demucs 默认未装**：体积 +400 MB。同上。
- **不签名跨账户运行**：installer 装到 `%LOCALAPPDATA%`（per-user），不需要管理员权限。要装到 `Program Files`（全机器）改 `melody-sheet.iss` 的 `DefaultDirName={autopf}\MelodySheet` 并把 `PrivilegesRequired=admin`。

## 卸载

控制面板 → 程序和功能 → **小提琴旋律谱** → 卸载。会移除 Program Files 内容但**保留 `%APPDATA%\MelodySheet\storage\`** 里的用户数据。

## 路径速查

| 路径 | 内容 |
|---|---|
| `installer/launcher.py` | exe 入口，启动 uvicorn + 打开浏览器 |
| `installer/melody-sheet.spec` | PyInstaller 配置 |
| `installer/melody-sheet.iss` | Inno Setup 安装器配置 |
| `installer/build.ps1` | 一键构建脚本（Windows 本地）|
| `installer/melody-sheet.ico` | （可选）应用图标。缺失时 PyInstaller/Inno Setup 用默认图标 |
| `installer/vendored/ffmpeg/` | 构建时下载的 ffmpeg.exe（被 spec 文件引用）|
| `installer/out/MelodySheet-Setup.exe` | 最终产物 |
| `dist/MelodySheet/MelodySheet.exe` | PyInstaller 中间产物（onedir 模式）|
| `apps/web/out/` | Next.js 静态导出（被 PyInstaller 打入 `_internal/web/`）|
| `.github/workflows/build-windows-installer.yml` | GH Actions 自动构建 |

## 调试

构建失败首先查：

1. **PyInstaller 报缺包**：把缺失模块名加进 `melody-sheet.spec` 的 `hiddenimports`。
2. **`basic-pitch` 在 Windows 报 CoreML**：build.ps1 已经装了 `basic-pitch[onnx]`，确认仍然走的是 ONNX runtime。
3. **静态前端 404**：检查 `apps\web\out\index.html` 存在；`NEXT_OUTPUT=export` 没设导致 build 仍是 Node.js 模式。
4. **运行时 `_internal\web` 找不到**：spec 的 `datas` 没把 `apps\web\out` 拷过去（spec 会跳过缺失的目录并打 warning）。
5. **杀软删 exe**：临时排除安装路径，或用代码签名证书。

跑 PyInstaller 单独看错误：

```powershell
cd <repo>
apps\api\.venv-build\Scripts\pyinstaller.exe --clean --noconfirm installer\melody-sheet.spec
.\dist\MelodySheet\MelodySheet.exe
```

console 窗口里能看到 Python traceback。
