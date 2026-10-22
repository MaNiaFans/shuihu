"""Reproduce selected behaviors of the supplied skill without changing its files."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "original" / "shuihu-dossier"
SCRIPTS = SKILL / "scripts"
BOOK = ROOT.parent / "水浒传 (施耐庵  罗贯中).txt"
CHECKS = ROOT / "checks"
CHECKS.mkdir(exist_ok=True)
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run(script, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", env=ENV,
        timeout=60,
    )
    return {"exit_code": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


results = {}
real_ws = CHECKS / "real_text_workspace"
split_result = run("split_text.py", "--src", BOOK, "--ws", real_ws)
if split_result["exit_code"]:
    raise RuntimeError(split_result)
chapters = sorted((real_ws / "text").glob("ch*.txt"))
ch100 = (real_ws / "text" / "ch100.txt").read_text("utf-8")
ch29_units = json.loads((real_ws / "data" / "units" / "ch029.json").read_text("utf-8"))
results["real_book_split"] = {
    "exit_code": split_result["exit_code"],
    "chapter_count": len(chapters),
    "duplicate_heading_warnings": split_result["stderr"].count("重复出现"),
    "appendix_1_in_ch100": "附录一 容与堂刻本书前四篇评论文字" in ch100,
    "appendix_2_in_ch100": "附录二 《忠义水浒传》叙" in ch100,
    "modern_notes_in_ch029_units": [u for u in ch29_units["units"] if u["text"].startswith("[1]")][:1],
}

spec = importlib.util.spec_from_file_location("reviewed_verify", SCRIPTS / "verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
sample = "甲方先行。乙方后至。"
results["quote_matching"] = {
    "valid_order_control": verify.quote_in("甲方先行……乙方后至", sample),
    "reversed_order_should_fail": verify.quote_in("乙方后至……甲方先行", sample),
    "fabricated_text_control": verify.quote_in("这里没有出现", sample),
}

ws = CHECKS / "synthetic_workspace"
save(ws / "data" / "units" / "ch001.json", {
    "chapter": 1, "title": "合成测试，不是水浒原文",
    "units": [{"id": 1, "text": "甲方先行。"}, {"id": 2, "text": "乙方后至。"}, {"id": 3, "text": "丙方送信。"}],
})


def scene(sid, interval):
    return {
        "scene_id": sid, "unit_range": interval, "location": "合成测试地点", "time": "昨日",
        "summary": "合成测试记录", "characters": [], "relation_events": [],
        "anomalies": [], "foreshadow": [], "absent_but_relevant": [],
    }


scene_path = ws / "data" / "scenes" / "ch001.json"
valid = scene("ch001-s01", [1, 3])
valid["characters"] = [{
    "canonical": "甲方", "name_in_text": "甲方", "presence": "acts", "presence_quote": "甲方先行",
    "actions": [{"what": "先行", "quote": "甲方先行"}], "speech": [],
}]
save(scene_path, {"chapter": 1, "scenes": [valid]})
results["valid_scene_control"] = run("verify.py", "scenes", scene_path, "--ws", ws)
valid_doc = CHECKS / "valid_dossier_control.md"
valid_doc.write_text("- [事实] 甲方先行。〔ch001-s01：「甲方先行」〕\n", encoding="utf-8")
results["valid_dossier_control"] = run("verify.py", "dossier", valid_doc, "--ws", ws)

missing = scene("ch001-s01", [1, 3])
missing["characters"] = [{
    "canonical": "甲方", "name_in_text": "甲方", "presence": "acts", "presence_quote": "",
    "actions": [{"what": "无依据的动作", "quote": ""}], "speech": [],
}]
save(scene_path, {"chapter": 1, "scenes": [missing]})
results["missing_required_quote"] = run("verify.py", "scenes", scene_path, "--ws", ws)

overlap = [scene("ch001-s01", [1, 2]), scene("ch001-s02", [2, 3])]
save(scene_path, {"chapter": 1, "scenes": overlap})
results["overlapping_scene_ranges"] = run("verify.py", "scenes", scene_path, "--ws", ws)

outside = scene("ch001-s01", [500, 600])
save(scene_path, {"chapter": 1, "scenes": [outside]})
results["out_of_bounds_empty_scene"] = run("verify.py", "scenes", scene_path, "--ws", ws)

doc_cases = {
    "bare_assertion_without_tag": "甲方飞天成仙。\n",
    "template_timeline_missing_citation": "- ch001-s01 · 某地 · [事实] 甲方飞天成仙。\n",
    "template_interpretation_missing_evidence": "- 【多视角对读】[推断] 甲方必然早有预谋。\n",
    "proper_tag_missing_citation_control": "- [事实] 甲方飞天成仙。\n",
}
for key, text in doc_cases.items():
    path = CHECKS / f"{key}.md"
    path.write_text(text, encoding="utf-8")
    results[key] = run("verify.py", "dossier", path, "--ws", ws)

save(ws / "data" / "characters.json", [
    {"canonical": n, "aliases": [], "ambiguous_aliases": []} for n in ("甲方", "乙方", "丙方")
])
first = scene("ch001-s01", [1, 2])
first["characters"] = [
    {"canonical": "甲方", "presence": "acts", "actions": [{"what": "先行", "quote": "甲方先行"}], "speech": []},
    {"canonical": "乙方", "presence": "mentioned", "actions": [], "speech": []},
]
first["foreshadow"] = [{"direction": "plants", "note": "合成的待核记录", "ref": None, "quote": "甲方先行"}]
second = scene("ch001-s02", [3, 3])
second["characters"] = [{"canonical": "丙方", "presence": "acts", "actions": [], "speech": []}]
second["relation_events"] = [{"from": "丙方", "to": "甲方", "type": "其他", "what": "测试的场外联系", "quote": "丙方送信"}]
second["absent_but_relevant"] = [{"canonical": "甲方", "why": "测试目标", "quote": "丙方送信"}]
save(scene_path, {"chapter": 1, "scenes": [first, second]})
save(ws / "data" / "reviews" / "ch001.review.json", {
    "chapter": 1, "round": 1, "script_gate": "pass", "verdict": "revise",
    "issues": [{"severity": "must", "detail": "合成的未通过审稿记录"}],
})
bundle_run = run("collect_character.py", "bundle", "甲方", "--ws", ws)
bundle = json.loads((ws / "data" / "bundles" / "甲方.json").read_text("utf-8"))
results["bundle_with_failed_review"] = {
    "command": bundle_run, "review_verdict": "revise", "timeline_count": len(bundle["timeline"]),
    "counterparts": bundle["counterparts"], "absent_related_person": "丙方",
    "timeline_keeps_time": "time" in bundle["timeline"][0],
    "bundle_keeps_foreshadow": "foreshadow" in bundle,
    "bundle_records_review_status": any("review" in k or "status" in k for k in bundle),
}

save(ROOT / "results.json", results)
print(json.dumps(results, ensure_ascii=False, indent=2))
