import os
import pytest
from thefuck.rules.cd_correction import match, get_new_command, _get_sub_dirs
from thefuck.types import Command


@pytest.mark.parametrize('command', [
    Command('cd foo', 'cd: foo: No such file or directory'),
    Command('cd foo/bar/baz',
            'cd: foo: No such file or directory'),
    Command('cd foo/bar/baz', 'cd: can\'t cd to foo/bar/baz'),
    Command('cd /foo/bar/', 'cd: The directory "/foo/bar/" does not exist')])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('cd foo', ''), Command('', '')])
def test_not_match(command):
    assert not match(command)


# Virtual directory tree for get_new_command / _get_sub_dirs tests:
#
# /
# ├── home/
# │   └── user/
# │       ├── documents/
# │       ├── downloads/
# │       ├── projects/
# │       │   ├── myapp/
# │       │   │   ├── src/
# │       │   │   └── tests/
# │       │   └── webapp/
# │       ├── 项目文档/
# │       │   └── 设计稿/
# │       ├── my folder/
# │       │   └── sub dir/
# │       └── file.txt  (not a directory)

_FAKE_FS = {
    '/': ['home', 'usr', 'tmp'],
    '/home': ['user'],
    '/home/user': ['documents', 'downloads', 'projects',
                   '\u9879\u76ee\u6587\u6863', 'my folder', 'file.txt'],
    '/home/user/projects': ['myapp', 'webapp'],
    '/home/user/projects/myapp': ['src', 'tests'],
    '/home/user/\u9879\u76ee\u6587\u6863': ['\u8bbe\u8ba1\u7a3f'],
    '/home/user/my folder': ['sub dir', 'notes.txt'],
}

_FAKE_DIRS = {
    '/', '/home', '/usr', '/tmp',
    '/home/user',
    '/home/user/documents', '/home/user/downloads', '/home/user/projects',
    '/home/user/\u9879\u76ee\u6587\u6863', '/home/user/my folder',
    '/home/user/projects/myapp', '/home/user/projects/webapp',
    '/home/user/projects/myapp/src', '/home/user/projects/myapp/tests',
    '/home/user/\u9879\u76ee\u6587\u6863/\u8bbe\u8ba1\u7a3f',
    '/home/user/my folder/sub dir',
}


@pytest.fixture
def mock_fs(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda p: list(_FAKE_FS.get(p, [])))
    monkeypatch.setattr(os.path, 'isdir', lambda p: p in _FAKE_DIRS)
    monkeypatch.setattr(os, 'getcwd', lambda: '/home/user')


# ===================== _get_sub_dirs tests =====================

@pytest.mark.parametrize('parent, expected', [
    ('/home/user', ['documents', 'downloads', 'projects',
                    '\u9879\u76ee\u6587\u6863', 'my folder']),
    ('/home/user/projects', ['myapp', 'webapp']),
])
def test_get_sub_dirs_returns_only_dirs(mock_fs, parent, expected):
    """file.txt and notes.txt should be filtered out."""
    assert _get_sub_dirs(parent) == expected


def test_get_sub_dirs_with_unicode(mock_fs):
    assert _get_sub_dirs('/home/user/\u9879\u76ee\u6587\u6863') == ['\u8bbe\u8ba1\u7a3f']


def test_get_sub_dirs_empty_dir(mock_fs):
    assert _get_sub_dirs('/home/user/documents') == []


# ===================== get_new_command tests =====================

@pytest.mark.parametrize('script, expected', [
    # single directory typo
    ('cd documens',
     'cd "/home/user/documents"'),
    # multi-level nested path correction
    ('cd projets/myap/scr',
     'cd "/home/user/projects/myapp/src"'),
    # absolute path correction
    ('cd /hom/usr',
     'cd "/home/user"'),
    # trailing slash stripped correctly
    ('cd documens/',
     'cd "/home/user/documents"'),
    # dot and dotdot navigation
    ('cd ./projets/../documens',
     'cd "/home/user/documents"'),
    # Unicode (Chinese) directory name correction
    ('cd \u9879\u76ee\u6587\u88c6',
     'cd "/home/user/\u9879\u76ee\u6587\u6863"'),
    # path with spaces (quoted)
    ('cd "my foulder"',
     'cd "/home/user/my folder"'),
    # multi-level path with spaces
    ('cd "my foulder/sub dri"',
     'cd "/home/user/my folder/sub dir"'),
])
def test_get_new_command(mock_fs, script, expected):
    cmd = Command(script, 'cd: No such file or directory')
    assert get_new_command(cmd) == expected


@pytest.mark.parametrize('script', [
    # completely unrecognizable directory name
    'cd zzzzzzz',
    # deep path where a subdirectory cannot be matched
    'cd documents/totally_nonexistent',
])
def test_get_new_command_fallback_to_cd_mkdir(mock_fs, monkeypatch, script):
    sentinel = 'mkdir -p fallback && cd fallback'
    monkeypatch.setattr(
        'thefuck.rules.cd_mkdir.get_new_command',
        lambda c: sentinel)
    cmd = Command(script, 'cd: No such file or directory')
    assert get_new_command(cmd) == sentinel
