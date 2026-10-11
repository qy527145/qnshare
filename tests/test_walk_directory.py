# -*- coding: utf-8 -*-
"""
walk_directory 的单元测试

只测纯文件系统逻辑，不联网、不涉及七牛SDK。
运行: uv run python -m unittest discover -s tests
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from qnshare.utils import walk_directory  # noqa: E402


class WalkDirectoryTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='qnshare-walk-')
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _make(self, *parts):
        """在临时目录下创建一个文件，返回其路径"""
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('x')
        return path

    def _keys(self, **kwargs):
        return [rel for _, rel in walk_directory(self.root, **kwargs)]

    def test_nested_relative_key_uses_forward_slash(self):
        """嵌套文件的key必须用'/'分隔——Windows反斜杠回归防护"""
        self._make('a.jpg')
        self._make('2024', 'b.jpg')

        keys = self._keys()
        self.assertEqual(sorted(keys), ['2024/b.jpg', 'a.jpg'])
        for key in keys:
            self.assertNotIn('\\', key)

    def test_hidden_files_and_dirs_skipped_by_default(self):
        """默认跳过'.'开头的文件和整个隐藏目录树"""
        self._make('visible.txt')
        self._make('.hidden.txt')
        self._make('.git', 'config')

        self.assertEqual(self._keys(), ['visible.txt'])

    def test_include_hidden(self):
        """include_hidden=True时隐藏内容一并产出"""
        self._make('visible.txt')
        self._make('.hidden.txt')
        self._make('.git', 'config')

        keys = self._keys(include_hidden=True)
        self.assertEqual(sorted(keys), ['.git/config', '.hidden.txt', 'visible.txt'])

    def test_non_recursive_only_top_level(self):
        """非递归只产出第一层文件，子目录里的不产出"""
        self._make('a.jpg')
        self._make('2024', 'b.jpg')

        self.assertEqual(self._keys(recursive=False), ['a.jpg'])

    def test_order_is_stable(self):
        """两次遍历顺序一致，重复检测才可复现"""
        for name in ('c.txt', 'a.txt', 'b.txt'):
            self._make(name)
        self._make('sub', 'z.txt')
        self._make('sub', 'y.txt')

        self.assertEqual(self._keys(), self._keys())

    def test_empty_directory_yields_nothing(self):
        self.assertEqual(self._keys(), [])

    def test_on_skip_reports_hidden_paths(self):
        """被跳过的隐藏项通过on_skip上报，供调用方计数"""
        self._make('.hidden.txt')
        self._make('.git', 'config')

        skipped = []
        list(walk_directory(self.root, on_skip=skipped.append))

        self.assertEqual(len(skipped), 2)
        self.assertTrue(all(os.path.basename(p).startswith('.') for p in skipped))

    def test_directory_symlink_not_followed(self):
        """目录软链不被跟进，避免成环"""
        target = os.path.join(self.root, 'real')
        os.makedirs(os.path.join(target, 'inner'))
        with open(os.path.join(target, 'inner', 'f.txt'), 'w', encoding='utf-8') as f:
            f.write('x')

        link = os.path.join(self.root, 'link')
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest('当前环境不支持创建目录软链')

        keys = self._keys()
        self.assertIn('real/inner/f.txt', keys)
        self.assertNotIn('link/inner/f.txt', keys)


if __name__ == '__main__':
    unittest.main()
