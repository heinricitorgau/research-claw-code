#!/usr/bin/env bash
# local_ai/prepare_bundle.sh
# 在有網路的機器上把本地 AI 執行環境打包進 repo，供之後離線直接跑。

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
RUST_DIR="$PROJECT_DIR/rust"
RUNTIME_DIR="$SCRIPT_DIR/runtime"
BIN_DIR="$RUNTIME_DIR/bin"
SOURCE_OLLAMA_HOME="${OLLAMA_HOME_OVERRIDE:-$HOME/.ollama}"
MANIFEST_ROOT="$SOURCE_OLLAMA_HOME/models/manifests/registry.ollama.ai/library"
BLOB_ROOT="$SOURCE_OLLAMA_HOME/models/blobs"
FAST_MODE=0
CACHED_ONLY=0
MODEL="${CLAW_MODEL:-qwen2.5-coder:14b}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fast)
            FAST_MODE=1
            ;;
        --cached-only)
            CACHED_ONLY=1
            ;;
        --help|-h)
            cat <<EOF
usage: bash local_ai/prepare_bundle.sh [model] [--fast] [--cached-only]

  --fast         優先重用既有 binary 與已打包模型，減少重建與重拷貝
  --cached-only  不下載模型；若本機快取缺少指定模型就直接失敗
EOF
            exit 0
            ;;
        *)
            if [[ "$1" == -* ]]; then
                fail "unknown option: $1"
            fi
            MODEL="$1"
            ;;
    esac
    shift
done

copy_tree() {
    local src="$1"
    local dst="$2"
    mkdir -p "$dst"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$src/" "$dst/"
    else
        rm -rf "$dst"
        mkdir -p "$dst"
        cp -R "$src/." "$dst/"
    fi
}

resolve_model_manifest_path() {
    local model_ref="$1"
    local model_name="${model_ref%%:*}"
    local model_tag="${model_ref#*:}"
    local exact_path="$MANIFEST_ROOT/$model_name/$model_tag"
    local latest_path="$MANIFEST_ROOT/$model_name/latest"

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

bundle_single_model() {
    local model="$1"
    local source_manifest=""
    source_manifest="$(resolve_model_manifest_path "$model")" || fail "cannot find manifest for model ${model}"
    local manifest_relpath="${source_manifest#"$MANIFEST_ROOT/"}"
    local target_root="$RUNTIME_DIR/ollama-home/models"
    local target_manifest_path="$target_root/manifests/registry.ollama.ai/library/$manifest_relpath"
    local target_manifest_dir
    target_manifest_dir="$(dirname "$target_manifest_path")"
    local target_blob_dir="$target_root/blobs"
    local digest
    local blob_name

    rm -rf "$RUNTIME_DIR/ollama-home"
    mkdir -p "$target_manifest_dir" "$target_blob_dir"
    cp "$source_manifest" "$target_manifest_path"

    while read -r digest; do
        blob_name="${digest/:/-}"
        [[ -f "$BLOB_ROOT/$blob_name" ]] || fail "missing blob for digest ${digest}"
        cp "$BLOB_ROOT/$blob_name" "$target_blob_dir/$blob_name"
    done < <(grep -o 'sha256:[0-9a-f]\{64\}' "$source_manifest")
}

model_manifest_path() {
    resolve_model_manifest_path "$MODEL"
}

model_cached_locally() {
    [[ -f "$(model_manifest_path)" ]]
}

bundle_already_matches() {
    [[ -f "$RUNTIME_DIR/bundle-manifest.txt" ]] || return 1
    [[ -d "$RUNTIME_DIR/ollama-home/models" ]] || return 1
    local bundled_model=""
    bundled_model="$(awk -F= '/^model=/{print $2}' "$RUNTIME_DIR/bundle-manifest.txt" | tail -n 1)"
    [[ "$bundled_model" == "$MODEL" ]]
}

install_claw_binary() {
    if [[ "$FAST_MODE" -eq 1 && -x "$BIN_DIR/claw" ]]; then
        ok "reusing bundled claw binary"
        return 0
    fi
    if [[ "$FAST_MODE" -eq 1 && -x "$RUST_DIR/target/release/claw" ]]; then
        install -m 755 "$RUST_DIR/target/release/claw" "$BIN_DIR/claw"
        ok "reusing existing release claw binary"
        return 0
    fi

    (
        cd "$RUST_DIR"
        cargo build --workspace --release
    )
    install -m 755 "$RUST_DIR/target/release/claw" "$BIN_DIR/claw"
    ok "bundled claw binary"
}

header "bundle target"
mkdir -p "$BIN_DIR"
ok "runtime dir: ${RUNTIME_DIR}"

header "tooling"
command -v cargo >/dev/null 2>&1 || fail "cargo not found; install Rust first"
command -v ollama >/dev/null 2>&1 || fail "ollama not found; install Ollama first"
ok "cargo: $(cargo --version)"
ok "ollama: $(ollama --version 2>/dev/null || echo installed)"

header "build claw"
install_claw_binary

header "prepare model"
if ! model_cached_locally; then
    if [[ "$CACHED_ONLY" -eq 1 ]]; then
        fail "model '${MODEL}' is not cached locally and --cached-only was requested"
    fi
    info "model not cached yet, pulling ${MODEL}"
    ollama pull "$MODEL"
fi
model_cached_locally || fail "model '${MODEL}' manifest is still missing after pull"
ok "model available locally: ${MODEL}"

header "bundle ollama"
cp -fL "$(command -v ollama)" "$BIN_DIR/ollama"
chmod +x "$BIN_DIR/ollama"
ok "bundled ollama executable"

if [[ ! -d "$SOURCE_OLLAMA_HOME" ]]; then
    fail "cannot find Ollama home at ${SOURCE_OLLAMA_HOME}"
fi

if [[ "$FAST_MODE" -eq 1 ]] && bundle_already_matches; then
    ok "reusing existing bundled model payload: ${MODEL}"
else
    bundle_single_model "$MODEL"
    ok "bundled only the selected model: ${MODEL}"
fi

header "write manifest"
cat > "$RUNTIME_DIR/bundle-manifest.txt" <<EOF
prepared_at=$(date '+%Y-%m-%d %H:%M:%S %z')
bundle_os=$(uname -s)
bundle_arch=$(uname -m)
model=${MODEL}
fast_mode=${FAST_MODE}
cached_only=${CACHED_ONLY}
claw_binary=${BIN_DIR}/claw
ollama_binary=${BIN_DIR}/ollama
ollama_home=${RUNTIME_DIR}/ollama-home
launch_command=bash local_ai/run.sh
EOF
ok "bundle manifest written"

header "summary"
if command -v du >/dev/null 2>&1; then
    info "bundle size: $(du -sh "$RUNTIME_DIR" | awk '{print $1}')"
fi

cat <<EOF

離線 bundle 已完成。

之後只要把整個 repo 複製到目標機器，就可以直接執行：
  bash local_ai/run.sh

若想改模型：
  bash local_ai/prepare_bundle.sh qwen2.5-coder:14b

若想盡量少下載、少重建：
  bash local_ai/prepare_bundle.sh --fast

若只允許使用本機已快取的模型：
  bash local_ai/prepare_bundle.sh --cached-only
EOF
