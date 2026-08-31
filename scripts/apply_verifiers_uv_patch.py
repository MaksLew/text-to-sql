#!/usr/bin/env python3
from pathlib import Path

import verifiers.v1.runtimes.base as runtime_base

path = Path(runtime_base.__file__)
old = '''    "pip install -q -U --user uv 2>/dev/null "
    f"|| {{ {_INSTALL_CURL}; {_DOWNLOAD_UV}; }}"
'''
new = '''    "{ command -v uv >/dev/null 2>&1 "
    "&& uv sync --help 2>/dev/null | grep -q -- --script; } "
    "|| pip install -q -U --user uv 2>/dev/null "
    f"|| {{ {_INSTALL_CURL}; {_DOWNLOAD_UV}; }}"
'''
text = path.read_text()
if new in text:
    print(f"Already patched: {path}")
elif old not in text:
    raise SystemExit(f"Pinned Verifiers bootstrap code not found: {path}")
else:
    path.write_text(text.replace(old, new, 1))
    print(f"Patched: {path}")
