#!/usr/bin/env bash
# 對外的清理入口：刪除 local_ai/deploy_local.sh 在 repo 內建立的離線 bundle。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec bash "$SCRIPT_DIR/cleanup_bundle.sh" "$@"
