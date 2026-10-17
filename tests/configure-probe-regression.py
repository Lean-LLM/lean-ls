#!/usr/bin/env python3
"""A nonzero wcwidth probe is a feature result, never a configure failure."""
from pathlib import Path
import os
import subprocess
import tempfile
import shutil

SOURCE = Path(__file__).resolve().parents[1] / 'configure'
with tempfile.TemporaryDirectory(prefix='lean-ls-probe-') as name:
    tmp = Path(name)
    shutil.copy2(SOURCE, tmp / 'configure')
    compiler = tmp / 'cc-probe'
    compiler.write_text('''#!/bin/bash
set -e
out=
args=("$@")
for ((i=0; i<${#args[@]}; ++i)); do
  if [[ ${args[i]} == -o ]]; then out=${args[i+1]}; break; fi
done
/usr/bin/cc "$@"
if [[ $out == build/probe_wcwidth_works ]]; then
  printf '#!/bin/sh\\nexit 8\\n' > "$out"
  chmod +x "$out"
fi
''')
    compiler.chmod(0o755)
    completed = subprocess.run(['/bin/sh', './configure'], cwd=tmp,
                               env={**os.environ, 'CC': str(compiler)},
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise AssertionError(f'configure returned {completed.returncode}: {completed.stderr}')
    text = (tmp / 'config.h').read_text()
    if '#define LISZT_REPLACE_WCWIDTH 1' not in text:
        raise AssertionError('nonzero probe did not enable replacement')
    print('PASS: nonzero feature probe does not abort configure')
