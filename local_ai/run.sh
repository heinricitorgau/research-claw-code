#!/usr/bin/env bash
# local_ai/run.sh
# 離線優先啟動器：
# 1. 優先使用 repo 內已打包好的 runtime
# 2. 啟動 bundled Ollama / model
# 3. 啟動 Anthropic↔OpenAI proxy（使用系統自帶 Python）
# 4. 啟動 claw CLI

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${CYAN}  ->${RESET} %s\n" "$1"; }
ok()    { printf "${GREEN}  ok${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}  !!${RESET} %s\n" "$1"; }
fail()  { printf "${RED}  xx${RESET} %s\n" "$1"; exit 1; }
header(){ printf "\n${BOLD}== %s ==${RESET}\n" "$1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RUNTIME_DIR="$SCRIPT_DIR/runtime"
BIN_DIR="$RUNTIME_DIR/bin"
BUNDLED_OLLAMA_HOME="$RUNTIME_DIR/ollama-home"
MANIFEST_PATH="$RUNTIME_DIR/bundle-manifest.txt"

bundled_model_manifest_path() {
    local model_ref="$1"
    local model_name="${model_ref%%:*}"
    local model_tag="${model_ref#*:}"
    local base_dir="${BUNDLED_OLLAMA_HOME}/models/manifests/registry.ollama.ai/library/$model_name"
    local exact_path="${base_dir}/${model_tag}"
    local latest_path="${base_dir}/latest"

    if [[ "$model_name" != "$model_ref" && -f "$exact_path" ]]; then
        printf "%s" "$exact_path"
        return 0
    fi
    if [[ -f "$latest_path" ]]; then
        printf "%s" "$latest_path"
        return 0
    fi
    if [[ -f "$exact_path" ]]; then
        printf "%s" "$exact_path"
        return 0
    fi
    return 1
}

bundled_model_request_name() {
    local model_ref="$1"
    local model_name="${model_ref%%:*}"
    local model_tag="${model_ref#*:}"
    local base_dir="${BUNDLED_OLLAMA_HOME}/models/manifests/registry.ollama.ai/library/$model_name"
    local exact_path="${base_dir}/${model_tag}"
    local latest_path="${base_dir}/latest"

    if [[ "$model_name" != "$model_ref" && -f "$exact_path" ]]; then
        printf "%s" "$model_ref"
        return 0
    fi
    if [[ -f "$latest_path" ]]; then
        printf "%s" "$model_name"
        return 0
    fi
    printf "%s" "$model_ref"
}

default_model="qwen2.5-coder:14b"
if [[ -f "$MANIFEST_PATH" ]]; then
    manifest_model="$(awk -F= '/^model=/{print $2}' "$MANIFEST_PATH" | tail -n 1)"
    if [[ -n "$manifest_model" ]]; then
        default_model="$manifest_model"
    fi
fi
MODEL="${CLAW_MODEL:-$default_model}"
PROXY_PORT="${CLAW_PROXY_PORT:-8082}"
OLLAMA_PORT="${CLAW_OLLAMA_PORT:-11435}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:${OLLAMA_PORT}}"
PERMISSION_MODE="${CLAW_PERMISSION_MODE:-read-only}"
SYSTEM_PROMPT="${CLAW_SYSTEM_PROMPT:-}"
PROMPT_PROFILE="${CLAW_PROMPT_PROFILE:-default_zh_tw}"
PROMPT_DIR="${CLAW_PROMPT_DIR:-$SCRIPT_DIR/prompts}"
RAG_QUERY=""

PROXY_PID=""
OLLAMA_PID=""

stop_listener_on_port() {
    local port="$1"
    local label="$2"
    local pids=""
    pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
        return 0
    fi
    warn "port ${port} already in use; restarting ${label}"
    while IFS= read -r pid; do
        [[ -n "$pid" ]] || continue
        kill "$pid" 2>/dev/null || true
    done <<< "$pids"
    for _ in $(seq 1 10); do
        if ! lsof -i ":${port}" -sTCP:LISTEN >/dev/null 2>&1; then
            ok "${label} port ${port} cleared"
            return 0
        fi
        sleep 1
    done
    fail "could not free port ${port} for ${label}"
}

cleanup() {
    printf "\n${BOLD}[claw-local]${RESET} shutting down...\n"
    if [[ -n "$PROXY_PID" ]]; then
        kill "$PROXY_PID" 2>/dev/null || true
        info "proxy stopped"
    fi
    if [[ -n "$OLLAMA_PID" ]]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
        info "ollama stopped"
    fi
}
trap cleanup EXIT INT TERM

print_banner() {
    printf "${BOLD}"
    cat <<'BANNER'
   _____ _                    _       ___  ___
  / ____| |                  | |     / _ \|_ _|
 | |    | | __ ___      __   | |    | | | || |
 | |    | |/ _` \ \ /\ / /   | |    | |_| || |
 | |____| | (_| |\ V  V /    | |___ \___/|___|
  \_____|_|\__,_| \_/\_/     |_____| offline
BANNER
    printf "${RESET}\n"
    printf "  model: ${CYAN}%s${RESET}\n" "$MODEL"
    printf "  perms: ${CYAN}%s${RESET}\n" "$PERMISSION_MODE"
    printf "  proxy: ${CYAN}http://127.0.0.1:%s${RESET}\n" "$PROXY_PORT"
    printf "  ollama: ${CYAN}%s${RESET}\n\n" "$OLLAMA_URL"
    printf "  prompt: ${CYAN}%s${RESET}\n" "$PROMPT_PROFILE"
    if [[ "${CLAW_RAG_ENABLED:-}" == "1" ]]; then
        printf "  rag: ${CYAN}enabled${RESET}\n"
    fi
    printf "\n"
}

find_claw_binary() {
    if [[ -x "$BIN_DIR/claw" ]]; then
        printf "%s" "$BIN_DIR/claw"
        return 0
    fi
    if [[ -x "$PROJECT_DIR/rust/target/release/claw" ]]; then
        printf "%s" "$PROJECT_DIR/rust/target/release/claw"
        return 0
    fi
    if [[ -x "$PROJECT_DIR/rust/target/debug/claw" ]]; then
        printf "%s" "$PROJECT_DIR/rust/target/debug/claw"
        return 0
    fi
    if command -v claw >/dev/null 2>&1; then
        command -v claw
        return 0
    fi
    return 1
}

find_ollama_binary() {
    if [[ -x "$BIN_DIR/ollama" ]]; then
        printf "%s" "$BIN_DIR/ollama"
        return 0
    fi
    if command -v ollama >/dev/null 2>&1; then
        command -v ollama
        return 0
    fi
    return 1
}

ollama_is_running() {
    curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1
}

model_exists_locally() {
    local ollama_bin="$1"
    if "$ollama_bin" list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$MODEL"; then
        return 0
    fi
    return 1
}

require_runtime_hint() {
    printf "\n"
    printf "需要先準備離線 bundle，才能保證「下載資料夾後直接跑」。\n\n"
    printf "先在有網路的機器上執行：\n"
    printf "  bash local_ai/deploy_local.sh\n\n"
    printf "完成後會把 claw、ollama 與模型快取打包進：\n"
    printf "  %s\n\n" "$RUNTIME_DIR"
    printf "之後把整個 research-claw-code 資料夾搬到離線機器，就能直接：\n"
    printf "  bash local_ai/run.sh\n"
}

find_python_binary() {
    if [[ -x "/usr/bin/python3" ]]; then
        printf "%s" "/usr/bin/python3"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    return 1
}

bundle_os="$(uname -s)"
bundle_arch="$(uname -m)"

print_banner

header "preflight"

if ! PYTHON_BIN="$(find_python_binary)"; then
    fail "python3 not found; this bundle expects the OS built-in Python runtime"
fi
ok "python: ${PYTHON_BIN}"

passthrough_args=()
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --import-docs)
            [[ "$#" -ge 2 ]] || fail "--import-docs requires a source path"
            "$PYTHON_BIN" "$SCRIPT_DIR/rag/import_usb_docs.py" "$2"
            exit 0
            ;;
        --reindex-rag)
            "$PYTHON_BIN" "$SCRIPT_DIR/rag/build_index.py"
            exit 0
            ;;
        --rag)
            [[ "$#" -ge 2 ]] || fail "--rag requires a question"
            export CLAW_RAG_ENABLED=1
            RAG_QUERY="$2"
            shift 2
            ;;
        *)
            passthrough_args+=("$1")
            shift
            ;;
    esac
done
if [[ "${#passthrough_args[@]}" -gt 0 ]]; then
    set -- "${passthrough_args[@]}"
else
    set --
fi

if ! CLAW_BIN="$(find_claw_binary)"; then
    require_runtime_hint
    fail "cannot find claw binary"
fi
ok "claw: ${CLAW_BIN}"

if ! OLLAMA_BIN="$(find_ollama_binary)"; then
    require_runtime_hint
    fail "cannot find ollama binary"
fi
ok "ollama: ${OLLAMA_BIN}"

USE_BUNDLED_OLLAMA=0
if [[ -d "$BUNDLED_OLLAMA_HOME" ]]; then
    export OLLAMA_MODELS="${BUNDLED_OLLAMA_HOME}/models"
    USE_BUNDLED_OLLAMA=1
    ok "using bundled models: ${OLLAMA_MODELS}"
else
    warn "bundled model cache not found; falling back to system ollama cache"
fi

if [[ -f "$MANIFEST_PATH" ]]; then
    expected_os="$(awk -F= '/^bundle_os=/{print $2}' "$MANIFEST_PATH" | tail -n 1)"
    expected_arch="$(awk -F= '/^bundle_arch=/{print $2}' "$MANIFEST_PATH" | tail -n 1)"
    if [[ -n "$expected_os" && "$bundle_os" != "$expected_os" ]]; then
        fail "bundle targets ${expected_os}, but this machine is ${bundle_os}"
    fi
    if [[ -n "$expected_arch" && "$bundle_arch" != "$expected_arch" ]]; then
        fail "bundle targets ${expected_arch}, but this machine is ${bundle_arch}"
    fi
    ok "bundle target matches this machine: ${bundle_os}/${bundle_arch}"
fi

export OLLAMA_HOST="127.0.0.1:${OLLAMA_PORT}"
BUNDLED_MODEL_MANIFEST=""
if [[ "$USE_BUNDLED_OLLAMA" -eq 1 ]]; then
    BUNDLED_MODEL_MANIFEST="$(bundled_model_manifest_path "$MODEL" || true)"
fi
OLLAMA_REQUEST_MODEL="$MODEL"
if [[ "$USE_BUNDLED_OLLAMA" -eq 1 ]]; then
    OLLAMA_REQUEST_MODEL="$(bundled_model_request_name "$MODEL")"
fi

header "ollama"

if [[ "$USE_BUNDLED_OLLAMA" -eq 1 ]]; then
    if ollama_is_running; then
        ok "bundled service already running at ${OLLAMA_URL}"
    else
        info "starting bundled ollama service on ${OLLAMA_URL}"
        "$OLLAMA_BIN" serve >/tmp/claw-local-ollama.log 2>&1 &
        OLLAMA_PID=$!
        for i in $(seq 1 30); do
            if ollama_is_running; then
                ok "bundled service ready in ${i}s"
                break
            fi
            sleep 1
            if [[ "$i" -eq 30 ]]; then
                fail "bundled ollama failed to start; check /tmp/claw-local-ollama.log"
            fi
        done
    fi
elif ollama_is_running; then
    ok "service already running at ${OLLAMA_URL}"
else
    info "starting ollama service"
    "$OLLAMA_BIN" serve >/tmp/claw-local-ollama.log 2>&1 &
    OLLAMA_PID=$!
    for i in $(seq 1 30); do
        if ollama_is_running; then
            ok "service ready in ${i}s"
            break
        fi
        sleep 1
        if [[ "$i" -eq 30 ]]; then
            fail "ollama failed to start; check /tmp/claw-local-ollama.log"
        fi
    done
fi

if [[ "$USE_BUNDLED_OLLAMA" -eq 1 && -f "$BUNDLED_MODEL_MANIFEST" ]]; then
    ok "bundled manifest found for model: ${MODEL}"
elif ! model_exists_locally "$OLLAMA_BIN"; then
    require_runtime_hint
    fail "model '${MODEL}' is not available locally"
fi
ok "model cached locally: ${MODEL}"

header "proxy"

stop_listener_on_port "$PROXY_PORT" "proxy"

proxy_args=(
    "$SCRIPT_DIR/proxy.py"
    --model "$MODEL"
    --ollama-model "$OLLAMA_REQUEST_MODEL"
    --port "$PROXY_PORT"
    --ollama-url "$OLLAMA_URL"
    --prompt-profile "$PROMPT_PROFILE"
    --prompt-dir "$PROMPT_DIR"
)
if [[ -n "$SYSTEM_PROMPT" ]]; then
    proxy_args+=(--system-prompt "$SYSTEM_PROMPT")
fi
"$PYTHON_BIN" "${proxy_args[@]}" >/tmp/claw-local-proxy.log 2>&1 &
PROXY_PID=$!
for i in $(seq 1 10); do
    if curl -sf "http://127.0.0.1:${PROXY_PORT}/health" >/dev/null 2>&1; then
        ok "proxy ready in ${i}s"
        break
    fi
    sleep 1
    if [[ "$i" -eq 10 ]]; then
        fail "proxy failed to start; check /tmp/claw-local-proxy.log"
    fi
done

header "launch"
printf "${GREEN}ready${RESET} local AI is up. Press Ctrl+C to exit.\n\n"

export ANTHROPIC_BASE_URL="http://127.0.0.1:${PROXY_PORT}"
export ANTHROPIC_API_KEY="local-ollama"

if [[ -n "$RAG_QUERY" && "$#" -eq 0 ]]; then
    set -- --output-format text prompt "$RAG_QUERY"
fi

if [[ "$#" -eq 0 ]]; then
    exec "$CLAW_BIN" --model "$MODEL" --permission-mode "$PERMISSION_MODE"
fi

args=("$@")
has_model_flag=0
for arg in "${args[@]}"; do
    if [[ "$arg" == "--model" ]]; then
        has_model_flag=1
        break
    fi
done

has_permission_flag=0
for arg in "${args[@]}"; do
    if [[ "$arg" == "--permission-mode" || "$arg" == --permission-mode=* ]]; then
        has_permission_flag=1
        break
    fi
done

final_args=()
if [[ "$has_model_flag" -eq 0 ]]; then
    final_args+=(--model "$MODEL")
fi
if [[ "$has_permission_flag" -eq 0 ]]; then
    final_args+=(--permission-mode "$PERMISSION_MODE")
fi
final_args+=("${args[@]}")

exec "$CLAW_BIN" "${final_args[@]}"
