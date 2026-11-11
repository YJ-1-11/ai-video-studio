# Skills 调用约定

## 来源与安装位置

仓库自带 `.agents/skills` 下的英语教学、视觉指导和字幕质检 Skills。以下两个是可选的上游 Skills，不随本仓库分发。按需从上游安装到本机或本仓库的 `.agents/skills`，并遵守上游条款：

- [Remotion Agent Skills](https://github.com/remotion-dev/skills)：`npx skills add remotion-dev/skills`，使用 `remotion-best-practices` 总入口。
- [Motion Design Skill](https://github.com/LottieFiles/motion-design-skill)：`npx skills add LottieFiles/motion-design-skill`，使用 `motion-design`。

## 何时加载

| 时机 | 必须按需加载的内容 |
|---|---|
| 写 React 视频组件、安排时间线、字幕、音视频、预览或导出 | remotion-best-practices/SKILL.md，再按其路由只读所需参考 |
| 设计运动语言、突出词语、例句转换、场景过渡、缓动、停留和错峰运动 | motion-design/SKILL.md，再读相关 director / reference / patterns |
| 制作动态样片前 | 先用 Motion Design 确定动作目的与节奏，再用 Remotion 指南落实为逐帧实现 |
| 动态样片和成片审核 | Motion Design 检查焦点与节奏，Remotion 检查确定性与技术问题，lesson-caption-qa 检查字幕可读性与同步 |
| 只处理文稿、配音或安装检查 | 无相关动效或视频实现问题时不加载这两包的全部资料 |

## 与工程约定整合

- 每项任务先查看审核状态。外部 Skill 建议的“立即预览”“立即创建合成”“自动安装/升级”不改变工程的人工审核与变更确认要求。尚未获准进入动态关，不启动预览或动态渲染。
- 使用 studio/studio.py 的受控入口，不直接照抄外部文档中的 npx studio/render 绕开审核、输出隔离或本机预览限制。现有工程不是空项目，不重新 scaffold。
- 运行工具锁定 Remotion 4.0.484；上游指南可能介绍更新版本。使用新 API 前核对已安装包是否支持，优先选兼容实现；不为匹配指南自动升级。需要重大环境变化时先确认。
- Motion Design 源于通用/UI 动效。时长、1/3 经验和三层运动等建议是参考，不是教学片强制规则：以获批总纲、学习者阅读时间、注意力和教学节奏为准，不强行增加背景动效。CSS/GSAP 的示例思路要转成 Remotion 帧驱动，不使用不可复现的实时 CSS 动画替代。
- 新项目可以独立打开；其 AGENTS.md 指明如何定位共享工具与相关 Skills。开始相关任务时实际读取所需文件，而不是只凭名称宣称已调用。
