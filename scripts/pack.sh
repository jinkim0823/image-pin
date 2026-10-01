#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$PROJECT_DIR"
VERSION="$(uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
mkdir -p dist
git archive --format=tar --prefix="image-pin-$VERSION/" HEAD | gzip > "dist/image-pin-$VERSION.tar.gz"
printf 'Created dist/image-pin-%s.tar.gz from the committed source.\n' "$VERSION"
