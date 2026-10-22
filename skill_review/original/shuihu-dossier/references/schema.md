# 数据格式规范

所有角色(抽取员、审稿员、撰写员)都按这里的格式读写文件。格式不要自行变通,脚本依赖这些字段名。

## 目录

1. 工作区布局
2. 人物库 characters.json
3. 场景文件 scenes/chNNN.json
4. 审稿意见 reviews/chNNN.review.json
5. 引用标记(档案里用)

---

## 1. 工作区布局

```
workspace/
├── text/chNNN.txt              底本原文(只读,不得改动)
├── data/
│   ├── units/chNNN.json        句段编号(split_text.py 生成,只读)
│   ├── characters.json         人物库(别名表)
│   ├── scenes/chNNN.json       场景抽取结果(通过审稿后才算定稿)
│   ├── reviews/                审稿意见与历轮记录
│   └── bundles/<人物>.json     collect_character.py 聚合结果
└── dossiers/<人物>.md          最终档案
```

## 2. 人物库 characters.json

```json
[
  {
    "canonical": "杨志",
    "aliases": ["青面兽", "杨制使", "杨提辖"],
    "ambiguous_aliases": [],
    "faction": "官军→二龙山→梁山",
    "first_chapter": 11,
    "notes": "消歧规则:……"
  }
]
```

- `canonical` 全库唯一,用底本里最常用的名字。
- 凡是被两个以上人物共用的称呼(同名、同姓同辈、泛称如「三郎」「教头」「提辖」)写进 `ambiguous_aliases`,脚本不会拿它们做全文检索;抽取员遇到时必须靠上下文判断并写明依据。
- 化名、假身份单独写在 `notes`,例如「某回中某人自称某某,实为谁」。
- 原文没有名字的人物(酒保、庄客、小喽啰、某差人)也要建档,`canonical` 写成 `无名·<场景描述>`,例如 `无名·酒店主人(ch005)`,便于被遮蔽的配角可检索。

## 3. 场景文件 scenes/chNNN.json

```json
{
  "chapter": 7,
  "scenes": [
    {
      "scene_id": "ch007-s01",
      "unit_range": [1, 14],
      "location": "东京 大相国寺菜园",
      "time": "原文给出的时间线索,没有就写 null",
      "summary": "一两句话,只写原文发生了什么,不含评价",
      "characters": [
        {
          "name_in_text": "原文里实际出现的称呼",
          "canonical": "人物库里的 canonical",
          "presence": "speaks | acts | mentioned | bystander | inferred_present",
          "presence_quote": "证明在场/被提及的原文片段(inferred_present 必填并写 inferred_reason)",
          "inferred_reason": "仅 inferred_present 需要:为何断定此人在场",
          "actions": [{"what": "他做了什么", "quote": "原文片段"}],
          "speech":  [{"quote": "他说的原话"}]
        }
      ],
      "relation_events": [
        {"from": "A", "to": "B",
         "type": "施恩|结怨|欺骗|救助|举荐|背叛|加害|结义|投靠|试探|隐瞒|其他",
         "what": "一句话", "quote": "原文片段"}
      ],
      "anomalies": [
        {"kind": "称呼变化|细节突兀|前后矛盾|物件重现|叙述语气|其他",
         "note": "哪里反常、可能与什么有关(仅描述,不下结论)", "quote": "原文片段"}
      ],
      "foreshadow": [
        {"direction": "plants|pays_off", "note": "埋下什么/回应了哪处",
         "ref": "回应的前文场景号,没有则 null", "quote": "原文片段"}
      ],
      "absent_but_relevant": [
        {"canonical": "不在场但此场景的事与他有关的人物", "why": "怎么有关",
         "quote": "原文片段"}
      ]
    }
  ]
}
```

硬性约束:

- `unit_range` 是 units 文件里的句段编号区间(含两端)。同一回的场景范围不得重叠、不得留下超过 3 个句段的空洞。
- 每个 `quote` 必须是该场景原文的连续片段;允许用「……」表示省略。脚本 `verify.py scenes` 会逐条核对。
- `presence` 含义:
  - `speaks` 原文有他的台词
  - `acts` 原文写了他的动作但无台词
  - `mentioned` 只是被别人提到,人不在场
  - `bystander` 原文明写他在场(如「众人」中被点名者、「一旁立着」),但无台词无动作
  - `inferred_present` 原文没点名,但按上下文必然在场(如「两个公人」「庄客」「小喽啰」)
- 没有内容的数组写 `[]`,不要省略字段,不要编造内容凑数。

## 4. 审稿意见 reviews/chNNN.review.json

```json
{
  "chapter": 7,
  "round": 1,
  "script_gate": "pass | fail",
  "verdict": "pass | revise",
  "blind_read_diff": {
    "missed_characters": [{"scene_id": "ch007-s02", "who": "...", "evidence_quote": "..."}],
    "wrong_presence": [{"scene_id": "...", "who": "...", "given": "acts", "should_be": "bystander", "why": "..."}]
  },
  "issues": [
    {"scene_id": "ch007-s03", "severity": "must|should|nit",
     "type": "漏人|错归属|引文不支持|混入非底本内容|过度解读|场景切分|别名错误|其他",
     "detail": "具体问题", "fix_hint": "怎么改"}
  ],
  "summary": "三句以内"
}
```

`verdict = pass` 的条件:`script_gate` 为 pass,且没有 `must` 级问题。

## 5. 引用标记(档案里用)

```
〔ch007-s03：「原文片段」〕
```

- 编号取自场景文件,引文取自该场景原文,省略用「……」。
- 一句话可带多个标记。
- 引文要短而准(8–40 字为宜),只摘最能支撑该断言的那一句,不要整段搬。
