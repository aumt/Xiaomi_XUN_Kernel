#!/bin/bash
# 克隆上游内核树 + ReSukiSU 到 kernel/（幂等）
# 版本参数从 UPSTREAM 文件读，环境变量可覆盖。
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K="$P/kernel"

# UPSTREAM 是版本参数的单一口径（CI 的「设置构建参数」步骤也读它）
# shellcheck disable=SC1091
[ -f "$P/UPSTREAM" ] && . "$P/UPSTREAM"

UPSTREAM_REPO="${UPSTREAM_REPO:-https://github.com/Xiaomi-Redmi-Pad-SE-Resources/android_kernel_xiaomi_sm6225.git}"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-lineage-23.0}"
UPSTREAM_COMMIT="${UPSTREAM_COMMIT:-676f5fa0e5617e95d5c5d10ac605206536376845}"

KSU_REPO="${KSU_REPO:-https://github.com/ReSukiSU/ReSukiSU.git}"
KSU_COMMIT="${KSU_COMMIT:-3a2745f78ab68e61c02a0681463021952083ec8c}"

echo "== 上游内核树 =="
# 浅克隆：我们要的只是 UPSTREAM_COMMIT 这一个状态，全量历史在 CI 上纯属浪费。
# 实测浅克隆不影响版本串形态 —— 本地 kernel/ 本来就是浅的，照样出 -g<12位sha>。
if [ ! -d "$K/.git" ]; then
  git clone --depth=1 --branch "$UPSTREAM_BRANCH" "$UPSTREAM_REPO" "$K"
fi
# 上面拿的是分支 tip；UPSTREAM_COMMIT 未必等于 tip，所以显式再取一次。
# 取不到不致命（tip 就是目标时本来也不需要），但下面必须核对 HEAD。
git -C "$K" fetch --depth=1 origin "$UPSTREAM_COMMIT" 2>/dev/null || true
git -C "$K" checkout -q "$UPSTREAM_COMMIT"
HEAD=$(git -C "$K" rev-parse HEAD)
echo "  HEAD = $HEAD"
# ★ 必须核对：上面那句 fetch 带了 `|| true`，按 sha 取失败时会静默留在分支 tip 上，
#   于是「钉了提交」就是假的 —— 编出来的东西跟 UPSTREAM 里写的不是一回事。
[ "$HEAD" = "$UPSTREAM_COMMIT" ] || {
  echo "::error::kernel/ HEAD=$HEAD 不等于 UPSTREAM_COMMIT=$UPSTREAM_COMMIT（按 sha fetch 失败？）"
  exit 1
}

echo "== ReSukiSU =="
if [ ! -d "$K/KernelSU/.git" ]; then
  rm -rf "$K/KernelSU"
  # ★ 必须全量克隆（不能 --depth=1）：KernelSU/kernel/Kbuild 用
  #   `git rev-list --count HEAD` 当版本号，浅克隆会算成 1，版本串就废了。
  git clone "$KSU_REPO" "$K/KernelSU"
fi
git -C "$K/KernelSU" fetch -q origin "$KSU_COMMIT" 2>/dev/null || true
git -C "$K/KernelSU" checkout -q "$KSU_COMMIT"
echo "  HEAD  = $(git -C "$K/KernelSU" rev-parse HEAD)"
REV=$(git -C "$K/KernelSU" rev-list --count HEAD)
echo "  rev-count = $REV  (KSU 版本号 = 30000+该值+700)"
# 浅克隆的兜底断言：真被浅克隆了上面那个数会掉到个位数，而版本串照编不误。
[ "$REV" -gt 1000 ] || {
  echo "::error::ReSukiSU rev-count=$REV 太小，几乎肯定是浅克隆 —— KSU 版本号会算错"
  exit 1
}
