
# AI Video Studio

面向英语教学视频的本地制作框架。用 Python 管理项目、版本、人工审核和帧时间线，用 Remotion 制作可编程画面，用 FFmpeg 合成与检查成片。可以在 Codex 中打开，也可直接用 PowerShell；不需要另建服务或后台。

- 每个项目支持多条视频，分别存放配音、草稿和审核快照。
- 流程：创作总纲 → 样片配音 → 静态画面 → 动态样片 → 分批审核 → 全片审核。送审快照记录 SHA-256 并设为只读；上游改版后，旧依赖不会自动通过下一关。
- 可输出 SRT、预览画面、渲染静帧与视频，并合成 H.264/AAC MP4。机器质检不代替听看和人工审核。
- 配音可选豆包语音（默认音色 Vivi 2.0），也支持兼容的通用 WAV 服务。仅在明确批准且带联网开关时调用。

## 安装（Windows 11 x64）

在 `PATH` 中准备 Python 3.12、Node.js 22（含 npm）、FFmpeg 和 FFprobe。依赖按仓库锁文件安装；这个仓库不含浏览器或二进制工具。下载浏览器需要联网。

```powershell
npm.cmd --prefix studio/tools/remotion ci
npm.cmd --prefix studio/tools/remotion run browser:ensure
npm.cmd --prefix studio/tools/remotion run check
python -B studio/studio.py --help
```

FFmpeg 需支持 `libx264` 和 AAC。项目预览用 `studio.py preview`，它只绑定本机。默认从 Remotion 的 Windows Chromium 缓存读取浏览器；如使用其他兼容的本地可执行文件，可在当前 PowerShell 会话设置 `AI_VIDEO_STUDIO_BROWSER` 为该可执行文件的完整路径。

## 创建一个项目

从仓库根目录运行：

```powershell
python -B studio/studio.py new MyLesson --title '我的英语课' --video V001
python -B studio/studio.py status MyLesson V001
python -B studio/studio.py prepare MyLesson V001 outline R001
```

项目创建后，先拟创作总纲并送审，再进入样片制作。详细见[操作说明](studio/README.md)和[工作区规则](AGENTS.md)。[Skills 说明](studio/SKILLS.md)包含可选的上游安装方法。

## 豆包语音（可选）

```powershell
Copy-Item -LiteralPath 'studio/tools/tts/.env.example' -Destination 'studio/tools/tts/.env'
notepad 'studio/tools/tts/.env'
python -B studio/studio.py tts-config
```

如果已有 `.env`，直接编辑，保留现有配置。使用新版时只填本机 `DOUBAO_API_KEY`；旧版另有配对的 App ID 和 Access Token。离线检查只验证配置是否齐全，不验证远端密钥或权限。参见[配音配置](studio/tools/tts/README.md)。

## 离线测试

```powershell
$env:AI_VIDEO_STUDIO_TEST_WORK = Join-Path (Get-Location) '_test-work'
python -B -m unittest discover -s studio/tests -p 'test_*.py'
node studio/tests/check-remotion.cjs
node studio/tools/remotion/studio-local.cjs --check-loopback
```

Python 测试不调用付费服务，不会写入正式项目；测试件位于已忽略的 `_test-work`。Remotion 检查读取已安装的依赖与浏览器文件，不渲染或启动预览。

## 本地内容与许可证

请把密钥、真实项目、媒体和素材留在本机。`projects` 和 `assets` 在仓库中只包含目录说明；`runtime` 自动按需创建。避免用强制加入文件的 Git 选项绕过忽略规则。

仓库自研代码和文档采用 [MIT](LICENSE)。Remotion、FFmpeg、Chromium、上游 Skills 和语音服务不随仓库分发，各自适用[上游条款](THIRD_PARTY.md)。
