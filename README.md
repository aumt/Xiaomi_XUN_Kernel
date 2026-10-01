# Xiaomi_XUN_Kernel

红米平板 SE（Redmi Pad SE，代号 **xun**，SM6225 / 骁龙 680）的自编译内核，
产出可直刷的 **AnyKernel3** 卡刷包，内含：

- **Droidspaces** 容器化支持（SYSVIPC / IPC_NS / PID_NS / USER_NS / DEVTMPFS，含 kABI 处理）
- **ReSukiSU**（最新）+ **SUSFS**
- **bpf_loop** 回填（`BPF_FUNC_loop`，daed 等依赖）
- 配套内核修复：BPF 回调的 **CFI `__nocfi`**、`bpf_sk_assign` 放行 **SO_REUSEPORT**

刷机包在 [Releases](../../releases) 里；也能用仓库自带的 GitHub Actions 自己编。

---

## 1. 设备与约束

| 项 | 值 |
|---|---|
| 机型 | Redmi Pad SE `23073RPBFC`，device `xun`，SoC SM6225 |
| 系统 | LineageOS 23.0（**UNOFFICIAL**，`23.0-20251020_232542-UNOFFICIAL-xun`），Android 16 |
| 厂商基线 | 小米 stock `OS2.0.205.0.VMUMIXM`（Android 13） |
| 原厂内核（LineageOS 直接复用） | `5.15.167-android13-8-00014-gbf0a81a7f319-ab13297889`，clang r450784e / LLD 14.0.7 |
| 本仓库产物 | `5.15.194-g<提交号>`，clang r450784d / LLD 14.0.6 |
| 分区 | A/B；`boot_a` 只有内核（`ramdisk_size=0`，47,372,800 B），ramdisk 在 `init_boot_a` |
| KMI | `android13-8`（与 `module_layout = 0x222dd63` 一致） |
| 工具链 | AOSP LLVM `clang-r450784d`（clang / LLD 14.0.6） |

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

这两条闸门（CRC 逐项比对 + 真缺口）已经做进 `scripts/build.sh`，
本地和 CI 都跑，**不符就中止构建**，不会发出一个刷了开不了机的包。

---

## 2. 上游基线

全在仓库根的 **`UPSTREAM`** 文件里（shell 片段，`scripts/fetch.sh` 与 CI 读同一份）：

| 用途 | 仓库 | 分支 / 提交 |
|---|---|---|
| 内核树 | `Xiaomi-Redmi-Pad-SE-Resources/android_kernel_xiaomi_sm6225` | `lineage-23.0` @ `676f5fa0e5617e95d5c5d10ac605206536376845` |
| ReSukiSU | `ReSukiSU/ReSukiSU` | `3a2745f78ab68e61c02a0681463021952083ec8c` |
| 配置基准 | 设备 `/proc/config.gz`（= 小米 stock 配置） | 归一为 `configs/xun-stock.config` |

`lineage-23.0` 是 ACK `android13-5.15` 派生，**5.15.194**，其上由社区导入了
xun 的厂商驱动（`Import … from xun-t-oss` 系列提交）。上游只存在 194 基线的 xun 树，
不存在 167 基线，所以基线只能是它。

### 为什么用设备配置而不是树里的 defconfig

树里自带 `gki_defconfig` + `vendor/bengal_GKI.config` + `vendor/xun_GKI.config` 的
AOSP 构建链，但设备实际跑的是**小米用自己配置编的内核**。`/proc/config.gz` 就是那份配置，
它既保证 `=y` 的内建驱动齐全（能开机），又保证 ABI 与模块同源。实测：用它做
`olddefconfig` 后，stock 里有而 194 树里没有的 `=y` 项只有 3 个，且全是构建探测项
（`CC_CAN_LINK` / `CC_CAN_LINK_STATIC` / `UAPI_HEADER_TEST`）。

---

## 3. 目录

```
UPSTREAM                版本参数的单一口径（上游提交 / ReSukiSU 提交）
configs/
  xun-stock.config      设备 /proc/config.gz（构建基准，勿改）
  xun-features.config   特性叠加片段（Droidspaces / ReSukiSU / SUSFS）
  xun-built.config      已发布那版编出来的完整 .config（留档）
  xun-stock-crc.tsv     ★ 原厂 469 个模块的 (符号, CRC) 基线，3414 条
  xun-stock-module-exports.txt
                        ★ 原厂模块彼此导出的符号集合（判「真缺口」用）
patches/                特性改动（按序号叠加到上游树）
scripts/
  fetch.sh              克隆上游内核树与 ReSukiSU 到 kernel/
  apply.sh              在 kernel/ 上叠补丁（幂等）
  build.sh              配置 + 硬闸 A/B + CRC/真缺口闸门 + make Image
  crc_check.py          CRC 闸门；--dump 可从厂商 .ko 重新生成基线
  gap_analysis.py       把「我方未导出」拆成模块自给 / 真缺口；--dump 同上
  package-ak3.sh        打 AnyKernel3 包
.github/workflows/
  build.yml             GitHub Actions：编 Image + 打刷机包（可选发 Release）
kernel/                 上游工作树（不入库，fetch.sh 现拉）
out/                    构建产物（不入库）
```

★ 那两个 `configs/xun-stock-*.{tsv,txt}` 是**纯数字/符号名**的基线，不含厂商代码 ——
所以闸门能在没有厂商 `.ko` 的 CI 里跑，也不必把 131MB 的私有模块分发进仓库。
本地有 `.ko` 时脚本优先现算，两者结论一致（实测 847 / 0 逐项相同）。

---

## 4. 构建

### 本地

```bash
bash scripts/fetch.sh          # 克隆 kernel/ 与 KernelSU/（浅克隆）
bash scripts/apply.sh          # 叠 patches/
CLANG_DIR=/path/to/clang-r450784d bash scripts/build.sh
bash scripts/package-ak3.sh    # 出 AnyKernel3-XUN-*.zip
```

`build.sh` 的环境变量：`CLANG_DIR`（工具链）、`CCACHE_DIR`、`BUILD_LOG`、
`JOBS`、`FEATURES=0|1`（默认 1，0 = 只编基线不叠特性）。

### GitHub Actions

Actions → **Build XUN Kernel (Redmi Pad SE)** → Run workflow。

| 输入 | 默认 | 说明 |
|---|---|---|
| `package_ak3` | true | 打包 AnyKernel3；关掉就只出 `Image` |
| `features` | true | 关掉 = 只编基线。**排查「刷了不开机是不是特性的锅」时用它**：基线能开机、特性版不能，问题就在特性里 |
| `ccache_update` | false | 换工具链 / 改配置后开启，刷新 ccache |
| `create_release` | false | 构建成功后自动发 Release（默认关，产物走 artifact） |

实测耗时：CI（4 核 / 16GB runner，**冷 ccache**）**30.6 分钟**；本地 Linux（16 核、热 ccache）22~29 分钟。
FullLTO 的 `vmlinux` 链接是单线程，占大头且不吃 ccache，内存峰值顶到 ~15GB（16GB runner 上必须补 swap）。
public 仓库的 Actions 额度不限，随便跑。

> 版本串在 CI 里长这样：`5.15.194-g<上游提交号>`。CI 的补丁是打到工作树上的，
> 树必然是脏的（否则会带 `-dirty`），workflow 里去掉了。它与本地开发时那份
> （`-g<特性提交号>`）**字符串不同、代码相同** —— 两边都指向同一套补丁。

---

## 5. 刷入

用任意支持 **AnyKernel3** 的方式刷（KernelSU 管理器 / TWRP / `fastboot` 都不必）：

1. 备份原 `boot` 分区（TWRP 备份，或 `dd if=/dev/block/by-name/boot of=...`）。
2. 卡刷 `AnyKernel3-XUN-*.zip`。
3. 重启后核对：

```bash
uname -r                    # 应为 5.15.194-g...
su -c 'cat /proc/version'
```

AnyKernel3 会自己判断当前槽位（A/B），只换 `boot` 里的内核，**不动 `init_boot` 的 ramdisk**，
所以不会碰到 Magisk / KSU 的 ramdisk 补丁。

> ⚠️ 刷内核有风险，可能导致无法开机、WiFi / 指纹异常等。出问题回刷备份的 `boot` 即可，
> 数据不受影响。

### 用了什么

- **ReSukiSU 管理器**：[ReSukiSU_CI](https://github.com/cctv18/ReSukiSU_CI/releases)
- **Droidspaces**：SYSVIPC / POSIX_MQUEUE / IPC_NS / PID_NS / USER_NS / DEVTMPFS /
  TMPFS_XATTR / NETFILTER_XT_* / IP_SET。`sysvsem` / `sysvshm` 搬进了
  `ANDROID_KABI_USE(6..8)` 里，不破坏 `task_struct` 布局（CRC 不符数为 0 即证）。
- **daed**：需要 `BPF_FUNC_loop`（5.15 上原本没有，已回填），以及 BPF 回调的
  CFI 修复 —— JITed 子程序不在 CFI 表里，内核 C 代码间接调用它会触发 CFI abort，
  表现为**瞬时全机静默 + 硬复位**，所以用 `noinline __nocfi` 包住调用点。

---

## 6. 状态与已知的坑

见 [`STATUS.md`](STATUS.md)：闸门实测数据、验收记录、移植过程中踩过的坑逐条列在那儿。

---

## 7. 致谢

- [Xiaomi-Redmi-Pad-SE-Resources](https://github.com/Xiaomi-Redmi-Pad-SE-Resources) —— 上游内核树
- [ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) —— 内核级 root
- [SUSFS](https://gitlab.com/simonpunk/susfs4ksu) —— root 隐藏
- [osm0sis/AnyKernel3](https://github.com/osm0sis/AnyKernel3) —— 卡刷包框架
- [Droidspaces](https://github.com/ravindu644/Droidspaces-OSS) —— 容器化支持
- [cctv18](https://github.com/cctv18) —— ReSukiSU 管理器构建与若干补丁思路
