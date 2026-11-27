#!/usr/bin/env bash
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd /mnt/e/Projects/vn-regulatory-rag

rm -f .tmp_create.sh .tmp_step.sh

echo "== leftover markers =="
grep -n "PART[0-9]" SPEC.md PLAN.md README.md || echo "none"

echo "== makefile tabs =="
echo "tab_recipe_lines=$(grep -c '^\t' Makefile)"

echo "== stage =="
git add -A
git status --short

echo "== commit =="
git commit -F .msg -q
rm -f .msg
git log --oneline -3

echo "== push =="
git push origin main 2>&1 | tail -3

echo "== remote tree =="
git fetch -q origin
git ls-tree -r --name-only origin/main
echo "remote_file_count=$(git ls-tree -r --name-only origin/main | wc -l)"

echo "== gate =="
make check 2>&1 | tail -8