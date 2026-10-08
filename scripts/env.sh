# Keep all tool caches inside this repo so /root (the nearly-full OS drive) stays untouched.
# Usage: source scripts/env.sh   (run pytest/go test/npm after sourcing)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export XDG_CACHE_HOME="$REPO_ROOT/.cache"
export PIP_CACHE_DIR="$REPO_ROOT/.cache/pip"
export UV_CACHE_DIR="$REPO_ROOT/.cache/uv"
export GOCACHE="$REPO_ROOT/.cache/go-build"
export GOMODCACHE="$REPO_ROOT/.cache/go-mod"
export npm_config_cache="$REPO_ROOT/.cache/npm"
export CARGO_HOME="$REPO_ROOT/.cache/cargo"
mkdir -p "$XDG_CACHE_HOME" "$PIP_CACHE_DIR" "$UV_CACHE_DIR" "$GOCACHE" "$GOMODCACHE" "$npm_config_cache"
