import pathlib
import re

from setuptools import setup

SCRIPT_PATH = pathlib.Path(__file__).parent / 'ustvgo_iptv.py'
match = re.search(r'^VERSION\s*=\s*[\'"](?P<version>.+?)[\'"]\s*',
                  SCRIPT_PATH.read_text(encoding='utf-8'), re.M)
assert match
VERSION = match.group('version')

if __name__ == '__main__':
    setup(version=VERSION)
