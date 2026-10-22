#!/usr/bin/env python3
"""把底本切成「回」,并把每回切成带编号的句段(unit)。

用法:
  python split_text.py --src 水浒传.txt --ws workspace     # 单文件,按「第X回」标题切
  python split_text.py --src text_dir/ --ws workspace      # 目录内已是 ch001.txt 之类

产出:
  workspace/text/chNNN.txt            每回原文
  workspace/data/units/chNNN.json     {"chapter":N,"title":"...","units":[{"id":1,"text":"..."}]}
句段编号是后续「场景范围」和「引文核验」的坐标,切分后不要再改动。
"""
import argparse, json, re, sys
from pathlib import Path

CN = "零〇一二三四五六七八九十百"
HEAD = re.compile(rf"^\s*第[{CN}]+回[ 　:：]?.*$", re.M)


def cn2int(s):
    d = {c: i for i, c in enumerate("零一二三四五六七八九")}
    d["〇"] = 0
    if "百" in s:
        h, _, r = s.partition("百")
        n = (d[h] if h else 1) * 100
        r = r.lstrip("零〇")
        return n + (cn2int(r) if r else 0)
    if "十" in s:
        t, _, r = s.partition("十")
        return (d[t] if t else 1) * 10 + (d[r] if r else 0)
    return d[s] if len(s) == 1 else int("".join(str(d[c]) for c in s))


def split_units(text, max_len=160):
    units = []
    for para in [p.strip() for p in text.splitlines() if p.strip()]:
        if len(para) <= max_len:
            units.append(para)
            continue
        # 长段按句末标点切,再合并到不超过 max_len
        parts = re.findall(r".+?(?:[。！？；]|$)", para)
        buf = ""
        for s in parts:
            if buf and len(buf) + len(s) > max_len:
                units.append(buf)
                buf = ""
            buf += s
        if buf:
            units.append(buf)
    return [{"id": i + 1, "text": u} for i, u in enumerate(units)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--ws", required=True)
    ap.add_argument("--max-len", type=int, default=160)
    a = ap.parse_args()
    ws = Path(a.ws)
    (ws / "text").mkdir(parents=True, exist_ok=True)
    (ws / "data" / "units").mkdir(parents=True, exist_ok=True)
    src = Path(a.src)
    chapters = {}
    if src.is_dir():
        for f in sorted(src.glob("ch*.txt")):
            n = int(re.search(r"(\d+)", f.stem).group(1))
            chapters[n] = f.read_text(encoding="utf-8")
    else:
        raw = src.read_text(encoding="utf-8")
        ms = list(HEAD.finditer(raw))
        if not ms:
            sys.exit("没找到「第X回」标题,请检查底本格式")
        for i, m in enumerate(ms):
            end = ms[i + 1].start() if i + 1 < len(ms) else len(raw)
            num = cn2int(re.search(rf"第([{CN}]+)回", m.group()).group(1))
            if num in chapters:
                print(f"警告: 回目 {num} 重复出现,已覆盖(检查是否有目录混入)", file=sys.stderr)
            chapters[num] = raw[m.start():end]
    for n, body in sorted(chapters.items()):
        (ws / "text" / f"ch{n:03d}.txt").write_text(body, encoding="utf-8")
        lines = [l for l in body.splitlines() if l.strip()]
        title = lines[0].strip() if lines else ""
        units = split_units("\n".join(lines[1:]), a.max_len)
        (ws / "data" / "units" / f"ch{n:03d}.json").write_text(
            json.dumps({"chapter": n, "title": title, "units": units}, ensure_ascii=False, indent=1),
            encoding="utf-8")
    print(f"完成: {len(chapters)} 回 -> {ws}")


if __name__ == "__main__":
    main()
