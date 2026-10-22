#!/usr/bin/env python3
"""按人物聚合。别名归一 -> 找章节 -> 汇总场景/关系/缺席影响。

子命令:
  resolve <名字> --ws WS   别名归一,打印 canonical 与全部别名;重名/歧义时列出候选
  hits    <名字> --ws WS   在原文里按别名全文检索,列出命中章回,并标出尚未抽取的回
  bundle  <名字> --ws WS   汇总已抽取的场景,输出 data/bundles/<canonical>.json

人物库: WS/data/characters.json
  [{"canonical":"杨志","aliases":["青面兽","杨制使"],"ambiguous_aliases":[],"faction":"","notes":""}]
"""
import argparse, json, sys
from collections import Counter, defaultdict
from pathlib import Path


def load_chars(ws):
    f = Path(ws) / "data" / "characters.json"
    if not f.exists():
        sys.exit(f"缺少人物库 {f}")
    return json.loads(f.read_text("utf-8"))


def resolve(chars, name):
    hit = [c for c in chars if name == c["canonical"] or name in c.get("aliases", [])]
    if not hit:  # 精确未中,退而求其次做子串匹配,结果必须交给人/模型确认
        hit = [c for c in chars if name in c["canonical"] or any(name in x for x in c.get("aliases", []))]
    return hit


def must_one(chars, name):
    h = resolve(chars, name)
    if not h:
        sys.exit(f"人物库中找不到「{name}」,请先补充 characters.json")
    if len(h) > 1:
        sys.exit("歧义,候选: " + "、".join(c["canonical"] for c in h) + "  请用 canonical 全名重试")
    return h[0]


def alias_set(chars, c):
    """用于全文检索的称呼:剔除被多人共用或标为歧义的称呼,避免污染。"""
    owners = defaultdict(set)
    for x in chars:
        for n in [x["canonical"], *x.get("aliases", [])]:
            owners[n].add(x["canonical"])
    return [n for n in [c["canonical"], *c.get("aliases", [])]
            if n not in c.get("ambiguous_aliases", []) and len(owners[n]) == 1]


def cmd_resolve(a):
    for c in resolve(load_chars(a.ws), a.name):
        print(json.dumps(c, ensure_ascii=False, indent=1))


def cmd_hits(a):
    chars = load_chars(a.ws)
    c = must_one(chars, a.name)
    names = alias_set(chars, c)
    res = []
    for f in sorted((Path(a.ws) / "text").glob("ch*.txt")):
        t = f.read_text("utf-8")
        cnt = {n: t.count(n) for n in names if n in t}
        if cnt:
            res.append((int(f.stem[2:]), sum(cnt.values()), cnt))
    print(f"{c['canonical']} 使用的检索名: {names}")
    for ch, tot, cnt in res:
        print(f"ch{ch:03d}  共{tot}处  {cnt}")
    sd = Path(a.ws) / "data" / "scenes"
    done = {int(p.stem[2:]) for p in sd.glob("ch*.json")} if sd.exists() else set()
    print("\n命中章回:", [ch for ch, _, _ in res])
    print("尚未抽取:", [ch for ch, _, _ in res if ch not in done])


def cmd_bundle(a):
    ws = Path(a.ws)
    chars = load_chars(ws)
    c = must_one(chars, a.name)
    canon = c["canonical"]
    names = {canon, *c.get("aliases", [])}
    timeline, rels, absent, anomalies, co = [], [], [], [], Counter()
    for f in sorted((ws / "data" / "scenes").glob("ch*.json")):
        for s in json.loads(f.read_text("utf-8"))["scenes"]:
            me = [x for x in s.get("characters", []) if x.get("canonical") == canon]
            if me:
                others = [{"canonical": x.get("canonical"), "presence": x.get("presence")}
                          for x in s["characters"] if x.get("canonical") != canon]
                timeline.append({"scene_id": s["scene_id"], "location": s.get("location"),
                                 "summary": s.get("summary"), "me": me[0], "others": others})
                for o in others:
                    co[o["canonical"]] += 1
                anomalies += [{**r, "scene_id": s["scene_id"]} for r in s.get("anomalies", [])]
            for r in s.get("relation_events", []):
                if canon in (r.get("from"), r.get("to")):
                    rels.append({**r, "scene_id": s["scene_id"]})
            for r in s.get("absent_but_relevant", []):
                if r.get("canonical") == canon or r.get("name") in names:
                    absent.append({**r, "scene_id": s["scene_id"], "scene_summary": s.get("summary")})
    out = {"canonical": canon, "profile": c, "timeline": timeline, "relation_events": rels,
           "absent_but_relevant": absent, "scene_anomalies": anomalies, "counterparts": co.most_common()}
    (ws / "data" / "bundles").mkdir(parents=True, exist_ok=True)
    p = ws / "data" / "bundles" / f"{canon}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print(f"{canon}: 场景 {len(timeline)} | 关系事件 {len(rels)} | 缺席影响 {len(absent)} | 对手方 {len(co)} -> {p}")
    print("交集最多:", "、".join(f"{n}({k})" for n, k in co.most_common(15)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n, fn in (("resolve", cmd_resolve), ("hits", cmd_hits), ("bundle", cmd_bundle)):
        p = sub.add_parser(n)
        p.add_argument("name")
        p.add_argument("--ws", required=True)
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)
