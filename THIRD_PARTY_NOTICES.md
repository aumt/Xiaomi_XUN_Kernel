# 第三方组件与许可证

本仓库（`Xiaomi_XUN_Kernel`）自身以 **GPL-3.0** 发布，全文见 [LICENSE](LICENSE)。

仓库里只存**补丁、脚本、配置基线**：上游内核树与 ReSukiSU 都不入库，由 `scripts/fetch.sh`
在构建时按 `UPSTREAM` 记录的提交现拉（`.gitignore` 里 `/kernel/`）；刷机包也只在 Release
发布（`*.zip` 同样被忽略）。所以下面分**仓库内**、**构建时引进来的**、**打进刷机包的**三部分写。

---

## 一、仓库内

### 1.1 本项目原创 —— GPL-3.0

`README.md`、`UPSTREAM`、`scripts/*.sh`、`scripts/*.py`、`.github/workflows/build.yml`、
`configs/xun-features.config`、`configs/xun-built.config` 由本项目编写，
以 **GPL-3.0** 授权，全文见 [LICENSE](LICENSE)。

### 1.2 `patches/0001`、`0002` —— 被改动的代码仍是 GPL-2.0-only

| 补丁 | 改了什么 |
|---|---|
| `0001-bpf_loop-Droidspaces-kABI.patch` | `BPF_FUNC_loop` 回填；Droidspaces 需要的 kABI（`sysvsem` / `sysvshm` 搬进 `ANDROID_KABI_USE`，不动 `task_struct` 布局） |
| `0002-daed-verifier-CFI-__nocfi-bpf_sk_assign-reuseport.patch` | verifier 白名单补齐；BPF 回调的 CFI `noinline __nocfi`；`bpf_sk_assign` 放行 `SO_REUSEPORT` |

两份补丁改的都是 Linux 内核（ACK `android13-5.15`）的既有文件，
**被改动的代码仍适用内核原本的许可：GPL-2.0-only**
（上游树根 `COPYING`：`GPL-2.0 WITH Linux-syscall-note`）。
补丁文本与提交信息由本项目整理；个别 hunk 参考了上游后续内核（如 6.6）的实现。

> Droidspaces 本身（[ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS)）
> 不在此仓库、也不在内核里 —— 这里只是把内核侧它需要的开关与 kABI 打开。

### 1.3 `patches/0003` —— 一个补丁里两种许可，按文件区分

| 部分 | 许可 |
|---|---|
| 新增的 `fs/susfs.c`、`include/linux/susfs.h`、`include/linux/susfs_def.h` 三份文件（SUSFS） | **GPL-3.0** |
| 其余 25 处对既有内核文件的改动（`fs/*`、`kernel/*`、`security/selinux/*`、`drivers/*` 等；含新增符号链接 `drivers/kernelsu`） | **GPL-2.0-only**（`drivers/kernelsu` 指向 ReSukiSU 内核部分，GPL-2.0，见 2.2） |

SUSFS 来自 [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu)（默认分支 `master`，
仓库根 `LICENSE` 为 GPLv3 全文），对应版本 `SUSFS_VERSION "v2.2.0"`。
上游**没有在源文件内逐文件声明许可**，本仓库按 GPL-3.0-only 标注，并把**来源、版本、
「本树作过改动」**写进了这三份文件的头部。

> ⚠️ **许可不兼容**：本内核树整体是 GPL-2.0-only，SUSFS 是 GPL-3.0，二者**互不兼容**，
> 不能合并分发。此处如实标注上游许可，**不代表合并分发在法律上成立**。
> 自行编译、自行刷机属于个人使用行为。

### 1.4 `configs/` —— 从设备固件提取的**数据**，不是代码

| 文件 | 来源 |
|---|---|
| `xun-stock.config` / `xun-stock.config.gz` | 设备 `/proc/config.gz`，即小米 stock `OS2.0.205.0.VMUMIXM` 的内核配置 |
| `xun-built.config` | 干净 194 树对该配置做 `olddefconfig` 的结果（配置可行性对照） |
| `xun-stock-crc.tsv` | 原厂 469 个模块的 `(符号, CRC)` 基线，3414 条 |
| `xun-stock-module-exports.txt` | 原厂模块彼此导出的符号集合 |

内容是**配置项与符号名/数字**，不含厂商代码、不含可执行代码。放进仓库正是为了让
CRC 与「真缺口」两道闸门能在**没有厂商 `.ko` 的 CI 里**跑，
而不必把 131MB 的私有模块分发进仓库。

---

## 二、构建时引进来的（不入库，也不随仓库分发）

### 2.1 上游内核树 —— GPL-2.0 WITH Linux-syscall-note

- `https://github.com/Xiaomi-Redmi-Pad-SE-Resources/android_kernel_xiaomi_sm6225.git`
- `lineage-23.0` @ `676f5fa0e5617e95d5c5d10ac605206536376845`（5.15.194）
- 许可：树根 `COPYING` 为 `GPL-2.0 WITH Linux-syscall-note`；个别文件另有自身声明，
  见树内 `LICENSES/`（含 `exceptions/Linux-syscall-note`）。

### 2.2 ReSukiSU —— 编进内核的是 GPL-2.0 那部分

- `https://github.com/ReSukiSU/ReSukiSU.git` @ `3a2745f78ab68e61c02a0681463021952083ec8c`
- 根 `LICENSE` = **GPL-3.0**；`KernelSU/kernel/LICENSE` = **GPL-2.0**。
  实际参与编译的是 `KernelSU/kernel/`，即 **GPL-2.0** 那部分。

### 2.3 AnyKernel3

见第三部分 —— 它进的是刷机包，不是仓库。

---

## 三、刷机包（Release 里的 `AnyKernel3-XUN-*.zip`）

`scripts/package-ak3.sh` 浅克隆 [osm0sis/AnyKernel3](https://github.com/osm0sis/AnyKernel3)
到 `anykernel3/`（`.gitignore` 已忽略），换上本仓库写死的 `anykernel.sh`，
放入编好的 `Image` 后打 zip。包里因此有三类东西：

**1）本项目的产物**

- `Image`：由 **上游内核树 + 本仓库 `patches/` + ReSukiSU** 编译得到，是内核的二进制。
  分发它适用内核的 **GPL-2.0**（含本仓库补丁的改动）；其中 SUSFS 三份文件为 **GPL-3.0**
  （见 1.3 的不兼容提示）。对应源码可完整重建：上游提交见 `UPSTREAM`，
  改动见 `patches/`，命令见 README 第 4 节。
- `anykernel.sh`：本项目按 AK3 模板写的配置脚本。

**2）AnyKernel3 自带脚本**（`anykernel.sh` 模板、`tools/ak3-core.sh` 等）
—— AnyKernel 脚本许可，类 BSD-3-Clause，© osm0sis 及贡献者，
全文见 AK3 仓库的 `LICENSE`。

**3）AK3 自带的第三方二进制**（许可引自 AK3 的 `LICENSE`）：

| 二进制 | 许可 |
|---|---|
| `tools/magiskboot`、`tools/magiskpolicy` | GPL-3.0-or-later（Magisk，© topjohnwu） |
| `tools/busybox` | GPL-2.0（仅 v2） |
| `tools/lptools_static`、`tools/fec`、`tools/snapshotupdater_static` | Apache-2.0 |
| `tools/httools_static` | MIT（© 2022 capntrips） |

AK3 里**本来还有、但本项目的包里没有**的可选二进制（`mkbootfs`、`mkbootimg`、`mkmtkhdr`、
`boot_signer*.jar`、mtd-utils、U-Boot、`mboot`、`futility`、`unpackelf`、`elftool`、`rkcrc`），
许可是 Apache-2.0 / GPLv2 / GPLv2+ / BSD-3-Clause / BSD-2-Clause，逐项见 AK3 的 `LICENSE`。

---

## 四、说明

- 本文件只做**如实标注**，不构成法律意见。已知的许可冲突（GPL-2.0-only 内核 + GPL-3.0 SUSFS）
  已在 1.3 点明。
- 各上游组件的版权归各自作者所有，出处见上文链接与 README 第 6 节「致谢」。
- 发现标注有误或缺少署名，请开 issue。
