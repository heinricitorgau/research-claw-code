#!/usr/bin/env bash
# 對外的部署入口：把 repo 準備成可離線直接執行的本地 AI bundle。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECONDS=0

bash "$SCRIPT_DIR/prepare_bundle.sh" "$@"

elapsed_seconds=$SECONDS
hours=$((elapsed_seconds / 3600))
minutes=$(((elapsed_seconds % 3600) / 60))
seconds=$((elapsed_seconds % 60))

printf '\n總耗時：%02d:%02d:%02d\n' "$hours" "$minutes" "$seconds"
