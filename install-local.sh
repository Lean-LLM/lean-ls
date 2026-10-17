#!/bin/sh
# Local, non-privileged install. Does NOT modify /usr/bin/ls or PATH.
set -eu
cd "$(dirname "$0")"
case "${1:-}" in
  '') build_lla=no ;;
  --with-lla) build_lla=yes ;;
  *) echo 'usage: ./install-local.sh [--with-lla]' >&2; exit 2 ;;
esac
command -v cc >/dev/null 2>&1 || { echo 'C compiler missing' >&2; exit 1; }
command -v make >/dev/null 2>&1 || { echo 'GNU make missing' >&2; exit 1; }
./configure
make -j2 lean-ls
[ -n "${HOME:-}" ] || { echo 'HOME not set' >&2; exit 1; }
bin="$HOME/.local/bin"
mkdir -p "$bin"
if [ -e "$bin/lean-ls" ] || [ -L "$bin/lean-ls" ]; then
  echo "Refusing to overwrite existing $bin/lean-ls" >&2
  exit 1
fi
if [ "$build_lla" = yes ]; then
  command -v cargo >/dev/null 2>&1 || { echo 'cargo missing: install Rust first' >&2; exit 1; }
  (cd lla-upstream && cargo build --release --locked -p lla)
  libexec="$HOME/.local/libexec/lean-ls"
  mkdir -p "$libexec"
  if [ -e "$libexec/lla" ] || [ -L "$libexec/lla" ]; then
    echo "Refusing to overwrite existing $libexec/lla" >&2
    exit 1
  fi
  install -m 755 lla-upstream/target/release/lla "$libexec/lla"
fi
install -m 755 lean-ls "$bin/lean-ls"
printf 'Installed %s/lean-ls\n' "$bin"
printf 'Use: %s/lean-ls --lean-ls-help\n' "$bin"
