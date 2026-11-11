# Codex 项目说明

本目录可以单独作为 Codex 工作区。向上两级是框架根目录。使用框架根目录中的 `studio/studio.py`，按项目 ID 与视频 ID 操作。工作台说明在 `studio/README.md`，创作 Skills 在 `.agents/skills`。

1. 先交创作总纲给用户确认，再做代表性片段：配音 → 静态画面 → 动态样片。每关等用户明确确认才开始下一关。之后按 video.json 中的批次顺序，逐批制作、逐批确认，再提交全片审核。
2. 每次制作前查 status 和 require。收到用户对具体修订的明确确认后才执行 approve；搭建确认、泛泛认可或 Codex 自评不算。快照和审核记录不覆盖；需要修改就新建修订，重新审核受影响的下游。
3. 视频放在 videos/Vxxx。配音文本与音频放在本项目 voiceover/Vxxx；不写其他项目。公共素材来自中央 assets，按项目记录来源及使用权；项目特有素材放 materials。
4. 不自动整理、移动或清理文件，除非用户同意。兼容工具可自主选择；明显成本、质量或重大环境变化先确认。未获批不调用付费服务或发送项目内容。

## 视频实现与动效 Skills

- 开始相关任务时先读 studio/SKILLS.md。
- 实现 React 视频组件、时间线、字幕、预览或渲染时，读取 .agents/skills/remotion-best-practices/SKILL.md，按任务路由加载参考。
- 设计或审核动画原则、缓动、运动节奏和元素编排时，读取 .agents/skills/motion-design/SKILL.md；动态样片先确定运动设计，再实现逐帧代码。
- 上述 Skills 不改变逐关人工审核、不可覆盖审核件、环境/费用确认和项目隔离约定；只在获准的关卡启动预览与制作。新指南 API 需核对现有 Remotion 4.0.484；不自动升级。具体整合与调用矩阵见 SKILLS.md。

- 上述两个第三方 Skills 仅在已安装且相关时加载，见 studio/SKILLS.md。未安装时按需使用内置 Skills。
