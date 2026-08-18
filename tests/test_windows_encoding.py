"""Windows-compatibility tests for python_check (UTF-8 in subprocess + temp file).

python_check spawns ruff/pyright and reads their output, and writes a temp file
for the check_content() path. On native Windows, a text-mode subprocess read or
temp-file write with no explicit encoding uses the locale codepage (cp1252):
- reading ruff/pyright UTF-8 output -> UnicodeDecodeError (crash) or mangling;
- writing non-ASCII source to the temp file -> UnicodeEncodeError (crash) before
  the checks even run.

Both are fixed by pinning encoding="utf-8". The source-inspection test below has
real teeth on Linux (the un-fixed source lacks the encoding); the runtime test
has teeth on Windows (the un-fixed code crashes there on non-ASCII).
"""

import re
from pathlib import Path

import amplifier_bundle_python_dev.checker as checker_mod
from amplifier_bundle_python_dev.checker import check_content


def test_every_subprocess_run_and_tempfile_pin_utf8():
    """Teeth on Linux: the un-fixed source has bare text=True / no temp encoding."""
    src = Path(checker_mod.__file__).read_text(encoding="utf-8")

    # Every subprocess.run(...) call that reads tool output must pin utf-8.
    runs = re.findall(r"subprocess\.run\((.*?)\)", src, flags=re.DOTALL)
    assert runs, "expected to find subprocess.run calls in checker.py"
    for call in runs:
        assert 'encoding="utf-8"' in call, (
            "a subprocess.run call decodes tool output without encoding='utf-8' "
            "(cp1252 on Windows -> crash/mangle on non-ASCII)"
        )

    # No bare `text=True)` without an encoding must survive.
    assert "capture_output=True, text=True)" not in src

    # The check_content temp file must be written as utf-8.
    assert 'delete=False, encoding="utf-8"' in src


def test_check_content_nonascii_does_not_crash():
    """Teeth on Windows: the un-fixed temp-file write crashes on non-ASCII here.

    On Linux this passes regardless (tempfile default is utf-8), so it is a
    documentation/regression guard here and a real crash-vs-no-crash teeth on
    native Windows.
    """
    source = "# caf\u00e9 \u2713 \u2014 \u65e5\u672c\u8a9e\nx = 1\n"
    # Must return a CheckResult, not raise UnicodeEncodeError/DecodeError.
    result = check_content(source, filename="unicode_sample.py")
    assert result is not None
    assert hasattr(result, "issues")
