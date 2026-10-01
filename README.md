# Xiaomi_XUN_Kernel

红米平板 SE（Redmi Pad SE，代号 **xun**，SM6225 / 骁龙 680）的自编译内核，
产出可直刷的 **AnyKernel3** 卡刷包，内含：

- **Droidspaces** 容器化支持（命名空间 / DEVTMPFS / ipset 等）
- **ReSukiSU**（最新）+ **SUSFS**
- **bpf_loop** 回填（`BPF_FUNC_loop`，daed 等依赖）
- 配套内核修复：BPF 回调的 **CFI `__nocfi`**、`bpf_sk_assign` 放行 **SO_REUSEPORT**

---

## 1. 设备与约束

| 项 | 值 |
|---|---|
| 机型 | Redmi Pad SE `23073RPBFC`，device `xun`，SoC SM6225 |
| 系统 | LineageOS 23.0（**UNOFFICIAL**，`23.0-20251020_232542-UNOFFICIAL-xun`），Android 16 |
| 厂商基线 | 小米 stock `OS2.0.205.0.VMUMIXM`（Android 13） |
| 在机内核 | `5.15.167-android13-8-00014-gbf0a81a7f319-ab13297889`，clang r450784e / LLD 14.0.7 |
| 分区 | A/B；`boot_a` 只有内核（`ramdisk_size=0`，47,372,800 B），ramdisk 在 `init_boot_a` |
| KMI | `android13-8`（与 `module_layout = 0x222dd63` 一致） |

### ★ 最关键的一条约束：ABI 必须匹配原厂模块

LineageOS 的设备树用 `TARGET_NO_KERNEL_OVERRIDE := true`，**不自编内核** ——
它直接复用小米出厂的内核 Image 与模块（从 `OS2.0.205.0.VMUMIXM` 抽出）。

因此我们只替换 `boot` 里的内核，`/vendor_dlkm/lib/modules` 与
`vendor_boot` ramdisk 里的原厂模块（共 **469 个 .ko、3414 个被 import 的符号**）
必须能照常装载。这要求：

1. **vermagic 尾串**一致 —— 需要 `SMP preempt mod_unload modversions aarch64`
   （`CONFIG_SMP=y` / `PREEMPT=y` / `MODULE_UNLOAD=y` / `MODVERSIONS=y`）。
   带 CRC 时 `same_magic()` 会跳过第一个空格前的 `UTS_RELEASE`，所以
   **版本串不必和原厂一样**。
2. **每个被模块引用的符号，其 `__crc_*` 必须逐一相同**。
3. 原厂开着 `CONFIG_TRIM_UNUSED_KSYMS=y`，我们关掉 ⇒ 导出面是**超集**，安全。

> 原厂 `CONFIG_MODULE_SIG_FORCE` **未开**，所以我们换内核后原厂签名模块照样能装载。

---

## 2. 上游基线

| 用途 | 仓库 | 分支 / 提交 |
|---|---|---|
| 内核树 | `Xiaomi-Redmi-Pad-SE-Resources/android_kernel_xiaomi_sm6225` | `lineage-23.0` @ `676f5fa0e5617e95d5c5d10ac605206536376845` |
| 配置基准 | 设备 `/proc/config.gz`（= 小米 stock 配置） | 归一为 `configs/xun-stock.config` |
| ReSukiSU | `ReSukiSU/ReSukiSU` | 见 `UPSTREAM` 文件 |

`lineage-23.0` 是 ACK `android13-5.15` 派生，**5.15.194**，其上由社区导入了
xun 的厂商驱动（`Import … from xun-t-oss` 系列提交）。上游只存在 194 基线的 xun 树，
不存在 167 基线，所以基线只能是它。

### 为什么用设备配置而不是树里的 defconfig

树里自带 `gki_defconfig` + `vendor/bengal_GKI.config` + `vendor/xun_GKI.config` 的
AOSP 构建链，但设备实际跑的是**小米用自己配置编的内核**。`/proc/config.gz` 就是那份配置，
它既保证 `=y` 的内建驱动齐全（能开机），又保证 ABI 与模块同源。实测：用它做
`olddefconfig` 后，stock 里有而 194 树里没有的 `=y` 项只有 3 个，且全是构建探测项
（`CC_CAN_LINK` / `CC_CAN_LINK_STATIC` / `UAPI_HEADER_TEST`）。

> ⚠️ 跑 `olddefconfig` 必须带 `LLVM=1 CC=clang`。否则 Kconfig 以为在用 gcc，
> `LD_IS_LLD` 不成立 ⇒ 自动 `LTO_NONE=y` 且 **`CFI_CLANG` 连带消失** ⇒
> 编出来的内核 CRC 与原厂不符、刷了开不了机。`scripts/build.sh` 里有硬闸挡住。

---

## 3. 目录

```
configs/
  xun-stock.config      设备 /proc/config.gz（构建基准，勿改）
  xun-features.config   特性叠加片段（Droidspaces / ReSukiSU / SUSFS）
patches/                特性改动（按序号叠加到上游树）
scripts/
  fetch.sh              克隆上游内核树与 ReSukiSU 到 kernel/
  apply.sh              在 kernel/ 上叠补丁
  build.sh              配置 + 硬闸 + make Image
  crc_check.py          拿设备 stock 模块的 __versions 与 Module.symvers 对 CRC
  package-ak3.sh        打 AnyKernel3 包
kernel/                 上游工作树（.gitignore，不入库）
out/                    构建产物（.gitignore）
```

---

## 4. 构建

```bash
bash scripts/fetch.sh          # 克隆 kernel/ 与 KernelSU/
bash scripts/apply.sh          # 叠 patches/
bash scripts/build.sh          # 出 out/arch/arm64/boot/Image
bash scripts/package-ak3.sh    # 出 AnyKernel3-XUN-*.zip
```

工具链：AOSP LLVM `clang-r450784d`（clang/LLD 14.0.6）。刷机前请先过
`scripts/crc_check.py`。

---

## 5. 状态

见 `STATUS.md`。
