#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
for tool in uv npm node vicinae gnome-screenshot; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Missing prerequisite: %s. See README.md for installation.\n' "$tool" >&2
        exit 1
    fi
done
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
npm ci --prefix extension --no-audit --no-fund
npm run build --prefix extension
ln -sfn -- "$PROJECT_DIR/bin/image-pin" "$INSTALL_BIN/image-pin"
printf 'Installed Image Pin. Search for Capture & Pin in Vicinae.\n'
if [[ "$INSTALL_BIN" != "$HOME/.local/bin" ]]; then
    printf 'Set Helper executable in Vicinae preferences to %s/image-pin\n' "$INSTALL_BIN"
fi
printf 'Existing pins keep running until the helper is restarted.\n'
