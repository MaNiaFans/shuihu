"""流程故障回归：只在独立临时目录使用虚构短文，不读小说、不登记真实验收。"""
import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FlowTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('fast_under_test', Path(__file__).with_name('fast_tools.py'))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.temp = tempfile.TemporaryDirectory(prefix='shuihu-flow-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.m.R = self.root.as_posix() + '/'
        for key, relative in {'TMP': '.venv/tmp/', 'QT': '全书追踪/待解问题与修订记录.md',
                              'PT': '全书追踪/人物称谓与身份.md', 'REG': '全书追踪/线索登记.md',
                              'README': 'README.md', 'PROG': '全书追踪/进度.md'}.items():
            setattr(self.m, key, self.m.R + relative)
        self.put('章节/第070回/07_执行与验收.md', '<a id="accepted"></a>\n当前状态：**第070回G1—G7验收通过。**\n')
        self.put('章节/第070回/04_修订定稿.md', 'previous\n')
        self.full_status = 'a已经回答。' + '已有经过；' * 45 + 'CH001-Q01-b待追踪；CH001-Q01-c未详。'
        self.put('章节/第070回/05_追踪与交接.md',
                 '## 四、完整状态清单\n| 1 | CH001-Q01 长题 | ' + self.full_status +
                 ' | [依据](#source) |\n<a id="clues"></a>\n')
        self.put('章节/第071回/07_执行与验收.md', '# prepared\n')
        self.put('章节/第071回/04_修订定稿.md', 'alpha\nbeta\n')
        self.put('章节/第071回/03_检校意见.md', self.review_text())
        self.put('章节/第071回/05_追踪与交接.md', self.handoff())
        self.put('全书追踪/待解问题与修订记录.md', '# questions\nold current\n')
        self.put('全书追踪/人物称谓与身份.md', '# people\nold current\n')
        self.put('全书追踪/进度.md', '# progress\n第七十回完成\n')
        self.put('全书追踪/线索登记.md',
                 '# clues\n最新：第070回G7写入，共1条。\n## 开放与部分回指\n'
                 '| CH001-T01 | L1 | old | 信息 | 开放 | old end | 第001回05 |\n## 归档\n')
        self.put('README.md', '# read\n\n第七十回\n\n[第七十回《old》](x)：old\n'
                 '| [第七十回](x) | old | unknown |\n')

    def put(self, relative, text):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode('utf-8'))
        return p

    def call(self, method, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return getattr(self.m, method)(*args)

    def read(self, relative):
        return (self.root / relative).read_text(encoding='utf-8')

    def review_text(self, extra='', blocker='无。'):
        return ('## 一、自读要点\n虚构短文顺序自读后记下要点。\n## 二、核对范围\n'
                '全文与交接核过。前回定稿差额：虚构前回已完成，相关差额已核。\n'
                '## 三、逐字改法\n### F01 · 04\n旧：\n~~~\nalpha\n~~~\n新：\n~~~\nALPHA\n~~~\n'
                + extra + '\n## 四、需写稿者处理\n' + blocker + '\n')

    def handoff(self):
        blocks = ['<a id="ch071-delta"></a>\nquestion delta',
                  '<a id="ch071-people"></a>\npeople delta',
                  '[第七十一回《test》](章节/第071回/04_修订定稿.md)：story',
                  '| [第七十一回](章节/第071回/04_修订定稿.md) | point | unknown |']
        return ('## 一、读取范围\n虚构材料。\n<a id="qchanges"></a>\n'
                '| 编号 | 题名 | 状态 | 依据 |\n| --- | --- | --- | --- |\n'
                '<a id="clues"></a>\n## 四、线索\n'
                '| CH071-T01 | L1 | new | 信息 | 开放 | end | 第071回05 |\n'
                '<a id="candidates"></a>\n' +
                '\n'.join('```markdown\n' + x + '\n```' for x in blocks) +
                '\n**5c. 现有行修改：**\n'
                '- **CH001-T01**　状态：部分回指。回指／去向末尾追加：；→第071回L1；信息到达\n')

    def prepare_fix(self):
        self.call('review', 71, '总编实际核查虚构稿及独立复核意见，前回差额已核。')

    def test_full_status_and_child_ids_survive_views(self):
        self.call('views', 71)
        text = self.read('.venv/tmp/问题简表_071.md')
        self.assertIn(self.full_status, text)
        self.assertIn('CH001-Q01-c未详', text)
        data = self.m.state(71)
        self.assertTrue((self.root / data['input']['snapshot'] / '问题简表_071.md').exists())

    def test_failed_second_patch_leaves_every_original_unchanged(self):
        extra = '### F02 · 04\n旧：\n~~~\nmissing\n~~~\n新：\n~~~\nNEW\n~~~\n'
        self.put('章节/第071回/03_检校意见.md', self.review_text(extra))
        self.prepare_fix()
        before = (self.root / '章节/第071回/04_修订定稿.md').read_bytes()
        record = (self.root / '章节/第071回/07_执行与验收.md').read_bytes()
        with self.assertRaises(self.m.FlowError):
            self.call('fix', 71)
        self.assertEqual(before, (self.root / '章节/第071回/04_修订定稿.md').read_bytes())
        self.assertEqual(record, (self.root / '章节/第071回/07_执行与验收.md').read_bytes())
        self.assertNotIn('fix', self.m.state(71))

    def test_patch_with_header_in_fence_and_crlf_keeps_source_history(self):
        self.put('章节/第071回/04_修订定稿.md', '## alpha\r\nbeta\r\n')
        text = self.review_text().replace('\nalpha\n', '\n## alpha\n').replace('\nALPHA\n', '\n## ALPHA\n')
        self.put('章节/第071回/03_检校意见.md', text)
        self.prepare_fix()
        self.call('fix', 71)
        data = self.m.state(71)['fix']
        self.assertEqual((self.root / data['history'] / '04_修订定稿.md').read_bytes(), b'## alpha\r\nbeta\r\n')
        self.assertEqual((self.root / '章节/第071回/04_修订定稿.md').read_bytes(), b'## ALPHA\r\nbeta\r\n')

    def test_accept_without_review_and_g7_cannot_advance(self):
        before = self.read('全书追踪/进度.md')
        with self.assertRaises(self.m.FlowError):
            self.call('accept', 71, '总编实际核验说明不能替代缺失的步骤证据。')
        self.assertFalse(self.m.accepted(71))
        self.assertEqual(before, self.read('全书追踪/进度.md'))

    def test_blocker_and_incomplete_review_stop(self):
        self.put('章节/第071回/03_检校意见.md', self.review_text(blocker='需要作者回查虚构人物。'))
        with self.assertRaises(self.m.FlowError):
            self.prepare_fix()

    def test_append_only_review_uses_current_batch_and_preserves_old_opinions(self):
        old = self.review_text(blocker='B01：需要作者回查虚构人物。')
        new = old + ('\n## 二、核对范围（R02）\n前回定稿差额：已核。作者已处理B01，复核改处与依赖后关闭。\n'
                     '## 三、逐字改法（R02）\n无。\n## 四、需写稿者处理（R02）\n无。\n')
        self.put('章节/第071回/03_检校意见.md', new)
        self.prepare_fix()
        self.call('fix', 71)
        self.assertIn(old, self.read('章节/第071回/03_检校意见.md'))
        self.assertEqual('alpha\nbeta\n', self.read('章节/第071回/04_修订定稿.md'))
        self.put('章节/第071回/03_检校意见.md', '## 一、自读要点\n只有要点。\n')
        with self.assertRaises(self.m.FlowError):
            self.prepare_fix()

    def test_predecessor_must_be_final_for_review(self):
        self.put('章节/第070回/07_执行与验收.md', '# not accepted\n')
        with self.assertRaises(self.m.FlowError):
            self.prepare_fix()

    def test_predecessor_change_invalidates_review(self):
        self.prepare_fix()
        self.put('章节/第070回/05_追踪与交接.md', 'changed predecessor\n')
        with self.assertRaises(self.m.FlowError):
            self.call('fix', 71)

    def test_new_input_snapshot_does_not_retroactively_validate_old_review(self):
        text = self.review_text().replace('前回定稿差额：虚构前回已完成，相关差额已核。', '此前检查未记录最终交接差额。')
        self.put('章节/第071回/03_检校意见.md', text)
        self.call('views', 71)
        with self.assertRaises(self.m.FlowError):
            self.prepare_fix()

    def test_draft_change_invalidates_review(self):
        self.prepare_fix()
        self.put('章节/第071回/04_修订定稿.md', 'changed draft\n')
        with self.assertRaises(self.m.FlowError):
            self.call('fix', 71)

    def test_pending_reference_blocks_global_write(self):
        self.put('章节/第071回/05_追踪与交接.md', self.handoff() + '\n- 待并**CH070-T01**\n')
        self.prepare_fix()
        self.call('fix', 71)
        before = self.read('全书追踪/线索登记.md')
        with self.assertRaises(self.m.FlowError):
            self.call('g7', 71)
        self.assertEqual(before, self.read('全书追踪/线索登记.md'))

    def test_status_correction_requires_review_evidence_and_is_not_silently_ignored(self):
        with self.assertRaises(self.m.FlowError):
            self.m.update_status('部分回指', '开放', '：只有候选', '')
        why = '。状态更正依据：F01 两端不能支持原判'
        new, rest = self.m.update_status('部分回指', '开放', '：只有候选' + why, why)
        self.assertEqual(('开放', '：只有候选'), (new, rest))
        self.assertEqual('部分回指', self.m.update_status('部分回指', '沿用', '：新增候选', '')[0])
        with self.assertRaises(self.m.FlowError):
            self.m.update_status('撤销', '开放', '：重开但无依据', '')

    def test_reopened_clue_moves_back_to_open_view(self):
        self.put('全书追踪/线索登记.md',
                 '# clues\n最新：第070回G7写入，共1条。\n## 开放与部分回指\n'
                 '| 编号 | 位置 | 文本 | 类别 | 状态 | 回指 | 来源 |\n| --- | --- | --- | --- | --- | --- | --- |\n'
                 '## 归档\n| CH001-T01 | L1 | old | 信息 | 已回指 | old end | 第001回05 |\n')
        why = '。状态更正依据：F02 已核旧判证据不成立'
        self.put('章节/第071回/05_追踪与交接.md', self.handoff().replace('状态：部分回指。', '状态：开放。').rstrip() + why + '\n')
        self.put('章节/第071回/03_检校意见.md', self.review_text().replace('全文与交接核过。', '全文与交接核过。' + why))
        self.prepare_fix()
        self.call('fix', 71)
        self.call('g7', 71)
        text = self.read('全书追踪/线索登记.md')
        self.assertLess(text.index('| CH001-T01 '), text.index('## 归档'))
        self.put('章节/第072回/07_执行与验收.md', '# prepared\n')
        self.call('views', 72)
        self.assertIn('| CH001-T01 ', self.read('.venv/tmp/线索简表_072.md'))

    def test_old_accept_anchor_does_not_override_need_review(self):
        for status in ('需复审。', '未完成。', '尚未完成内容检查。', '第七十回完成，待核。'):
            with self.subTest(status=status):
                self.put('章节/第070回/07_执行与验收.md', '<a id="accepted"></a>\n当前状态：' + status + '\n')
                with self.assertRaises(self.m.FlowError):
                    self.prepare_fix()

    def test_batch_save_failure_rolls_back(self):
        a = self.put('a.txt', 'a')
        b = self.put('b.txt', 'b')
        real_replace = self.m.os.replace
        count = 0
        def fail_second(src, dst):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('simulated disk failure')
            return real_replace(src, dst)
        with patch.object(self.m.os, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                self.m.write_batch({str(a): 'A', str(b): 'B'})
        self.assertEqual(('a', 'b'), (a.read_text(), b.read_text()))

    def test_full_pipeline_only_accept_advances_navigation(self):
        self.prepare_fix()
        self.call('fix', 71)
        self.call('g7', 71)
        self.assertIn('第七十回完成', self.read('全书追踪/进度.md'))
        self.call('nav', 71)
        self.assertFalse(self.m.accepted(71))
        self.assertIn('第七十回完成', self.read('全书追踪/进度.md'))
        self.call('accept', 71, '总编实读复核意见、修改差异与五处全局落点，确认虚构用例闭合。')
        self.assertTrue(self.m.accepted(71))
        self.assertIn('第七十一回完成', self.read('全书追踪/进度.md'))
        self.assertIn('待本地提交', self.read('章节/第071回/07_执行与验收.md'))
        self.assertEqual(self.m.state(71)['accept']['globals'], self.m.fingerprints(self.m.global_paths()))
        self.m.require_previous(72)
        self.put('章节/第071回/05_追踪与交接.md', 'changed after accept\n')
        with self.assertRaises(self.m.FlowError):
            self.m.require_previous(72)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    unittest.main()
