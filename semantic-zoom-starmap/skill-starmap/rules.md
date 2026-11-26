# 推导规则（zoomgen 怎么从文档读出星图）
本文件是 zoomgen 推导规则与检查规则的唯一出处；协议字段见 `zoom.schema.json`。

## 1. 节点
- 只有三种节点：星系（system）、文件夹（dir）、文件（file）。文件是最小单位，文件里的节不是节点。
- 文件夹和它的头脑文件是同一个节点：引用头脑文件就是引用这个文件夹。头脑文件这样认：文件夹里有 SKILL.md 就是它，否则是 README.md（SKILL.md 旁边的 README.md 怎么写，见 semantic-zoom-architecture 的 file-structure.md 第 5 条）。根文件夹的节点就是星系。
- 头脑文件什么时候必须有、没有时怎么默认，规则在 semantic-zoom-architecture 的 file-structure.md 第 2 条。zoomgen 认 skill 文件夹的办法：登记表里 root 以 skills: 开头或写了 "skill": true 的，根目录就是 skill 文件夹；子文件夹写在 hints 的 skills 里。
- 文件节点带一份节的清单（sections），是文件里的各级标题，原文完整，只供页面显示，不是节点。json 文件的节清单是它的顶层键。
- 星系记下源目录在哪（location），来自登记表。

## 2. 层级（按文件种类）
层级的规则在 semantic-zoom-architecture 的 layers.md；下表是 zoomgen 怎么判定每个节点属于哪一层。

| 节点 | 层 |
|---|---|
| 星系：根文件夹及其头脑文件（README.md；skill 根目录为 SKILL.md） | L0 |
| 根目录下的文档（.md）和子文件夹，也就是根目录的头脑文件直接列出的节点 | L1 |
| 更深的文档和子文件夹 | L2 |
| 参数、数据、代码、脚本、页面（.json .py .js .ts .sh .html .css .yaml 等，以及其他非 .md 文件），不论在哪一层 | L3 |

要改某个文件或文件夹的层，在 zoom.hints.json 的 layers 里按路径写（格式见 `zoom.schema.json` 的 hints 说明）。

## 3. 一句话角色
- 文件：取所在文件夹的头脑文件里列它的那一行（链接或目录树优先，其次反引号点名），再其次取文件的一级标题、frontmatter description、脚本文档字符串或页面标题。
- 文件夹：取它自己的头脑文件，即一级标题下第一行正文或 frontmatter description；没有头脑文件时按 § 1 说的默认。

## 4. 定义（defines）
根目录头脑文件里表头为「概念 | 出处」的表，每行把概念挂到它的出处文件上；写了「§ 节」的，节号跟在概念后面。

## 5. 边
- 「见 文件 § 节」是 ref，文件名带不带反引号都认；边连两个文件，§ 节原样记在边的 sections 里。
- 正文点名文件（反引号或 Markdown 链接）但没写「见」是 mention；头脑文件链接自己下面的文件是包含关系，不画边。
- `params.xxx` 是 param；生成文件里「（来自 文件 节）」是 copy；生成文件头里的「生成器：脚本」是 generates；正文点名另一个已知系统 id 是跨星系 mention。
- 派工、调度、读、写、遵循推不出来，写在 hints。

## 6. 人机接口
hints 的 interface；没有 hints 时用 SKILL.md 的 description 做一个「触发」入口。

## 7. 检查
- **断链：** 引用或链接的文件不存在。
- **节对不上：** 文件在，但「§ 节」对不上它的任何标题。
- **疑似复写：** 同一句至少 28 字的正文出现在两个以上文件，或 params.json 里的时刻在正文又写了一遍。写着「见」或点名了文件的句子算引用；CHANGELOG 和生成文件不查。
- **结构：** 根目录没有头脑文件；skill 文件夹没有 SKILL.md；SKILL.md 和一份不只是一句指向的 README.md 并存；头脑文件没列出它下面的某个文件或子文件夹。
- **已确认的复写：** hints 的 accepted 里列过的疑似复写（按句子开头对），挪进 checks.accepted，不算问题。哪条确认已经对不上任何疑似复写，记一条提示。
- **引用深度（不拦）：** 从一个文件出发沿 ref 边往下跟，最远要跟几跳、一共要再读几个文件；2 跳以上的各记一条。上限不在这里，在 semantic-zoom-architecture 的 params.json。
- **成圈（不拦）：** 几个文件沿 ref 边互相引用成圈，各记一条。
- **提示（不算问题）：** 其他文件夹没有头脑文件、按默认处理的，各记一条。
