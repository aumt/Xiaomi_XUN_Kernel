#!/bin/bash
# 打 AnyKernel3 卡刷包：只替换 boot 里的内核，不动 ramdisk（GKI v4，ramdisk 在 init_boot）
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMG="$P/out/arch/arm64/boot/Image"
AK3_URL="${AK3_URL:-https://github.com/osm0sis/AnyKernel3}"
AK3_DIR="$P/anykernel3"

[ -s "$IMG" ] || { echo "::error::找不到 $IMG，先跑 scripts/build.sh"; exit 1; }

rm -rf "$AK3_DIR"
git clone --depth=1 "$AK3_URL" "$AK3_DIR"
rm -rf "$AK3_DIR/.git"
cd "$AK3_DIR"
cp "$IMG" ./Image
[ -s ./Image ] || { echo "::error::Image 拷贝失败"; exit 1; }

# ★ 不靠 sed 去改上游模板：上游措辞一变 sed 就静默不命中。
#   上游模板里 IS_SLOT_DEVICE 是 0，而 ak3-core.sh 的判定是
#       case $IS_SLOT_DEVICE in 1|auto)
#   0 一个分支都不匹配 ⇒ SLOT 为空 ⇒ `for part in $name$SLOT $name` 只试 boot，
#   永远试不到 boot_a/boot_b ⇒ A/B 机上 abort "Unable to determine boot partition"。
#   所以整份写死，并对关键行加断言 —— 被误改就当场失败，别等刷机才发现。
cat > anykernel.sh <<'AK3CONF'
### AnyKernel3 Ramdisk Mod Script
## osm0sis @ xda-developers

### AnyKernel setup
# global properties
properties() { '
kernel.string=RedmiPadSE-XUN
do.devicecheck=0
do.modules=0
do.systemless=1
do.cleanup=1
do.cleanuponabort=0
device.name1=
device.name2=
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; } # end properties


### AnyKernel install
## boot files attributes
boot_attributes() {
set_perm_recursive 0 0 755 644 $RAMDISK/*;
set_perm_recursive 0 0 750 750 $RAMDISK/init* $RAMDISK/sbin;
} # end attributes

# boot shell variables
BLOCK=boot;
IS_SLOT_DEVICE=auto;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;

# import functions/variables and setup patching - see for reference (DO NOT REMOVE)
. tools/ak3-core.sh;

# boot install
split_boot; # GKI v4: ramdisk 在 init_boot，boot 仅内核 -> 不解包 ramdisk
flash_boot; # 仅替换内核，跳过 ramdisk 重打包
## end boot install
AK3CONF

grep -qx 'IS_SLOT_DEVICE=auto;' anykernel.sh || { echo "::error::IS_SLOT_DEVICE 不是 auto —— 为 0 会跳过 slot 判定，A/B 机找不到 boot_b"; exit 1; }
grep -q '^BLOCK=boot;'          anykernel.sh || { echo "::error::BLOCK 不是 boot"; exit 1; }
grep -q '^split_boot;'          anykernel.sh || { echo "::error::缺 split_boot"; exit 1; }
grep -q '^flash_boot;'          anykernel.sh || { echo "::error::缺 flash_boot"; exit 1; }
grep -q '^do.devicecheck=0'     anykernel.sh || { echo "::error::do.devicecheck 不为 0"; exit 1; }
! grep -q 'tuna'                anykernel.sh || { echo "::error::混进了上游 tuna 打补丁段"; exit 1; }

# 包名用「从 Image 里实际抽出的版本串」，而不是配置里的默认值
VER_ACTUAL=$(strings -a ./Image | grep -oE '5\.15\.[0-9]+(-[A-Za-z0-9._+-]+)?' | sort -u \
             | awk 'length > max { max = length; best = $0 } END { print best }' || true)
[ -n "$VER_ACTUAL" ] || { echo "::error::从 Image 抽不到版本串，拒绝用占位名打包"; exit 1; }
echo "  Image 实际版本串: $VER_ACTUAL"

TAG="${AK3_TAG:-ReSukiSU}"
AK3_NAME="AnyKernel3-XUN-$VER_ACTUAL-$TAG.zip"
rm -f "../$AK3_NAME"
zip -r9 "../$AK3_NAME" ./* -x '*.git*' >/dev/null
echo "=== 刷机包: $P/$AK3_NAME ==="
ls -l "$P/$AK3_NAME"
echo "ak3name=$AK3_NAME"
