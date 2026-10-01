#!/bin/bash
# 在 kernel/ 上按序叠 patches/*.patch（幂等：已应用则跳过）
#   RESET=1  先把 kernel/ 硬重置回 FETCH_HEAD 再叠
set -uo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K="$P/kernel"

[ -d "$K/.git" ] || { echo "::error::kernel/ 不存在，先跑 scripts/fetch.sh"; exit 1; }
cd "$K" || exit 1

if [ "${RESET:-0}" = "1" ]; then
  echo "--- 重置到 $(cat "$P/UPSTREAM" 2>/dev/null || echo '跟踪的上游提交') ---"
  git reset --hard
  git clean -fdq
fi

shopt -s nullglob
mapfile -t PATCHES < <(ls -1 "$P"/patches/*.patch 2>/dev/null | sort)
[ "${#PATCHES[@]}" -gt 0 ] || { echo "patches/ 为空，无需叠加"; exit 0; }

for f in "${PATCHES[@]}"; do
  n=$(basename "$f")
  if git apply --check --reverse "$f" 2>/dev/null; then
    echo "  [跳过] $n  （已应用）"
    continue
  fi
  echo "  [应用] $n"
  # 不用 --3way：三方合并会把冲突悄悄留在索引里、编出来才发现
  git apply --verbose "$f" || { echo "::error::$n 应用失败"; exit 1; }
done

echo "--- 叠加完成，工作树改动 ---"
git diff --stat | tail -20
