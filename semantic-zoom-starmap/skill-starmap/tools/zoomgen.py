#!/usr/bin/env python3
# Copyright (c) 2026 Xuhao Chao. All rights reserved. Proprietary; see LICENSE at the repository root.
"""zoomgen：从一个技能 / 项目目录生成语义缩放清单 zoom.json（协议 2.0），顺带查断链、复写与结构。
用法：
  python3 tools/zoomgen.py <源目录> [--id ID] [--hints 文件] [--out 文件] [--known id,id] [--exclude 目录,目录] [--location 文字] [--skill] [--strict]
  python3 tools/zoomgen.py --index <清单目录>      # 重写该目录的 index.json
  python3 tools/zoomgen.py --all registry.json      # 按登记表重新生成全部清单和 index.json
协议（字段、节点类型、边类型）只在 zoom.schema.json；推导规则与层级映射见 rules.md。
--strict：有断链或结构问题时返回 1（适合放进交付前检查或提交前钩子）。"""
import json, re, sys, pathlib, posixpath, datetime, argparse, fnmatch

SKIP_DIRS = {"__pycache__", "node_modules", ".git"}
SKIP_FILES = {"zoom.json"}
HEADS = ("SKILL.md", "README.md")              # 头脑文件的认法，见 rules.md § 1
EXEMPT_DUP = {"CHANGELOG.md"}
MIN_DUP = 28           # 复写检查：规范化后至少这么长的句子才比
PATH_RX = r"[\w][\w./-]*\.(?:md|json|py|html|js|ts|sh|css|ya?ml|toml|txt)"
REF_RX = re.compile(r"见\s*`?(" + PATH_RX + r")`?(\s*§\s*[^。；;，,\n|`）)」』]*)?")
LINK_RX = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
TICK_RX = re.compile(r"`([\w*][\w./*-]*(?:\.\w+|/))`")

def clean(s):
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.sub(r"https?://\S+", "（链接）", s)
    s = LINK_RX.sub(r"\1", s)
    s = s.replace("**", "").replace("`", "").replace("__", "")
    return re.sub(r"\s+", " ", s).strip(" -*>#|")

def short(s, n=None):
    """一句话角色：取第一句，原文完整，不加省略号。"""
    s = clean(s)
    for stop in "。；;":
        i = s.find(stop)
        if i > 8: return s[: i + 1]
    return s

def norm(s):
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    return re.sub(r"[\s`*：:。，,、]", "", s).lower()

def frontmatter(t):
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    out, key = {}, None
    if m:
        for line in m.group(1).splitlines():
            if line[:1] in " \t" and key:
                out[key] = (out[key] + " " + line.strip()).strip(); continue
            k, _, v = line.partition(":")
            if not _: continue
            key = k.strip(); v = v.strip()
            out[key] = "" if v in (">", "|", ">-", "|-") else v.strip('"').strip("'")
    return out

def body_lines(t):
    """去掉 frontmatter 与代码块后的 (行号, 行)。"""
    m = re.match(r"^---\n.*?\n---\n", t, re.S)
    skip = t[: m.end()].count("\n") if m else 0
    inside = False
    for i, line in enumerate(t.splitlines(), 1):
        if i <= skip: continue
        if line.startswith("```"): inside = not inside; continue
        if not inside: yield i, line

class Gen:
    def __init__(s, root, sid=None, hints=None, known=(), exclude=(), location=None, skill=False):
        s.root = pathlib.Path(root).resolve()
        s.exclude = set(exclude)
        s.hints = json.loads(pathlib.Path(hints).read_text(encoding="utf-8")) if hints else {}
        s.known = set(known)
        s.location = location or str(root)
        s.text, s.binary = {}, set()
        for p in sorted(s.root.rglob("*")):
            parts = p.relative_to(s.root).parts
            if not p.is_file() or p.name in SKIP_FILES: continue
            if any(x in SKIP_DIRS or x.startswith(".") for x in parts) or parts[0] in s.exclude: continue
            rel = "/".join(parts)
            raw = p.read_bytes()
            if b"\0" in raw[:4096]: s.binary.add(rel); s.text[rel] = ""; continue
            s.text[rel] = raw.decode("utf-8", errors="replace")
        s.dirs = {""}
        for rel in s.text:
            parts = rel.split("/")
            for i in range(1, len(parts)): s.dirs.add("/".join(parts[:i]) + "/")
        s.head = {}
        for d in s.dirs:
            h = next((d + n for n in HEADS if d + n in s.text), None)
            if h: s.head[d] = h
        s.head_dir = {h: d for d, h in s.head.items()}
        root_head = s.head.get("")
        s.front = frontmatter(s.text.get(root_head, "")) if root_head else {}
        sk = frontmatter(s.text.get("SKILL.md", ""))
        s.sid = sid or s.hints.get("system", {}).get("id") or sk.get("name") or s.root.name
        s.sid = re.sub(r"[^a-z0-9-]+", "-", s.sid.lower()).strip("-")
        s.skill_desc = sk.get("description", "")
        s.layers = s.hints.get("layers", {})
        s.skill_dirs = set(s.hints.get("skills", [])) | ({""} if skill else set())
        s.nodes, s.edges = {}, {}
        s.checks = {"broken": [], "unresolved": [], "duplicates": [], "structure": [], "info": [],
                    "accepted": [], "depth": [], "cycles": []}
        s.headings = {rel: s.parse_headings(rel) for rel in s.text}

    # ---------- 节点 id 与层级 ----------
    def dir_id(s, d): return s.sid if d == "" else f"{s.sid}:{d}"
    def nid(s, rel):
        if rel.endswith("/") or rel == "": return s.dir_id(rel)
        return s.dir_id(s.head_dir[rel]) if rel in s.head_dir else f"{s.sid}:{rel}"
    @staticmethod
    def parent_dir(rel):
        p = posixpath.dirname(rel.rstrip("/"))
        return p + "/" if p else ""

    def layer_file(s, rel):
        """层级判定的实现；判定只写在 rules.md § 2。"""
        if rel in s.layers: return s.layers[rel]
        if not rel.endswith(".md"): return 3
        return 1 if s.parent_dir(rel) == "" else 2
    def layer_dir(s, d):
        if d == "": return 0
        if d in s.layers: return s.layers[d]
        return 1 if s.parent_dir(d) == "" else 2

    # ---------- 读 ----------
    def parse_headings(s, rel):
        t = s.text[rel]
        if rel.endswith(".json"):
            try: data = json.loads(t)
            except Exception: return []
            return [{"level": 2, "title": k} for k in data] if isinstance(data, dict) else []
        if not rel.endswith(".md"): return []
        out = []
        for _, line in body_lines(t):
            m = re.match(r"^(#{1,4})\s+(.+?)\s*#*$", line)
            if m:
                title = clean(m.group(2))
                h = {"level": len(m.group(1)), "title": title}
                if "冻结" in title or "沿用规格" in title: h["frozen"] = True
                out.append(h)
        return out

    def first_prose(s, rel):
        for _, line in body_lines(s.text[rel]):
            x = line.strip()
            if not x or x.startswith(("#", "|", "<!--", "---", ">")): continue
            if re.match(r"^[-*]\s|^\d+\.\s", x): return None
            return x
        return None

    def h1(s, rel):
        hs = s.headings.get(rel) or []
        return hs[0]["title"] if hs and hs[0]["level"] == 1 else None

    def listing(s, d):
        """头脑文件里列出的下层：{路径: 角色}，以及点名过的名字与通配。"""
        h = s.head.get(d)
        roles, names, globs = {}, set(), []
        strong = set()   # 链接、目录树列出的角色优先于反引号点名（见 rules.md § 3）
        def put(tf, r, firm):
            if firm and tf not in strong: roles[tf] = r; strong.add(tf)
            elif not firm: roles.setdefault(tf, r)
        if not h: return roles, names, globs
        t = s.text[h]
        inside = False
        for line in t.splitlines():
            if line.startswith("```"): inside = not inside; continue
            if inside:
                m = re.match(r"^[\s│├└─|`+\\-]*([\w.-]+/?)\s{2,}(\S.*)$", line)
                if m:
                    names.add(m.group(1).rstrip("/"))
                    tf = s.target(h, m.group(1))
                    if tf: put(tf, m.group(2).strip(), True)
                continue
            for lm in LINK_RX.finditer(line):
                tf = s.target(h, lm.group(2))
                if not tf: continue
                if tf in s.head_dir: tf = s.head_dir[tf]
                names.add(tf.rstrip("/").split("/")[-1])
                put(tf, s.role_from_line(line, lm.group(1)), True)
            for tm in TICK_RX.finditer(line):
                tok = tm.group(1)
                if "*" in tok: globs.append(tok.split("/")[-1]); continue
                tf = s.target(h, tok)
                if tf and tf in s.head_dir: tf = s.head_dir[tf]
                names.add((tf or tok).rstrip("/").split("/")[-1])
                if tf:
                    if line.lstrip().startswith(("-", "*", "|")):
                        cells = [c.strip() for c in line.strip().strip("|").split("|")]
                        r = cells[1] if line.lstrip().startswith("|") and len(cells) > 1 else s.role_from_line(line, tok)
                        put(tf, r, False)
        return roles, names, globs

    @staticmethod
    def role_from_line(line, name):
        c = clean(line)
        n = clean(name)
        if c.startswith(n):
            rest = c[len(n):].lstrip(" ：:—-→")
            if rest: return rest
        return c

    # ---------- 路径解析 ----------
    def target(s, rel_from, f):
        """f 指向的本系统路径；None = 不在本系统（跳过）；False = 应在却不存在（断链）。"""
        f = f.strip().split("#")[0]
        if not f or "<" in f or re.match(r"^[a-z]+:", f): return None
        base = posixpath.dirname(rel_from)
        for cand in (f, posixpath.join(base, f)):
            c = posixpath.normpath(cand)
            if c.startswith("..") or c.startswith("/"): continue
            if c == ".": return ""
            if c.split("/")[0] in s.exclude: return None
            if c in s.text: return c
            if c + "/" in s.dirs: return c + "/"
        c = posixpath.normpath(posixpath.join(base, f))
        if c.startswith(".."): return None
        return False

    def sec_ok(s, tf, sec):
        if tf.endswith("/") or tf == "": tf = s.head.get(tf, "")
        hs = s.headings.get(tf)
        if not hs: return True   # 代码、页面没有标题，不查
        sec = re.sub(r"[（(][^）)]*[）)]", "", sec.replace("§", "")).strip()
        if not sec: return True
        titles = [h["title"] for h in hs]
        for piece in re.split(r"[、，,]|\s和\s", sec):
            piece = piece.strip()
            if not piece: continue
            num = re.match(r"^(?:第\s*)?(\d+(?:\.\d+)*)(?:\s*[–-]\s*\d+(?:\.\d+)*)?", piece)
            if num:
                n = num.group(1)
                if not any(re.match(r"^§?\s*" + re.escape(n) + r"(?:[.\s、]|$)", t) for t in titles): return False
                continue
            word = norm(re.sub(r"\s*第.*$", "", piece))
            word = re.sub(r"\d+$", "", word)
            if len(word) < 2: continue
            if not any(word == norm(t) or word in norm(t) or (len(norm(t)) >= 2 and norm(t) in word) for t in titles): return False
            break   # 名字后面的「第 2、4 条」是条目号，不再逐项查
        return True

    # ---------- 建树 ----------
    def add(s, nid, parent, kind, title, layer, **kw):
        n = {"id": nid, "parent": parent, "layer": layer, "kind": kind, "title": title}
        n.update({k: v for k, v in kw.items() if v not in (None, "", [], False)})
        s.nodes[nid] = n
        return n

    def build(s):
        h = s.hints.get("system", {})
        rh = s.head.get("")
        title = h.get("title") or (s.h1(rh) if rh else None) or s.front.get("name") or s.sid
        params = s.load_json("params.json")
        version = h.get("version") or (params or {}).get("system_version") or s.front.get("version") \
            or (re.search(r"\bv(\d+(?:\.\d+)+)\b", title or "") or [None, None])[1]
        role = h.get("role") or short(s.front.get("description", ""), 90) or short(s.first_prose(rh) or "", 90) if rh else h.get("role")
        s.add(s.sid, None, "system", clean(title), 0, role=role, version=version, source=rh, head=rh,
              sections=s.sections_of(rh), generated=None)
        listings = {d: s.listing(d) for d in s.dirs}
        s.listings = listings
        for d in sorted(s.dirs - {""}, key=lambda x: (x.count("/"), x)):
            hd = s.head.get(d)
            fm = frontmatter(s.text.get(hd, "")) if hd else {}
            role = short(fm.get("description", "")) or (short(s.first_prose(hd) or "") if hd else "") \
                or listings[s.parent_dir(d)][0].get(d, "")
            title = (s.h1(hd) if hd else None) or d
            s.add(s.nid(d), s.dir_id(s.parent_dir(d)), "dir", clean(title), s.layer_dir(d), role=role,
                  source=hd or d, head=hd, sections=s.sections_of(hd))
        for rel in sorted(s.text):
            if rel in s.head_dir: continue
            pd = s.parent_dir(rel)
            lrole = listings[pd][0].get(rel, "")
            gen = "【生成文件】" in lrole or bool(re.search(r"生成文件.{0,4}勿手改", s.text[rel][:400]))
            role = lrole.replace("【生成文件】", "").strip() or s.own_role(rel)
            s.add(s.nid(rel), s.dir_id(pd), "file", rel.split("/")[-1], s.layer_file(rel), role=role,
                  source=rel, sections=s.sections_of(rel), generated=gen)

    def sections_of(s, rel):
        if not rel: return None
        hs = s.headings.get(rel) or []
        if hs and hs[0]["level"] == 1 and rel.endswith(".md"): hs = hs[1:]   # 一级标题是文件名字，不算节
        return hs or None

    def own_role(s, rel):
        t = s.text[rel]
        if rel.endswith(".md"):
            fm = frontmatter(t)
            return short(fm.get("description", "")) or short(s.h1(rel) or "", 40)
        if rel.endswith(".py"):
            m = re.search(r'"""(.+?)(?:\n|""")', t); return short(m.group(1)) if m else ""
        if rel.endswith(".html"):
            m = re.search(r"<title>(.*?)</title>", t, re.S); return clean(m.group(1)) if m else "页面"
        if rel.endswith(".json"):
            d = s.load_json(rel)
            if isinstance(d, dict):
                for k in ("title", "description"):
                    if isinstance(d.get(k), str): return short(d[k])
            return "参数 / 数据"
        return ""

    def load_json(s, rel):
        try: return json.loads(s.text[rel]) if rel in s.text else None
        except Exception: return None

    # ---------- 边 ----------
    def is_anc(s, a, b):
        while b in s.nodes:
            b = s.nodes[b]["parent"]
            if b == a: return True
        return False

    def edge(s, a, b, kind, src, sec=None):
        if not a or not b or a == b: return
        if kind == "mention" and (s.is_anc(a, b) or s.is_anc(b, a)): return   # 包含关系，不画
        if kind == "ref" and s.is_anc(b, a): return                              # 指向自己所在的上层
        k = (a, b, kind)
        e = s.edges.get(k)
        if not e: e = s.edges[k] = {"from": a, "to": b, "kind": kind, "source": src}
        else: e["n"] = e.get("n", 1) + 1
        if sec:
            e.setdefault("sections", [])
            if sec not in e["sections"]: e["sections"].append(sec)

    def scan(s):
        for rel, t in s.text.items():
            if not rel.endswith(".md"): continue
            here = s.nid(rel)
            if s.nodes.get(here, {}).get("generated"): s.scan_generated(rel, t); continue
            for i, line in body_lines(t):
                src = f"{rel}:{i}"
                taken = set()
                for m in REF_RX.finditer(line):
                    f, sec = m.group(1), (m.group(2) or "").strip()
                    tf = s.target(rel, f)
                    taken.add(f)
                    if tf is None: continue
                    if tf is False:
                        s.checks["broken"].append({"node": here, "at": src, "ref": f, "why": "引用的文件不存在"}); continue
                    sec = re.sub(r"\s+", " ", sec).rstrip(" 的里中") or None
                    if sec and not s.sec_ok(tf, sec):
                        s.checks["unresolved"].append({"node": here, "at": src, "ref": f"{tf} {sec}", "why": "「§ 节」对不上标题"})
                    s.edge(here, s.nid(tf), "ref", src, sec)
                for m in LINK_RX.finditer(line):
                    f = m.group(2)
                    if f in taken or re.match(r"^(https?:|mailto:|#)", f): continue
                    tf = s.target(rel, f)
                    if tf is None: continue
                    if tf is False:
                        s.checks["broken"].append({"node": here, "at": src, "ref": f, "why": "链接的文件不存在"}); continue
                    taken.add(f)
                    s.edge(here, s.nid(tf), "mention", src)
                for m in TICK_RX.finditer(line):
                    f = m.group(1)
                    if f in taken or "*" in f or f == "params.json": continue
                    tf = s.target(rel, f)
                    if tf: s.edge(here, s.nid(tf), "mention", src)
                for m in re.finditer(r"`params(?:\.json)?\.([A-Za-z_]\w*)", line):
                    if "params.json" in s.text: s.edge(here, s.nid("params.json"), "param", src, "§ " + m.group(1))
                for other in s.known:
                    if other != s.sid and re.search(r"(?<![\w-])" + re.escape(other) + r"(?![\w-])", line):
                        s.edge(here, other, "mention", src)

    def scan_generated(s, rel, t):
        m = re.search(r"生成器[：:]\s*(" + PATH_RX + ")", t[:400])
        if m:
            tf = s.target(rel, m.group(1))
            if tf: s.edge(s.nid(tf), s.nid(rel), "generates", f"{rel}:1")
        for h in s.headings.get(rel, []):
            mm = re.search(r"来自\s*(" + PATH_RX + r")\s*([^）)]*)", h["title"])
            if not mm: continue
            tf = s.target(rel, mm.group(1))
            if tf: s.edge(s.nid(tf), s.nid(rel), "copy", f"{rel} § {h['title']}", ("§ " + mm.group(2).strip()) if mm.group(2).strip() else None)

    # ---------- 出处表 ----------
    def defines(s):
        rh = s.head.get("")
        if not rh: return
        on = False
        for i, line in body_lines(s.text[rh]):
            r = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", line)
            if not r: on = False; continue
            a, b = r.groups()
            if "概念" in a and "出处" in b: on = True; continue
            if not on or set(a) <= set("-: "): continue
            m = re.match(r"`?(" + PATH_RX + r")`?\s*(.*)$", b)
            if not m: continue
            tf = s.target(rh, m.group(1))
            concept = clean(a)
            if not tf:
                s.checks["broken"].append({"node": s.sid, "at": f"{rh}:{i}", "ref": m.group(1), "why": f"概念「{concept}」的出处文件不存在"}); continue
            sec = clean(m.group(2))
            if sec and not s.sec_ok(tf, sec):
                s.checks["unresolved"].append({"node": s.sid, "at": f"{rh}:{i}", "ref": f"{tf} {sec}", "why": f"概念「{concept}」的节对不上标题"})
            s.nodes[s.nid(tf)].setdefault("defines", []).append(concept + (f"（{sec}）" if sec else ""))

    # ---------- 结构 ----------
    def structure(s):
        for d in sorted(s.dirs):
            did = s.dir_id(d)
            hd = s.head.get(d)
            if d in s.skill_dirs and d + "SKILL.md" not in s.text:
                s.checks["structure"].append({"node": did, "at": d or "./", "why": "skill 文件夹必须有 SKILL.md"})
            if not hd:
                if d == "": s.checks["structure"].append({"node": did, "at": "./", "why": "根目录必须有头脑文件（README.md 或 SKILL.md）"})
                elif d not in s.skill_dirs: s.checks["info"].append({"node": did, "at": d, "why": "没有头脑文件，按默认处理：下面的文件就是它的节点"})
                continue
            pointer = None
            if hd.endswith("SKILL.md") and d + "README.md" in s.text:
                pointer = d + "README.md"
                body = "".join(clean(l) for _, l in body_lines(s.text[pointer]) if not l.startswith("#"))
                rest = re.sub(r"SKILL\.md|[见请看参阅\s。.:：`\[\]()（）]", "", body)   # 除了指向，剩下的字
                if "SKILL.md" not in body or len(rest) > 20:
                    s.checks["structure"].append({"node": s.nid(pointer), "at": pointer, "why": "两个头脑文件：SKILL.md 旁边的 README.md 不只是一句「见 SKILL.md」"})
            _, names, globs = s.listings[d]
            kids = [r for r in s.text if s.parent_dir(r) == d and r not in (hd, pointer)] + \
                   [x for x in s.dirs if x and s.parent_dir(x) == d]
            for k in kids:
                base = k.rstrip("/").split("/")[-1]
                if base in names or any(fnmatch.fnmatch(base, g) for g in globs): continue
                s.checks["structure"].append({"node": s.nid(k), "at": hd, "ref": k, "why": "头脑文件没列出它"})

    # ---------- 复写 ----------
    def duplicates(s):
        seen = {}
        for rel, t in s.text.items():
            if not rel.endswith(".md") or rel.split("/")[-1] in EXEMPT_DUP or s.nodes.get(s.nid(rel), {}).get("generated"): continue
            for i, line in body_lines(t):
                if line.startswith("#") or "见" in line or re.search(r"`" + PATH_RX + "`", line) or re.match(r"^\|?[\s|:-]+$", line): continue
                n = re.sub(r"^\s*(?:\d+\.|[-*>|])\s*", "", clean(line))
                n = re.sub(r"[\s，。；：、,.;:()（）]", "", n)
                if len(n) >= MIN_DUP: seen.setdefault(n, []).append(f"{rel}:{i}")
        for n, where in seen.items():
            if len({w.split(":")[0] for w in where}) > 1:
                s.checks["duplicates"].append({"node": s.nid(where[0].split(":")[0]), "at": where, "text": n[:40] + ("…" if len(n) > 40 else ""), "why": "同一句话出现在多个文件"})
        params = s.load_json("params.json")
        if params:
            vals = set()
            def walk(v):
                if isinstance(v, dict): [walk(x) for x in v.values()]
                elif isinstance(v, list): [walk(x) for x in v]
                elif isinstance(v, str) and re.fullmatch(r"\d{1,2}:\d{2}", v): vals.add(v)
            walk(params)
            for rel, t in s.text.items():
                if not rel.endswith(".md") or rel.split("/")[-1] in EXEMPT_DUP or s.nodes.get(s.nid(rel), {}).get("generated"): continue
                for i, line in enumerate(t.splitlines(), 1):
                    for v in vals:
                        if re.search(r"(?<![\d:-])" + re.escape(v) + r"(?![\d:])", line):
                            s.checks["duplicates"].append({"node": s.nid(rel), "at": [f"{rel}:{i}"], "text": v, "why": "params.json 里的数值在正文又写了一遍"})

    def accept(s):
        """hints 的 accepted 里确认过的疑似复写，挪到 checks.accepted，不再算问题；规则见 rules.md § 7。"""
        keys = []
        for it in s.hints.get("accepted", []):
            k = re.sub(r"[\s，。；：、,.;:()（）…]", "", clean(it.get("text", "")))
            if k: keys.append((k, it.get("why", "")))
        used, keep = set(), []
        for d in s.checks["duplicates"]:
            n = d["text"].rstrip("…")
            hit = next((i for i, (k, _) in enumerate(keys) if n.startswith(k) or k.startswith(n)), None)
            if hit is None: keep.append(d); continue
            used.add(hit); s.checks["accepted"].append(dict(d, why=keys[hit][1] or "已确认"))
        s.checks["duplicates"] = keep
        for i, (k, _) in enumerate(keys):
            if i not in used:
                s.checks["info"].append({"node": s.sid, "at": "zoom.hints.json accepted", "ref": k[:40], "why": "这条确认已经对不上任何疑似复写，可以删掉"})

    # ---------- 引用深度 ----------
    def depth(s):
        """沿「见 文件 § 节」（ref 边）往下跟：每个文件最远要跟几跳、一共要再读几个文件；互相引用成圈的记进 cycles。规则见 rules.md § 7。"""
        g = {}
        for e in s.edges.values():
            if e["kind"] == "ref" and e["from"] in s.nodes and e["to"] in s.nodes: g.setdefault(e["from"], []).append(e["to"])
        for a in sorted(g):
            dist, order, path = {a: 0}, [a], {a: [a]}
            for x in order:
                for y in sorted(g.get(x, [])):
                    if y not in dist: dist[y] = dist[x] + 1; path[y] = path[x] + [y]; order.append(y)
            far = max(order, key=lambda x: dist[x])
            if dist[far] >= 2:
                s.checks["depth"].append({"node": a, "hops": dist[far], "files": len(order) - 1, "path": path[far]})
        reach = {}
        def closure(a):
            if a not in reach:
                seen, todo = set(), list(g.get(a, []))
                while todo:
                    x = todo.pop()
                    if x not in seen: seen.add(x); todo.extend(g.get(x, []))
                reach[a] = seen
            return reach[a]
        done = set()
        for a in sorted(g):
            if a in done or a not in closure(a): continue
            ring = sorted(x for x in closure(a) if a in closure(x))
            done.update(ring)
            s.checks["cycles"].append({"node": ring[0], "nodes": ring, "why": "这些文件互相引用成圈"})

    # ---------- hints ----------
    def full(s, x):
        if ":" in x or x == s.sid or x in s.known: return x
        x = x.split("#")[0]
        if x in s.text or x in s.dirs: return s.nid(x)
        return f"{s.sid}:{x}"

    def apply_hints(s):
        for k in s.layers:
            if k not in s.text and k not in s.dirs:
                s.checks["broken"].append({"node": s.sid, "at": "zoom.hints.json layers", "ref": k, "why": "层级覆盖指向的路径不存在"})
        for e in s.hints.get("edges", []):
            a, b = s.full(e["from"]), s.full(e["to"])
            for x in (a, b):
                if (x == s.sid or x.startswith(s.sid + ":")) and x not in s.nodes:
                    s.checks["broken"].append({"node": s.sid, "at": "zoom.hints.json", "ref": x, "why": "hints 里的节点不存在"})
            s.edges[(a, b, e["kind"])] = {k: v for k, v in {"from": a, "to": b, "kind": e["kind"], "source": e.get("source", "zoom.hints.json"),
                                                            "note": e.get("note")}.items() if v}
        iface = s.hints.get("interface")
        if iface is None and s.skill_desc:
            iface = [{"dir": "in", "label": "触发：" + short(s.skill_desc, 70), "via": "SKILL.md", "source": "SKILL.md § frontmatter"}]
        out = []
        for it in iface or []:
            it = dict(it)
            if it.get("via"): it["via"] = s.full(it["via"])
            out.append(it)
        return out

    def run(s):
        s.build(); s.defines(); s.scan(); s.duplicates(); s.accept(); s.structure()
        iface = s.apply_hints()
        s.depth()
        sysn = s.nodes[s.sid]
        return {
            "zoom": "2.0",
            "generated": {"by": "skill-starmap/tools/zoomgen.py", "at": datetime.date.today().isoformat(),
                          "from": sorted(s.text), "note": "生成文件，勿手改。改源文件或 zoom.hints.json 后重新运行 zoomgen。"},
            "system": {k: v for k, v in {"id": s.sid, "title": sysn["title"], "version": sysn.get("version"), "role": sysn.get("role"),
                                          "source": sysn.get("source"), "location": s.location}.items() if v},
            "interface": iface,
            "nodes": list(s.nodes.values()),
            "edges": list(s.edges.values()),
            "checks": s.checks,
        }

def resolve_root(r):
    """登记表里的 skills:<名字> 指已安装技能的同步目录（只读）。"""
    hits = sorted(pathlib.Path("/root/.claude/skills/synced").glob("*/" + r[7:]))
    return hits[0] if hits else None

def summary(m):
    c = m["checks"]
    return (f"{m['system']['id']}: {len(m['nodes'])} 节点 {len(m['edges'])} 边 · 断链 {len(c['broken'])} · 节对不上 {len(c['unresolved'])}"
            f" · 疑似复写 {len(c['duplicates'])} · 结构 {len(c['structure'])} · 提示 {len(c['info'])}"
            f" · 最深引用 {max((x['hops'] for x in c.get('depth', [])), default=1 if any(e['kind'] == 'ref' for e in m['edges']) else 0)} 跳"
            f" · 成圈 {len(c.get('cycles', []))} · 已确认复写 {len(c.get('accepted', []))}")

def build_all(reg_path):
    reg_path = pathlib.Path(reg_path); base = reg_path.parent
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    out_dir = base / reg.get("out", "manifests")
    ids = [e["id"] for e in reg["systems"]]
    bad = 0
    for e in reg["systems"]:
        root = resolve_root(e["root"]) if e["root"].startswith("skills:") else (base / e["root"]).resolve()
        if not root or not root.exists(): print(f"{e['id']}: 找不到源目录 {e['root']}"); bad += 1; continue
        hints = base / e["hints"] if e.get("hints") else None
        skill = e.get("skill", e["root"].startswith("skills:"))
        m = Gen(root, e["id"], hints, ids, e.get("exclude", []), e.get("location") or e["root"], skill).run()
        (out_dir / f"{e['id']}.zoom.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        print(summary(m))
        bad += len(m["checks"]["broken"]) + len(m["checks"]["structure"])
    write_index(out_dir)
    return bad

def write_index(d):
    d = pathlib.Path(d)
    items = []
    for p in sorted(d.glob("*.zoom.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        items.append({"file": p.name, "id": m["system"]["id"], "title": m["system"]["title"], "zoom": m.get("zoom")})
    (d / "index.json").write_text(json.dumps({"zoom": "2.0", "manifests": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"index.json：{len(items)} 份清单")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?")
    ap.add_argument("--id"); ap.add_argument("--hints"); ap.add_argument("--out"); ap.add_argument("--location")
    ap.add_argument("--known", default="", help="其他系统 id，用逗号分隔；正文点名它们时连一条跨星系的边")
    ap.add_argument("--exclude", default="", help="跳过的子目录，用逗号分隔")
    ap.add_argument("--skill", action="store_true", help="根目录是 skill 文件夹（必须有 SKILL.md）")
    ap.add_argument("--index"); ap.add_argument("--all"); ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    if a.index: write_index(a.index); sys.exit(0)
    if a.all: sys.exit(1 if build_all(a.all) and a.strict else 0)
    g = Gen(a.root, a.id, a.hints, [k for k in a.known.split(",") if k], [x for x in a.exclude.split(",") if x], a.location, a.skill)
    m = g.run()
    out = pathlib.Path(a.out) if a.out else g.root / "zoom.json"
    out.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(summary(m) + f" → {out}")
    for k in ("broken", "structure", "unresolved", "duplicates", "info"):
        for x in m["checks"][k][:12]: print(f"  [{k}] {x}")
    sys.exit(1 if a.strict and (m["checks"]["broken"] or m["checks"]["structure"]) else 0)
