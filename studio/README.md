# AI Video Studio · 操作入口

在 Codex 打开仓库根目录或任一 projects 下的项目。先读 AGENTS.md。以下 PowerShell 命令从仓库根目录运行：

```powershell
$studio = Join-Path (Get-Location) 'studio/studio.py'
python -B $studio --help
```

## 项目与审核

```powershell
python -B $studio new MyLesson --title '项目标题' --video V001 --batches B001 B002
python -B $studio add-video MyLesson V002
python -B $studio status MyLesson V001
python -B $studio prepare MyLesson V001 outline R001
```

- 项目里有 AGENTS.md、project.json、materials、voiceover 和 videos；视频有 video.json、草稿、审核件、时间线和源文件。每条视频独立维护审核链；按 video.json 的 batches 顺序制作，进入正式制作前定好顺序。
- 每关先用 require PROJECT VIDEO STAGE 或 status 检查。用 prepare 建工作目录，把文件放进对应的阶段和版本。样片配音可对 prepare 加 --voice，在 voiceover/V001/sample-voice/R001 保存配音文本及音频。草稿与审核快照分开。
- submit PROJECT VIDEO STAGE REV FILE [FILE ...] 将**相对于项目根目录**的指定文件复制到 videos/VIDEO/review/STAGE/REV/artifacts，文件设为只读并保存校验值。不要就地改送审件；有反馈就用 R002 等新版本。可以把技术报告、文稿或其他支持文件一起送审。
- 用户明确确认具体版本之后才执行 approve PROJECT VIDEO STAGE REV --confirmed-by-user --note '实际确认内容及引用'。工具记录人工确认，不会替用户批准。新修订获批后，依赖旧修订的下游不再放行；原审核文件仍保留。
- 阶段名依次为 outline → sample-voice → sample-stills → sample-motion → B001 等已配置批次 → final。审核通过的文件从 review 读取；不要从仍可改动的草稿读取代替。只读和校验用于防误改，不是针对有管理员权限者的强制访问控制。
- 除规定的送审复制外，不自动整理、移动或删除。中断或失败留下的缓存可后续列清单，由用户批准后处理。

## 制作工具

| 命令 | 用途 |
|---|---|
| check-timeline PROJECT VIDEO FILE | 校验场景全覆盖、帧区间、字幕重叠和阅读提醒；模板需填入真实时长、场景和台词后才可通过 |
| captions PROJECT VIDEO STAGE REV FILE | 以统一帧时钟导出 SRT，生成新文件 |
| still / render PROJECT VIDEO STAGE REV ENTRY COMPOSITION OUTPUT | 用项目 source 下自行创作的 Remotion 注册入口导出 PNG 静帧或 MP4；静帧可用 --frame |
| preview PROJECT VIDEO STAGE REV ENTRY | 动态样片及之后按需启动 Remotion 自带预览，只绑定本机地址；用终端显示的地址打开，Ctrl+C 停止 |
| mux PROJECT VIDEO STAGE REV PICTURE SPEECH OUTPUT [--srt SRT] | 用 FFmpeg 生成 H.264/AAC MP4；可加可选英文字幕；不会为了适配视频而裁切较长配音 |
| qa PROJECT VIDEO MEDIA [--timeline FILE] | 检查容器、编码、解码和可选的时长/尺寸/帧率；静音片加 --silent-ok |
| tts PROJECT VIDEO STAGE REV SCRIPT OUTPUT --options JSON --allow-network | 用户批准使用网络/费用后才调用支持 HTTPS JSON input、Bearer 和原始 PCM WAV 响应的 TTS 服务 |

- 所有文件参数按项目根目录传相对路径。Remotion 原始工程留在各视频 source；模板的 timeline-composition.jsx 只提供场景/字幕装配组件，不含画面内容或可渲染样片。自行在 ENTRY 中注册 Composition，以校验后的时间线设置帧率、尺寸、长度；按实际素材制作各 Scene。项目专用的 Remotion 公共文件放入该视频 source/public，不把目录指向其他项目。
- 质量检查的字幕来源是实际配音；静帧上已烧录字幕时，不重复打开可选字幕。QA 不代替听看与用户批准。
- 通用 TTS 提供商的令牌通过进程环境 AI_VIDEO_TTS_TOKEN，服务端点通过 AI_VIDEO_TTS_URL；options 用于经核对的厂商字段（模型、音色、WAV 输出等），不放令牌。不支持此协议的服务需要独立适配器。文本和成功生成的音频留在所属项目 voiceover 下的同一视频、阶段、版本；没有默认供应商，也没有自动调用。
- 共用 CLI、画面/音频脚本是建议路径，不是创作限制。兼容工具可以替换，重大成本、质量和环境变化需用户确认。


预览应走上述 preview 命令：已安装版本的原生命令默认可能监听局域网，不要从共用工具目录直接运行旧的 npm run studio 入口。

Skills 的来源、调用时机及与现有审核/工具版本的整合规则，见 studio/SKILLS.md。

## 豆包语音：Vivi 2.0

密钥只填在 studio/tools/tts/.env。首次使用时，从同目录的 .env.example 复制并按需填写。
用 tts-config 检查配置字段，无网络请求；使用 tts 时指定 --provider doubao，仍须满足审核及 --allow-network。
原有通用 WAV 提供商入口保持不变。见 studio/tools/tts/README.md。
