# Source this in every script that runs outside `make`.
# Usage: source scripts/env.sh
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/vn-rag"
export HF_HOME="$HOME/.cache/huggingface"
export PYTHONUTF8=1