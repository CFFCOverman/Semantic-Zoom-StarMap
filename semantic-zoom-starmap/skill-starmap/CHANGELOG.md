# CHANGELOG
- 2.4（2026-11-25）：三项新检查，都不拦提交。引用深度：沿 ref 边从一个文件最远要跟几跳、要再读几个文件，2 跳以上的记进 checks.depth。成圈：互相引用成圈的文件记进 checks.cycles。已确认的复写：hints 新增 accepted，确认过的疑似复写挪进 checks.accepted，不再每次重问。规则在 rules.md § 7，字段在 zoom.schema.json；页面没有改。
- 2.3（2026-11-19）：manifests/ 多一份仓库根目录的清单 semantic-zoom-starmap.zoom.json，由仓库根目录的 sza.py 生成，不进登记表，免得装好的技能去扫上一层目录；反查一步写明有 sza.py 时用 refs 命令；去掉 SKILL.md 里重复的一行版权声明。sza.py 的 change 命令直接读页面里的「用 AI 改」模板，模板仍只在 page/starmap.html。
- 2.2（2026-11-19）：给 AI 一个入口。skill-starmap 成为 skill 文件夹：新增 SKILL.md 当头脑文件，写明接口（输入源目录或登记表，产出星图清单、检查报告和星图页面）、引用表和步骤（插入新技能、改文件前反查）；README.md 只留一句指向 SKILL.md；推导和检查规则原文移到 rules.md。页面加「用 AI 改」：选中文件或文件夹，复制一句改动指令，写明源文件、按架构技能的 daily-change.md 改、星图记录的引用方。
- 2.1（2026-11-19）：跟随架构技能的两条新规则。L1 改为根目录的头脑文件直接列出的节点（根目录下的文档和子文件夹），更深的为 L2，参数、代码等仍为 L3（判定在 rules.md § 2）。头脑文件：根目录和 skill 文件夹必须有（skill 文件夹要 SKILL.md），缺了算结构问题；其他文件夹没有时按默认处理，只记提示（checks.info）。登记表和 hints 可标出 skill 文件夹。
- 2.0（2026-11-19）：按新版 semantic-zoom-architecture 改。文件是最小单位：节点只剩星系、文件夹、文件，节改成文件节点上的完整标题清单，引用边连文件并在 sections 里保留「§ 节」。层级按文件种类分 L0–L3（映射在 rules.md § 2），可在 hints 的 layers 覆盖。文件夹和它的头脑文件合成一个节点，角色取自自己的头脑文件。每个文件夹补了头脑文件；新增结构检查；清单记源目录位置；协议升到 zoom 2.0。打包的架构技能换成拆分版。
- 1.0（2026-11-19）：协议 zoom.json 1.0、zoomgen、星图页面；种子：Research OS v5、semantic-zoom-architecture、本工具，以及用户自建的其余 8 个技能（只用自动推导）。
