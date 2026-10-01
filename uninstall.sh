#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
INSTALL_BIN="${IMAGE_PIN_BIN_DIR:-$HOME/.local/bin}"
EXTENSIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/vicinae/extensions"
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    "$PROJECT_DIR/bin/image-pin" shutdown 2>/dev/null || true
fi
if [[ -L "$INSTALL_BIN/image-pin" && "$(readlink -f -- "$INSTALL_BIN/image-pin")" == "$PROJECT_DIR/bin/image-pin" ]]; then
    rm -- "$INSTALL_BIN/image-pin"
fi
EXTENSION_PATH="$EXTENSIONS_DIR/image-pin"
if [[ -f "$EXTENSION_PATH/package.json" ]]; then
    "$PROJECT_DIR/.venv/bin/python" - "$EXTENSION_PATH" <<'PY'
import json, pathlib, shutil, sys
path = pathlib.Path(sys.argv[1])
metadata = json.loads((path / 'package.json').read_text())
if metadata.get('name') == 'image-pin' and metadata.get('author') == 'jinkim0823':
    shutil.rmtree(path)
else:
    raise SystemExit('Refusing to remove an extension with different ownership metadata')
PY
fi
printf 'Removed launcher and Vicinae extension. Source, saved images and logs were kept.\n'
