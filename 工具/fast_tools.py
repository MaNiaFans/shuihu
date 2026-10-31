# -*- coding: utf-8 -*-
"""快速流程3.1 总编工具，只做机械处理。
用法：python 工具/fast_tools.py views|deps|check05|fix|g7|nav NNN [dry]
      python 工具/fast_tools.py review|accept NNN --note 实际核验说明
      python 工具/fast_tools.py snapshot NNN 原因
review/accept只登记总编实际核验；脚本不判定原文是否读完或解释是否成立。
"""
import sys, os, re, shutil, collections, datetime, hashlib, json, tempfile
from pathlib import Path

R = Path(__file__).resolve().parents[1].as_posix() + '/'
TMP = R + '.venv/tmp/'
FAST = '阅读规则/shuihu-close-reading/references/快速流程_3.1.md'
REG = R + '全书追踪/线索登记.md'
QT = R + '全书追踪/待解问题与修订记录.md'
PT = R + '全书追踪/人物称谓与身份.md'
README = R + 'README.md'
PROG = R + '全书追踪/进度.md'
BASE = 70
CN = '零一二三四五六七八九'
STATE_RE = re.compile(r'<!-- fast-tools-state\n(.*?)\n-->', re.S)


class FlowError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise FlowError(message)


def digest(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest() if os.path.isfile(f) else None


def fingerprints(paths):
    return {os.path.relpath(p, R).replace('\\', '/'): digest(p) for p in paths}


def drafts(n):
    return [cdir(n) + x for x in ('03_检校意见.md', '04_修订定稿.md', '05_追踪与交接.md')]


def dependencies(n):
    # 已验收链以前回为入口；所有实际用于问题重建的05也绑定版本。
    paths = [QT, PT, REG, cdir(BASE) + '05_追踪与交接.md']
    paths += [cdir(m) + '05_追踪与交接.md' for m in range(BASE + 1, n)
              if os.path.isfile(cdir(m) + '05_追踪与交接.md')]
    paths += [cdir(n - 1) + '04_修订定稿.md']
    return fingerprints(paths)


def state(n):
    f = cdir(n) + '07_执行与验收.md'
    require(os.path.isfile(f), '缺07执行记录')
    text = rdu(f)
    matches = list(STATE_RE.finditer(text))
    require(len(matches) <= 1, '07流程版本记录重复')
    return json.loads(matches[0].group(1)) if matches else {}


def state_text(n, data, message=None):
    f = cdir(n) + '07_执行与验收.md'
    text, nl = rd(f)
    text = STATE_RE.sub('', text.replace('\r\n', '\n')).rstrip()
    if message:
        text += '\n\n' + message
    return (text + '\n\n<!-- fast-tools-state\n' +
            json.dumps(data, ensure_ascii=False, indent=2) + '\n-->\n').replace('\n', nl)


def accepted(n):
    f = cdir(n) + '07_执行与验收.md'
    if not os.path.isfile(f):
        return False
    text = rdu(f)
    statuses = re.findall(r'^当前状态：(.*)$', text, re.M)
    if not statuses or '<a id="accepted"></a>' not in text:
        return False
    latest = statuses[-1]
    if any(word in latest for word in ('需复审', '未完成', '未通过', '未验收', '待验收', '待复核', '待修订', '待独立', '待核', '待补')):
        return False
    return bool(re.match(r'^(?:\*\*)?第[\d一二三四五六七八九十百]+回(?:G1—G7)?(?:验收通过|完成)', latest))


def require_previous(n):
    require(accepted(n - 1), f'第{n - 1:03d}回未完成，最终交接须按回次收尾')
    require(all(os.path.isfile(cdir(n - 1) + x) for x in ('04_修订定稿.md', '05_追踪与交接.md')),
            '前回完成登记缺对应稿件')
    final = state(n - 1).get('accept')
    if final:
        require(final['files'] == fingerprints(drafts(n - 1)), '前回完成后稿件有变化，先核具体差额及有效验收')


def snapshot(n, reason, paths=None):
    paths = paths or drafts(n)
    folder = Path(cdir(n)) / '历史' / (datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f') + '_' +
                                      re.sub(r'[^\w\u4e00-\u9fff-]', '_', reason)[:40])
    folder.mkdir(parents=True, exist_ok=False)
    for path in paths:
        if os.path.isfile(path):
            shutil.copy2(path, folder / Path(path).name)
    return folder


def write_batch(changes, expected=None):
    """全部内容先准备；写入异常回滚。进程被强停后仍须凭版本核对恢复，不声称跨文件系统原子性。"""
    expected = expected or {}
    for path, sha in expected.items():
        require(digest(path) == sha, '准备期间文件变化，未写入：' + path)
    originals, staged, replaced = {}, {}, []
    try:
        for path, text in changes.items():
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            originals[path] = p.read_bytes() if p.exists() else None
            handle, tmp = tempfile.mkstemp(prefix='.' + p.name + '.', suffix='.tmp', dir=p.parent)
            staged[path] = tmp
            with os.fdopen(handle, 'wb') as fh:
                fh.write(text.encode('utf-8'))
        for path, sha in expected.items():
            require(digest(path) == sha, '保存前文件变化，未写入：' + path)
        for path, tmp in staged.items():
            os.replace(tmp, path)
            replaced.append(path)
    except BaseException:
        for path in reversed(replaced):
            if originals[path] is None:
                Path(path).unlink(missing_ok=True)
            else:
                Path(path).write_bytes(originals[path])
        raise
    finally:
        for tmp in staged.values():
            Path(tmp).unlink(missing_ok=True)


def section(text, title):
    """取最后一组同名二级节；旧轮次保留，代码围栏中的标题不参与。"""
    active, fence, out, result = False, None, [], ''
    for line in text.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker.group(1)[0]
            elif marker.group(1)[0] == fence:
                fence = None
        if fence is None and line.startswith('## '):
            if active:
                result = '\n'.join(out).strip()
            active = line[3:].strip().startswith(title)
            out = []
            continue
        if active:
            out.append(line)
    return '\n'.join(out).strip() if active else result


def read_review(n):
    text = rdu(drafts(n)[0])
    for title in ('一、自读要点', '二、核对范围', '三、逐字改法', '四、需写稿者处理'):
        require(section(text, title), '03缺完整的' + title)
    blockers = section(text, '四、需写稿者处理')
    require(blockers.strip() in ('无', '无。'), '03仍有需写稿者处理项；复核者须追加实际关闭与当前意见，不覆盖旧轮次')
    return text


def deps(n):
    data = state(n)
    before = data.get('input', {}).get('dependencies', {})
    current = dependencies(n)
    changed = [p for p in before.keys() | current.keys() if before.get(p) != current.get(p)]
    print('前回已完成：', accepted(n - 1), '输入版本：', '已有' if before else '未绑定')
    for path in changed:
        print('变化', path)
    return changed


def review(n, note):
    require(not accepted(n), '已完成章节须按既有07登记定点返修，不能重置验收')
    require(note and len(note.strip()) >= 8, 'review须提供实际核查范围与结论 --note；不是请求用户批准')
    require_previous(n)
    require(all(os.path.isfile(p) for p in drafts(n)), '缺03/04/05')
    read_review(n)
    data = state(n)
    deps(n)
    # 这行由复核者写入03；总编不能替写文学判断或事后追认旧观察。
    require('前回定稿差额：' in section(rdu(drafts(n)[0]), '二、核对范围'),
            '复核者须在03核对范围记“前回定稿差额：”及实际检查结论；新生成输入不能追认旧复核')
    data['review'] = {'files': fingerprints(drafts(n)), 'dependencies': dependencies(n),
                      'note': note.strip(), 'time': now()}
    for key in ('fix', 'g7', 'nav'):
        data.pop(key, None)
    wr(cdir(n) + '07_执行与验收.md', state_text(n, data))
    print('review', f'{n:03d}', '已绑定实际稿件与前回定稿；不代表整回验收')


def gate(n, stage='review'):
    require_previous(n)
    data = state(n)
    require(stage in data and 'review' in data, '缺' + stage + '实际核验记录')
    expected_deps = dict(data['review']['dependencies'])
    if stage in ('g7', 'nav'):
        expected_deps.update({p: h for p, h in data.get('g7', {}).get('globals', {}).items() if p in expected_deps})
    require(expected_deps == dependencies(n), '前回或全局已变化；先核真实差额，再更新review')
    require(data['review']['files'].get(os.path.relpath(drafts(n)[0], R).replace('\\', '/')) == digest(drafts(n)[0]),
            '03在核验后变化')
    expected = data[stage].get('files', {})
    require(expected == fingerprints(drafts(n)), '当前03/04/05与' + stage + '绑定版本不一致')
    read_review(n)
    return data


def cnum(x):
    if x == 100:
        return '一百'
    t, o = divmod(x, 10)
    return (CN[t] if t > 1 else '') + ('十' if t else '') + (CN[o] if o else '')


def rd(f):
    with open(f, encoding='utf-8', newline='') as fh:
        s = fh.read()
    return s, ('\r\n' if '\r\n' in s else '\n')


def rdu(f):
    return Path(f).read_text(encoding='utf-8')


def wr(f, s):
    write_batch({f: s})


def cdir(n):
    return R + f'章节/第{n:03d}回/'


def now():
    return datetime.datetime.now().strftime('%m-%d %H:%M')


def h8(f):
    if not os.path.exists(f):
        return '无'
    return digest(f)[:8].upper()


# ---------- setup ----------
def setup():
    tpl = ('# 本回规则入口\n\n'
           f'项目根规则：[AGENTS](../../AGENTS.md)。自第七十一回起按[快速流程3.1](../../{FAST})执行：执行者只读该文件和任务包，不读执行简令和逐回执行合同。相对路径按本文件所在章节目录解析。\n\n'
           '写稿者顺序读完本回全文后写04／05；复核者先自己读完原文、写下要点，再打开04／05核对。本文件不授权推进新章。\n')
    wr(R + '阅读规则/shuihu-close-reading/assets/章回AGENTS模板.md', tpl)
    for n in range(71, 101):
        if os.path.isdir(cdir(n)) and not accepted(n):
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
             '授权范围不变：做到第一百回，每回本地提交，不推送，不启动全书整合。总编脚本见工具/fast_tools.py。')
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
            q[m.group(0)] = (c[2].replace('`', '').replace(m.group(0), '').strip(), c[3].strip(),
                            f'[第{BASE:03d}回05第四节]({cdir(BASE)}05_追踪与交接.md#complete-list)；' + c[4].strip())
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
            q[qid] = (title or q.get(qid, ('',))[0], st,
                      f'[第{n:03d}回05]({cdir(n)}05_追踪与交接.md#qchanges)' +
                      ('（未验收草稿，最终交接须核差额）' if not accepted(n) else ''))
    return q


# ---------- views ----------
def views(n):
    N = f'{n:03d}'
    q = current_q(n)
    L = [f'# 问题简表（供第{N}回用，{now()}生成）', '',
         f'第{BASE:03d}回05完整清单为基线，加第{BASE + 1:03d}回起各回05“问题清单变更”，只含第{N}回之前的材料。全部状态原样保留，不截断子项；来源标明未验收草稿，不视为最终状态。', '',
         '| 编号 | 题名 | 完整状态 | 来源与依据 |', '| --- | --- | --- | --- |']
    for qid, (t, st, src) in q.items():
        L.append(f'| {qid} | {t} | {st} | {src} |')
    wr(TMP + f'问题简表_{N}.md', '\n'.join(L) + '\n')
    s = rdu(REG)
    a = s.index('## 开放与部分回指')
    b = s.index('## 归档')
    have = set(re.findall(r'^\| (CH\d{3}-T\d{2}) ', s, re.M))
    rows = [l for l in s[a:b].split('\n') if l.startswith('| CH') and int(l[4:7]) < n]
    out = [f'# 线索简表（供第{N}回用，{now()}生成）', '',
           f'全局线索登记“开放与部分回指”段全部{len(rows)}条，只留编号、位置、文本所写、状态；回指历史和来源见 {REG} 原行。表末另列前几回未入全局的新T；未验收稿只是待核输入。', '',
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
    if not accepted(n):
        data = state(n)
        folder = snapshot(n, '输入版本', [TMP + f'问题简表_{N}.md', TMP + f'线索简表_{N}.md'])
        for m in range(BASE + 1, n):
            source = cdir(m) + '05_追踪与交接.md'
            if os.path.isfile(source) and not accepted(m):
                shutil.copy2(source, folder / f'第{m:03d}回05_输入.md')
        data['input'] = {'dependencies': dependencies(n), 'prepared_at': now(),
                         'snapshot': os.path.relpath(folder, R).replace('\\', '/'),
                         'meaning': '输入准备版本，不追认此前阅读已使用此版本'}
        wr(cdir(n) + '07_执行与验收.md', state_text(n, data))
    print('views', N, 'q', len(q), 'clues', len(rows), 'extra', extra,
          os.path.getsize(TMP + f'问题简表_{N}.md') // 1024, 'K',
          os.path.getsize(TMP + f'线索简表_{N}.md') // 1024, 'K')


# ---------- 07 ----------
def prep(n, t0, end, a, b, nxt):
    """切片：正文为原L t0—end（含），注释原L a—b（无注释写0 0），nxt为下一回回题行。"""
    N = f'{n:03d}'
    raw = Path(R + '水浒传 (施耐庵  罗贯中).txt').read_bytes()
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
    Path(d + '00_正文.txt').write_bytes(body)
    if a:
        Path(d + '00_注释.txt').write_bytes(note)
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
    require(not (force and '<a id="accepted"></a>' in old), '不能覆盖已验收07')
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
          '- 执行者：由总编按本次实际任务包与回执登记角色、新上下文及可核实模型，不预填。复核者先自读原文、保存要点后才看04／05。授权见[任务范围](../../全书追踪/任务范围.md)顶部。\n')
    if keep:
        s += ('\n## 3.0流程下的派发记录（均中断、未产出）\n\n'
              '| 顺序／阶段 | 实际读取或检查范围 | 产物／版本入口 | 结果、缺口与下一步 |\n| --- | --- | --- | --- |\n'
              + '\n'.join(keep) + '\n')
    s += '\n## 步骤\n\n| 步骤 | 时间 | 结果与版本 |\n| --- | --- | --- |\n| 准备00 | — | 正文、注释按原书字节切片，映射已核 |\n'
    if old:
        snapshot(n, '重建07前', [f] + drafts(n))
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


def accept(n, note=None):
    f = cdir(n) + '07_执行与验收.md'
    s, nl = rd(f)
    if accepted(n):
        print('已有历史完成登记；本次未重新验收')
        return
    require(note and len(note.strip()) >= 8, 'accept须提供总编实际核验及全局回读说明 --note')
    data = gate(n, 'nav')
    check05(n)
    require(data['g7']['globals'] == fingerprints(global_paths()), '全局写入后有变化，须回查实际差额')
    expected = {p: digest(p) for p in global_paths() + drafts(n) + [f]}
    changes = navigation(n)
    final_globals = fingerprints(global_paths())
    final_globals.update({os.path.relpath(p, R).replace('\\', '/'): hashlib.sha256(text.encode('utf-8')).hexdigest()
                          for p, text in changes.items()})
    data['accept'] = {'note': note.strip(), 'time': now(), 'files': fingerprints(drafts(n)), 'globals': final_globals}
    message = (('' if 'id="accepted"' in s else '<a id="accepted"></a>\n') + f'当前状态：**第{cnum(n)}回完成（快速流程3.1，{now()}）。**'
               '全局表、README、线索登记与进度已同步；待本地提交，不推送。\n' + '总编验收与回读：' + note.strip())
    changes[f] = state_text(n, data, message)
    snapshot(n, '验收登记前', global_paths() + [f])
    write_batch(changes, expected)
    print('accept', f'{n:03d}')


# ---------- 05 checks ----------
RANK = {'开放': 0, '部分回指': 1, '已回指': 2}


def parse5c(c05):
    if '**5c.' not in c05:
        return []
    sec = c05.split('**5c.')[1]
    return re.findall(r'^- \*\*(CH\d{3}-T\d{2})\*\*[\u3000 ]*状态：(.*?)。回指／去向(.*?)\s*$', sec, re.M)


def update_status(old, wanted, rest, review_text):
    wanted = wanted.replace('（不变）', '').strip()
    if wanted == '沿用':
        return old, rest
    require(wanted in RANK or wanted == '撤销' or re.fullmatch(r'并入(?:某)?CH\d{3}-Q\d{2}(?:-[a-z])?', wanted),
            '无法识别的线索状态：' + wanted)
    correction = re.search(r'。状态更正依据：(.*)$', rest)
    downgrade = ((old in RANK and wanted in RANK and RANK[wanted] < RANK[old]) or
                 ((old.startswith('并入') or old == '撤销') and old != wanted) or wanted == '撤销')
    if downgrade:
        require(correction and len(correction.group(1).strip()) >= 3 and correction.group(0) in review_text,
                f'状态冲突 {old}→{wanted}：须由复核者在03给出“。状态更正依据：…”；若沿用旧状态，05明确写沿用')
    return wanted, rest[:correction.start()] if correction else rest


def check05(n):
    N = f'{n:03d}'
    d = cdir(n)
    errs = []
    for x in ('04_修订定稿.md', '05_追踪与交接.md'):
        require(os.path.exists(d + x), 'missing ' + x)
    s = rdu(d + '05_追踪与交接.md')
    for a in ('<a id="qchanges"></a>', '<a id="clues"></a>', '<a id="candidates"></a>'):
        if s.count(a) != 1:
            errs.append(f'锚点{a}出现{s.count(a)}次')
    if errs:
        raise FlowError('\n'.join(errs))
    if re.search(r'^- 待并\*\*|编号待定|编号待对齐', s, re.M):
        errs.append('仍有待并5c或未确定编号，最终交接未完成')
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
        if ost.startswith('并入') and nst in ('沿用', ost):
            errs.append(f'5c {tid}已{ost}：新证据应记在该Q下，不再独立更新T')
            continue
        try:
            update_status(ost, nst, rest, rdu(d + '03_检校意见.md') if os.path.isfile(d + '03_检校意见.md') else '')
        except FlowError as error:
            errs.append(f'5c {tid} {error}')
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
    require(not errs, 'check05失败，未写入：' + '；'.join(errs))
    if warns:
        print('\n'.join(warns))


# ---------- fix from 03 ----------
def fix(n, dry=False):
    d = cdir(n)
    data = state(n)
    if data.get('fix', {}).get('files') == fingerprints(drafts(n)):
        gate(n, 'fix')
        print('fix已落实，当前版本未变')
        return
    data = gate(n)
    s = read_review(n)
    content = section(s, '三、逐字改法')
    chunks = re.split(r'(?m)^(?=### F\d+)', content)
    files = {}
    res = []
    ids = set()
    errors = []
    for ch in chunks:
        mh = re.match(r'### (F\d+)\D*?(04|05)', ch)
        if not mh:
            continue
        fid, which = mh.group(1), mh.group(2)
        require(fid not in ids, '重复修改编号：' + fid)
        ids.add(fid)
        mm = re.search(r'旧：[ \t]*\n(~~~|```)[^\n]*\n(.*?)\n\1[ \t]*\n\s*新：[ \t]*\n(~~~|```)[^\n]*\n(.*?)\n\3', ch, re.S)
        if not mm:
            res.append((fid, which, '无法解析'))
            errors.append(fid + '无法解析')
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
            errors.append(f'{fid}旧文出现{k}次')
            continue
        files[p][0] = t.replace(o, w, 1)
        res.append((fid, which, '已改'))
    for r in res:
        print(*r)
    require(len(res) == len(re.findall(r'^### F\d+', content, re.M)), '存在未解析的修改标题')
    require(res or content in ('无', '无。'), '修改清单为空且未明确写无')
    require(not errors, '整批未保存：' + '；'.join(errors))
    if not dry:
        changes = {p: t for p, (t, nl) in files.items()}
        expected = {R + p: h for p, h in data['review']['files'].items()}
        folder = snapshot(n, '逐字修改前')
        result_hashes = fingerprints(drafts(n))
        result_hashes.update({os.path.relpath(p, R).replace('\\', '/'): hashlib.sha256(t.encode('utf-8')).hexdigest()
                              for p, t in changes.items()})
        data['fix'] = {'files': result_hashes, 'ids': sorted(ids), 'history': os.path.relpath(folder, R).replace('\\', '/')}
        f = d + '07_执行与验收.md'
        expected[f] = digest(f)
        changes[f] = state_text(n, data)
        write_batch(changes, expected)
    print('fix', f'{n:03d}', '共', len(res), '条，已改', sum(1 for r in res if r[2] == '已改'), '（dry）' if dry else '')


# ---------- global write ----------
def g7(n, dry=False):
    require(not accepted(n), '已完成章节须先登记定点返修范围')
    data = gate(n, 'fix')
    check05(n)
    expected = {p: digest(p) for p in global_paths() + drafts(n)}
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
    k = max(kk for kk, l in enumerate(TL[:ah]) if l.startswith('|'))
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
        st, rest = update_status(ost, st, rest, rdu(drafts(n)[0]))
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
    reopened = [l for l in TL[ah:] if l.startswith('| CH') and l.split('|')[5].strip() in ('开放', '部分回指')]
    head = [l for l in TL[:ah] if l not in moved]
    insert = len(head)
    while insert and not head[insert - 1].strip():
        insert -= 1
    head[insert:insert] = reopened
    TL = head + [l for l in TL[ah:] if l not in reopened] + moved
    TL += ['']
    out[REG] = nl.join(TL)
    rows = [l for l in TL if l.startswith('| CH')]
    cnt = collections.Counter('并入' if r.split('|')[5].strip().startswith('并入') else r.split('|')[5].strip() for r in rows)
    print('open', len(openrows), 'arch', len(archrows), 'moved', [l.split('|')[1].strip() for l in moved],
          'total', len(rows), dict(cnt))
    if dry:
        print('dry run, nothing written')
        return
    folder = snapshot(n, '全局写入前', global_paths())
    hashes = fingerprints(global_paths())
    hashes.update({os.path.relpath(p, R).replace('\\', '/'): hashlib.sha256(text.encode('utf-8')).hexdigest()
                   for p, text in out.items()})
    data['g7'] = {'globals': hashes, 'files': fingerprints(drafts(n)),
                  'history': os.path.relpath(folder, R).replace('\\', '/')}
    f = cdir(n) + '07_执行与验收.md'
    expected[f] = digest(f)
    out[f] = state_text(n, data)
    write_batch(out, expected)
    for f, b in ((QT, qd), (PT, pp), (README, story), (README, row)):
        print(os.path.basename(f), b.strip() in rd(f)[0].replace('\r\n', '\n'))


def global_paths():
    return [QT, PT, README, REG, PROG]


def navigation(n):
    N = f'{n:03d}'
    C = cnum(n)
    rows = [l for l in rdu(REG).split('\n') if l.startswith('| CH')]
    cnt = collections.Counter('并入' if r.split('|')[5].strip().startswith('并入') else r.split('|')[5].strip() for r in rows)
    tot, op, pa, hu, bi = len(rows), cnt['开放'], cnt['部分回指'], cnt['已回指'], cnt['并入']
    zhu = len(current_q(n + 1))

    out = {}
    def rep(f, ln, new):
        s, nl = rd(f)
        L = s.split(nl)
        L[ln - 1] = new
        out[f] = nl.join(L)

    rep(QT, 2, f'当前有效问题交接截至第{C}回末；自第七十一回起执行[快速流程3.1](../{FAST})。完整状态以[第{BASE:03d}回完整清单](../章节/第{BASE:03d}回/05_追踪与交接.md#complete-list)为基线，加第{BASE + 1:03d}回起各回05的“问题清单变更”（最新见[第{N}回](../章节/第{N}回/05_追踪与交接.md#qchanges)），现共{zhu}个累计主项（含已答、归并与分歧，不是未解数）；最新[{n}回增量](#ch{N}-delta)。线索另见[全局线索登记](线索登记.md)。')
    rep(PT, 2, f'当前有效人物交接截至第{C}回末；自第七十一回起执行快速流程3.1。最新[{n}回人物增量](#ch{N}-people)、[成稿](../章节/第{N}回/04_修订定稿.md)。此前身份、职司、责任、受影响者与未知按有效旧据保持。')
    rep(README, 3, f'本地阅读材料到第{C}回末。自第七十一回起按[快速流程3.1]({FAST})：一人顺序通读后写成稿，另一人先自读原文再复核。可直接读[第{C}回成稿](章节/第{N}回/04_修订定稿.md)；问题状态见[全局问题表](全书追踪/待解问题与修订记录.md)，线索见[全局线索登记](全书追踪/线索登记.md)。全书人物档案尚未整合。')
    s, nl = rd(REG)
    s2 = re.sub(r'最新：第\d{3}回G7写入[^\n]*?。(?=\r?\n)',
                f'最新：第{N}回G7写入，现共{tot}条（开放{op}、部分回指{pa}、已回指{hu}、并入Q {bi}），见[第{N}回05](../章节/第{N}回/05_追踪与交接.md#clues)。', s, 1)
    if s2 == s:
        print('WARN register status line not replaced')
    out[REG] = s2
    s, nl = rd(PROG)
    L = s.split(nl)
    next_step = (f'下一步第{cnum(n + 1)}回。' if n < 100 else
                 '本底本逐回任务完成，全书整合尚未启动。')
    L[1] = (f'持续执行（2026-10-30起快速流程3.1）：第{C}回完成，累计主项{zhu}，线索登记{tot}条。'
            f'见[成稿](../章节/第{N}回/04_修订定稿.md)、[追踪](../章节/第{N}回/05_追踪与交接.md)、[记录](../章节/第{N}回/07_执行与验收.md#accepted)。本地提交以07后续记录为准，不推送；{next_step}')
    out[PROG] = nl.join(L)
    return out


def nav(n):
    data = gate(n, 'g7')
    require(data['g7']['globals'] == fingerprints(global_paths()), '全局与已写版本不符')
    navigation(n)  # 验证可生成；完成导航与accepted由accept同批保存。
    data['nav'] = {'files': fingerprints(drafts(n)), 'time': now()}
    wr(cdir(n) + '07_执行与验收.md', state_text(n, data))
    print('nav已核；全局当前回目保持至总编accept')


def main():
    a = sys.argv[1:]
    cmd = a[0]
    if cmd == 'setup':
        setup()
    elif cmd == 'views':
        views(int(a[1]))
    elif cmd == 'deps':
        deps(int(a[1]))
    elif cmd == 'review':
        require(len(a) >= 4 and a[2] == '--note', '用法：review NNN --note 实际核查范围与结论')
        review(int(a[1]), a[3])
    elif cmd == 'snapshot':
        require(len(a) >= 3, '用法：snapshot NNN 原因')
        print(snapshot(int(a[1]), a[2]))
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
        accept(int(a[1]), a[3] if len(a) >= 4 and a[2] == '--note' else None)
    else:
        print(__doc__)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except (FlowError, OSError, ValueError, AssertionError, IndexError, KeyError) as error:
        print('停止：' + str(error), file=sys.stderr)
        sys.exit(1)
