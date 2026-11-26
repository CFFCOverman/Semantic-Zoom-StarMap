# CHANGELOG
- v4（2026-11-25）：让这套架构能被度量，并减掉小改动的开销。sza.py 新增 incident 和 stats，日志多记级别、引用数、实际动的文件和检查结果，提交前钩子拦下的也记一行。改动分三级（参数级、内部级、接口级，定义在架构技能 daily-change.md § 改动分级），change 加 --kind。改前版本只存一处：节点已提交且干净时只记 git 提交号，不再复制文件，restore 按日志从 git 或快照取。架构技能新增 metrics.md（度量）和 params.json（阈值，暂定值）；SKILL.md 写明适用边界，layers.md 写明横切规则放 L1。技能星图升 2.4。
- v3（2026-11-19）：加命令入口 sza.py（install、update、install-hook、check、pack、snapshot、restore、history、refs、change、done），Claude Code 斜杠命令 /sza-change、/sza-check、/sza-pack、/sza-restore、/sza-update，AGENTS.md 和 CLAUDE.md 指向；仓库根目录也上星图（第三颗星，由 sza.py 生成）；架构技能的 daily-change.md、starmap.md 写明有 sza.py 时用哪条命令；技能星图升 2.3。
- v2（2026-11-19）：拆分版架构技能 + 技能星图 2.2；补齐版权（LICENSE、NOTICE、两个 SKILL.md 的 license 字段、脚本和页面的版权行）。
- v1（2026-11-19）：单文件架构技能 + 技能星图 1.0。
