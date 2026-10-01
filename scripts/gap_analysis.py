#!/usr/bin/env python3
"""
真缺口分析：把 crc_check.py 报的「我方未导出 N 个」拆成两类。

  A) stock 模块之间自给自足的 —— 某个 stock .ko 自己 EXPORT 了它。
     这类与我们无关：运行时那些 .ko 一起加载，符号由它们自己提供。

  B) 真缺口 —— 没有任何 stock 模块导出它，只能由 vmlinux 提供。
     这类才会让模块加载报 "Unknown symbol"。

判定导出面用 `readelf -sW` 里的 `__ksymtab_<sym>` 条目（精确），
不用 `__ksymtab_strings`（那个会把裸命名空间串混进来 —— 厂商 `__versions`
里 0 次、我方 symvers 里 0 次、而我方段内同样有，三条同时满足才是这类假阳性）。

stock 侧来源两种（同 crc_check.py）：
  1. 厂商 .ko 在场 —— readelf 现算。
  2. 不在场 —— 读已固化的导出面清单 $XUN_MODULE_EXPORTS
     （缺省 configs/xun-stock-module-exports.txt，只有符号名，可公开）。

用法:
    gap_analysis.py              分析（上面的 $XUN_CRC_RESULT 由 crc_check.py 写出）
    gap_analysis.py --dump [目标] 从厂商 .ko 固化导出面清单
"""
import json, os, glob, subprocess, sys, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

STOCK_DIRS = [d for d in os.environ.get('XUN_STOCK_DIRS', '').split(':') if d] or [
    os.path.join(_ROOT, '_recon', 'modules'),
    os.path.join(_ROOT, '_recon', 'vramdisk', 'lib', 'modules'),
]
EXPORTS_TXT = os.environ.get('XUN_MODULE_EXPORTS') or os.path.join(
    _ROOT, 'configs', 'xun-stock-module-exports.txt')
RESULT = os.environ.get('XUN_CRC_RESULT') or os.path.join(_ROOT, 'out', 'crc_result.json')
GAP_OUT = os.environ.get('XUN_GAP_RESULT') or os.path.join(_ROOT, 'out', 'gap_result.json')


def find_kos():
    ko = []
    for d in STOCK_DIRS:
        ko += glob.glob(os.path.join(d, '**', '*.ko'), recursive=True)
    return sorted(ko)


def module_exports(path):
    """该 .ko 导出的符号集合，走 __ksymtab_<sym> 符号名。"""
    try:
        out = subprocess.run(['readelf', '-sW', path],
                             capture_output=True, text=True, check=True).stdout
    except Exception:
        return set()
    syms = set()
    for line in out.splitlines():
        # 形如:  1234: 0000000000000000    16 OBJECT  GLOBAL DEFAULT   12 __ksymtab_foo
        m = re.search(r'\s__(?:ksymtab|ksymtab_gpl|ksymtab_unused|ksymtab_unused_gpl)_(\S+)\s*$', line)
        if m:
            syms.add(m.group(1))
    return syms


def collect_exports():
    """返回 (ko 数, 导出符号集合)。没有 .ko 时返回 (0, 空集)。"""
    kos = find_kos()
    exported = set()
    for k in kos:
        exported |= module_exports(k)
    return len(kos), exported


def load_exports_txt(path):
    out = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                out.add(line)
    return out


def dump_exports(dest):
    nko, exported = collect_exports()
    if not exported:
        print(f'!! 在 {":".join(STOCK_DIRS)} 下一个 .ko 都没找到，无法固化导出面')
        return 1
    with open(dest, 'w') as f:
        f.write('# stock 模块自己 EXPORT 的符号集合\n')
        f.write('# 由 scripts/gap_analysis.py --dump 生成；用来把 crc_check.py 报的\n')
        f.write('# 「我方未导出」拆成「模块自给」与「真缺口」。只有符号名，可公开。\n')
        for s in sorted(exported):
            f.write(s + '\n')
    print(f'已写 {dest}: {len(exported)} 个符号（来自 {nko} 个 .ko）')
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--dump':
        return dump_exports(sys.argv[2] if len(sys.argv) > 2 else EXPORTS_TXT)

    if not os.path.exists(RESULT):
        print(f'!! 找不到 {RESULT} —— 先跑 scripts/crc_check.py <vmlinux.symvers>')
        return 2
    missing = set(json.load(open(RESULT))['missing'])

    nko, exported_by_modules = collect_exports()
    if nko:
        print(f"stock .ko = {nko}")
        print(f"stock 模块自己导出的符号 = {len(exported_by_modules)}")
    else:
        if not os.path.exists(EXPORTS_TXT):
            print(f'!! 既没有 .ko（{":".join(STOCK_DIRS)}）也没有导出面清单 {EXPORTS_TXT}')
            return 2
        exported_by_modules = load_exports_txt(EXPORTS_TXT)
        print(f"stock .ko = 0（改用导出面清单 {os.path.relpath(EXPORTS_TXT, _ROOT)}）")
        print(f"stock 模块自己导出的符号 = {len(exported_by_modules)}")

    print(f"未导出（待拆分）= {len(missing)}")

    self_supplied = missing & exported_by_modules
    true_gap = missing - exported_by_modules

    print()
    print(f"  A) 模块自给自足（与我们无关） : {len(self_supplied)}")
    print(f"  B) 真缺口（只能 vmlinux 提供）: {len(true_gap)}")

    os.makedirs(os.path.dirname(GAP_OUT), exist_ok=True)
    with open(GAP_OUT, 'w') as f:
        json.dump({
            'missing_total': len(missing),
            'self_supplied': sorted(self_supplied),
            'true_gap': sorted(true_gap),
            'exported_by_modules': len(exported_by_modules),
        }, f, indent=1)

    print()
    print("---- 真缺口全量（B）----")
    for s in sorted(true_gap):
        print("   ", s)

    # 非 0 即失败：有真缺口就说明有模块会 "Unknown symbol" 装不上
    return 0 if not true_gap else 1


if __name__ == '__main__':
    sys.exit(main())
