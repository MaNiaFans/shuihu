#!/usr/bin/env python3
"""程序化核验,不依赖模型自评。

子命令:
  scenes  <scenes.json> --ws WS     核验场景抽取 JSON 里每条 quote 是否真在其场景范围内
  dossier <dossier.md>  --ws WS     核验档案中每个引用标记 + 分层标签是否合规

引用标记格式(档案里):  〔ch007-s03：「原文片段」〕
引文规则: 归一化(去空白与标点)后必须是该场景原文的连续子串;
          引文中可用「……」表示省略,每段至少 4 字。
退出码: 0 全通过; 1 有失败(失败项逐条打印,供打回重写)。
"""
import argparse, json, re, sys
from pathlib import Path

PUNCT = re.compile(r"[\s\u3000，。、；：？！“”‘’「」『』（）()《》〈〉—…·,.;:?!\"'\-－]+")


def norm(s):
    return PUNCT.sub("", s)


REF = re.compile(r"〔(ch\d{3}-s\d{2})[:：]\s*「([^」]+)」〕")
REF_ANY = re.compile(r"〔(ch\d{3}-s\d{2})")
TAG = re.compile(r"^\s*(?:[-*]|\d+[.、])?\s*\[(事实|推断|评点|猜想)\]")
_cache = {}


def load_scene_text(ws, scene_id):
    ch = int(scene_id[2:5])
    f = ws / "data" / "scenes" / f"ch{ch:03d}.json"
    u = ws / "data" / "units" / f"ch{ch:03d}.json"
    if not f.exists() or not u.exists():
        return None
    if ch not in _cache:
        _cache[ch] = (json.loads(f.read_text("utf-8")), json.loads(u.read_text("utf-8")))
    scenes, units = _cache[ch]
    for s in scenes["scenes"]:
        if s["scene_id"] == scene_id:
            a, b = s["unit_range"]
            return "".join(x["text"] for x in units["units"] if a <= x["id"] <= b)
    return None


def quote_in(quote, text):
    segs = [norm(x) for x in re.split(r"……+|\.\.\.+", quote)]
    segs = [x for x in segs if x]
    if not segs:
        return False, "引文为空"
    ntext = norm(text)
    for x in segs:
        if len(x) < 4 and len(segs) > 1:
            return False, f"省略号分段过短: {x}"
        if x not in ntext:
            return False, f"原文中找不到: {x[:30]}"
    return True, ""


def cmd_scenes(a):
    ws = Path(a.ws)
    data = json.loads(Path(a.file).read_text("utf-8"))
    bad = []
    for s in data["scenes"]:
        text = load_scene_text(ws, s["scene_id"])
        if text is None:
            bad.append((s["scene_id"], "场景范围无法定位原文(检查 unit_range 与文件落盘位置)"))
            continue

        def chk(q, where):
            if not q:
                return
            ok, why = quote_in(q, text)
            if not ok:
                bad.append((s["scene_id"], f"{where}: {why}"))

        for c in s.get("characters", []):
            who = c.get("canonical")
            for x in c.get("actions", []):
                chk(x.get("quote"), f"{who}.action")
            for x in c.get("speech", []):
                chk(x.get("quote"), f"{who}.speech")
            chk(c.get("presence_quote"), f"{who}.presence")
        for key in ("relation_events", "anomalies", "foreshadow", "absent_but_relevant"):
            for r in s.get(key, []):
                chk(r.get("quote"), key)
    report(bad, "场景抽取")


def cmd_dossier(a):
    ws = Path(a.ws)
    lines = Path(a.file).read_text("utf-8").splitlines()
    bad = []
    for i, ln in enumerate(lines, 1):
        refs = REF.findall(ln)
        if len(REF_ANY.findall(ln)) != len(refs):
            bad.append((f"L{i}", "引用标记格式错误,应为〔chNNN-sNN：「引文」〕"))
        for sid, q in refs:
            text = load_scene_text(ws, sid)
            if text is None:
                bad.append((f"L{i}", f"{sid} 不存在"))
                continue
            ok, why = quote_in(q, text)
            if not ok:
                bad.append((f"L{i}", f"{sid} 引文不实: {why}"))
        m = TAG.match(ln)
        if m:
            tag = m.group(1)
            if tag in ("事实", "推断") and not refs:
                bad.append((f"L{i}", f"[{tag}] 没有任何有效引用"))
            if tag == "推断" and "依据" not in ln:
                bad.append((f"L{i}", "[推断] 须写明「依据」哪几处原文及推理"))
            if tag == "评点" and "出处" not in ln:
                bad.append((f"L{i}", "[评点] 须写明「出处」(批语版本与回目)"))
            if tag == "猜想" and "另一种读法" not in ln:
                bad.append((f"L{i}", "[猜想] 须附「另一种读法」"))
    report(bad, "档案")


def report(bad, name):
    if not bad:
        print(f"[通过] {name}核验全部通过")
        sys.exit(0)
    print(f"[失败] {name}核验发现 {len(bad)} 处问题:")
    for where, why in bad:
        print(f"  - {where}: {why}")
    sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n, fn in (("scenes", cmd_scenes), ("dossier", cmd_dossier)):
        p = sub.add_parser(n)
        p.add_argument("file")
        p.add_argument("--ws", required=True)
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)
