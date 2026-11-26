# Semantic Zoom Architecture + Skill Starmap

> NOTICE: Copyright (c) 2026 Xuhao Chao. All rights reserved. Proprietary; see [LICENSE](LICENSE). Commercial use, redistribution or derivative works require prior written permission.

## L0 · 总览

人 ↔ AI 的接口：人读每个系统的第 0 层概览，再逐层放大；AI 按同一套规则写系统、生成星图清单。人只用一条命令入口 `sza.py` 安装、检查、打包、快照和退回；要 AI 改某处时，`sza.py change` 打印一段改动指令，人把它交给 AI（Claude Code 里是 `/sza-change`）。推送 git 和上传 claude.ai 由人来做。

- [semantic-zoom-architecture/](semantic-zoom-architecture/SKILL.md)：语义缩放架构技能（拆分版）。文件夹 = 模块，每个文件夹一个头脑文件，文件是最小单位，层级按文件种类分 L0–L3；每个定义只在一处，其他地方用「见 文件 § 节」引用
- [skill-starmap/](skill-starmap/SKILL.md)：通用技能星图。每个系统带一份 zoom.json 清单，页面把所有系统画成可缩放的星图；节点只到文件为止
- [sza.py](sza.py)：命令入口，安装、更新、检查、打包、快照、退回、改动、度量；跨平台，只用标准库
- .claude/commands/：Claude Code 斜杠命令 /sza-change、/sza-check、/sza-pack、/sza-restore、/sza-update，每个只调用 sza.py
- [AGENTS.md](AGENTS.md)：给任何 AI 的一句指向，先读架构技能，命令用 sza.py
- [CLAUDE.md](CLAUDE.md)：Claude Code 读的入口，只导入 AGENTS.md
- [zoom.hints.json](zoom.hints.json)：仓库根目录这颗星的手写边和人机接口
- [CHANGELOG.md](CHANGELOG.md)：整仓发布记录
- [LICENSE](LICENSE)：专有许可
- [NOTICE](NOTICE)：版权声明

## 概念 → 唯一出处
| 概念 | 出处 |
|---|---|
| 命令和参数 | `sza.py` 文件头 |
| 给 AI 的入口 | `AGENTS.md` |
| 许可 | `LICENSE` |

架构规则、改一处的步骤、星图字段和给 AI 的改动指令模板，出处在两个技能各自的 SKILL.md 里。

## 快速开始

需要 Python 3（Windows 上命令用 `python` 或 `py` 代替 `python3`）。全部命令和参数写在 sza.py 的文件头，也可以运行 `python3 sza.py -h`。

第一次安装（例子里把本仓库克隆到项目的 tools/ 下）：

1. 克隆本仓库：
```
git clone <仓库地址> tools/semantic-zoom-starmap
```
2. 在要用它的项目根目录运行：
```
python3 tools/semantic-zoom-starmap/sza.py install
```
它把两个技能复制进项目的 `.claude/skills`，把斜杠命令复制进 `.claude/commands`。
3. 项目用 git 时，再运行一次，以后每次提交前自动检查：
```
python3 tools/semantic-zoom-starmap/sza.py install-hook
```

另外两种装法：
- 给所有项目用：`install` 后面加 `--user`，装进用户目录的 `~/.claude/skills`。
- 只在本仓库里用：在本仓库根目录运行 `python3 sza.py install`。

平时：
```
python3 sza.py change semantic-zoom-architecture/split.md "拆分的条件加一条"
python3 sza.py done semantic-zoom-architecture/split.md
python3 sza.py check
python3 sza.py pack
```
第一条先记下改前版本、反查谁引用它，再打印给 AI 的改动指令；AI 改完运行第二条。不满意时 `python3 sza.py restore <文件>` 退回。只改数值或错别字时第一条加 `--kind param`。发现改了一处、别处没跟上，运行 `python3 sza.py incident <文件> "说明"` 记一次；`python3 sza.py stats` 看这套架构有没有在起作用。拉了新版本后运行 `python3 sza.py update`。

## 看星图

页面按相对路径读 `manifests/index.json`，所以要和 `manifests/` 放在同一层再用静态服务器打开，例如：

```
cd skill-starmap
cp page/starmap.html .
python3 -m http.server 8000   # 打开 http://localhost:8000/starmap.html
```

也可以直接把 zoom.json 拖进页面，只在本机显示。
