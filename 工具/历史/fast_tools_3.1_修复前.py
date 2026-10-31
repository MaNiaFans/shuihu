# -*- coding: utf-8 -*-
"""快速流程3.1 总编工具，只做机械处理。
用法：python fast_tools.py setup | views NNN | init07 NNN | log NNN 步骤 结果 | check05 NNN | fix NNN [dry] | g7 NNN [dry] | nav NNN | accept NNN
"""
import sys, os, re, shutil, collections, datetime, hashlib

R = 'e:/水浒/'
TMP = R + '.venv/tmp/'
FAST = '阅读规则/shuihu-close-reading/references/快速流程_3.1.md'
REG = R + '全书追踪/线索登记.md'
QT = R + '全书追踪/待解问题与修订记录.md'
PT = R + '全书追踪/人物称谓与身份.md'
README = R + 'README.md'
PROG = R + '全书追踪/进度.md'
BASE = 70
CN = '零一二三四五六七八九'


def cnum(x):
    if x == 100:
        return '一百'
    t, o = divmod(x, 10)
    return (CN[t] if t > 1 else '') + ('十' if t else '') + (CN[o] if o else '')


def rd(f):
    s = open(f, encoding='utf-8', newline='').read()
    return s, ('\r\n' if '\r\n' in s else '\n')


def rdu(f):
    return open(f, encoding='utf-8').read()


def wr(f, s):
    with open(f, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


def cdir(n):
    return R + f'章节/第{n:03d}回/'


def now():
    return datetime.datetime.now().strftime('%m-%d %H:%M')


def h8(f):
    if not os.path.exists(f):
        return '无'
    return hashlib.sha256(open(f, 'rb').read()).hexdigest()[:8].upper()


# ---------- setup ----------
def setup():
    tpl = ('# 本回规则入口\n\n'
           f'项目根规则：[AGENTS](../../AGENTS.md)。自第七十一回起按[快速流程3.1](../../{FAST})执行：执行者只读该文件和任务包，不读执行简令和逐回执行合同。相对路径按本文件所在章节目录解析。\n\n'
           '写稿者顺序读完本回全文后写04／05；复核者先自己读完原文、写下要点，再打开04／05核对。本文件不授权推进新章。\n')
    wr(R + '阅读规则/shuihu-close-reading/assets/章回AGENTS模板.md', tpl)
    for n in range(71, 101):
        if os.path.isdir(cdir(n)):
            wr(cdir(n) + 'AGENTS.md', tpl)
    note = ('> **当前执行方式（2026-10-30起）：**用户指令“做快点，真的太慢了，后面还有30章没有做”。'
            f'自第七十一回起按[快速流程3.1]({FAST})执行：一人顺序通读后写04／05，另一人先自读原文再复核，逐字改法由总编脚本落实；'
            '不再写01／02，不单设写稿前对照轮。下文与之不一致处以快速流程为准；第一至七十回的记录不变。')
    s, nl = rd(R + 'AGENTS.md')
    if '快速流程_3.1' not in s:
        L = s.split(nl)
        L[1:1] = ['', note]
        wr(R + 'AGENTS.md', nl.join(L))
    note2 = ('当前执行方式（2026-10-30）：第七十回用时近4小时后，用户说“做快点，真的太慢了，后面还有30章没有做”。'
             f'自第七十一回起改用[快速流程3.1](../{FAST})，未另做流程变更的独立检验（用户要求从快）。'
             '授权范围不变：做到第一百回，每回本地提交，不推送，不启动全书整合。总编脚本：e:\\水浒\\.venv\\tmp\\fast_tools.py。')
    f = R + '全书追踪/任务范围.md'
    s, nl = rd(f)
    if '快速流程_3.1' not in s:
        L = s.split(nl)
        L[1:1] = [note2]
        wr(f, nl.join(L))
    print('setup ok')


# ---------- questions ----------
def baseline_q():
    s = rdu(cdir(BASE) + '05_追踪与交接.md')
    a = s.index('## 四、完整状态清单')
    b = s.index('<a id="clues"></a>')
    q = collections.OrderedDict()
    for l in s[a:b].split('\n'):
        c = l.split('|')
        if len(c) < 5 or not c[1].strip().isdigit():
            continue
        m = re.search(r'CH\d{3}-Q\d{2}', c[2])
        if m:
            q[m.group(0)] = (c[2].replace('`', '').replace(m.group(0), '').strip(), c[3].strip(), f'第{BASE:03d}回05')
    return q


def qchanges(n):
    f = cdir(n) + '05_追踪与交接.md'
    if not os.path.exists(f):
        return []
    s = rdu(f)
    if '<a id="qchanges"></a>' not in s:
        return []
    out = []
    started = False
    for l in s.split('<a id="qchanges"></a>')[1].split('\n'):
        if l.startswith('|'):
            started = True
            c = l.split('|')
            if len(c) < 5:
                continue
            m = re.fullmatch(r'\s*`?(CH\d{3}-Q\d{2})`?\s*', c[1])
            if m:
                out.append((m.group(1), c[2].strip(), c[3].strip()))
        elif started and (l.startswith('#') or l.startswith('<a id=')):
            break
    return out


def current_q(upto):
    q = baseline_q()
    for n in range(BASE + 1, upto):
        for qid, title, st in qchanges(n):
            q[qid] = (title or q.get(qid, ('',))[0], st, f'第{n:03d}回05')
    return q


# ---------- views ----------
def views(n):
    N = f'{n:03d}'
    q = current_q(n)
    L = [f'# 问题简表（供第{N}回用，{now()}生成）', '',
         f'第{BASE:03d}回05完整清单为基线，加第{BASE + 1:03d}回起各回05“问题清单变更”，只含第{N}回之前的材料。状态只截前140字，全文见“来源”所列05（基线行在第{BASE:03d}回05第四节）。', '',
         '| 编号 | 题名 | 状态（截取） | 来源 |', '| --- | --- | --- | --- |']
    for qid, (t, st, src) in q.items():
        st1 = st if len(st) <= 140 else st[:140] + '…'
        L.append(f'| {qid} | {t} | {st1} | {src} |')
    wr(TMP + f'问题简表_{N}.md', '\n'.join(L) + '\n')
    s = rdu(REG)
    a = s.index('## 开放与部分回指')
    b = s.index('## 归档')
    have = set(re.findall(r'^\| (CH\d{3}-T\d{2}) ', s, re.M))
    rows = [l for l in s[a:b].split('\n') if l.startswith('| CH')]
    out = [f'# 线索简表（供第{N}回用，{now()}生成）', '',
           f'全局线索登记“开放与部分回指”段全部{len(rows)}条，只留编号、位置、文本所写、状态；回指历史和来源见 e:\\水浒\\全书追踪\\线索登记.md 原行。表末另列前几回已写成、尚未写入全局的新T（只含第{N}回之前）。', '',
           '| 编号 | 位置 | 文本所写 | 状态 |', '| --- | --- | --- | --- |']
    for l in rows:
        c = l.split('|')
        out.append(f'| {c[1].strip()} | {c[2].strip()} | {c[3].strip()} | {c[5].strip()} |')
    extra = 0
    for m in range(BASE + 1, n):
        f = cdir(m) + '05_追踪与交接.md'
        if not os.path.exists(f):
            continue
        t = rdu(f)
        if '<a id="clues"></a>' not in t:
            continue
        for l in t.split('<a id="clues"></a>')[1].split('\n'):
            if l.startswith(f'| CH{m:03d}-T'):
                c = l.split('|')
                tid = c[1].strip()
                if tid in have or len(c) < 8:
                    continue
                have.add(tid)
                if c[5].strip() in ('开放', '部分回指'):
                    out.append(f'| {tid} | {c[2].strip()} | {c[3].strip()} | {c[5].strip()}（第{m:03d}回05，尚未写入全局） |')
                    extra += 1
    wr(TMP + f'线索简表_{N}.md', '\n'.join(out) + '\n')
    print('views', N, 'q', len(q), 'clues', len(rows), 'extra', extra,
          os.path.getsize(TMP + f'问题简表_{N}.md') // 1024, 'K',
          os.path.getsize(TMP + f'线索简表_{N}.md') // 1024, 'K')


# ---------- 07 ----------
def prep(n, t0, end, a, b, nxt):
    """切片：正文为原L t0—end（含），注释原L a—b（无注释写0 0），nxt为下一回回题行。"""
    N = f'{n:03d}'
    raw = open(R + '水浒传 (施耐庵  罗贯中).txt', 'rb').read()
    L = raw.splitlines(keepends=True)
    title = L[t0 - 1].decode('utf-8').strip()
    assert title.startswith(f'第{cnum(n)}回'), title
    if n < 100:
        assert L[nxt - 1].decode('utf-8').strip().startswith(f'第{cnum(n + 1)}回'), 'next title'
    d = cdir(n)
    os.makedirs(d, exist_ok=False)
    lines = L[t0 - 1:end]
    body = b''.join(lines)
    note = b''.join(L[a - 1:b]) if a else b''
    open(d + '00_正文.txt', 'wb').write(body)
    if a:
        open(d + '00_注释.txt', 'wb').write(note)
    hh = lambda x: hashlib.sha256(x).hexdigest().upper()
    ne = [i for i, l in enumerate(lines) if l.strip()]
    nn = sum(1 for l in L[a - 1:b] if l.strip().startswith(b'[')) if a else 0
    sepline = L[end].strip().startswith(b'*') if end < len(L) else False
    src = (f'# 第{cnum(n)}回来源与范围\n'
           f'底本为项目根目录《水浒传 (施耐庵  罗贯中).txt》，源书自载人民文学出版社百回整理本、以容与堂本为底本并校其他本；本项目未同印刷本逐字校勘。源文件SHA256：{hh(raw)}。\n'
           '| 材料 | 原书范围／本地映射 | 实际行数／边界 | SHA256 |\n| --- | --- | --- | --- |\n'
           f'| 正文 | 原L{t0}—{end}；本地行＋{t0 - 1} | {len(lines)}行／{len(ne)}非空；首行为回题，末非空原L{t0 + ne[-1]}，尾空保留 | {hh(body)} |\n'
           + (f'| 现代注释 | 原L{a}—{b}；注本地行＋{a - 1} | {b - a + 1}行／{nn}条，按原字保留 | {hh(note)} |\n' if a else '| 现代注释 | 不适用 | 本回无注释 | — |\n')
           + f'\n正文题为“{title}”；' + (f'正文后原L{end + 1}为分隔线，' if sepline else '本回正文后无分隔线，') + (f'注释在L{a}—{b}，' if a else '') + f'下一回标题在L{nxt}。准备时按原始字节切片并核与原书一致。\n'
           f'实际资料接触：总编准备只显示相邻回题、分隔线、注释序号行长度及相邻行的空白／字符长度，未显示或通读本回叙事正文、注释内容与下一回正文。证据截止第{cnum(n)}回；必要前情仅定点读此前各回00原文。\n')
    wr(d + '00_来源与范围.md', src)
    shutil.copy(R + '阅读规则/shuihu-close-reading/assets/章回AGENTS模板.md', d + 'AGENTS.md')
    init07(n, True)
    print('prep', N, title, len(lines), len(ne), nn)


def init07(n, force=False):
    N = f'{n:03d}'
    C = cnum(n)
    f = cdir(n) + '07_执行与验收.md'
    old = rdu(f) if os.path.exists(f) else ''
    if not force and '3.1快速流程' in old and old.startswith(f'# 第{C}回'):
        print('07 already fast', N)
        return
    keep = [l for l in old.split('\n') if l.startswith('| P1')]
    src = rdu(cdir(n) + '00_来源与范围.md')
    m = re.search(r'原L(\d+)—(\d+)；本地行＋(\d+)', src)
    rng = f'原L{m.group(1)}—{m.group(2)}，本地＋{m.group(3)}' if m else '见来源'
    s = (f'# 第{C}回：执行与验收（3.1快速流程）\n\n'
         f'仅总编维护。流程见[快速流程3.1](../../{FAST})；本页只记步骤、时间、版本与结果。\n\n'
         f'- 资料：[正文](00_正文.txt)（{rng}）、[注释](00_注释.txt)、[来源与边界](00_来源与范围.md)。总编准备时只看边界与行长，未通读正文。\n'
         '- 执行者：general-task-execution子agent，每次调用为新上下文，型号不可核。复核者先自读原文、写下要点后才看04／05。授权见[任务范围](../../全书追踪/任务范围.md)顶部。\n')
    if keep:
        s += ('\n## 3.0流程下的派发记录（均中断、未产出）\n\n'
              '| 顺序／阶段 | 实际读取或检查范围 | 产物／版本入口 | 结果、缺口与下一步 |\n| --- | --- | --- | --- |\n'
              + '\n'.join(keep) + '\n')
    s += '\n## 步骤\n\n| 步骤 | 时间 | 结果与版本 |\n| --- | --- | --- |\n| 准备00 | — | 正文、注释按原书字节切片，映射已核 |\n'
    wr(f, s)
    print('init07', N)


def log(n, step, text):
    d = cdir(n)
    text = (text.replace('{h04}', h8(d + '04_修订定稿.md'))
            .replace('{h05}', h8(d + '05_追踪与交接.md'))
            .replace('{h03}', h8(d + '03_检校意见.md')))
    f = d + '07_执行与验收.md'
    s, nl = rd(f)
    wr(f, s.rstrip('\r\n') + nl + f'| {step} | {now()} | {text} |' + nl)
    print('log', f'{n:03d}', step)


def accept(n):
    f = cdir(n) + '07_执行与验收.md'
    s, nl = rd(f)
    if 'id="accepted"' in s:
        print('already accepted')
        return
    s = (s.rstrip('\r\n') + nl + nl + '<a id="accepted"></a>' + nl
         + f'当前状态：**第{cnum(n)}回完成（快速流程3.1，{now()}）。**全局表、README、线索登记与进度已同步；本地提交，未推送。' + nl)
    wr(f, s)
    print('accept', f'{n:03d}')


# ---------- 05 checks ----------
RANK = {'开放': 0, '部分回指': 1, '已回指': 2}


def parse5c(c05):
    if '**5c.' not in c05:
        return []
    sec = c05.split('**5c.')[1]
    return re.findall(r'^- \*\*(CH\d{3}-T\d{2})\*\*[\u3000 ]*状态：(.*?)。回指／去向(.*?)\s*$', sec, re.M)


def check05(n):
    N = f'{n:03d}'
    d = cdir(n)
    errs = []
    for x in ('04_修订定稿.md', '05_追踪与交接.md'):
        if not os.path.exists(d + x):
            print('missing', x)
            return
    s = rdu(d + '05_追踪与交接.md')
    for a in ('<a id="qchanges"></a>', '<a id="clues"></a>', '<a id="candidates"></a>'):
        if s.count(a) != 1:
            errs.append(f'锚点{a}出现{s.count(a)}次')
    if errs:
        print('\n'.join(errs))
        return
    if s.count('**5c.') > 1:
        errs.append('**5c.出现多次')
    cand = s.split('<a id="candidates"></a>')[1]
    blocks = re.findall(r'```markdown\n(.*?)```', cand, re.S)
    if len(blocks) not in (4, 5):
        errs.append(f'候选代码块{len(blocks)}个')
    else:
        if f'<a id="ch{N}-delta"></a>' not in blocks[0]:
            errs.append('问题增量缺锚点')
        if f'<a id="ch{N}-people"></a>' not in blocks[1]:
            errs.append('人物增量缺锚点')
        if not blocks[2].strip().startswith(f'[第{cnum(n)}回《'):
            errs.append('故事段开头不符')
        if '\n' in blocks[2].strip():
            errs.append('故事段不止一行')
        if not blocks[3].strip().startswith(f'| [第{cnum(n)}回]'):
            errs.append('表行开头不符')
    sec = s.split('<a id="clues"></a>')[1].split('<a id="candidates"></a>')[0]
    ids = []
    merged = set()
    for l in sec.split('\n'):
        if l.startswith(f'| CH{N}-T'):
            c = l.split('|')
            tid = c[1].strip()
            if len(c) != 9:
                errs.append(f'{tid}栏数{len(c) - 2}')
            st = c[5].strip() if len(c) > 5 else ''
            if st.startswith('并入'):
                merged.add(tid)
            elif st not in ('开放', '部分回指'):
                errs.append(f'{tid}状态“{st}”')
            ids.append(tid)
    if len(ids) != len(set(ids)):
        errs.append('新增T编号重复')
    if sorted(ids) != [f'CH{N}-T{i:02d}' for i in range(1, len(ids) + 1)]:
        errs.append('新增T编号不连续')
    arch = set()
    if len(blocks) == 5:
        arch = set(l.split('|')[1].strip() for l in blocks[4].split('\n') if l.startswith(f'| CH{N}-T'))
    if arch != merged:
        errs.append(f'归档块与并入行不一致：{sorted(arch ^ merged)}')
    reg = rdu(REG)
    items = parse5c(s)
    warns = []
    for tid, st, rest in items:
        rows = [l for l in reg.split('\n') if l.startswith('| ' + tid + ' ')]
        if len(rows) != 1:
            errs.append(f'5c {tid}在全局{len(rows)}行')
            continue
        old = rows[0].split('|')[6]
        ost, nst = rows[0].split('|')[5].strip(), st.replace('（不变）', '').strip()
        if (ost in RANK and nst in RANK and RANK[nst] < RANK[ost]) or (ost.startswith('并入') and nst in RANK):
            warns.append(f'提示：5c {tid}全局现为“{ost}”，稿写“{nst}”，g7将保留“{ost}”')
        if rest.startswith('：') or rest.startswith('末尾追加：'):
            pass
        elif rest.startswith('在“'):
            mm = re.match(r'在“(.*?)”前插入：', rest)
            if not mm or (mm.group(1) not in old and mm.group(1).replace('‘', '“').replace('’', '”') not in old):
                errs.append(f'5c {tid}插入锚句不在原栏')
        else:
            errs.append(f'5c {tid}格式不识')
    n5c = len(re.findall(r'^- \*\*CH\d{3}-T\d{2}\*\*', s.split('**5c.')[1], re.M)) if '**5c.' in s else 0
    if n5c != len(items):
        errs.append(f'5c行{n5c}条，可解析{len(items)}条')
    print(f'check05 {N}: 新T {len(ids)}（并入{len(merged)}），5c {len(items)}，问题变更 {len(qchanges(n))}，'
          f'04 {os.path.getsize(d + "04_修订定稿.md") // 1024}K，05 {os.path.getsize(d + "05_追踪与交接.md") // 1024}K')
    print('\n'.join(errs) if errs else '格式无误')
    if warns:
        print('\n'.join(warns))


# ---------- fix from 03 ----------
def fix(n, dry=False):
    d = cdir(n)
    s = rdu(d + '03_检校意见.md')
    m = re.search(r'^## 三、逐字改法[^\n]*\n(.*?)(?=^## |\Z)', s, re.S | re.M)
    if not m:
        print('03无“三、逐字改法”节')
        return
    chunks = re.split(r'(?m)^(?=### F\d+)', m.group(1))
    files = {}
    res = []
    for ch in chunks:
        mh = re.match(r'### (F\d+)\D*?(04|05)', ch)
        if not mh:
            continue
        fid, which = mh.group(1), mh.group(2)
        mm = re.search(r'旧：[ \t]*\n(~~~|```)[^\n]*\n(.*?)\n\1[ \t]*\n\s*新：[ \t]*\n(~~~|```)[^\n]*\n(.*?)\n\3', ch, re.S)
        if not mm:
            res.append((fid, which, '无法解析'))
            continue
        old, new = mm.group(2), mm.group(4)
        p = d + ('04_修订定稿.md' if which == '04' else '05_追踪与交接.md')
        if p not in files:
            files[p] = list(rd(p))
        t, nl = files[p]
        o, w = old.replace('\n', nl), new.replace('\n', nl)
        k = t.count(o)
        if k != 1:
            res.append((fid, which, f'旧文出现{k}次，未改'))
            continue
        files[p][0] = t.replace(o, w, 1)
        res.append((fid, which, '已改'))
    for r in res:
        print(*r)
    if not dry:
        for p, (t, nl) in files.items():
            wr(p, t)
    print('fix', f'{n:03d}', '共', len(res), '条，已改', sum(1 for r in res if r[2] == '已改'), '（dry）' if dry else '')


# ---------- global write ----------
def g7(n, dry=False):
    N = f'{n:03d}'
    c05 = rdu(cdir(n) + '05_追踪与交接.md')
    cand = c05.split('<a id="candidates"></a>')[1]
    blocks = re.findall(r'```markdown\n(.*?)```', cand, re.S)
    qd, pp, story, row = blocks[0], blocks[1], blocks[2].strip(), blocks[3].strip()
    arch = blocks[4].strip() if len(blocks) > 4 else ''
    out = {}
    for f, b in ((QT, qd), (PT, pp)):
        s, nl = rd(f)
        if f'<a id="ch{N}-' in s:
            raise SystemExit('global already has ch' + N + ' block: ' + os.path.basename(f))
        out[f] = s.rstrip('\r\n') + nl + nl + b.strip().replace('\n', nl) + nl
    s, nl = rd(README)
    L = s.split(nl)
    prev = cnum(n - 1)
    i = [k for k, l in enumerate(L) if l.startswith(f'[第{prev}回《')][0]
    L[i + 1:i + 1] = ['', story]
    j = [k for k, l in enumerate(L) if l.startswith(f'| [第{prev}回]')][0]
    L.insert(j + 1, row)
    out[README] = nl.join(L)
    t, nl = rd(REG)
    TL = t.split(nl)
    existing = set(re.findall(r'^\| (CH\d{3}-T\d{2}) ', t, re.M))
    sec5 = c05.split('<a id="clues"></a>')[1]
    seen = set()
    openrows = []
    for l in sec5.split('\n'):
        if l.startswith(f'| CH{N}-T'):
            tid = l.split('|')[1].strip()
            if tid in seen:
                continue
            seen.add(tid)
            if l.split('|')[5].strip() in ('开放', '部分回指'):
                openrows.append(l)
    archrows = [l for l in arch.split('\n') if l.startswith(f'| CH{N}')]
    dup = [r.split('|')[1].strip() for r in openrows + archrows if r.split('|')[1].strip() in existing]
    if dup:
        raise SystemExit('already in register: ' + ','.join(dup))
    ah = [k for k, l in enumerate(TL) if l.startswith('## 归档')][0]
    k = max(kk for kk, l in enumerate(TL[:ah]) if l.startswith('| CH'))
    for r in reversed(openrows):
        TL.insert(k + 1, r)
    while TL and not TL[-1].strip():
        TL.pop()
    TL += archrows
    for tid, st, rest in parse5c(c05):
        st = st.replace('（不变）', '').strip()
        extra = None
        m = re.search(r'。另：本行第二栏“(.*?)”改为“(.*?)”$', rest)
        if m:
            extra = (m.group(1), m.group(2))
            rest = rest[:m.start()]
        ks = [kk for kk, l in enumerate(TL) if l.startswith('| ' + tid + ' ')]
        assert len(ks) == 1, tid
        c = TL[ks[0]].split('|')
        old = c[6].strip()
        ost = c[5].strip()
        if ost in RANK and st in RANK and RANK[st] < RANK[ost]:
            print('WARN 降级未采用', tid, ost, '->', st)
            st = ost
        elif ost.startswith('并入') and st in RANK:
            print('WARN 并入行改状态未采用', tid, ost, '->', st)
            st = ost
        if rest.startswith('：'):
            new = rest[1:].strip()
        elif rest.startswith('末尾追加：'):
            new = old + rest[len('末尾追加：'):].strip()
        elif rest.startswith('在“'):
            mm = re.match(r'在“(.*?)”前插入：(.*)', rest)
            anc, ins = mm.group(1), mm.group(2).strip()
            alt = anc.replace('‘', '“').replace('’', '”')
            if anc not in old and alt in old:
                anc = alt
            assert anc in old, (tid, anc)
            new = old.replace(anc, ins + anc, 1)
        else:
            raise SystemExit('unparsed ' + tid)
        c[5] = ' ' + st + ' '
        c[6] = ' ' + new + ' '
        c[7] = ' ' + c[7].strip() + f'；后端第{N}回05#clues '
        if extra:
            assert c[2].strip() == extra[0], (tid, c[2])
            c[2] = ' ' + extra[1] + ' '
        TL[ks[0]] = '|'.join(c)
        print('5c', tid, st)
    ah = [k for k, l in enumerate(TL) if l.startswith('## 归档')][0]
    moved = [l for l in TL[:ah] if l.startswith('| CH') and l.split('|')[5].strip() not in ('开放', '部分回指')]
    if moved:
        TL = [l for l in TL[:ah] if l not in moved] + TL[ah:] + moved
    TL += ['']
    out[REG] = nl.join(TL)
    rows = [l for l in TL if l.startswith('| CH')]
    cnt = collections.Counter('并入' if r.split('|')[5].strip().startswith('并入') else r.split('|')[5].strip() for r in rows)
    print('open', len(openrows), 'arch', len(archrows), 'moved', [l.split('|')[1].strip() for l in moved],
          'total', len(rows), dict(cnt))
    if dry:
        print('dry run, nothing written')
        return
    bak = TMP + f'g7bak{N}/'
    os.makedirs(bak, exist_ok=True)
    if not os.listdir(bak):
        for f in (QT, PT, README, REG, PROG):
            shutil.copy(f, bak + os.path.basename(f))
    for f, s in out.items():
        wr(f, s)
    for f, b in ((QT, qd), (PT, pp), (README, story), (README, row)):
        print(os.path.basename(f), b.strip() in rd(f)[0].replace('\r\n', '\n'))


def nav(n):
    N = f'{n:03d}'
    C = cnum(n)
    rows = [l for l in rdu(REG).split('\n') if l.startswith('| CH')]
    cnt = collections.Counter('并入' if r.split('|')[5].strip().startswith('并入') else r.split('|')[5].strip() for r in rows)
    tot, op, pa, hu, bi = len(rows), cnt['开放'], cnt['部分回指'], cnt['已回指'], cnt['并入']
    zhu = len(current_q(n + 1))

    def rep(f, ln, new):
        s, nl = rd(f)
        L = s.split(nl)
        L[ln - 1] = new
        wr(f, nl.join(L))

    rep(QT, 2, f'当前有效问题交接截至第{C}回末；自第七十一回起执行[快速流程3.1](../{FAST})。完整状态以[第{BASE:03d}回完整清单](../章节/第{BASE:03d}回/05_追踪与交接.md#complete-list)为基线，加第{BASE + 1:03d}回起各回05的“问题清单变更”（最新见[第{N}回](../章节/第{N}回/05_追踪与交接.md#qchanges)），现共{zhu}个累计主项（含已答、归并与分歧，不是未解数）；最新[{n}回增量](#ch{N}-delta)。线索另见[全局线索登记](线索登记.md)。')
    rep(PT, 2, f'当前有效人物交接截至第{C}回末；自第七十一回起执行快速流程3.1。最新[{n}回人物增量](#ch{N}-people)、[成稿](../章节/第{N}回/04_修订定稿.md)。此前身份、职司、责任、受影响者与未知按有效旧据保持。')
    rep(README, 3, f'本地阅读材料到第{C}回末。自第七十一回起按[快速流程3.1]({FAST})：一人顺序通读后写成稿，另一人先自读原文再复核。可直接读[第{C}回成稿](章节/第{N}回/04_修订定稿.md)；问题状态见[全局问题表](全书追踪/待解问题与修订记录.md)，线索见[全局线索登记](全书追踪/线索登记.md)。全书人物档案尚未整合。')
    s, nl = rd(REG)
    s2 = re.sub(r'最新：第\d{3}回G7写入[^\n]*?。(?=\r?\n)',
                f'最新：第{N}回G7写入，现共{tot}条（开放{op}、部分回指{pa}、已回指{hu}、并入Q {bi}），见[第{N}回05](../章节/第{N}回/05_追踪与交接.md#clues)。', s, 1)
    if s2 == s:
        print('WARN register status line not replaced')
    wr(REG, s2)
    s, nl = rd(PROG)
    L = s.split(nl)
    nxt = cnum(n + 1) if n < 100 else '（全书逐回完成）'
    L[1] = (f'持续执行（2026-10-30起快速流程3.1）：第{C}回完成，累计主项{zhu}，线索登记{tot}条。'
            f'见[成稿](../章节/第{N}回/04_修订定稿.md)、[追踪](../章节/第{N}回/05_追踪与交接.md)、[记录](../章节/第{N}回/07_执行与验收.md#accepted)。本地提交、未推送；下一步第{nxt}回。')
    wr(PROG, nl.join(L))
    print('nav', N, 'zhu', zhu, 'clues', tot, op, pa, hu, bi)


if __name__ == '__main__':
    a = sys.argv[1:]
    cmd = a[0]
    if cmd == 'setup':
        setup()
    elif cmd == 'views':
        views(int(a[1]))
    elif cmd == 'init07':
        init07(int(a[1]), len(a) > 2 and a[2] == 'force')
    elif cmd == 'prep':
        prep(*map(int, a[1:7]))
    elif cmd == 'log':
        log(int(a[1]), a[2], a[3])
    elif cmd == 'check05':
        check05(int(a[1]))
    elif cmd == 'fix':
        fix(int(a[1]), len(a) > 2 and a[2] == 'dry')
    elif cmd == 'g7':
        g7(int(a[1]), len(a) > 2 and a[2] == 'dry')
    elif cmd == 'nav':
        nav(int(a[1]))
    elif cmd == 'accept':
        accept(int(a[1]))
    else:
        print(__doc__)
