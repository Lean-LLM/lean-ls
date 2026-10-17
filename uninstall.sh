#!/usr/bin/env bash
# Restore Ubuntu GNU ls before removing lean-ls files.
set -Eeuo pipefail
SYS=/usr/bin/ls
ORIGINAL=/usr/bin/ls.lean-ls-original
ENGINE=/usr/local/libexec/lean-ls/lean-ls
CLI=/usr/local/bin/lean-ls
LINK_BACKUP=/usr/local/libexec/lean-ls/preinstall-ls-symlink
[[ $EUID -eq 0 ]] || { echo 'Run: sudo ./uninstall.sh' >&2; exit 1; }
if [[ ! -L "$SYS" || $(readlink "$SYS") != "$ENGINE" ]]; then
    echo 'ls is not the lean-ls symlink; refusing to change it' >&2
    exit 1
fi
if [[ $(dpkg-divert --truename "$SYS") != "$ORIGINAL" || ! -x "$ORIGINAL" ]]; then
    echo 'GNU backup/diversion missing or inconsistent; no changes made' >&2
    exit 1
fi
# Atomic restoration first; the rest of uninstall cannot leave ls unusable.
TMP=$(mktemp "$SYS.restore.XXXXXXXX")
trap 'rm -f -- "$TMP"' EXIT
if [[ -L "$LINK_BACKUP" ]]; then
    rm -f -- "$TMP"
    ln -s -- "$(readlink -- "$LINK_BACKUP")" "$TMP"
else
    cp -p -- "$ORIGINAL" "$TMP"
fi
mv -Tf -- "$TMP" "$SYS"
dpkg-divert --quiet --local --no-rename --divert "$ORIGINAL" --remove "$SYS"
rm -f -- "$ORIGINAL" "$LINK_BACKUP"
if [[ -L "$CLI" && $(readlink "$CLI") == "$ENGINE" ]]; then rm -f -- "$CLI"; fi
rm -f -- "$ENGINE"
rmdir /usr/local/libexec/lean-ls 2>/dev/null || true
printf 'Restored GNU ls. No aliases or shell configuration changed.\n'
