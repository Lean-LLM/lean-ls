#!/usr/bin/env python3
"""Exercise install/upgrade/uninstall with paths and dpkg-divert state isolated.

Requires root; never changes real /usr/bin/ls or system dpkg diversions.
"""
import os
import shlex
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check(cmd, env, cwd, success=True):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=55)
    if (p.returncode == 0) != success:
        raise AssertionError(f'{cmd} exit={p.returncode}\n{p.stdout}\n{p.stderr}')
    return p


def build_mock_deb(temp):
    pkg = temp / 'pkg'
    (pkg / 'DEBIAN').mkdir(parents=True)
    (pkg / 'usr/bin').mkdir(parents=True)
    shutil.copy2('/usr/bin/ls', pkg / 'usr/bin/gnuls')
    (pkg / 'DEBIAN/control').write_text('Package: gnu-coreutils\nVersion: 1\nArchitecture: amd64\nMaintainer: test <test@example.com>\nDescription: test fixture\n')
    deb = temp / 'gnu-coreutils_fixture.deb'
    check(['dpkg-deb', '--build', str(pkg), str(deb)], os.environ, temp)
    return deb


def make_mock_tools(temp, deb):
    mock_bin = temp / 'mock-bin'
    mock_bin.mkdir()
    diversion = mock_bin / 'dpkg-divert'
    diversion.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
args=sys.argv[1:]
p=Path(os.environ['LEAN_LS_TEST_DIVERSION'])
if '--truename' in args:
    print(p.read_text().strip() if p.exists() else args[-1]); sys.exit(0)
if '--add' in args:
    if p.exists(): sys.exit(1)
    p.write_text(args[args.index('--divert')+1]); sys.exit(0)
if '--remove' in args:
    if not p.exists(): sys.exit(1)
    p.unlink();sys.exit(0)
sys.exit(2)
''')
    diversion.chmod(0o755)
    apt = mock_bin / 'apt-get'
    apt.write_text('#!/bin/sh\nif [ "$1" = download ] && [ "${2%%=*}" = gnu-coreutils ]; then cp "$LEAN_LS_TEST_DEB" ./gnu-coreutils_fixture.deb; else exit 1; fi\n')
    apt.chmod(0o755)
    return mock_bin


def make_sandbox(temp, binary_target, deb):
    fake = temp / 'fake-system'
    for path in ('usr/bin', 'usr/local/bin', 'usr/local/libexec'):
        (fake / path).mkdir(parents=True)
    sys = fake / 'usr/bin/ls'
    if binary_target is None:
        shutil.copy2('/usr/bin/ls', sys)
    else:
        sys.symlink_to(binary_target)
    (fake / 'bin').symlink_to('usr/bin')
    original = fake / 'usr/bin/ls.lean-ls-original'
    engine_dir = fake / 'usr/local/libexec/lean-ls'
    cli = fake / 'usr/local/bin/lean-ls'
    script = temp / 'scripts'
    script.mkdir()
    replacements = {
        'SYS=/usr/bin/ls': f'SYS={sys}',
        'GNU_INSTALLED=/usr/bin/gnuls': f'GNU_INSTALLED={fake / "usr/bin/gnuls"}',
        'ORIGINAL=/usr/bin/ls.lean-ls-original': f'ORIGINAL={original}',
        'ENGINE_DIR=/usr/local/libexec/lean-ls': f'ENGINE_DIR={engine_dir}',
        'ENGINE=/usr/local/libexec/lean-ls/lean-ls': f'ENGINE={engine_dir / "lean-ls"}',
        'LINK_BACKUP=/usr/local/libexec/lean-ls/preinstall-ls-symlink': f'LINK_BACKUP={engine_dir / "preinstall-ls-symlink"}',
        'CLI=/usr/local/bin/lean-ls': f'CLI={cli}',
        '/bin/ls)': f'{fake / "bin/ls"})',
        '/usr/local/bin/ls ': f'{fake / "usr/local/bin/ls"} ',
        'mkdir -p -- "$ENGINE_DIR" /usr/local/bin': 'mkdir -p -- "$ENGINE_DIR" "$(dirname "$CLI")"',
    }
    # ROOT points to source, not to the isolated installer copy.
    for filename in ('install.sh', 'uninstall.sh'):
        content = (ROOT / filename).read_text()
        content = content.replace('ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)', f'ROOT={ROOT}')
        for old, new in replacements.items():
            content = content.replace(old, new)
        outfile = script / filename
        outfile.write_text(content)
        outfile.chmod(0o755)
    mockbin = make_mock_tools(temp, deb)
    env = {**os.environ, 'PATH': str(mockbin) + ':' + os.environ['PATH'],
           'LEAN_LS_TEST_DIVERSION': str(temp / 'state-diversion'),
           'LEAN_LS_TEST_DEB': str(deb)}
    return script, env, sys, original, engine_dir, cli


def verify_install(script, env, sys, original, engine_dir, cli, prior):
    result = check([str(script / 'install.sh')], env, ROOT)
    assert '100%' in result.stdout, result.stdout
    assert original.is_file()
    assert sys.is_symlink() and os.readlink(sys) == str(engine_dir / 'lean-ls')
    assert cli.is_symlink()
    if prior is None:
        assert not (engine_dir / 'preinstall-ls-symlink').exists()
    else:
        assert (engine_dir / 'preinstall-ls-symlink').is_symlink()
        assert os.readlink(engine_dir / 'preinstall-ls-symlink') == prior
    assert check([str(sys), '-la', str(ROOT)], env, ROOT).stdout == check([str(original), '-la', str(ROOT)], env, ROOT).stdout
    return result


def run_case(label, target, deb):
    with tempfile.TemporaryDirectory(prefix='lean-ls-install-test-') as tmp:
        temp = Path(tmp)
        script, env, sys, original, engine_dir, cli = make_sandbox(temp, target, deb)
        verify_install(script, env, sys, original, engine_dir, cli, target)
        # Upgrade does not alter original GNU copy or original link backup.
        check([str(script / 'install.sh')], env, ROOT)
        if target is not None:
            assert os.readlink(engine_dir / 'preinstall-ls-symlink') == target
        assert sys.is_symlink() and os.readlink(sys) == str(engine_dir / 'lean-ls')
        check([str(script / 'uninstall.sh')], env, ROOT)
        if target is None:
            assert sys.is_file() and not sys.is_symlink()
        else:
            assert sys.is_symlink() and os.readlink(sys) == target
        assert not original.exists() and not (engine_dir / 'preinstall-ls-symlink').exists()
        assert not (temp / 'state-diversion').exists()
        print(f'PASS: {label}: install + upgrade + uninstall, link restored')


def run_interactive_tty(deb):
    """Catch errexit failures hidden when progress is captured through a pipe."""
    if shutil.which('script') is None:
        raise AssertionError('util-linux script is needed for real terminal coverage')
    with tempfile.TemporaryDirectory(prefix='lean-ls-tty-test-') as tmp:
        temp = Path(tmp)
        target = '/bin/echo'  # Installed ls is non-GNU, as in the user report.
        scripts, env, sys, original, engine_dir, cli = make_sandbox(temp, target, deb)
        installed = sys.parent / 'gnuls'
        shutil.copy2('/usr/bin/ls', installed)
        # runuser must be able to reach the staged GNU binary.
        temp.chmod(0o755)
        (temp / 'fake-system').chmod(0o755)
        (temp / 'fake-system/usr').chmod(0o755)
        (temp / 'fake-system/usr/bin').chmod(0o755)
        env['LEAN_LS_TEST_DEB'] = str(temp / 'missing.deb')
        # script(1) allocates a controlling pseudo-terminal for the installer.
        # -e returns the child's exit code rather than silently succeeding.
        command = shlex.quote(str(scripts / 'install.sh'))
        p = check(['script', '-q', '-e', '-c', command, '/dev/null'], env, ROOT)
        assert '  5%' in p.stdout and '100%' in p.stdout, p.stdout
        assert 'using installed GNU coreutils binary' in p.stdout, p.stdout
        assert not 'unexpected failure' in p.stdout, p.stdout
        assert sys.is_symlink() and os.readlink(sys) == str(engine_dir / 'lean-ls')
        check(['script', '-q', '-e', '-c', command, '/dev/null'], env, ROOT)
        check([str(scripts / 'uninstall.sh')], env, ROOT)
        assert sys.is_symlink() and os.readlink(sys) == target
        assert not original.exists() and not (temp / 'state-diversion').exists()
        print('PASS: interactive TTY: install + upgrade + uninstall (5-100% progress)')


def run_installed_gnu(deb):
    with tempfile.TemporaryDirectory(prefix='lean-ls-installed-gnu-') as tmp:
        temp = Path(tmp)
        script, env, sys, original, engine_dir, cli = make_sandbox(temp, '/bin/echo', deb)
        installed = sys.parent / 'gnuls'
        shutil.copy2('/usr/bin/ls', installed)
        # The installed GNU executable must be visible to the unprivileged
        # detection subprocess, even though this fixture is owned by root.
        temp.chmod(0o755)
        (temp / 'fake-system').chmod(0o755)
        (temp / 'fake-system/usr').chmod(0o755)
        (temp / 'fake-system/usr/bin').chmod(0o755)
        env['LEAN_LS_TEST_DEB'] = str(temp / 'missing.deb')
        result = verify_install(script, env, sys, original, engine_dir, cli, '/bin/echo')
        assert 'using installed GNU coreutils binary' in result.stdout
        check([str(script / 'install.sh')], env, ROOT)
        check([str(script / 'uninstall.sh')], env, ROOT)
        print('PASS: installed /usr/bin/gnuls prevents unnecessary apt download')


def run_bad_archive(deb):
    with tempfile.TemporaryDirectory(prefix='lean-ls-bad-archive-') as tmp:
        temp = Path(tmp)
        script, env, sys, original, engine_dir, cli = make_sandbox(temp, '/bin/echo', deb)
        pkg = temp / 'empty-pkg'
        (pkg / 'DEBIAN').mkdir(parents=True)
        (pkg / 'DEBIAN/control').write_text('Package: gnu-coreutils\nVersion: 1\nArchitecture: amd64\nMaintainer: test <test@example.com>\nDescription: invalid package\n')
        bad = temp / 'invalid.deb'
        check(['dpkg-deb', '--build', str(pkg), str(bad)], os.environ, temp)
        env['LEAN_LS_TEST_DEB'] = str(bad)
        p = check([str(script / 'install.sh')], env, ROOT, success=False)
        assert 'no /usr/bin/gnuls' in p.stderr
        assert sys.is_symlink() and os.readlink(sys) == '/bin/echo'
        assert not original.exists() and not (temp / 'state-diversion').exists()
        print('PASS: malformed downloaded package leaves original ls intact')


def run_failure(deb):
    with tempfile.TemporaryDirectory(prefix='lean-ls-failure-test-') as tmp:
        temp = Path(tmp)
        script, env, sys, original, engine_dir, cli = make_sandbox(temp, '/bin/echo', deb)
        # Guaranteed package-recovery failure leaves ls untouched.
        env['LEAN_LS_TEST_DEB'] = str(temp / 'missing.deb')
        p = check([str(script / 'install.sh')], env, ROOT, success=False)
        assert 'Cannot download gnu-coreutils' in p.stderr
        assert sys.is_symlink() and os.readlink(sys) == '/bin/echo'
        assert not original.exists() and not (temp / 'state-diversion').exists()
        print('PASS: package recovery failure preserves original ls')



def run_compile_failure(deb):
    with tempfile.TemporaryDirectory(prefix='lean-ls-compile-failure-') as tmp:
        temp = Path(tmp)
        script, env, sys, original, engine_dir, cli = make_sandbox(temp, '/usr/bin/ls', deb)
        env['CC'] = '/bin/false'
        result = check([str(script / 'install.sh')], env, ROOT, success=False)
        assert 'Compilation failed' in result.stderr, result.stderr
        assert 'Build failure details' in result.stderr, result.stderr
        assert sys.is_symlink() and os.readlink(sys) == '/usr/bin/ls'
        assert not original.exists()
        assert not (temp / 'state-diversion').exists()
        assert not cli.exists()
        print('PASS: failed external build reports diagnostics and preserves ls')


def run_post_activation_failure(deb):
    with tempfile.TemporaryDirectory(prefix='lean-ls-rollback-test-') as tmp:
        temp = Path(tmp)
        script, env, sys, original, engine_dir, cli = make_sandbox(temp, '/usr/bin/ls', deb)
        # Force the last smoke-test comparison to fail, after activating ls.
        cmp = temp / 'mock-bin/cmp'
        cmp.write_text('#!/bin/sh\nexit 1\n')
        cmp.chmod(0o755)
        p = check([str(script / 'install.sh')], env, ROOT, success=False)
        assert 'ls output differs from GNU' in p.stderr
        assert sys.is_symlink() and os.readlink(sys) == '/usr/bin/ls'
        assert not original.exists() and not (temp / 'state-diversion').exists()
        assert not (engine_dir / 'preinstall-ls-symlink').exists()
        print('PASS: failed post-activation smoke test restores symlink/diversion')


if __name__ == '__main__':
    if os.geteuid():
        raise SystemExit('Run as root in a disposable build environment')
    with tempfile.TemporaryDirectory(prefix='lean-ls-pkg-fixture-') as tmp:
        deb = build_mock_deb(Path(tmp))
        run_case('regular GNU binary', None, deb)
        run_interactive_tty(deb)
        run_case('GNU symlink', '/usr/bin/ls', deb)
        run_case('non-GNU symlink + gnu-coreutils apt recovery', '/bin/echo', deb)
        run_installed_gnu(deb)
        run_failure(deb)
        run_bad_archive(deb)
        run_compile_failure(deb)
        run_post_activation_failure(deb)
