#!/usr/bin/env bash
# Install the pinned MIT-licensed WeRead adapter outside the skill checkout.
set -euo pipefail
VERSION=0.1.2
PREFIX="${WEREAD_INSTALL_DIR:-$HOME/.local/share/wechat-download-skill/weread-omni}"
node -e 'const [major,minor]=process.versions.node.split(".").map(Number); if (major<22 || (major===22 && minor<13)) process.exit(1)' || {
  echo 'Node.js >=22.13.0 is required for weread-omni.' >&2
  exit 1
}
mkdir -p "$PREFIX"
chmod 700 "$PREFIX"
npm install --prefix "$PREFIX" --no-audit --no-fund --save-exact "weread-omni@$VERSION"
"$PREFIX/node_modules/.bin/weread-omni" --version
