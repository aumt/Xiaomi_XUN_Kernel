#!/bin/bash
# 配置 + 硬闸 + make Image
#   FEATURES=0  只编基线（stock 配置，不叠特性片段）
#   FEATURES=1  叠 configs/xun-features.config（默认）
set -uo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K="$P/kernel"; O="$P/out"
FEATURES="${FEATURES:-1}"
LOG="${BUILD_LOG:-$P/build.log}"
JOBS="${JOBS:-$(nproc)}"
CLANG_DIR="${CLANG_DIR:-/home/user/nx729j/clang-r450784d}"

export PATH="$CLANG_DIR/bin:$PATH"
export ARCH=arm64 SUBARCH=arm64
export LLVM=1 LLVM_IAS=1
export CROSS_COMPILE=aarch64-linux-gnu-
export CCACHE_DIR="${CCACHE_DIR:-/home/user/xun/ccache}"
export CC="ccache clang"
export TZ=Asia/Shanghai

[ -d "$K" ] || { echo "::error::kernel/ 不存在，先跑 scripts/fetch.sh"; exit 1; }

{
echo "===== 构建开始 $(date -Is)  FEATURES=$FEATURES  jobs=$JOBS ====="
ccache -M 30G 2>&1 | tail -2
cd "$K" || exit 1

echo "--- 配置 ---"
mkdir -p "$O"
cat "$P/configs/xun-stock.config" > "$O/.config"
if [ "$FEATURES" != "0" ]; then
  cat "$P/configs/xun-features.config" >> "$O/.config"
fi
# 关裁剪：让导出面成为原厂（TRIM_UNUSED_KSYMS=y）的超集
scripts/config --file "$O/.config" -d TRIM_UNUSED_KSYMS

# ★ 必须带 CC=clang：否则 Kconfig 以为用 gcc ⇒ LD_IS_LLD 不成立
#   ⇒ 自动 LTO_NONE=y 且 CFI_CLANG 连带消失 ⇒ CRC 与原厂不符、刷了开不了机。
make O="$O" ARCH=arm64 LLVM=1 LLVM_IAS=1 CC="$CC" LD=ld.lld olddefconfig 2>&1 | tail -3

echo "--- 硬闸 A：编译/ABI 前提 ---"
fail=0
for S in LTO_CLANG_FULL CFI_CLANG CFI_CLANG_SHADOW MODVERSIONS LD_IS_LLD SMP PREEMPT MODULE_UNLOAD; do
  n=$(grep -c "^CONFIG_${S}=y\$" "$O/.config")
  echo "  CONFIG_${S}=y -> $n (须为1)"
  [ "$n" = "1" ] || fail=1
done
for S in LTO_NONE LTO_CLANG_THIN MODULE_SIG_FORCE; do
  n=$(grep -c "^CONFIG_${S}=y\$" "$O/.config")
  echo "  CONFIG_${S}=y -> $n (须为0)"
  [ "$n" = "0" ] || fail=1
done

echo "--- 硬闸 B：特性片段逐项落地 ---"
# ★ olddefconfig 会把 depends 未满足的项静默丢掉；不逐项回查就会
#   「配了但没生效」地编出个缺功能的包。
if [ "$FEATURES" != "0" ] && [ -s "$P/configs/xun-features.config" ]; then
  miss=0
  while read -r sym; do
    [ -n "$sym" ] || continue
    n=$(grep -c "^CONFIG_${sym}=y\$" "$O/.config")
    if [ "$n" != "1" ]; then echo "  ✗ CONFIG_${sym} 未落地"; miss=$((miss+1)); fi
  done < <(sed -n 's/^CONFIG_\([A-Za-z0-9_]*\)=y$/\1/p' "$P/configs/xun-features.config")
  echo "  未落地项 = $miss (须为0)"
  [ "$miss" = "0" ] || fail=1
fi
[ "$fail" = "0" ] || { echo "!! 硬闸失败，中止"; exit 1; }
echo "--- 硬闸通过 ---"

echo "--- make Image 开始 $(date -Is) ---"
( while true; do sleep 60; echo "  [心跳 $(date +%H:%M:%S)] load=$(cut -d' ' -f1 /proc/loadavg) mem=$(free -m | awk '/Mem:/{print $3"/"$2"M"}')"; done ) &
HB=$!
make O="$O" ARCH=arm64 LLVM=1 LLVM_IAS=1 CC="$CC" LD=ld.lld OBJCOPY=llvm-objcopy \
     CROSS_COMPILE="$CROSS_COMPILE" -j"$JOBS" Image 2>&1
RC=$?
kill $HB 2>/dev/null
echo "--- make 退出码 = $RC  $(date -Is) ---"

echo "--- 产物 ---"
ls -l "$O/arch/arm64/boot/Image" 2>/dev/null
echo "  Image sha256 = $(sha256sum "$O/arch/arm64/boot/Image" 2>/dev/null | cut -d' ' -f1)"
# ★ CRC 闸门要的是 vmlinux.symvers，不是 Module.symvers。
#   `make Image` 的 MODPOST 步骤写 vmlinux.symvers；Module.symvers 只有
#   `make modules` 才生成，而且 `make modules_prepare` 两者都不生成
#   （它只跑 prepare + module.lds）。stock 的 469 个 .ko 全是外部模块，
#   它们 import 的符号要么来自 vmlinux、要么来自彼此 —— 所以 vmlinux 的
#   导出面就是完整靶子，不需要把模块导出面并进来。
SYM="$O/vmlinux.symvers"
if [ -s "$SYM" ]; then
  echo "  vmlinux.symvers 行数 = $(wc -l < "$SYM")"
else
  echo "!! vmlinux.symvers 缺失 —— 编译没走到 MODPOST，CRC 闸门无法执行"
  RC=1
fi

if [ -s "$SYM" ]; then
  # ★ 闸门必须真的能拦住。写成 `python3 … | grep …` 的话，$? 是 grep 的退出码，
  #   脚本报「CRC 不符」也照样 0 通过 —— 闸门形同虚设。所以落盘再判。
  echo "--- CRC 闸门 ---"
  python3 "$P/scripts/crc_check.py" "$SYM" > "$O/crc_gate.txt" 2>&1
  CRC_RC=$?
  grep -E '^\[stock|^\[ours|CRC 一致|CRC 不符|未导出' "$O/crc_gate.txt" || true
  if [ "$CRC_RC" != "0" ]; then
    echo "!! CRC 闸门失败：stock 模块 import 的 __crc_* 与我们不符，刷进去模块会装不上"
    sed -n '/CRC 不符明细/,/未导出明细/p' "$O/crc_gate.txt" | head -35
    RC=1
  fi

  echo "--- 真缺口闸门（把「未导出」拆成模块自给 / 真缺口）---"
  python3 "$P/scripts/gap_analysis.py" > "$O/gap_gate.txt" 2>&1
  GAP_RC=$?
  grep -E '模块自己导出|A\)|B\)' "$O/gap_gate.txt" || true
  if [ "$GAP_RC" != "0" ]; then
    echo "!! 真缺口闸门失败：有符号只能由 vmlinux 提供而我们没导出，模块会 Unknown symbol"
    sed -n '/真缺口全量/,$p' "$O/gap_gate.txt" | head -30
    RC=1
  fi
fi
echo "  ---- 版本串 ----"
strings -a "$O/arch/arm64/boot/Image" 2>/dev/null | grep -oE '5\.15\.[0-9]+[-A-Za-z0-9._+]*' | sort -u | head -5
echo "===== 构建结束 $(date -Is) rc=$RC ====="
} 2>&1 | tee "$LOG"
# ★ 用 PIPESTATUS[0] 取左边那段（构建本体）的退出码。写成
#     } > "$LOG" 2>&1 ; tail -1 "$LOG"
#   的话脚本退出码恒为 tail 的 0 —— 硬闸失败、make 失败在 CI 里全被吞掉，
#   会「绿着」发出一个编坏的内核。tee 同时让 CI 日志实时可见：
#   runner 若被内存掐掉，连 if: always() 的步骤都会被跳过，
#   只有已经流式发出去的日志行能活下来。
RC=${PIPESTATUS[0]}
echo "日志：$LOG"
echo "构建退出码 = $RC"
exit "$RC"
