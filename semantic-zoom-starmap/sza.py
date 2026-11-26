#!/usr/bin/env python3
# Copyright (c) 2026 Xuhao Chao. All rights reserved. Proprietary; see LICENSE at the repository root.
"""sza：语义缩放架构（SZA）+ 技能星图（SSM）的一条命令入口。只用 Python 3 标准库，Windows、macOS、Linux 通用，不建软链接。
本文件头是这些命令的唯一出处；其他地方只写「见 sza.py 文件头」。命令在项目根目录运行（Windows 把 python3 换成 python 或 py）。

第一次
  python3 sza.py install [--user | --target 目录] [--no-commands]
      把两个技能复制进 <项目>/.claude/skills（--user：~/.claude/skills），顺带把 .claude/commands 里的斜杠命令复制过去。
      在别的项目里用时，从那个项目的根目录运行：python3 <本仓库>/sza.py install
  python3 sza.py install-hook [--force]
      加 git 提交前钩子：每次提交先跑 check，断链或结构问题不为 0 就拦下。

日常
  python3 sza.py change <文件或文件夹> ["要改什么"] [--kind param|internal|interface] [--copy]
      要 AI 改某处时用：先记下改前版本，再从星图反查谁引用它，打印一段可以直接粘给任何 AI 的改动指令（--copy 同时放进剪贴板）。
      --kind 是改动分级：param 参数级、internal 内部级（默认）、interface 接口级；param 级不列引用方，指令更短。
      改前版本只存一处：这个节点已在 git 里且没有未提交的改动时，只在日志里记提交号，不复制文件；否则复制快照。
  python3 sza.py done <文件或文件夹> [--why 说明]
      AI 改完后用：重新检查，显示和改前版本的差别，记一行日志（级别、引用数、实际动了哪些文件、检查结果）。
  python3 sza.py refs <文件或文件夹>
      只反查：谁引用它（哪一节、写在哪一行），它又引用谁。
  python3 sza.py check [--strict]
      重新生成星图清单，查断链、节对不上、疑似复写、结构和引用深度。断链或结构不为 0 时失败；--strict 时节对不上、疑似复写和引用过深也算失败。
  python3 sza.py pack [--strict] [--name 名字]
      先 check，通过了才打包到 dist/：每个技能一个 zip（上传 claude.ai 的 Settings > Skills 用），再加一个整仓发布 zip（带 LICENSE、NOTICE）。

度量
  python3 sza.py incident <文件或文件夹> "说明" [--kind stale|skipped]
      发现一次事故就记一行：stale（默认）是改了一处、别处没跟上；skipped 是 AI 没打开引用就动手。
  python3 sza.py stats [--days N]
      从日志汇总：各级改动数、事故率、检查拦下次数、波及、定级不符、引用深度，以及拆分和合并的提示。阈值读 semantic-zoom-architecture/params.json。

备份与退回（不用 git 也能用）
  python3 sza.py snapshot <文件或文件夹> [--why 说明]
      复制到 .sza/history/<路径>/<时间>/，并在 .sza/history/log.jsonl 记一行：谁、哪个节点、为什么。手动运行时总是复制。
  python3 sza.py restore <文件或文件夹> [--at 时间或提交号]
      退回到最近一次 change 之前的版本：日志记的是提交号就从 git 取，记的是快照就从快照取（--at 指定某次，写时间或提交号的开头几位即可）；
      现在的版本有未提交的改动时，退回前先存一份快照。
  python3 sza.py history [<文件或文件夹>]
      列出快照和日志。

维护
  python3 sza.py update [--pull]
      拉新版本后（--pull 替你在本仓库运行 git pull --ff-only）按上次 install 的设置重新复制，列出这次改了哪些文件。

日志字段（.sza/history/log.jsonl，一行一条 JSON，本文件头是唯一出处）
  at 时间、who 谁、action 动作、node 节点、why 原因；改前记录另有 kind 级别、refs 引用它的地方数，以及 commit 提交号或 snapshot 快照位置二选一；
  done 另有 kind、refs、touched 实际改动的文件（有 git 时）、checks 各项检查的条数；check-failed 是提交前钩子拦下的一次，带 checks；incident 另有 kind。

通用选项：--registry 登记表（默认 skill-starmap/registry.json）；--who 名字（写进日志，默认取环境变量 SZA_WHO 或系统用户名）。
规则本身（怎么定位、看波及、快照、只改一处）见 semantic-zoom-architecture/daily-change.md § 日常小改，分级见同一文件 § 改动分级，各项度量的含义见 semantic-zoom-architecture/metrics.md § 度量；星图字段见 skill-starmap/zoom.schema.json。"""
import argparse, datetime, difflib, fnmatch, getpass, hashlib, json, os, re, shutil, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS = ("semantic-zoom-architecture", "skill-starmap")
REGISTRY = ROOT / "skill-starmap" / "registry.json"
ZOOMGEN = ROOT / "skill-starmap" / "tools" / "zoomgen.py"
PAGE = ROOT / "skill-starmap" / "page" / "starmap.html"
COMMANDS = ROOT / ".claude" / "commands"
HEADS = ("SKILL.md", "README.md")
SKIP = {".git", "__pycache__", ".sza", "dist", ".DS_Store", "Thumbs.db"}
HOOK_MARK = "# sza pre-commit hook"
PARAMS = ROOT / "semantic-zoom-architecture" / "params.json"      # 阈值的唯一出处
LEVELS = {"param": "参数级", "internal": "内部级", "interface": "接口级"}   # 定义见 daily-change.md § 改动分级
BEFORE = "snapshot-before-change"
RELEASE = "semantic-zoom-starmap"
# 仓库根目录这颗星：只在本仓库里用默认登记表时生成，不写进 skill-starmap/registry.json，免得装好的技能去扫它上一层的目录
ROOT_SYSTEM = {"id": RELEASE, "root": "..", "hints": "../zoom.hints.json", "exclude": list(SKILLS) + ["dist"],
               "location": "semantic-zoom-starmap/（仓库根目录：命令入口与许可）"}

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

# ---------- 小工具 ----------
def now():
    t = datetime.datetime.now(datetime.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ"), t.strftime("%Y-%m-%dT%H%M%SZ")

def find_base(start=None):
    """项目根目录：从当前目录往上，第一个有 .sza 或 .git 的目录；都没有就用当前目录。"""
    p = Path(start or Path.cwd()).resolve()
    for d in (p, *p.parents):
        if (d / ".sza").exists() or (d / ".git").exists(): return d
    return p

def rel(p, base):
    try: return Path(p).resolve().relative_to(Path(base).resolve()).as_posix()
    except ValueError: return Path(p).resolve().as_posix()

def relref(target, start):
    """target 相对 start 的写法（正斜杠）；Windows 上不在同一个盘时退回绝对路径。"""
    try: return Path(os.path.relpath(target, start)).as_posix()
    except ValueError: return Path(target).as_posix()

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def files_under(d):
    d = Path(d)
    if d.is_file(): return {d.name: d}
    out = {}
    for p in sorted(d.rglob("*")):
        parts = p.relative_to(d).parts
        if p.is_file() and not any(x in SKIP or x.endswith(".pyc") for x in parts):
            out["/".join(parts)] = p
    return out

def sync(src, dst):
    """把 src 文件夹同步到 dst：新增、改动的复制，src 里没有的删掉。返回 (新增, 改动, 删除)。"""
    src, dst = Path(src), Path(dst)
    a, b = files_under(src), files_under(dst) if dst.exists() else {}
    added, changed, removed = [], [], []
    for k, p in a.items():
        q = dst / k
        if k not in b: added.append(k)
        elif digest(p) != digest(b[k]): changed.append(k)
        else: continue
        q.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, q)
    for k, q in b.items():
        if k not in a: removed.append(k); q.unlink()
    for d in sorted((x for x in dst.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)) if dst.exists() else []:
        if not any(d.iterdir()): d.rmdir()
    return added, changed, removed

def who(a):
    return a.who or os.environ.get("SZA_WHO") or getpass.getuser()

def log(base, rec):
    f = Path(base) / ".sza" / "history" / "log.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh: fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

def read_log(base):
    f = Path(base) / ".sza" / "history" / "log.jsonl"
    if not f.exists(): return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try: out.append(json.loads(line))
        except ValueError: pass
    return out

def params():
    try: return json.loads(PARAMS.read_text(encoding="utf-8"))
    except (OSError, ValueError): return {}

def git(base, *args, rc=False):
    """在项目根目录跑 git。rc=True 返回退出码；否则成功返回输出，失败或没装 git 返回 None。"""
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=str(base), capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return 127 if rc else None
    return r.returncode if rc else (r.stdout if r.returncode == 0 else None)

def git_commit_of(base, path):
    """节点已在 git 里且没有未提交的改动时，返回当前提交号；否则 None（这时要复制快照，免得丢东西）。"""
    if not (Path(base) / ".git").exists(): return None
    head, r = git(base, "rev-parse", "HEAD"), rel(path, base)
    if not head or Path(r).is_absolute(): return None
    st = git(base, "status", "--porcelain", "--", r)
    if st is None or st.strip() or not (git(base, "ls-files", "--", r) or "").strip(): return None
    return head.strip()

def last_before(base, path):
    """这个节点最近一次 change 记下的改前记录。"""
    node = rel(path, base)
    hit = [r for r in read_log(base) if r.get("action") == BEFORE and r.get("node") == node]
    return hit[-1] if hit else None

def target_path(base, s):
    p = Path(s)
    p = p if p.is_absolute() else (Path.cwd() / p)
    return p.resolve()

# ---------- 快照与退回 ----------
def snapshots(base, path):
    """某个文件或文件夹的全部快照，旧的在前。"""
    d = Path(base) / ".sza" / "history" / rel(path, base)
    if not d.is_dir(): return []
    return sorted(x for x in d.iterdir() if x.is_dir() and (x / Path(path).name).exists())

def do_snapshot(base, path, why, by, action="snapshot", extra=None):
    path = Path(path)
    if not path.exists(): sys.exit(f"找不到 {path}")
    at, stamp = now()
    home = Path(base) / ".sza" / "history" / rel(path, base)
    slot, i = home / stamp, 1
    while slot.exists(): i += 1; slot = home / f"{stamp}-{i}"
    dst = slot / path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir(): shutil.copytree(path, dst, ignore=shutil.ignore_patterns(*SKIP, "*.pyc"))
    else: shutil.copy2(path, dst)
    log(base, {"at": at, "who": by, "action": action, "node": rel(path, base), "why": why, **(extra or {}), "snapshot": rel(dst.parent, base)})
    return dst

def record_before(base, path, why, by, extra):
    """改前版本只存一处：能用 git 就只记提交号，否则复制快照。返回给人看的一句话。"""
    sha = git_commit_of(base, path)
    if sha:
        at, _ = now()
        log(base, {"at": at, "who": by, "action": BEFORE, "node": rel(path, base), "why": why, **extra, "commit": sha})
        return f"git 提交 {sha[:10]}（没有复制文件）"
    return "快照 " + rel(do_snapshot(base, path, why, by, BEFORE, extra).parent, base)

def git_restore(base, p, sha, by, why):
    r = rel(p, base)
    if git(base, "cat-file", "-e", sha + "^{commit}", rc=True) != 0: sys.exit(f"git 里找不到提交 {sha}。")
    dirty = (git(base, "status", "--porcelain", "--", r) or "").strip()
    if git(base, "diff", "--quiet", sha, "--", r, rc=True) == 0 and not dirty:
        sys.exit("和那个提交里的版本没有差别，不用退回。")
    if dirty and p.exists(): do_snapshot(base, p, f"退回到 {sha[:10]} 之前的自动快照", by, "auto-before-restore")
    if git(base, "restore", "--source", sha, "--worktree", "--", r, rc=True) != 0 and git(base, "checkout", sha, "--", r, rc=True) != 0:
        sys.exit(f"git 没能把 {r} 退回到 {sha[:10]}。")
    at, _ = now()
    log(base, {"at": at, "who": by, "action": "restore", "node": r, "why": why, "from": "git:" + sha})
    print(f"已退回：{r} ← git 提交 {sha[:10]}（改动留在工作区，没有提交；之后新加的未跟踪文件没有删）。接着运行 check 同步星图。")

def same(a, b):
    fa, fb = files_under(a), files_under(b)
    return fa.keys() == fb.keys() and all(digest(fa[k]) == digest(fb[k]) for k in fa)

def cmd_snapshot(a):
    base = find_base(); p = target_path(base, a.path)
    dst = do_snapshot(base, p, a.why or "", who(a))
    print(f"已快照：{rel(p, base)} → {rel(dst.parent, base)}")

def cmd_restore(a):
    base = find_base(); p = target_path(base, a.path)
    snaps = snapshots(base, p)
    before = last_before(base, p)
    if a.at:
        hit = [s for s in snaps if s.name.startswith(a.at)]
        if not hit:
            if re.fullmatch(r"[0-9a-f]{6,40}", a.at): return git_restore(base, p, a.at, who(a), a.why or "")
            sys.exit(f"没有以 {a.at} 开头的快照。可选：" + ("、".join(s.name for s in snaps) or "（没有快照）"))
        pick = hit[-1]
    elif before and before.get("commit"):
        return git_restore(base, p, before["commit"], who(a), a.why or "")
    elif not snaps:
        sys.exit(f"{rel(p, base)} 还没有改前记录（日志里没有提交号，.sza/history 里也没有快照）。")
    else:
        auto = {r.get("snapshot") for r in read_log(base) if r.get("action") == "auto-before-restore"}
        diff = [s for s in snaps if rel(s, base) not in auto and not (p.exists() and same(s / p.name, p))]
        if not diff: sys.exit("没有和现在不同的快照，不用退回（撤销上一次退回用 --at 指定那份自动快照）。")
        pick = diff[-1]
    if p.exists(): do_snapshot(base, p, f"退回到 {pick.name} 之前的自动快照", who(a), "auto-before-restore")
    src = pick / p.name
    if src.is_dir():
        if p.exists(): shutil.rmtree(p)
        shutil.copytree(src, p)
    else:
        p.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, p)
    at, _ = now()
    log(base, {"at": at, "who": who(a), "action": "restore", "node": rel(p, base), "why": a.why or "", "from": rel(pick, base)})
    print(f"已退回：{rel(p, base)} ← {pick.name}。接着运行 check 同步星图。")

def cmd_history(a):
    base = find_base()
    node = rel(target_path(base, a.path), base) if a.path else None
    rows = [r for r in read_log(base) if not node or r.get("node", "").startswith(node)]
    if not rows: print("还没有记录。"); return
    for r in rows:
        print(f"{r.get('at','')}  {r.get('action',''):<22} {LEVELS.get(r.get('kind'), r.get('kind') or ''):<4} {r.get('node','')}  {r.get('who','')}  {r.get('why','')}"
              + (f"  [git {r['commit'][:10]}]" if r.get("commit") else ""))

# ---------- 检查（调用 zoomgen） ----------
def registry_of(a):
    return Path(a.registry).resolve() if getattr(a, "registry", None) else REGISTRY

def out_dir(reg):
    return reg.parent / json.loads(reg.read_text(encoding="utf-8")).get("out", "manifests")

def norm_manifest(raw):
    try: m = json.loads(raw)
    except ValueError: return raw
    if isinstance(m, dict) and isinstance(m.get("generated"), dict): m["generated"].pop("at", None)
    return json.dumps(m, sort_keys=True, ensure_ascii=False)

def systems(reg):
    data = json.loads(reg.read_text(encoding="utf-8"))
    return data["systems"] + ([ROOT_SYSTEM] if reg == REGISTRY else [])

def zoomgen(reg, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-I", str(ZOOMGEN), *args], cwd=str(reg.parent),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

def run_check(reg, strict=False, quiet=False):
    """重新生成星图清单并汇总问题。只有生成日期变了的清单保持原样，免得每天都多出改动。返回 (通过, 改了的清单)。"""
    od = out_dir(reg)
    before = {p.name: p.read_bytes() for p in od.glob("*.json")} if od.exists() else {}
    r = zoomgen(reg, "--all", str(reg))
    if r.returncode: print(r.stdout + r.stderr); return False, []
    if reg == REGISTRY:
        e = ROOT_SYSTEM
        ids = ",".join(x["id"] for x in systems(reg))
        g = zoomgen(reg, e["root"], "--id", e["id"], "--hints", e["hints"], "--exclude", ",".join(e["exclude"]), "--known", ids,
                    "--location", e["location"], "--out", str(od / f"{e['id']}.zoom.json"))
        if g.returncode: print(g.stdout + g.stderr); return False, []
        zoomgen(reg, "--index", str(od))
    changed = []
    for p in od.glob("*.json"):
        old = before.get(p.name)
        if old is not None and norm_manifest(old) == norm_manifest(p.read_bytes()): p.write_bytes(old)
        elif old != p.read_bytes(): changed.append(p)
    hard = soft = 0
    lines = []
    cap = params().get("ref_hops_max")
    counts = {"broken": 0, "structure": 0, "unresolved": 0, "duplicates": 0, "deep": 0, "hops": 0}
    for p in sorted(od.glob("*.zoom.json")):
        m = json.loads(p.read_text(encoding="utf-8")); c = m.get("checks", {})
        sid = m["system"]["id"]
        hops = max((x["hops"] for x in c.get("depth", [])), default=1 if any(e["kind"] == "ref" for e in m["edges"]) else 0)
        deep = [x for x in c.get("depth", []) if cap and x["hops"] > cap]
        lines.append(f"{sid}: {len(m['nodes'])} 节点 {len(m['edges'])} 边 · 断链 {len(c.get('broken', []))} · 节对不上 {len(c.get('unresolved', []))}"
                     f" · 疑似复写 {len(c.get('duplicates', []))} · 结构 {len(c.get('structure', []))}"
                     f" · 最深引用 {hops} 跳 · 成圈 {len(c.get('cycles', []))} · 已确认复写 {len(c.get('accepted', []))}")
        for k in ("broken", "structure", "unresolved", "duplicates"):
            for x in c.get(k, []): lines.append(f"  [{k}] {sid}: {x}")
        for x in deep: lines.append(f"  [引用过深] {sid}: {' → '.join(x['path'])}（{x['hops']} 跳，上限 {cap}）")
        hard += len(c.get("broken", [])) + len(c.get("structure", []))
        soft += len(c.get("unresolved", [])) + len(c.get("duplicates", [])) + len(deep)
        for k in ("broken", "structure", "unresolved", "duplicates"): counts[k] += len(c.get(k, []))
        counts["deep"] += len(deep); counts["hops"] = max(counts["hops"], hops)
    for x in r.stdout.splitlines():
        if "找不到源目录" in x: lines.append("  " + x); hard += 1; counts["broken"] += 1
    run_check.counts = counts
    ok = hard == 0 and (soft == 0 or not strict)
    if not quiet or not ok:
        print("\n".join(lines))
        if changed: print("星图清单有更新：" + "、".join(rel(p, ROOT) for p in changed) + "（生成文件，一起提交）")
        print("检查通过。" if ok else "检查不通过：断链和结构问题必须为 0" + ("；--strict 下节对不上、疑似复写和引用过深也要为 0" if strict else "") + "。")
        if ok and soft: print(f"另有 {soft} 条节对不上、疑似复写或引用过深，逐条确认；确认过不算问题的复写写进 zoom.hints.json 的 accepted。")
    return ok, changed

def cmd_check(a):
    ok, changed = run_check(registry_of(a), a.strict)
    if a.hook and ok and changed:
        subprocess.run(["git", "add", "--"] + [str(p) for p in changed], cwd=str(ROOT))
        print("已把更新的星图清单加进这次提交。")
    if a.hook and not ok:
        at, _ = now()
        log(find_base(), {"at": at, "who": who(a), "action": "check-failed", "node": "", "why": "提交前钩子拦下", "checks": run_check.counts})
    sys.exit(0 if ok else 1)

# ---------- 反查 ----------
def page_const(name):
    """从星图页面读常量，页面是这些文字的唯一出处（见 skill-starmap/page/starmap.html）。"""
    t = PAGE.read_text(encoding="utf-8")
    m = re.search(r"const " + name + r"\s*=\s*(\"(?:[^\"\\]|\\.)*\"|\{.*?\}|\d+);", t, re.S)
    if not m: sys.exit(f"星图页面里找不到 {name}")
    v = m.group(1)
    if v.startswith("{"): return dict(re.findall(r"(\w+):\s*\"([^\"]*)\"", v))
    return json.loads(v)

def locate(reg, path):
    """文件或文件夹 → (系统 id, 星图节点 id, 清单)。不在任何登记的系统里时返回 None。"""
    best = None
    for e in systems(reg):
        if e["root"].startswith("skills:"): continue
        root = (reg.parent / e["root"]).resolve()
        try: parts = path.relative_to(root).parts
        except ValueError: continue
        if parts and parts[0] in e.get("exclude", []): continue
        if not best or len(root.parts) > len(best[1].parts): best = (e, root, parts)
    if not best: return None
    e, root, parts = best
    sid = e["id"]
    mf = out_dir(reg) / f"{sid}.zoom.json"
    m = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {"nodes": [], "edges": []}
    if path.is_dir(): d, f = parts, None
    else: d, f = parts[:-1], parts[-1]
    folder = root.joinpath(*d)
    head = "SKILL.md" if (folder / "SKILL.md").exists() else "README.md"
    if f is None or f == head: nid = sid if not d else f"{sid}:{'/'.join(d)}/"
    else: nid = f"{sid}:{'/'.join(parts)}"
    return sid, nid, m, root

def refs_of(m, nid, sid):
    ids = {n["id"]: n for n in m["nodes"]}
    inside = (lambda x: x == nid or x.startswith(nid + ":")) if nid == sid else (lambda x: x == nid or (nid.endswith("/") and x.startswith(nid)))
    ins = [e for e in m["edges"] if inside(e["to"]) and not inside(e["from"])]
    outs = [e for e in m["edges"] if inside(e["from"]) and not inside(e["to"])]
    return ins, outs, ids

def describe(e, other, ids, kinds):
    n = ids.get(e[other], {})
    return f"{e[other]} 的 {e.get('source') or n.get('source') or e[other]}{(' ' + '、'.join(e['sections'])) if e.get('sections') else ''}（{kinds.get(e['kind'], e['kind'])}）"

def cmd_refs(a):
    base = find_base(); p = target_path(base, a.path)
    if not p.exists(): sys.exit(f"找不到 {a.path}")
    run_check(registry_of(a), quiet=True)
    hit = locate(registry_of(a), p)
    if not hit: sys.exit(f"{rel(p, base)} 不在登记表的任何系统里；把它所在的项目登记进 registry.json 再试。")
    sid, nid, m, _ = hit
    ins, outs, ids = refs_of(m, nid, sid)
    kinds = page_const("KINDS")
    print(f"星图节点：{nid}")
    print(f"谁引用它（{len(ins)}）：")
    for e in ins: print("  - " + describe(e, "from", ids, kinds))
    print(f"它引用谁（{len(outs)}）：")
    for e in outs: print("  - " + describe(e, "to", ids, kinds))
    print("星图只记录生成那一刻的引用，以源文件为准。")

# ---------- 改动 ----------
def copy_to_clipboard(text):
    for cmd in (["clip"], ["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        if shutil.which(cmd[0]):
            try:
                data = ("\ufeff" + text).encode("utf-16le") if cmd[0] == "clip" else text.encode("utf-8")
                subprocess.run(cmd, input=data, check=True); return True
            except Exception: continue
    return False

def cmd_change(a):
    base = find_base(); p = target_path(base, a.path)
    if not p.exists(): sys.exit(f"找不到 {a.path}")
    reg = registry_of(a)
    run_check(reg, quiet=True)
    what = " ".join(a.what).strip()
    hit = locate(reg, p)
    nrefs = 0
    kinds, tpl, cap = page_const("KINDS"), page_const("EDIT_TEMPLATE"), page_const("EDIT_REFS_MAX")
    if hit:
        sid, nid, m, sroot = hit
        src = (rel(p, sroot) if p != sroot else "根目录") + ("（文件夹）" if p.is_dir() else "")
        loc = rel(sroot, base) + "/" if sroot != base else "项目根目录"
        ins, _, ids = refs_of(m, nid, sid)
        seen = []
        for e in ins:
            x = describe(e, "from", ids, kinds)
            if x not in seen: seen.append(x)
        nrefs = len(seen)
        refs = (f"星图记录的引用方：{'；'.join(seen[:cap])}{f'；另有 {len(seen) - cap} 处' if len(seen) > cap else ''}（以源文件为准）。"
                if seen else "星图里没有记录指向它的连线，以源文件为准，改前在源文件里再查一遍。")
    else:
        sid, refs = base.name, "它不在星图登记的系统里，改前在源文件里自己查一遍谁引用它。"
        src, loc = rel(p, base) + ("（文件夹）" if p.is_dir() else ""), "项目根目录"
    where = record_before(base, p, what or "改动前记录", who(a), {"kind": a.kind, "refs": nrefs})
    daily = rel(ROOT / "semantic-zoom-architecture" / "daily-change.md", base)
    if a.kind == "param": refs = f"共 {nrefs} 处引用它，参数级改动不用逐处跟改。"
    text = tpl.replace("{sys}", sid).replace("{src}", src).replace("{loc}", loc).replace("{refs}", refs)
    py = "python3" if os.name != "nt" else "python"
    text += (f"\n要改什么：{what or '（在这里写）'}"
             f"\n改动分级：{LEVELS[a.kind]}（各级走哪几条见 {daily} § 改动分级）。动手后发现级别定低了，先停下来告诉我。"
             f"\n改前版本已经记下：{where}，不用再快照；不满意运行 {py} {rel(ROOT / 'sza.py', base)} restore {rel(p, base)}。"
             f"\n改完运行 {py} {rel(ROOT / 'sza.py', base)} done {rel(p, base)}：断链和结构必须为 0，再把改了哪些地方告诉我。")
    print(text)
    if a.copy: print("\n（已复制到剪贴板）" if copy_to_clipboard(text) else "\n（没找到剪贴板工具，手动复制上面这段）")

def cmd_done(a):
    base = find_base(); p = target_path(base, a.path)
    reg = registry_of(a)
    ok, _ = run_check(reg)
    before = last_before(base, p) or {}
    rec = {"kind": before.get("kind"), "refs": before.get("refs")}
    sha = before.get("commit")
    snaps = [] if sha else snapshots(base, p)
    if sha:
        skip = (rel(out_dir(reg), base) + "/", ".sza/", "dist/")
        names = (git(base, "diff", "--name-only", sha, "--") or "").splitlines() + (git(base, "ls-files", "--others", "--exclude-standard") or "").splitlines()
        touched = sorted({x for x in names if x and not x.startswith(skip)})
        rec["touched"] = touched[:30]; rec["touched_n"] = len(touched)
        diff = (git(base, "diff", "--unified=1", sha, "--", rel(p, base)) or "").splitlines()
        n = sum(1 for x in diff if x[:1] in "+-" and x[:3] not in ("+++", "---"))
        print(f"\n和改前版本（git {sha[:10]}）的差别（{n} 行）：" if diff else f"\n和改前版本（git {sha[:10]}）没有差别。")
        for x in diff[:60]: print(x)
        if len(diff) > 60: print(f"……另有 {len(diff) - 60} 行")
        if len(touched) > 1: print(f"这次一共动了 {len(touched)} 个文件：" + "、".join(touched[:12]) + ("……" if len(touched) > 12 else ""))
        if len(touched) > 1 and rec["kind"] in ("param", "internal"):
            print(f"注意：定的是{LEVELS[rec['kind']]}，却动了不止一个文件；核对一下是不是该算接口级，或者有定义没收在一处。")
    elif snaps and p.is_file():
        old = (snaps[-1] / p.name).read_text(encoding="utf-8", errors="replace").splitlines()
        new = p.read_text(encoding="utf-8", errors="replace").splitlines()
        diff = list(difflib.unified_diff(old, new, f"{snaps[-1].name}/{p.name}", rel(p, base), lineterm="", n=1))
        print(f"\n和改前快照的差别（{sum(1 for x in diff if x[:1] in '+-' and x[:3] not in ('+++', '---'))} 行）：" if diff else "\n和改前快照没有差别。")
        for x in diff[:60]: print(x)
        if len(diff) > 60: print(f"……另有 {len(diff) - 60} 行")
    elif snaps:
        print(f"\n文件夹和改前快照{'相同' if same(snaps[-1] / p.name, p) else '不同'}。")
    at, _ = now()
    rec = {k: v for k, v in rec.items() if v is not None}
    log(base, {"at": at, "who": who(a), "action": "done" if ok else "done-failed", "node": rel(p, base), "why": a.why or "", **rec,
               "checks": getattr(run_check, "counts", {})})
    sys.exit(0 if ok else 1)

# ---------- 度量 ----------
def cmd_incident(a):
    base = find_base(); p = target_path(base, a.path)
    at, _ = now()
    log(base, {"at": at, "who": who(a), "action": "incident", "node": rel(p, base), "why": " ".join(a.what).strip(), "kind": a.kind})
    print(f"已记一次事故（{'别处没跟上' if a.kind == 'stale' else '没跟引用就动手'}）：{rel(p, base)}。运行 stats 看汇总。")

def cmd_stats(a):
    """各项的含义见 semantic-zoom-architecture/metrics.md § 度量；这里只算数。"""
    base, reg, P = find_base(), registry_of(a), params()
    rows = read_log(base)
    if a.days:
        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=a.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = [r for r in rows if r.get("at", "") >= since]
    span = f"最近 {a.days} 天" if a.days else "全部记录"
    changes = [r for r in rows if r.get("action") == BEFORE]
    dones = [r for r in rows if r.get("action") in ("done", "done-failed")]
    inc = [r for r in rows if r.get("action") == "incident"]
    stale, skipped = [r for r in inc if r.get("kind") != "skipped"], [r for r in inc if r.get("kind") == "skipped"]
    blocked = [r for r in rows if r.get("action") in ("done-failed", "check-failed")]
    print(f"度量（{span}，{rows[0]['at'][:10]} 起）" if rows else f"度量（{span}）：还没有记录。先用 change / done 改几次再看。")
    if not rows: return
    by = {k: sum(1 for r in changes if r.get("kind", "internal") == k) for k in LEVELS}
    print(f"改动 {len(changes)} 次：" + "、".join(f"{LEVELS[k]} {v}" for k, v in by.items()) + f"；其中 {len(dones)} 次做了 done")
    rate = lambda n: f"{n}（每 10 次改动 {n * 10 / len(changes):.1f}）" if changes else str(n)
    print(f"过时事故：{rate(len(stale))}")
    print(f"没跟引用：{rate(len(skipped))}")
    print(f"检查拦下：{len(blocked)} 次（done 没通过 {sum(1 for r in blocked if r['action'] == 'done-failed')}，提交前钩子 {sum(1 for r in blocked if r['action'] == 'check-failed')}）")
    withrefs = [r["refs"] for r in changes if isinstance(r.get("refs"), int)]
    wt = [r for r in dones if isinstance(r.get("touched_n"), int)]
    if withrefs: print(f"波及：每次改动平均 {sum(withrefs) / len(withrefs):.1f} 处引用它" + (f"，实际平均动 {sum(r['touched_n'] for r in wt) / len(wt):.1f} 个文件" if wt else "（没有 git，实际动了几个文件没记）"))
    off = [r for r in wt if r.get("kind") in ("param", "internal") and r["touched_n"] > 1]
    print(f"定级不符：{len(off)} 次（定的是参数级或内部级，却动了不止一个文件）")
    for r in off[-5:]: print(f"  - {r['at'][:10]} {r['node']}（{LEVELS[r['kind']]}，动了 {r['touched_n']} 个文件）")
    od, cap = out_dir(reg), P.get("ref_hops_max")
    for f in sorted(od.glob("*.zoom.json")) if od.exists() else []:
        m = json.loads(f.read_text(encoding="utf-8")); d = m.get("checks", {}).get("depth", [])
        top = max(d, key=lambda x: x["hops"], default=None)
        if top: print(f"引用深度：{m['system']['id']} 最深 {top['hops']} 跳{f'（上限 {cap}）' if cap else ''}，从 {top['node']} 起要再读 {top['files']} 个文件")
    hints, limit = [], P.get("split_lines")
    for e in systems(reg) if limit else []:
        if e["root"].startswith("skills:"): continue
        root = (reg.parent / e["root"]).resolve()
        for k, f in files_under(root).items() if root.is_dir() else []:
            if not k.endswith(".md") or k.split("/")[0] in e.get("exclude", []) or k.split("/")[-1] == "CHANGELOG.md": continue
            n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            if n > limit: hints.append(f"  - 考虑拆分：{rel(f, base)} 有 {n} 行（上限 {limit}）")
    count, pair = {}, {}
    for r in wt:
        fs = sorted(set(r.get("touched", [])))
        for x in fs: count[x] = count.get(x, 0) + 1
        for i, x in enumerate(fs):
            for y in fs[i + 1:]: pair[(x, y)] = pair.get((x, y), 0) + 1
    cmin, share = P.get("cochange_min"), P.get("cochange_share")
    for (x, y), n in sorted(pair.items(), key=lambda kv: -kv[1]) if cmin and share else []:
        if n >= cmin and n / min(count[x], count[y]) >= share:
            hints.append(f"  - 考虑合并或抽出共用定义：{x} 和 {y} 一起改了 {n} 次（各改 {count[x]}、{count[y]} 次）")
    print("拆分与合并提示（阈值在 semantic-zoom-architecture/params.json）：" + ("" if hints else "没有。"))
    for x in hints[:20]: print(x)

# ---------- 安装与更新 ----------
def rewrite_command(text, sza_ref):
    return text.replace("python3 sza.py", f'python3 "{sza_ref}"')

def install(base, target, commands, user, quiet=False):
    report = {}
    for s in SKILLS:
        report[f"skills/{s}"] = sync(ROOT / s, target / s)
    if commands and COMMANDS.is_dir():
        cdir = (Path.home() / ".claude" / "commands") if user else (base / ".claude" / "commands")
        if cdir.resolve() != COMMANDS.resolve():
            ref = (ROOT / "sza.py").as_posix() if user else relref(ROOT / "sza.py", base)
            added, changed = [], []
            for f in sorted(COMMANDS.glob("sza-*.md")):
                q = cdir / f.name; new = rewrite_command(f.read_text(encoding="utf-8"), ref)
                if q.exists() and q.read_text(encoding="utf-8") == new: continue
                (changed if q.exists() else added).append(f.name)
                q.parent.mkdir(parents=True, exist_ok=True); q.write_text(new, encoding="utf-8")
            report["commands"] = (added, changed, [])
    rec = base / ".sza" / "install.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    at, _ = now()
    recs = [r for r in load_installs(base) if r.get("target") != target.as_posix()]
    recs.append({"at": at, "target": target.as_posix(), "user": user, "commands": commands, "from": ROOT.as_posix()})
    rec.write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")
    return report

def load_installs(base):
    """装过的位置，一个位置一条记录（项目里和 --user 可以同时有）。"""
    rec = Path(base) / ".sza" / "install.json"
    if not rec.exists(): return []
    data = json.loads(rec.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]

def print_report(report, target):
    total = 0
    for k, (ad, ch, rm) in report.items():
        for tag, xs in (("新增", ad), ("改动", ch), ("删除", rm)):
            for x in xs: print(f"  {tag}  {k}/{x}"); total += 1
    print(f"装到 {target.as_posix()}：{total} 个文件有变化。" if total else f"{target.as_posix()} 已是最新。")

def cmd_install(a):
    base = find_base()
    target = (Path.home() / ".claude" / "skills") if a.user else Path(a.target).resolve() if a.target else base / ".claude" / "skills"
    print_report(install(base, target, not a.no_commands, a.user), target)
    print("下一步：在 Claude Code 里输入 /sza-check；要改某处时用 /sza-change <文件> <要改什么>。claude.ai 网页版用 pack 打出的 zip 上传。")

def cmd_update(a):
    base = find_base()
    recs = load_installs(base)
    if not recs: sys.exit("还没装过：先运行 install。")
    if a.pull:
        if not (ROOT / ".git").exists(): sys.exit(f"{ROOT.as_posix()} 不是 git 仓库，没法 --pull；手动下载新版覆盖后再运行 update。")
        subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"], check=True)
    for r in recs:
        target = Path(r["target"])
        print_report(install(base, target, r.get("commands", True), r.get("user", False)), target)

def cmd_install_hook(a):
    base = find_base()
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(base), capture_output=True, text=True, check=True).stdout.strip()
        hooks = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=str(base), capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit("这里不是 git 仓库（或没装 git）；没有 git 时在交付前手动运行 check。")
    top = Path(top); hooks = Path(hooks) if Path(hooks).is_absolute() else top / hooks
    hook = hooks / "pre-commit"
    if hook.exists() and HOOK_MARK not in hook.read_text(encoding="utf-8", errors="replace") and not a.force:
        sys.exit(f"{hook.as_posix()} 已有别的钩子，没动它。加 --force 覆盖，或在它里面加一行：python3 {relref(ROOT / 'sza.py', top)} check --hook")
    sza = relref(ROOT / "sza.py", top)
    extra = f' --registry "{relref(registry_of(a), top)}"' if a.registry else ""
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\n" + HOOK_MARK + "（sza.py install-hook 生成，勿手改；命令见 sza.py 文件头）\n"
                    f'PY="{Path(sys.executable).as_posix()}"\n'
                    '[ -x "$PY" ] || PY=$(command -v python3 || command -v python || command -v py)\n'
                    f'exec "$PY" "{sza}" check --hook{extra}\n', encoding="utf-8", newline="\n")
    try: hook.chmod(0o755)
    except OSError: pass
    print(f"已加提交前钩子：{hook.as_posix()}。每次提交先跑 check。")

# ---------- 打包 ----------
def ignored(relpath, patterns):
    """简化版 .gitignore 匹配：带斜杠的按路径前缀，不带的按任一层名字。"""
    parts = relpath.split("/")
    for pat in patterns:
        p = pat.strip("/")
        if "/" in p:
            if fnmatch.fnmatch(relpath, p) or relpath.startswith(p + "/"): return True
        elif any(fnmatch.fnmatch(x, p) for x in (parts[:-1] if pat.endswith("/") else parts)): return True
    return False

def zip_dir(src, zpath, top, skip=()):
    n = 0
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for k, p in files_under(src).items():
            if any(ignored(k, [s]) for s in skip): continue
            z.write(p, f"{top}/{k}"); n += 1
    return n

def cmd_pack(a):
    ok, _ = run_check(registry_of(a), a.strict)
    if not ok: sys.exit("检查没通过，没有打包。")
    base, dist = find_base(), ROOT / "dist"
    dist.mkdir(exist_ok=True)
    gi = ROOT / ".gitignore"
    pats = [x.strip() for x in gi.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")] if gi.exists() else []
    made = []
    for s in SKILLS:
        z = dist / f"{s}.zip"
        if z.exists(): do_snapshot(base, z, "打新包前保存上一版技能 zip", who(a), "snapshot-before-pack")
        zip_dir(ROOT / s, z, s, pats); made.append(z)
    name = a.name or f"{RELEASE}-{datetime.date.today().isoformat()}"
    z = dist / f"{name}.zip"
    n = zip_dir(ROOT, z, RELEASE, pats + [".claude/skills/"]); made.append(z)
    for x in made: print(f"  {rel(x, ROOT)}（{x.stat().st_size // 1024} KB）")
    print(f"打包完成，整仓 zip 里 {n} 个文件。技能 zip 在 claude.ai 的 Settings > Skills 上传；整仓 zip 是发布用的，推送和上传由你来做。")

# ---------- 命令行 ----------
def main():
    ap = argparse.ArgumentParser(prog="sza.py", description="SZA + SSM 的命令入口；完整说明见本文件头。",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_); p.set_defaults(fn=fn)
        p.add_argument("--registry", help="星图登记表，默认 skill-starmap/registry.json")
        p.add_argument("--who", help="写进日志的名字")
        return p
    p = add("install", cmd_install, "把两个技能和斜杠命令装进项目"); g = p.add_mutually_exclusive_group()
    g.add_argument("--user", action="store_true"); g.add_argument("--target"); p.add_argument("--no-commands", action="store_true")
    p = add("update", cmd_update, "按上次 install 的设置重新复制"); p.add_argument("--pull", action="store_true")
    p = add("install-hook", cmd_install_hook, "加 git 提交前钩子"); p.add_argument("--force", action="store_true")
    p = add("check", cmd_check, "重新生成星图并检查"); p.add_argument("--strict", action="store_true"); p.add_argument("--hook", action="store_true", help=argparse.SUPPRESS)
    p = add("pack", cmd_pack, "检查通过后打包到 dist/"); p.add_argument("--strict", action="store_true"); p.add_argument("--name")
    p = add("snapshot", cmd_snapshot, "改动前快照"); p.add_argument("path"); p.add_argument("--why")
    p = add("restore", cmd_restore, "退回到改前版本（git 或快照）"); p.add_argument("path"); p.add_argument("--at"); p.add_argument("--why")
    p = add("history", cmd_history, "列出快照和日志"); p.add_argument("path", nargs="?")
    p = add("refs", cmd_refs, "反查谁引用它"); p.add_argument("path")
    p = add("change", cmd_change, "快照 + 反查 + 打印给 AI 的改动指令"); p.add_argument("path"); p.add_argument("what", nargs="*"); p.add_argument("--copy", action="store_true")
    p.add_argument("--kind", choices=list(LEVELS), default="internal", help="改动分级，默认 internal")
    p = add("done", cmd_done, "改完后检查并记日志"); p.add_argument("path"); p.add_argument("--why")
    p = add("incident", cmd_incident, "记一次事故"); p.add_argument("path"); p.add_argument("what", nargs="*")
    p.add_argument("--kind", choices=["stale", "skipped"], default="stale")
    p = add("stats", cmd_stats, "从日志汇总度量"); p.add_argument("--days", type=int)
    a = ap.parse_args()
    a.fn(a)

if __name__ == "__main__":
    main()
