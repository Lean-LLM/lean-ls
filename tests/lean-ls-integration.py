#!/usr/bin/env python3
"""Integration tests for GNU-compatible default, strict, and lla routing.

Uses only Python standard library. Run from package root.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get('LEAN_LS_TEST_BINARY', str(ROOT / 'lean-ls')))
GNU = os.environ.get('LEAN_LS_TEST_GNU', '/usr/bin/ls' if Path('/usr/bin/ls').is_file() else '/bin/ls')
CHECKS = 0


def run(argv, env, cwd=None):
    return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, cwd=cwd, check=False)


def expect(condition, label):
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(label)


with tempfile.TemporaryDirectory(prefix='lean-ls-test-') as scratch:
    p = Path(scratch)
    fixture = p / 'fixture'
    fixture.mkdir()
    (fixture / 'sub dir').mkdir()
    (fixture / 'sub dir' / 'child').write_text('child')
    (fixture / 'b file').write_text('abc')
    (fixture / 'a-file.log').write_text('a')
    (fixture / '.hidden').write_text('h')
    (fixture / 'link').symlink_to('a-file.log')
    (fixture / 'broken-link').symlink_to('nonexistent')
    (fixture / 'executable').write_text('#!/bin/sh\n')
    (fixture / 'executable').chmod(0o755)
    env = dict(os.environ, LC_ALL='C', TZ='UTC0', COLUMNS='80', LS_COLORS='')
    for flags in ((), ('-1',), ('-l',), ('-la',), ('-laF',), ('-lS',),
                  ('-lt',), ('-lr',), ('-lR',), ('-U1',), ('-C',), ('-x',),
                  ('-m',), ('-h',), ('-n',), ('-Q',), ('-F',), ('--zero',),
                  ('--time-style=long-iso',), ('--group-directories-first',),
                  ('--quoting-style=shell-escape',), ('--color=always',)):
        args = (*flags, str(fixture))
        baseline = run([GNU, *args], env)
        candidate = run([str(BINARY), *args], env)
        expect((candidate.returncode, candidate.stdout) ==
               (baseline.returncode, baseline.stdout), f'GNU parity: {args}')

    for flags in ((), ('-l',), ('--version',), ('--help',),
                  ('--hyperlink=always',)):
        args = (*flags, str(fixture)) if '--help' not in flags and '--version' not in flags else flags
        baseline = subprocess.run(['/usr/bin/ls', *args], executable=GNU,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=env, check=False)
        candidate = run([str(BINARY), '--lean-strict', *args], env)
        expect((candidate.returncode, candidate.stdout, candidate.stderr) ==
               (baseline.returncode, baseline.stdout, baseline.stderr),
               f'GNU strict: {args}')

    # System-wide ls entrypoint must always invoke genuine GNU without
    # honoring LEAN_LS_LLA or LEAN_LS_GNU_LS environment switches.
    ls_entry = p / 'ls'
    ls_entry.symlink_to(BINARY)
    poisoned = {**env, 'LEAN_LS_LLA': '/missing/lla',
                'LEAN_LS_GNU_LS': '/missing/gnu'}
    for flags in ((), ('-l',), ('-lR',), ('--version',),
                  ('--help',), ('--definitely-invalid',),
                  ('--color=always',), ('--hyperlink=always',),
                  ('--quoting-style=shell-escape',)):
        args = (*flags, str(fixture)) if '--version' not in flags and '--help' not in flags else flags
        reference = subprocess.run([str(ls_entry), *args], executable=GNU,
                                   capture_output=True, env=env, check=False)
        actual = run([str(ls_entry), *args], poisoned)
        expect((reference.returncode, reference.stdout, reference.stderr) ==
               (actual.returncode, actual.stdout, actual.stderr),
               f'exact ls alias: {args}')
    # GNU input/environment matrix: exact parity must include stderr/status
    # under color, locale, quoting, and error handling, not merely filenames.
    (fixture / 'line\nbreak').write_text('')
    (fixture / 'tab\tname').write_text('')
    for changes in ({'LC_ALL': 'C'}, {'LC_ALL': 'C.UTF-8'},
                    {'LS_COLORS': 'di=01;33:ex=01;32'},
                    {'TIME_STYLE': 'full-iso'},
                    {'BLOCK_SIZE': '1K'},
                    {'POSIXLY_CORRECT': '1'}):
        testenv = {**poisoned, **changes}
        for flags in (('-la',), ('-1',), ('-l', '--color=always'),
                      ('-C', '-w', '80'), ('--zero',)):
            args = (*flags, str(fixture))
            reference = subprocess.run([str(ls_entry), *args], executable=GNU,
                                       capture_output=True, env=testenv, check=False)
            actual = run([str(ls_entry), *args], testenv)
            expect((reference.returncode, reference.stdout, reference.stderr) ==
                   (actual.returncode, actual.stdout, actual.stderr),
                   f'ls exact env matrix: {changes} {args}')

    # The kernel exec filename is authoritative even if a subprocess supplies
    # a misleading argv[0], including one that does not say "ls".
    for flags in (('-la',), ('--help',), ('--bad-option',)):
        args = ['custom-process-name', *flags]
        reference = subprocess.run(args, executable=GNU, capture_output=True,
                                   env=env, check=False)
        actual = subprocess.run(args, executable=str(ls_entry),
                                capture_output=True, env=poisoned, check=False)
        expect((reference.returncode, reference.stdout, reference.stderr) ==
               (actual.returncode, actual.stdout, actual.stderr),
               f'execve with overridden argv[0]: {args}')

    # '--json' remains unsupported by GNU ls, never rerouted to lla.
    baseline = subprocess.run([str(ls_entry), '--json'], executable=GNU,
                              capture_output=True, env=env, check=False)
    candidate = run([str(ls_entry), '--json'], poisoned)
    expect((baseline.returncode, baseline.stdout, baseline.stderr) ==
           (candidate.returncode, candidate.stdout, candidate.stderr),
           'GNU ls flags are never repurposed')

    # Fake lla exercises routing even on machines without Rust installed.
    mock = p / 'lla-mock'
    mock.write_text('#!/bin/sh\nprintf "<%s>\\n" "$@"\n')
    mock.chmod(0o755)
    env['LEAN_LS_LLA'] = str(mock)
    for command, expected in ((['--lla', '-t', '-d', '3'], b'<-t>\n<-d>\n<3>\n'),
                              (['--json', str(fixture)],
                               f'<--json>\n<{fixture}>\n'.encode()),
                              (['--search', 'TODO', str(fixture)],
                               f'<--search>\n<TODO>\n<{fixture}>\n'.encode())):
        actual = run([str(BINARY), *command], env)
        expect(actual.returncode == 0 and actual.stdout == expected,
               f'lla dispatch: {command}')

    expect(run([str(BINARY), '--lean-strict', '--lla'], env).returncode == 2,
           'reject conflicting engines')
    no_lla = {**env, 'LEAN_LS_LLA': str(p / 'not-installed')}
    expect(run([str(BINARY), '--json'], no_lla).returncode == 127,
           'missing lla reports status 127')
    expect(run([str(BINARY), '--lean-version'], env).returncode == 0,
           'lean-ls version')

print(f'lean-ls integration: {CHECKS} checks passed')
