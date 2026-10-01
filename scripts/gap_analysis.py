#!/usr/bin/env python3
"""
真缺口分析：把 crc_check.py 报的「我方未导出 N 个」拆成两类。

  A) stock 模块之间自给自足的 —— 某个 stock .ko 自己 EXPORT 了它。
     这类与我们无关：运行时那些 .ko 一起加载，符号由它们自己提供。

  B) 真缺口 —— 没有任何 stock 模块导出它，只能由 vmlinux 提供。
     这类才会让模块加载报 "Unknown symbol"。

判定导出面用 `readelf -sW` 里的 `__ksymtab_<sym>` 条目（精确），
不用 `__ksymtab_strings`（那个会把裸命名空间串混进来，见
nx729j-stock-ksymtab-extraction 记忆里的假阳性）。
"""
import json, os, glob, subprocess, sys, re

STOCK_DIRS = [
    '/home/user/xun/_recon/modules',
    '/home/user/xun/_recon/vramdisk/lib/modules',
]
RESULT = '/home/user/xun/_recon/crc_result.json'


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


def main():
    missing = set(json.load(open(RESULT))['missing'])
    kos = find_kos()
    print(f"stock .ko = {len(kos)}")
    print(f"未导出（待拆分）= {len(missing)}")

    exported_by_modules = set()
    per_ko = {}
    for k in kos:
        e = module_exports(k)
        per_ko[k] = e
        exported_by_modules |= e
    print(f"stock 模块自己导出的符号 = {len(exported_by_modules)}")

    self_supplied = missing & exported_by_modules
    true_gap = missing - exported_by_modules

    print()
    print(f"  A) 模块自给自足（与我们无关） : {len(self_supplied)}")
    print(f"  B) 真缺口（只能 vmlinux 提供）: {len(true_gap)}")

    out = {
        'missing_total': len(missing),
        'self_supplied': sorted(self_supplied),
        'true_gap': sorted(true_gap),
        'exported_by_modules': len(exported_by_modules),
    }
    with open('/home/user/xun/_recon/gap_result.json', 'w') as f:
        json.dump(out, f, indent=1)

    print()
    print("---- 真缺口全量（B）----")
    for s in sorted(true_gap):
        print("   ", s)

    # 每个真缺口：有多少个 stock 模块 import 它
    print()
    print("---- 真缺口按「被几个模块 import」排序（前 40）----")
    import collections
    cnt = collections.Counter()
    for k, e in per_ko.items():
        pass
    # 需要 import 面，从 crc_check 的 stock 符号表重算成本高，这里跳过


if __name__ == '__main__':
    main()
