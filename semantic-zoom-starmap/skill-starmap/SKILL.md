---
name: skill-starmap
description: 把技能或项目画成可缩放的星图并做检查。按 semantic-zoom-architecture 新建或改完一个技能、项目后用：生成它的星图清单 zoom.json，查断链、节对不上、疑似复写和结构问题，重新发布星图页面。改一个文件之前也用：反查谁引用它。
license: "Proprietary. Copyright (c) 2026 Xuhao Chao. All rights reserved. See LICENSE at the repository root."
---
# Skill Starmap v2.4

> NOTICE: Copyright (c) 2026 Xuhao Chao. All rights reserved. Proprietary; see LICENSE at the repository root. Commercial use, redistribution or derivative works require prior written permission.

> **规则（语义缩放）**：本目录按 semantic-zoom-architecture 组织：文件夹 = 模块，每个文件夹一个头脑文件，文件是最小单位。协议字段与边类型只在 `zoom.schema.json`；zoomgen 的推导规则（含层级映射）只在 `rules.md`；插入步骤和反查步骤只在本文件 § 步骤。`manifests/` 下全是生成文件，勿手改。

## 接口
- 输入：一个技能或项目的源目录；或登记了多个系统的 `registry.json`（登记方法见本文件 § 步骤）。只读，不改被扫描技能的任何文件。
- 产出：
  - 星图清单：`manifests/<id>.zoom.json` 和 `manifests/index.json`，字段见 `zoom.schema.json`。
  - 检查报告：zoomgen 在命令行打印，也写进清单的 checks，每项的含义见 rules.md § 7。
  - 星图页面：`page/starmap.html`，和 manifests/ 一起发布；选中一个文件或文件夹可以复制一句「用 AI 改」指令。

## L0 全景：人与 AI 怎么协作
```
人（用户）
 ├─ 加技能 ── 在频道说「把 X 技能上星图」；需要手写的边写进该技能的 zoom.hints.json
 ├─ 看图 ──── 星图页面：拉远看全部技能，点一颗星展开下一层，选中看谁引用它、它引用谁
 ├─ 改文件 ── 在页面选中文件，点「用 AI 改」，把复制的指令粘给 AI
 └─ 决定 ──── 哪些技能上图；hints 里的派工 / 调度 / 读写 / 遵循边和层级覆盖
        │
AI（Claude）
 ├─ 生成 ──── 运行 zoomgen，产出每个技能的 zoom.json，报断链、节对不上、疑似复写、结构问题
 ├─ 发布 ──── 星图页面与 manifests/ 一起发布；页面只读清单，不含数据
 └─ 不做 ──── 改被扫描技能的任何文件（只读）
```

## 节点
本文件是这个文件夹的头脑文件。下面每个文件、每个子文件夹一行职责：
- [README.md](README.md)：给人看的入口，只有一句指向本文件
- [rules.md](rules.md)：zoomgen 怎么从文档读出星图（节点、层级、角色、定义、边、人机接口、检查）
- [CHANGELOG.md](CHANGELOG.md)：版本记录
- [zoom.schema.json](zoom.schema.json)：协议，清单字段、节点类型、边类型、人机接口方向的唯一出处
- [zoom.hints.json](zoom.hints.json)：本工具自己的手写边、人机接口与层级覆盖
- [registry.json](registry.json)：登记表，哪些系统上星图、源目录在哪
- [tools/](tools/README.md)：生成星图清单的脚本
- [page/](page/README.md)：星图页面（渲染器）
- [hints/](hints/README.md)：暂存别的技能的 zoom.hints.json（源目录只读时用）
- [manifests/](manifests/README.md)：【生成文件】各系统的 zoom.json 与 index.json

## 引用
| 概念 | 出处 |
|---|---|
| 清单字段、节点类型、边类型、接口方向 | `zoom.schema.json` |
| 推导规则与检查规则 | `rules.md` |
| 层级映射（文件种类 → L0–L3） | `rules.md` § 2 |
| 插入新技能、反查的步骤 | `SKILL.md` § 步骤 |
| 本工具的手写边、接口与层级覆盖 | `zoom.hints.json` |
| 页面交互（缩放、展开、高亮、搜索、用 AI 改） | `page/starmap.html` |
| 命令行用法 | `tools/zoomgen.py` |

## 步骤

### 插一个新技能进来
1. 可选：在技能根目录写 `zoom.hints.json`，只放推不出来的边、人机接口和层级覆盖（格式见 `zoom.schema.json` 的 hints 说明；路径可省略系统前缀）。源目录只读时放在 `hints/<技能 id>.zoom.hints.json`。
2. 在 `registry.json` 登记它（root 写源目录，location 写给人看的位置，是 skill 就加 "skill": true），然后生成：
```
python3 tools/zoomgen.py --all registry.json
```
3. 看输出：断链和结构问题必须为 0；节对不上和疑似复写逐条确认，确认过不算问题的复写写进 hints 的 accepted；最深引用和成圈只是提示（含义见 rules.md § 7）。
4. 重新发布页面（manifests/ 随页面一起发布）。只想在本机看一眼时，把 zoom.json 直接拖进页面即可，不会上传。

### 改一个文件之前：反查
1. 仓库根目录有 sza.py 时运行 python3 sza.py refs <文件>，它读的就是下面这份清单。否则在 `manifests/<id>.zoom.json` 的 edges 里找 to 是这个文件（或它所在文件夹）的边，列出 from、sections 和 source：谁引用它、引用哪一节、写在哪一行。人在页面上选中这个文件，右栏「指向它」是同一份清单。
2. 星图只记录生成那一刻的引用，以源文件为准。改法按 semantic-zoom-architecture 的 daily-change.md，改完回到上面第 2–4 条重新生成和发布。
