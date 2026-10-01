#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
HELPER_ONLY=false
case "${1:-}" in
    '') ;;
    --helper-only) HELPER_ONLY=true ;;
    *) printf 'Usage: %s [--helper-only]\n' "$0" >&2; exit 2 ;;
esac
# The helper alone works from the command line, desktop shortcuts or a Vicinae
# extension installed from the store; only the local extension build needs Node.
TOOLS=(uv gnome-screenshot)
if [[ "$HELPER_ONLY" == false ]]; then
    TOOLS+=(npm node vicinae)
fi
for tool in "${TOOLS[@]}"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Missing prerequisite: %s. See README.md for installation.\n' "$tool" >&2
        exit 1
    fi
done
# Qt 6's X11 platform plugin cannot load without libxcb-cursor.
LDCONFIG="$(command -v ldconfig || printf /sbin/ldconfig)"
if ! "$LDCONFIG" -p 2>/dev/null | grep -q 'libxcb-cursor\.so\.0'; then
    printf 'Missing library: libxcb-cursor0 (required by Qt 6). See README.md for installation.\n' >&2
    exit 1
fi
INSTALL_BIN="${IMAGE_PIN_BIN_DIR:-$HOME/.local/bin}"
mkdir -p -- "$INSTALL_BIN"
if [[ -e "$INSTALL_BIN/image-pin" || -L "$INSTALL_BIN/image-pin" ]]; then
    if [[ ! -L "$INSTALL_BIN/image-pin" || "$(readlink -f -- "$INSTALL_BIN/image-pin")" != "$PROJECT_DIR/bin/image-pin" ]]; then
        printf 'Refusing to replace an unrelated file: %s/image-pin\n' "$INSTALL_BIN" >&2
        exit 1
    fi
fi
cd -- "$PROJECT_DIR"
uv sync --locked
if [[ "$HELPER_ONLY" == false ]]; then
    npm ci --prefix extension --no-audit --no-fund
    npm run build --prefix extension
fi
ln -sfn -- "$PROJECT_DIR/bin/image-pin" "$INSTALL_BIN/image-pin"
if [[ "$HELPER_ONLY" == true ]]; then
    printf 'Installed the Image Pin helper: %s/image-pin capture\n' "$INSTALL_BIN"
else
    printf 'Installed Image Pin. Search for Capture & Pin in Vicinae.\n'
fi
if [[ "$INSTALL_BIN" != "$HOME/.local/bin" ]]; then
    printf 'Set Helper executable in Vicinae preferences to %s/image-pin\n' "$INSTALL_BIN"
fi
printf 'Existing pins keep running until the helper is restarted.\n'
