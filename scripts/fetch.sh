#!/bin/bash
# 克隆上游内核树 + ReSukiSU 到 kernel/（幂等）
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K="$P/kernel"

UPSTREAM_REPO="${UPSTREAM_REPO:-https://github.com/Xiaomi-Redmi-Pad-SE-Resources/android_kernel_xiaomi_sm6225.git}"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-lineage-23.0}"
UPSTREAM_COMMIT="${UPSTREAM_COMMIT:-676f5fa0e5617e95d5c5d10ac605206536376845}"

KSU_REPO="${KSU_REPO:-https://github.com/ReSukiSU/ReSukiSU.git}"
KSU_COMMIT="${KSU_COMMIT:-3a2745f78ab68e61c02a0681463021952083ec8c}"

echo "== 上游内核树 =="
if [ ! -d "$K/.git" ]; then
  git clone --branch "$UPSTREAM_BRANCH" "$UPSTREAM_REPO" "$K"
fi
git -C "$K" fetch --depth=1 origin "$UPSTREAM_COMMIT" 2>/dev/null || true
git -C "$K" checkout -q "$UPSTREAM_COMMIT"
echo "  HEAD = $(git -C "$K" rev-parse HEAD)"

echo "== ReSukiSU =="
# ★ 必须全量克隆（不能 --depth=1）：KernelSU/kernel/Kbuild 用
#   `git rev-list --count HEAD` 当版本号，浅克隆会算成 1，版本串就废了。
if [ ! -d "$K/KernelSU/.git" ]; then
  rm -rf "$K/KernelSU"
  git clone "$KSU_REPO" "$K/KernelSU"
fi
git -C "$K/KernelSU" fetch -q origin "$KSU_COMMIT" 2>/dev/null || true
git -C "$K/KernelSU" checkout -q "$KSU_COMMIT"
echo "  HEAD  = $(git -C "$K/KernelSU" rev-parse HEAD)"
echo "  rev-count = $(git -C "$K/KernelSU" rev-list --count HEAD)  (KSU 版本号 = 30000+该值+700)"
