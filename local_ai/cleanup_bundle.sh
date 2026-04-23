#!/usr/bin/env bash
# local_ai/cleanup_bundle.sh
# 刪除 repo 內由 prepare_bundle.sh 建立的離線 bundle，不動系統全域模型快取。

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${CYAN}  ->${RESET} %s\n" "$1"; }
ok()    { printf "${GREEN}  ok${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}  !!${RESET} %s\n" "$1"; }
fail()  { printf "${RED}  xx${RESET} %s\n" "$1"; exit 1; }
header(){ printf "\n${BOLD}== %s ==${RESET}\n" "$1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$SCRIPT_DIR/runtime"

header "cleanup target"
info "repo bundle dir: ${RUNTIME_DIR}"

if [[ ! -d "$RUNTIME_DIR" ]]; then
    warn "nothing to clean; ${RUNTIME_DIR} does not exist"
    exit 0
fi

bundle_size="unknown"
if command -v du >/dev/null 2>&1; then
    bundle_size="$(du -sh "$RUNTIME_DIR" | awk '{print $1}')"
fi

rm -rf "$RUNTIME_DIR"
ok "removed repo bundle: ${RUNTIME_DIR}"

cat <<EOF

已刪除由 local_ai/deploy_local.sh / local_ai/prepare_bundle.sh 建立的 repo 內離線 bundle。
釋放空間：約 ${bundle_size}

注意：
- 這只會刪除 local_ai/runtime/
- 不會刪除 ~/.ollama 內原本或後續下載的系統全域模型快取
EOF
