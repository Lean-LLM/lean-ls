#!/usr/bin/env bash
# lean-ls: Ubuntu system-wide install. Keeps GNU ls available via dpkg-divert.
set -Eeuo pipefail
umask 022

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
SYS=/usr/bin/ls
ORIGINAL=/usr/bin/ls.lean-ls-original
ENGINE_DIR=/usr/local/libexec/lean-ls
ENGINE=$ENGINE_DIR/lean-ls
CLI=/usr/local/bin/lean-ls
STEP=0
CREATED_COPY=0
CREATED_DIVERSION=0
ACTIVATED=0
UPGRADING=0
TMPBIN=
TMPLINK=
CREATED_CLI=0
CREATED_LINK_BACKUP=0
CREATED_ENGINE=0
LINK_BACKUP=$ENGINE_DIR/preinstall-ls-symlink
RECOVERY_DIR=
BUILD_DIR=
BUILD_LOG=
GNU_SOURCE=$SYS
GNU_INSTALLED=/usr/bin/gnuls

progress() {
    local value=$1 label=$2 filled bar= i
    filled=$((value / 5))
    for ((i=0; i<20; ++i)); do
        if ((i < filled)); then bar+='='; else bar+=' '; fi
    done
    if [[ -t 1 ]]; then
        printf '\r[%s] %3d%%  %-42s' "$bar" "$value" "$label"
        # A false arithmetic test is exit status 1. Do not return that
        # status from progress() under set -e when writing to a TTY.
        if ((value == 100)); then printf '\n'; fi
    else
        printf '[%s] %3d%%  %s\n' "$bar" "$value" "$label"
    fi
}
fail() { printf '\nlean-ls: %s\n' "$*" >&2; exit 1; }
# Restore the pre-install directory entry, including an existing symlink.
# A relative symlink must retain its original text, not a rebased target.
restore_ls() {
    local staged
    staged=$(mktemp "$SYS.restore.XXXXXXXX") || return 1
    if [[ -L "$LINK_BACKUP" ]]; then
        rm -f -- "$staged"
        ln -s -- "$(readlink -- "$LINK_BACKUP")" "$staged" || return 1
    else
        cp -p -- "$ORIGINAL" "$staged" || return 1
    fi
    mv -Tf -- "$staged" "$SYS"
}
cleanup() {
    local status=$?
    trap - EXIT
    if ((status != 0)); then
        printf '\nlean-ls: install failed; checking restoration...\n' >&2
        if ((ACTIVATED && !UPGRADING)) && [[ -e "$ORIGINAL" ]]; then
            restore_ls || printf 'WARNING: could not automatically restore %s\n' "$SYS" >&2
        fi
        if ((CREATED_DIVERSION)); then
            dpkg-divert --quiet --local --no-rename --divert "$ORIGINAL" --remove "$SYS" || true
        fi
        if ((CREATED_COPY)) && [[ $(dpkg-divert --truename "$SYS") == "$SYS" ]]; then
            rm -f -- "$ORIGINAL"
        fi
        if ((CREATED_LINK_BACKUP)); then rm -f -- "$LINK_BACKUP"; fi
    fi
    if ((status != 0 && CREATED_CLI && UPGRADING == 0)); then
        rm -f -- "$CLI"
    fi
    if ((status != 0 && CREATED_ENGINE && UPGRADING == 0)); then
        rm -f -- "$ENGINE"
        rmdir -- "$ENGINE_DIR" 2>/dev/null || true
    fi
    [[ -z "$TMPBIN" ]] || rm -f -- "$TMPBIN"
    [[ -z "$TMPLINK" ]] || rm -f -- "$TMPLINK"
    [[ -z "$RECOVERY_DIR" ]] || rm -rf -- "$RECOVERY_DIR"
    [[ -z "$BUILD_DIR" ]] || rm -rf -- "$BUILD_DIR"
    if [[ -n "$BUILD_LOG" && $status -eq 0 ]]; then rm -f -- "$BUILD_LOG"; fi
    exit "$status"
}
# The existing ls can be a symlink to GNU coreutils (e.g. alternatives).
# Check as an unprivileged account: never run an untrusted old ls as root.
# A non-GNU replacement requires recovery of an original from the exact
# installed, authenticated Ubuntu coreutils package version.
is_gnu_ls() {
    local output test_user=${SUDO_USER:-nobody}
    [[ -x "$1" ]] || return 1
    output=$(LC_ALL=C runuser -u "$test_user" -- "$1" --version 2>/dev/null) || return 1
    [[ "$output" == 'ls (GNU coreutils) '* ]]
}
recover_packaged_gnu() {
    local deb package installed_version installed_status
    # Ubuntu 25.10+ splits `coreutils` into a metapackage and alternatives:
    # `gnu-coreutils` provides /usr/bin/gnuls, not /usr/bin/ls.
    # Prefer a verified installed GNU binary: no network or package changes.
    if [[ -x "$GNU_INSTALLED" ]] && is_gnu_ls "$GNU_INSTALLED"; then
        GNU_SOURCE=$GNU_INSTALLED
        printf 'lean-ls: using installed GNU coreutils binary %s\n' "$GNU_SOURCE"
        return
    fi
    command -v apt-get >/dev/null && command -v dpkg-deb >/dev/null && command -v dpkg-query >/dev/null ||
        fail 'Cannot recover GNU ls: apt-get/dpkg-deb/dpkg-query missing'
    # Pin to the installed gnu-coreutils version if present. If Ubuntu is
    # using uutils instead, download the repository candidate WITHOUT
    # installing or changing the system-selected coreutils implementation.
    package=gnu-coreutils
    installed_status=$(dpkg-query -W -f='${Status}' gnu-coreutils 2>/dev/null || true)
    if [[ "$installed_status" == 'install ok installed' ]]; then
        installed_version=$(dpkg-query -W -f='${Version}' gnu-coreutils) ||
            fail 'Cannot determine installed gnu-coreutils version'
        [[ -n "$installed_version" ]] || fail 'Empty installed gnu-coreutils version'
        package="gnu-coreutils=$installed_version"
    fi
    RECOVERY_DIR=$(mktemp -d /var/tmp/lean-ls-gnu.XXXXXXXX) || fail 'Cannot create recovery directory'
    chmod 0755 "$RECOVERY_DIR"
    printf 'lean-ls: recovering %s from configured Ubuntu apt sources\n' "$package"
    (cd -- "$RECOVERY_DIR" && apt-get download "$package") ||
        fail "Cannot download $package; original ls remains untouched"
    shopt -s nullglob
    local debs=("$RECOVERY_DIR"/gnu-coreutils_*.deb)
    shopt -u nullglob
    ((${#debs[@]} == 1)) || fail 'Expected exactly one downloaded gnu-coreutils package'
    deb=${debs[0]}
    dpkg-deb --extract "$deb" "$RECOVERY_DIR/pkg" || fail 'Cannot extract gnu-coreutils'
    GNU_SOURCE=$RECOVERY_DIR/pkg/usr/bin/gnuls
    [[ -x "$GNU_SOURCE" ]] || fail 'Downloaded gnu-coreutils package has no /usr/bin/gnuls'
    is_gnu_ls "$GNU_SOURCE" || fail 'Downloaded GNU ls failed executable verification'
}

trap cleanup EXIT
trap 'rc=$?; printf "lean-ls: unexpected failure at script line %s (exit %s)\n" "$LINENO" "$rc" >&2' ERR
trap 'exit 130' INT
trap 'exit 143' TERM

[[ $EUID -eq 0 ]] || fail 'Run: sudo ./install.sh'
command -v dpkg-divert >/dev/null || fail 'Ubuntu/dpkg-divert is required'
[[ -e "$SYS" ]] || fail "Missing/broken $SYS (check symlink target)"
[[ -x "$SYS" ]] || fail "Not executable: $SYS"
[[ $(readlink -f /bin/ls) == "$(readlink -f "$SYS")" ]] || fail 'Non-merged /usr: /bin/ls differs; refusing unsafe partial override'
[[ ! -e /usr/local/bin/ls && ! -L /usr/local/bin/ls ]] || fail '/usr/local/bin/ls already shadows system ls; remove only after checking its ownership'
# A user-local wrapper is not overwritten; its effect is reported after installation.
# SUDO_USER home can differ from root HOME.
if [[ -n ${SUDO_USER:-} && ${SUDO_USER} != root ]]; then
    userhome=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [[ -n $userhome && ( -e $userhome/.local/bin/ls || -L $userhome/.local/bin/ls ) ]]; then
        printf 'lean-ls: WARNING: %s/.local/bin/ls may shadow system ls for %s\n' "$userhome" "$SUDO_USER" >&2
    fi
fi

if [[ -L "$SYS" && $(readlink "$SYS") == "$ENGINE" && \
      $(dpkg-divert --truename "$SYS") == "$ORIGINAL" && -x "$ORIGINAL" ]]; then
    UPGRADING=1
elif [[ $(dpkg-divert --truename "$SYS") != "$SYS" ]]; then
    fail 'Existing dpkg diversion is not owned by lean-ls; refusing to replace it'
elif [[ -e "$ORIGINAL" || -L "$ORIGINAL" ]]; then
    fail "$ORIGINAL already exists; refusing to overwrite it"
fi
if ((UPGRADING == 0)); then
    [[ ! -e "$LINK_BACKUP" && ! -L "$LINK_BACKUP" ]] || fail "Existing link backup: $LINK_BACKUP"
    # A symlink is valid input, but dereferencing an unknown replacement
    # would make 'ls' silently retain its non-GNU semantics.
    GNU_SOURCE=$(readlink -e -- "$SYS") || fail "Cannot resolve original $SYS"
    if ! is_gnu_ls "$GNU_SOURCE"; then
        printf "lean-ls: WARNING: existing ls is not GNU; successful installation will switch ls behavior to GNU\n" >&2
        recover_packaged_gnu
    fi
fi
if [[ -e "$CLI" || -L "$CLI" ]]; then
    [[ -L "$CLI" && $(readlink "$CLI") == "$ENGINE" ]] || fail "$CLI exists but is not a lean-ls symlink"
fi
# Stage GNU original before integration tests. This allows pre-existing
# non-GNU ls symlinks to be recovered without skewing the test baseline.
if ((UPGRADING == 0)); then
    cp -p -- "$GNU_SOURCE" "$ORIGINAL"
    CREATED_COPY=1
fi
progress 5 'Preflight OK; GNU ls preserved'

# Never compile in the checkout: it may be on NTFS/exFAT, noexec, or
# contain root-owned build outputs left by earlier sudo attempts.
if ! command -v cc >/dev/null || ! command -v make >/dev/null; then
    progress 10 'Installing build tools'
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends build-essential
fi
command -v cc >/dev/null && command -v make >/dev/null || fail 'C compiler / make missing'
command -v runuser >/dev/null || fail 'runuser is required for an unprivileged build'
BUILD_USER=${SUDO_USER:-nobody}
[[ $BUILD_USER != root ]] || BUILD_USER=nobody
id "$BUILD_USER" >/dev/null 2>&1 || fail "Build user does not exist: $BUILD_USER"
BUILD_DIR=$(mktemp -d /var/tmp/lean-ls-build.XXXXXXXX) || fail 'Cannot create temporary build directory'
# Copy a minimal source set. Never build third-party source as root.
for required in configure Makefile src tests; do
    [[ -e "$ROOT/$required" ]] || fail "Source missing: $ROOT/$required (use the complete release archive)"
done
cp -a -- "$ROOT/configure" "$ROOT/Makefile" "$ROOT/src" "$ROOT/tests" "$BUILD_DIR/" ||
    fail 'Cannot stage build sources'
chown -R -- "$BUILD_USER" "$BUILD_DIR" || fail 'Cannot set temporary build ownership'
BUILD_LOG=$(mktemp /var/tmp/lean-ls-build-log.XXXXXXXX) || fail 'Cannot create build log'
progress 15 'Building in isolated writable directory'
if ! runuser -u "$BUILD_USER" -- /bin/bash -c \
    'set -e; cd -- "$1"; ./configure; make -j2 lean-ls' bash "$BUILD_DIR" \
    >"$BUILD_LOG" 2>&1; then
    printf 'lean-ls: Build failure details (last 70 lines):\n' >&2
    tail -n 70 -- "$BUILD_LOG" >&2 || true
    fail "Compilation failed; checkout unchanged. Build log: $BUILD_LOG"
fi
progress 40 'Native engine compiled'

# Validate the staged binary, not an old in-tree executable.
if command -v python3 >/dev/null; then
    if ! LEAN_LS_TEST_GNU="$ORIGINAL" LEAN_LS_GNU_LS="$ORIGINAL" \
        LEAN_LS_TEST_BINARY="$BUILD_DIR/lean-ls" \
        python3 "$BUILD_DIR/tests/lean-ls-integration.py" >"$BUILD_LOG" 2>&1; then
        printf 'lean-ls: Compatibility test failure details:\n' >&2
        tail -n 70 -- "$BUILD_LOG" >&2 || true
        fail "Compatibility tests failed; system ls unchanged. Log: $BUILD_LOG"
    fi
else
    "$BUILD_DIR/lean-ls" --lean-strict --version >/dev/null ||
        fail 'Strict GNU smoke test failed; system ls unchanged'
fi
progress 65 'GNU byte-identity integration checks passed'

mkdir -p -- "$ENGINE_DIR" /usr/local/bin
TMPBIN=$(mktemp "$ENGINE_DIR/.lean-ls.XXXXXXXX")
install -m 0755 -- "$BUILD_DIR/lean-ls" "$TMPBIN"
# Version mode executes the compiled engine in-place before activation.
"$TMPBIN" --lean-version >/dev/null
# Stage the installed engine atomically (works on upgrades).
if [[ ! -e "$ENGINE" && ! -L "$ENGINE" ]]; then CREATED_ENGINE=1; fi
mv -Tf -- "$TMPBIN" "$ENGINE"
TMPBIN=
if [[ ! -e "$CLI" && ! -L "$CLI" ]]; then
    ln -s -- "$ENGINE" "$CLI"
    CREATED_CLI=1
fi
progress 80 'Engine installed without changing ls yet'

if ((UPGRADING == 0)); then
    # --no-rename keeps ls functional during diversion registration.
    if [[ -L "$SYS" ]]; then
        cp -Pp -- "$SYS" "$LINK_BACKUP"
        CREATED_LINK_BACKUP=1
    fi
    dpkg-divert --quiet --local --no-rename --divert "$ORIGINAL" --add "$SYS"
    CREATED_DIVERSION=1
    [[ $(dpkg-divert --truename "$SYS") == "$ORIGINAL" ]] || fail 'dpkg diversion validation failed'
    TMPLINK=$(mktemp "$SYS.lean-ls.XXXXXXXX")
    rm -f -- "$TMPLINK"
    ln -s -- "$ENGINE" "$TMPLINK"
    mv -Tf -- "$TMPLINK" "$SYS"
    TMPLINK=
    ACTIVATED=1
fi
progress 90 'System-wide ls activated'

# System smoke test. /usr/bin/ls should delegate to the preserved GNU binary.
[[ -L "$SYS" && $(readlink "$SYS") == "$ENGINE" ]] || fail 'ls activation missing'
[[ -x "$ORIGINAL" ]] || fail 'GNU original missing'
[[ $(dpkg-divert --truename "$SYS") == "$ORIGINAL" ]] || fail 'dpkg diversion missing'
"$SYS" --version >/dev/null
cmp -s <("$SYS" -la -- "$ROOT") <("$ORIGINAL" -la -- "$ROOT") || fail 'ls output differs from GNU'
progress 100 'Installed; default ls is byte-exact GNU'
printf 'Commands: ls (exact GNU); lean-ls (optimized); lean-ls --lla (optional)\n'
if [[ -L "$LINK_BACKUP" ]]; then printf 'Original ls symlink preserved for uninstall.\n'; fi
if [[ -n ${SUDO_USER:-} && -e "${userhome:-/nonexistent}/.local/bin/ls" ]]; then printf 'WARNING: existing ~/.local/bin/ls may take priority in PATH.\n' >&2; fi
printf 'Rollback: sudo ./uninstall.sh\n'
