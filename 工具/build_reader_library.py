"""从有效研究生成只读查阅入口；不生成文学判断，不改原章节。"""
from pathlib import Path
import argparse
import collections
import hashlib
import importlib.util
import json
import os
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '读者版'


def read(p):
    return Path(p).read_text(encoding='utf-8-sig')


def save(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + '\n', encoding='utf-8')


def rel(target, parent):
    return os.path.relpath(target, parent).replace('\\', '/')


def link(label, target, parent, fragment=''):
    return f'[{label}]({rel(target, parent)}{fragment})'


def fileinfo(p):
    p = Path(p)
    return {'path': p.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'bytes': p.stat().st_size}


def check():
    """只核机械一致性，内容是否成立仍由独立复审判断。"""
    data = OUT / '资料'
    chapters = json.loads(read(data / '章节索引.json'))
    people = json.loads(read(data / '人物索引.json'))
    questions = json.loads(read(data / '问题索引.json'))
    clues = json.loads(read(data / '线索索引.json'))
    manifest = json.loads(read(data / '来源清单.json'))
    assert [c['chapter'] for c in chapters] == list(range(1, 101))
    assert len(people) == len({p['name'] for p in people}) == 108
    assert len(questions) == len({q['id'] for q in questions}) == 178
    assert len(clues) == len({c['id'] for c in clues}) == 1990
    errors = []
    versions = {v['path']: v for c in chapters for v in c['versions']}
    versions.update({v['path']: v for v in manifest['inputs']})
    adopted = data / '成稿版本.json'
    if adopted.is_file():
        adopted = json.loads(read(adopted))
        versions.update({v['path']: v for v in adopted['articles']})
        versions.update({v['path']: v for v in adopted['navigation']})
        versions.update({v['path']: v for v in adopted['evidence']})
    for name, expected in versions.items():
        p = ROOT / name
        actual = fileinfo(p) if p.is_file() else {}
        if any(actual.get(k) != expected[k] for k in ('path', 'sha256', 'bytes')):
            errors.append(f'来源版本变化：{name}')
    count = 0
    pages = sorted(OUT.rglob('*.md'))
    starts = {c['chapter']: c['source_start'] for c in chapters}
    pattern = re.compile(r'\[([^\]]+)\]\((<[^>]+>|[^\s()]+(?:\([^)]*\)[^\s()]*)*)\)')
    for page in pages:
        fenced = False
        for line in read(page).splitlines():
            if re.match(r'^\s*(```|~~~)', line):
                fenced = not fenced
                continue
            if fenced:
                continue
            for m in pattern.finditer(line):
                target = unquote(m.group(2).strip('<>'))
                if '://' in target or target.startswith(('mailto:', 'data:')):
                    continue
                name, _, fragment = target.partition('#')
                p = (page.parent / name).resolve() if name else page
                count += 1
                if not p.is_file():
                    errors.append(f'{page.relative_to(ROOT)}：文件不存在 {target}')
                elif re.fullmatch(r'L\d+(?:-L?\d+)?', fragment):
                    bounds = [int(n) for n in re.findall(r'\d+', fragment)]
                    if min(bounds) < 1 or max(bounds) > len(read(p).splitlines()):
                        errors.append(f'{page.relative_to(ROOT)}：行号越界 {target}')
                citation = re.search(r'本L([\d、—–\-]+)／原L([\d、—–\-]+)', m.group(1))
                chapter = re.search(r'第(\d{3})回/00_正文\.txt', name.replace('\\', '/'))
                if citation and chapter:
                    local, original = ([int(x) for x in re.findall(r'\d+', citation.group(i))]
                                       for i in (1, 2))
                    expected = [starts[int(chapter.group(1))] + n - 1 for n in local]
                    if original != expected:
                        errors.append(f'{page.relative_to(ROOT)}：本L/原L换算不符 {m.group(1)}')
    print(f'机械核查：100回、108人、178问题、1990线索；'
          f'{len(versions)}个来源版本，{len(pages)}页，{count}个本地文件/行号链接。')
    if errors:
        raise SystemExit('\n'.join(errors))
    print('版本与文件/行号链接有效；此结果不代替内容复审。')


def main():
    spec = importlib.util.spec_from_file_location('fast_reader_inputs', ROOT / '工具/fast_tools.py')
    fast = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fast)
    rows = {}
    for line in read(ROOT / 'README.md').splitlines():
        if not line.startswith('|'):
            continue
        m = re.search(r'(?:章节/第|阅读成果/第)(\d{3})', line)
        if m:
            cells = [x.strip() for x in re.split(r'(?<!\\)\|', line)[1:-1]]
            if len(cells) == 3:
                rows[int(m.group(1))] = cells[1:]
    assert set(rows) == set(range(1, 101)), '首页应有100回有效导航'
    source = read(ROOT / '水浒传 (施耐庵  罗贯中).txt').replace('\r\n', '\n')
    chapters = []
    for n in range(1, 101):
        d = ROOT / '章节' / f'第{n:03d}回'
        raw = d / '00_正文.txt'
        body = read(raw).replace('\r\n', '\n')
        needle = body.rstrip('\n')
        start = source.find(needle)
        assert start >= 0, f'{n}正文无法与源书定位'
        startline = source[:start].count('\n') + 1
        original = d / ('04_修订定稿_接任R02.md' if n == 51 else '04_修订定稿.md')
        followup = d / ('05_追踪与交接_接任R02.md' if n == 51 else '05_追踪与交接.md')
        reader = ROOT / '阅读成果' / f'第{n:03d}回.md' if n <= 16 else original
        assert reader.is_file() and original.is_file()
        if n >= 71:
            assert fast.accepted(n), f'{n}缺快速流程有效验收入口'
        elif n > 1:
            record = d / '07_执行与验收.md'
            assert record.is_file() and any(d.glob('03*.md')), f'{n}缺旧验收依据'
            assert re.search(r'验收通过|核验通过|G1—G7正式验收', read(record)), f'{n}待核旧验收入口'
        chapters.append({'chapter': n, 'title': body.splitlines()[0].strip(),
                         'reading': reader.relative_to(ROOT).as_posix(),
                         'research': original.relative_to(ROOT).as_posix(),
                         'followup': followup.relative_to(ROOT).as_posix(),
                         'raw': raw.relative_to(ROOT).as_posix(),
                         'source_start': startline, 'local_lines': len(body.splitlines()),
                         'summary': rows[n][0], 'reading_focus': rows[n][1],
                         'basis': '旧试读及已有阅读版' if n == 1 else '有效验收稿',
                         'versions': [fileinfo(p) for p in (raw, original, reader, followup)
                                      if p.is_file()]})
    data = OUT / '资料'
    data.mkdir(parents=True, exist_ok=True)
    save(data / '章节索引.json', json.dumps(chapters, ensure_ascii=False, indent=2))

    dest = OUT / '05_百回阅读' / '00_百回目录.md'
    text = ['# 水浒百回阅读目录', '',
            '按章回连续阅读可从这里进入。第一至十六回链接到已核阅读版，第十七至一百回链接到有效成稿；每回另附原文与追踪入口。', '',
            '第一回保留旧试读的真实限度，其余回目沿用现有有效验收；这里的编排不重做或升级原阅读记录。', '',
            '| 回目 | 本回经过 | 回查 |', '| --- | --- | --- |']
    for c in chapters:
        n = c['chapter']
        r = link(c['title'], ROOT / c['reading'], dest.parent)
        rawlink = link('原文', ROOT / c['raw'], dest.parent)
        follow = link('追踪', ROOT / c['followup'], dest.parent)
        text.append(f'| {r} | {c["summary"]} | {rawlink} · {follow} |')
    save(dest, '\n'.join(text))

    # 名册以第99回已核分类表为名单，以第71回实际星表配绰号、星名。
    names = {}
    for line in read(ROOT / '章节/第099回/04_修订定稿.md').splitlines():
        cells = [x.strip() for x in line.split('|')[1:-1]]
        if len(cells) != 3 or not cells[1].isdigit():
            continue
        for name in re.sub(r'正将|偏将', '', cells[2]).replace('；', '、').split('、'):
            name = name.strip()
            assert name and name not in names, name
            names[name] = cells[0]
    assert len(names) == 108
    stars = []
    for i, line in enumerate(read(ROOT / '章节/第071回/00_正文.txt').splitlines(), 1):
        if not 20 <= i <= 142:
            continue
        hits = list(re.finditer(r'[天地][\u4e00-\u9fff]{1,2}星', line))
        for j, hit in enumerate(hits):
            tail = line[hit.end():hits[j + 1].start() if j + 1 < len(hits) else len(line)].strip()
            found = [name for name in names if tail.endswith(name)]
            if found:
                name = max(found, key=len)
                stars.append({'name': name, 'alias': tail[:-len(name)].strip(),
                              'star': hit.group(), 'star_line': i, 'class99': names[name]})
    assert len(stars) == 108 and len({x['name'] for x in stars}) == 108, len(stars)
    rawtexts = {c['chapter']: read(ROOT / c['raw']) for c in chapters}
    dest = OUT / '06_查阅索引' / '01_一百零八人查阅.md'
    text = ['# 一百零八人查阅', '',
            '姓名、绰号与星名据第七十一回星表；分类据第九十九回已核名册。第九十九回的病故分类包含预叙，不代表同日死亡；二十七人朝觐也不是全书最终存活人数。', '',
            '“姓名出现回目”只作原文检索导航，含名单、转述和典故等字面命中；须读原段判断是否在场，不能据此自动认定身份或关系。正文“侯建”与星表“侯健”另留字形差异。主要人物的连贯分析见人物深读，各人完整行迹仍可回到百回成稿。', '',
            '| 姓名 | 绰号与星名 | 第99回名册分类 | 姓名出现回目 |', '| --- | --- | --- | --- |']
    for person in stars:
        name = person['name']
        occurrences = []
        for n, s in rawtexts.items():
            if name in s or (name == '侯健' and '侯建' in s):
                occurrences.append(n)
        person['literal_chapters'] = occurrences
        parts = [link(f'{n:03d}', ROOT / chapters[n - 1]['reading'], dest.parent) for n in occurrences]
        starlink = link(person['star'], ROOT / '章节/第071回/00_正文.txt', dest.parent,
                        '#L' + str(person['star_line']))
        text.append(f'| {name} | {person["alias"]} · {starlink} | {person["class99"]} | {"、".join(parts)} |')
    save(dest, '\n'.join(text))
    save(data / '人物索引.json', json.dumps(stars, ensure_ascii=False, indent=2))

    questions = fast.current_q(101)
    assert len(questions) == 178
    qdata = []
    dest = OUT / '06_查阅索引' / '02_问题与未解处.md'
    text = ['# 问题与未解处', '',
            '以下保留178个累计问题入口的完整有效状态，包含已答、部分已答、未详、归并和分歧，不能把总数当成未解数量。复杂题全部子项与直达依据照旧保存。读者文章中的解释须与这些边界并读；小说没有回答的事，不因结书而补出答案。', '',
            '此页是有效交接的机械汇编，不是新一轮文学裁定。历史出处仍可由各回追踪与全局问题表回查。', '']
    for qid, (title, state, origin) in questions.items():
        source_chapter = int(re.search(r'第(\d{3})回[/\\]05_', origin).group(1))
        source_parent = ROOT / '章节' / f'第{source_chapter:03d}回'
        def rebase(match):
            label, target = match.group(1), match.group(2)
            p, sep, fragment = target.partition('#')
            if '://' in p:
                return match.group()
            targetpath = Path(p) if Path(p).is_absolute() else source_parent / p
            if not p:
                targetpath = ROOT / chapters[source_chapter - 1]['followup']
            if not targetpath.is_file() and (ROOT / p).is_file():
                targetpath = ROOT / p
            # 51回始终沿实际验收指定的接任路径，不把中间稿当成有效稿。
            if targetpath.parent.name == '第051回':
                if targetpath.name == '04_修订定稿.md':
                    targetpath = targetpath.with_name('04_修订定稿_接任R02.md')
                elif targetpath.name == '05_追踪与交接.md':
                    targetpath = targetpath.with_name('05_追踪与交接_接任R02.md')
            if targetpath.is_file():
                return link(label, targetpath, dest.parent, ('#' + fragment) if sep else '')
            return match.group()
        combined = f'{state}\n\n依据：{origin}'
        combined = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', rebase, combined)
        qdata.append({'id': qid, 'title': title, 'state': state, 'source': origin})
        text += [f'## {qid} {title}', '', combined, '']
    save(dest, '\n'.join(text))
    save(data / '问题索引.json', json.dumps(qdata, ensure_ascii=False, indent=2))

    clues = []
    for line in read(ROOT / '全书追踪/线索登记.md').splitlines():
        if not re.match(r'^\| CH\d{3}-T\d{2} ', line):
            continue
        c = [x.strip() for x in line.split('|')[1:-1]]
        assert len(c) == 7
        clues.append(dict(zip(('id', 'position', 'text', 'category', 'status', 'followup', 'source'), c)))
    assert len(clues) == len({x['id'] for x in clues}) == 1990
    save(data / '线索索引.json', json.dumps(clues, ensure_ascii=False, indent=2))
    manifest = {'scope': '百回有效成果的读者版资料库', 'chapters': 100, 'people': 108,
                'questions': len(qdata), 'clues': len(clues),
                'clue_states': dict(collections.Counter(x['status'] if not x['status'].startswith('并入') else '并入Q' for x in clues)),
                'limits': ['第一回沿旧试读范围', '索引不冒称新的文学复核', '专题独立复审另见整合记录',
                           '人物姓名出现回目是字面导航，不是已确认的全部出场清单',
                           '中性位置链保存送审入口，实际补读与定位更正见独立复审记录'],
                'inputs': [fileinfo(ROOT / f) for f in ('README.md', '全书追踪/人物称谓与身份.md',
                           '全书追踪/待解问题与修订记录.md', '全书追踪/线索登记.md')]}
    save(data / '来源清单.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f'已建100回阅读入口、108人导航、{len(qdata)}完整问题与{len(clues)}线索索引；未改原章节。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只核来源版本、索引计数和本地文件/行号链接')
    args = parser.parse_args()
    check() if args.check else main()
