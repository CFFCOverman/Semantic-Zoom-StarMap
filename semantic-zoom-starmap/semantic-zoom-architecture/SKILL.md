---
name: "semantic-zoom-architecture"
description: "Use whenever creating, changing or initializing any program, skill, system or file with m_Overman, small edits included: semantic-zoom layers, one source per definition, references only."
license: "Proprietary. Copyright (c) 2026 Xuhao Chao. All rights reserved. See LICENSE at the repository root."
---
# 语义缩放架构（人与 AI 的协作架构法）

> NOTICE: Copyright (c) 2026 Xuhao Chao. All rights reserved. Proprietary; see LICENSE at the repository root. Commercial use, redistribution or derivative works require prior written permission.

像看星空：拉到最远是整个宇宙（全景），拨开一个节点，才进入它的下一层，每层只呈现当前这一层该看到的结构。软件里最接近的现成做法是 C4 模型（系统与人 → 容器 → 组件 → 代码）。定义只写一次，其他地方只引用（单一事实来源 single source of truth；引用原文而非复写，即 transclusion）。

## 接口
- 输入：要新建或修改的项目、skill 或文件，以及要改的是哪个节点（定位方法见 daily-change.md § 日常小改 第 1 条）。
- 边界：本架构只管东西写在哪、谁引用谁、怎么改才不留过时的副本。权限模型、数据结构、备份策略这些内容本身要另行设计，设计好了再按本架构放置。
- 产出：按结构放好的文件（见 file-structure.md § 文件结构即架构）、改前的快照记录（见 daily-change.md § 日常小改 第 3 条）、同步好的星图（见 starmap.md § 星图清单）。

## L0：什么情况看哪一节
只打开与当前情况对应的那一个文件，不必通读全部；文件里写到「见 文件 § 节」时，再去打开那一个。三条铁律对所有情况都适用，就在下面。
- 新项目 → [新项目的步骤](new-project.md)
- 重组已有项目的整体结构 → [改已有项目](restructure.md)
- 新建文件或文件夹、决定东西放哪 → [文件结构即架构](file-structure.md)
- 分清 L0 到 L3 每层放什么 → [层级](layers.md)
- 日常改一处（一个节点、一个 skill、一个步骤）→ [日常小改](daily-change.md)
- 不确定要不要分开写、把一节拆成独立文件或 skill → [拆分](split.md)
- 写新 skill 或项目 README → [模板](templates/README.md)
- 改完同步星图、改前查谁引用 → [星图清单](starmap.md)
- 交付前 → [交付前检查清单](delivery-checklist.md)
- 想知道这套架构有没有在起作用，或发现一处过时 → [度量](metrics.md)
- 调阈值（引用深度、拆分长度、一起改的比例）→ [参数](params.json)

## 三条铁律
1. **逐层展开：** 每一层只展开上一层的一个节点，不跨层、不提前展开细节。
2. **一处定义：** 每个概念、规则、数值只在它所属的那一层、那一个文件、那一节里定义一次。数值统一放在一个参数文件（如 params.json）。
3. **只引用不复写：** 其他地方一律写「见 <文件> § <节>」。需要在别处出现的内容，用生成文件（顶部标明「生成文件，勿手改，来源：…」），不手抄。
