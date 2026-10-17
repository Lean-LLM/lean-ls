# lean-ls v0.2.4

Linux listing compatibility layer combining GNU `ls`, the accelerated liszt C engine, and optional lla features.

**Project:** https://github.com/Lean-LLM/lean-ls

## One-command Ubuntu installation

Download/extract the source distribution, then run:

```bash
sudo ./install.sh
```

The installer checks dependencies, builds from source, runs integration tests,
registers a local `dpkg-divert` for `/usr/bin/ls`, and atomically activates a
symlink to `/usr/local/libexec/lean-ls/lean-ls`. It also creates
`/usr/local/bin/lean-ls`. It does **not** modify `.bashrc`, `.zshrc`, or PATH.
A verified copy of GNU `ls` is preserved at `/usr/bin/ls.lean-ls-original` and
registered as the dpkg diversion destination. Package upgrades may replace that destination; reassess compatibility after a coreutils-provider upgrade. The installer
accepts an existing `ls` symlink and preserves its original link text for
uninstall. If that link resolves to a non-GNU executable, the installer
uses verified `/usr/bin/gnuls` if present; otherwise it downloads
the **`gnu-coreutils`** package through apt (pinning the installed version if available); if that cannot be done, it stops without modifying `ls`.
The first installation may therefore need network access for that recovery.
Newer Ubuntu releases use `coreutils` as a meta package: it does **not**
contain the GNU `ls` executable. The implementation is in `gnu-coreutils`,
under `/usr/bin/gnuls`. `lean-ls` never installs an alternative coreutils
provider or modifies which coreutils provider Ubuntu has selected.

**On GNU-based systems, ordinary `ls` retains GNU output. On your Ubuntu with uutils, `ls` will change to GNU output.** The overridden
`ls` entrypoint executes the original installed GNU `ls` binary, forwarding
its original argument vector, environment, file descriptors, and exit behavior.
It does **not** speed up GNU `ls`, since exact output is the default safety
requirement. The extra exec adds some startup cost.

| Command | Behavior |
|---|---|
| `ls -la` | Original GNU `ls`; byte-exact stdout and stderr |
| `/bin/ls -la` | Same on merged-/usr Ubuntu |
| `/usr/bin/ls -la` | Original GNU engine through diversion |
| `lean-ls -la` | Accelerated native listing, approximate GNU compatibility |
| `lean-ls --tree` | Native directory tree |
| `lean-ls --git -l` | Git-aware native listing |
| `lean-ls --lean-strict -la` | Invoke genuine GNU `ls` |
| `lean-ls --json` | Optional lla engine; `lla` must be installed |
| `lean-ls --lla -t` | Original lla CLI, if installed |

The fast engine is derived from liszt and is *not* proven 100% byte-identical
under every GNU version, locale, terminal mode, security context, or odd
filename. When invoked **as `ls`**, all flags remain GNU flags; nothing is
reinterpreted by the native or lla engines. The fast `lean-ls` command is a
separate opt-in command, by design.

## Safety, compatibility, and limitations

- Ubuntu Linux with merged `/usr` and dpkg; the installation is deliberately
  rejected on non-merged layouts, pre-existing unrelated diversions, or
  shadowing `/usr/local/bin/ls` wrappers. A `~/.local/bin/ls` wrapper is warned
  about, not silently overwritten. Existing `/usr/bin/ls` symlinks are
  preserved for rollback, including when recovery via apt is required.
- Shell aliases/functions or an unrelated earlier executable on PATH can still
  shadow the overridden `/usr/bin/ls`. An executable with a hardcoded custom
  implementation is outside the scope of an `ls` override.
- Existing running processes are unaffected until their next `ls` exec.
- `dpkg-divert --no-rename` protects essential commands during activation;
  the symlink is replaced atomically. Rollback restores the original *before*
  removing the diversion.
- The source compilation is staged in a writable private `/var/tmp` directory
  and performed as the invoking non-root user (or `nobody` without `SUDO_USER`).
  On failure the installer prints the failing build or test log. Ubuntu build tools are installed
  from apt if not present.
- Compile and verify on your own machine; do not deploy unsigned or
  uninspected third-party installers to production without review.

## Ubuntu 25.10 / 26.04 / 26.10 GNU recovery

Ubuntu's `coreutils` can be a small meta package rather than the actual GNU
binary package. **Do not attempt to recover GNU ls by extracting `coreutils`.**
The installer first verifies `/usr/bin/gnuls` (provided by `gnu-coreutils`).
If missing, it downloads `gnu-coreutils` from the configured apt repositories
and extracts `usr/bin/gnuls` into a private staging directory without changing
the selected Ubuntu coreutils provider. If recovery fails or the executable
is not GNU, the installer exits before activating any system-wide override.

## Remove the override completely

From the same extracted directory:

```bash
sudo ./uninstall.sh
```

This restores `/usr/bin/ls`, unregisters the diversion, and removes the
`lean-ls` executable and symlink. The uninstall refuses to overwrite other
software's modifications.

## Developer tests

```bash
./configure
make -j2
python3 tests/lean-ls-integration.py
sh tests/unit/run.sh
FUZZ_TRIALS=10 sh tests/fuzz/run-tree.sh
```

GitHub Actions also installs and uninstalls the override on an ephemeral
Ubuntu runner, where allowed. Installation script prints a 0–100% progress bar.

## License and origins

- Fast listing engine: liszt 0.3.0 C source, GPL-3.0-or-later,
  https://github.com/tenseleyFlow/liszt
- Optional extended engine source: lla 0.6.6 (MIT),
  https://github.com/chaqchase/lla; its original MIT license is preserved.
- Dispatch and packaging: GPL-3.0-or-later.

`ls.c` from GNU coreutils alone is **not** a buildable standalone program; it
requires gnulib and other coreutils build components. lean-ls delegates to
Ubuntu's installed GNU binary instead of pretending a partial source file can
supply complete GNU compatibility.

## v0.2.4 Ubuntu install troubleshooting

`sudo ./install.sh` compiles under `/var/tmp/lean-ls-build.*` as the invoking
non-root user, so source trees on external/noexec or read-only mounts do not
block compilation. `./configure` correctly handles a nonzero `wcwidth` probe.

If a build or compatibility check fails, the installer prints the final 70
log lines and retains a `/var/tmp/lean-ls-build-log.*` file. It does not
activate `/usr/bin/ls` before compilation and tests succeed.

Ubuntu with uutils at `/usr/bin/ls`: this project intentionally changes
`ls` to **GNU** when successfully installed, using installed `/usr/bin/gnuls`
as the compatibility baseline. It preserves your original uutils symlink
for uninstall. This is not byte-identical to uutils output; it is byte-identical
to the installed GNU `gnuls`.

Do not clone the empty repository as an installation method until this
release is pushed to GitHub. Extract this release archive instead.

### Interactive terminal regression fixed in v0.2.4

Earlier installers exited at the first 5% progress update when invoked
from an interactive terminal with `set -e`. The arithmetic expression
`((value == 100)) && printf '\n'` returned failure for progress values
below 100. Version 0.2.4 uses a normal `if` statement and adds a
pseudo-terminal installation/rollback regression test.

Use this release archive, not the currently empty GitHub repository.
