# 星图清单（zoom.json）
每个项目交付时自带一份星图清单，让人在星图页面上看见层级，以及谁引用谁、谁生成谁、谁派工给谁。星图工具在本仓库的 skill-starmap/（页面是 skill-starmap/page/starmap.html）。
1. 字段、节点类型和边类型只在 skill-starmap 的 `zoom.schema.json` 定义，这里不复写。
2. 清单是生成文件：运行 `python3 skill-starmap/tools/zoomgen.py <项目目录>`，它从 README 目录树、「概念 → 唯一出处」表和正文里的「见 文件 § 节」推出节点和边，顶部标「勿手改」。
3. 脚本推不出来的边（派工、调度、读、写、遵循）、L0 人机接口，以及确认过不算问题的疑似复写（accepted），写在项目根目录的 `zoom.hints.json`，只写这些。
4. 把项目登记进 `skill-starmap/registry.json`，运行 `python3 tools/zoomgen.py --all registry.json`，重新发布星图。
5. **反查：** 改之前先问“节点 X 在哪、谁引用它”，从 zoom.json 的边里读出答案。仓库里有 sza.py 时运行 python3 sza.py refs <文件>；没有时由 AI 读 zoom.json 列出。
6. **自动把关：** zoomgen 挂到提交前钩子（有 sza.py 时运行 python3 sza.py install-hook 装好），断链或结构问题不过就拦下提交；引用深度超过 `params.ref_hops_max`、文件互相引用成圈只提示，不拦。发布星图是 daily-change.md § 日常小改 的最后一步，由有发布权限的 AI 做。
