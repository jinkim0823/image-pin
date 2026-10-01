#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$PROJECT_DIR"
bash -n install.sh uninstall.sh bin/image-pin scripts/check.sh scripts/pack.sh
uv lock --check
QT_QPA_PLATFORM=offscreen uv run test_pin.py
uv run test_install.py
npm run typecheck --prefix extension
npm run lint --prefix extension
npm run build --prefix extension -- --out ../dist/extension
if [[ "${1:-}" == --desktop ]]; then
    uv run test_desktop.py
fi
