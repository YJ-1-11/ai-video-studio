# 豆包语音 · Vivi 2.0

- 本机配置文件：studio/tools/tts/.env（从同目录 .env.example 复制，然后编辑并保存为 UTF-8）。
- 新版豆包语音控制台：只填 DOUBAO_API_KEY。旧版：留空 API Key，填同一应用的 DOUBAO_APP_ID 和 DOUBAO_ACCESS_TOKEN。不要把密钥填入项目、发到聊天或提交到 Git。配置不执行脚本、不回显凭据。
- Vivi 2.0 已预填：DOUBAO_RESOURCE_ID=seed-tts-2.0，DOUBAO_SPEAKER_ID=zh_female_vv_uranus_bigtts。先到同一控制台项目确认已开通语音合成 2.0。Vivi 是通用音色，并非官方表中标注为特定英语口音的专用音色；英语发音需在配音审核时听验。
- 从仓库根目录运行 python -B studio/studio.py tts-config 检查字段是否齐全。不发网络请求，也不验证密钥有效性。
- 创作总纲通过、用户确认本次联网及可能费用后，再运行 tts 命令并指定 --provider doubao --allow-network。可通过 --options 设置 speech_rate；纯英文可用 language=en（中英混读不要强制 en）。输出 WAV 保存在所属项目对应视频、关卡和修订的 voiceover。
- `voice_direction` 可向 2.0 提供不朗读的语气或发音指示。需要指定英文音素时，`ipa_ssml: true` 使 `.txt` 可含 `<speak>` 及 `<phoneme alphabet="ipa" ph="…">`；不接受其他标签。使用兼容音色，控制标记稿长度，仍须试听验音。
- 官方文档：https://docs.volcengine.com/docs/doubao-voice/http-chunked-sse-unidirectional-streaming-v3?lang=zh
- 官方音色表：https://docs.volcengine.com/docs/doubao-voice/tone-list-3?lang=zh
