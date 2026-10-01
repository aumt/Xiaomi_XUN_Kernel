#!/usr/bin/env python3
"""比对：设备 stock 模块 import 的 (符号, CRC) vs 我们内核导出的 (符号, CRC)。

用法:
    crc_check.py <vmlinux.symvers> [--list]   跑闸门
    crc_check.py --dump [目标.tsv]            从厂商 .ko 固化基线 TSV

stock 侧的来源有两种：
  1. 有厂商 .ko —— 解析每个 .ko 的 __versions 段，合并。
     目录由 $XUN_STOCK_DIRS 给出（冒号分隔），缺省 <仓库根>/_recon/{modules,
     vramdisk/lib/modules}（放本地抽取出来的厂商模块，不入库）。
  2. 没有 .ko（CI）—— 读已固化的 TSV 基线（$XUN_STOCK_CRC，
     缺省 configs/xun-stock-crc.tsv）。基线里只有「符号名 + CRC 数字」，
     不含厂商代码，所以能随仓库公开分发。

★ 闸门要喂 vmlinux.symvers，不是 Module.symvers：`make Image` 的 MODPOST 写前者；
  后者只有 `make modules` 才生成，而 `make modules_prepare` 两者都不生成。
"""
import os, struct, sys, json, glob

MODULE_NAME_LEN = 56
ENTRY = 8 + MODULE_NAME_LEN

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

DIRS = [d for d in os.environ.get('XUN_STOCK_DIRS', '').split(':') if d] or [
    os.path.join(_ROOT, '_recon', 'modules'),
    os.path.join(_ROOT, '_recon', 'vramdisk', 'lib', 'modules'),
]
TSV = os.environ.get('XUN_STOCK_CRC') or os.path.join(_ROOT, 'configs', 'xun-stock-crc.tsv')
RESULT_JSON = os.environ.get('XUN_CRC_RESULT') or os.path.join(_ROOT, 'out', 'crc_result.json')


def parse_versions(path):
    data = open(path, 'rb').read()
    if data[:4] != b'\x7fELF' or data[4] != 2 or data[5] != 1:
        return None
    e_shoff, = struct.unpack_from('<Q', data, 0x28)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', data, 0x3a)
    if not e_shoff or not e_shnum:
        return None
    shs = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        shs.append(struct.unpack_from('<IIQQQQIIQQ', data, off))
    strtab_off = shs[e_shstrndx][4]

    def shname(n):
        e = data.index(b'\0', strtab_off + n)
        return data[strtab_off + n:e].decode('latin1')

    for (name, typ, flags, addr, offset, size, link, info, align, entsize) in shs:
        if shname(name) == '__versions':
            out = {}
            for i in range(size // ENTRY):
                base = offset + i * ENTRY
                crc, = struct.unpack_from('<Q', data, base)
                nm = data[base + 8:base + 8 + MODULE_NAME_LEN].split(b'\0')[0].decode('latin1')
                if nm:
                    out[nm] = crc & 0xffffffff
            return out
    return None


def find_kos():
    ko = []
    for d in DIRS:
        ko += glob.glob(os.path.join(d, '**', '*.ko'), recursive=True)
    return sorted(ko)


def collect_stock():
    """返回 (ko 列表, 解析成功的模块数, {符号: crc}, {符号: {冲突的 crc}})。

    .ko 一个都没有时返回 (空, 0, {}, {})，调用方改用 TSV 基线。
    """
    ko = find_kos()
    syms, conflicts, nmod = {}, {}, 0
    for p in ko:
        v = parse_versions(p)
        if v is None:
            continue
        nmod += 1
        for k, c in v.items():
            if k in syms and syms[k] != c:
                conflicts.setdefault(k, {syms[k]}).add(c)
            syms[k] = c
    return ko, nmod, syms, conflicts


def load_tsv(path):
    out = {}
    with open(path) as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) != 2:
                continue
            sym, crc = parts
            out[sym] = int(crc, 16)
    return out


def dump_tsv(dest):
    ko, nmod, stock, conflicts = collect_stock()
    if not stock:
        print(f'!! 在 {":".join(DIRS)} 下一个 .ko 都没找到，无法固化基线')
        return 1
    with open(dest, 'w') as f:
        f.write('# stock 模块 import 的 (符号, CRC) 基线\n')
        f.write('# 由 scripts/crc_check.py --dump 生成；CRC 闸门读它，\n')
        f.write('# 这样就不必把厂商 .ko 分发进仓库。\n')
        f.write('# 格式: 符号<TAB>CRC(0x十六进制)\n')
        for s in sorted(stock):
            f.write(f'{s}\t{stock[s]:#010x}\n')
    print(f'已写 {dest}: {len(stock)} 个符号'
          f'（.ko {len(ko)} 个，解析成功 {nmod}，自冲突 {len(conflicts)}）')
    if conflicts:
        print('  ⚠ stock 模块之间 CRC 不一致的符号（已按最后出现取值）:')
        for s in sorted(conflicts)[:20]:
            print(f'     {s}: {sorted(hex(c) for c in conflicts[s])}')
    return 0


def parse_symvers(path):
    out = {}
    for line in open(path):
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        crc_s, sym = parts[0].strip(), parts[1].strip()
        if not crc_s.startswith('0x'):
            continue
        out[sym] = int(crc_s, 16)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    if sys.argv[1] == '--dump':
        return dump_tsv(sys.argv[2] if len(sys.argv) > 2 else TSV)

    symvers = sys.argv[1]

    ko, nmod, stock, conflicts = collect_stock()
    if nmod:
        print(f"[stock] .ko 文件 {len(ko)}，解析成功 {nmod}，符号 {len(stock)}，自冲突 {len(conflicts)}")
    else:
        if not os.path.exists(TSV):
            print(f'[stock] 既没有 .ko（{":".join(DIRS)}）也没有 TSV 基线 {TSV}')
            return 2
        stock = load_tsv(TSV)
        print(f"[stock] 无 .ko，改用 TSV 基线 {os.path.relpath(TSV, _ROOT)}，符号 {len(stock)}")

    mine = parse_symvers(symvers)
    print(f"[ours ] Module.symvers 符号 {len(mine)}")

    missing = sorted(s for s in stock if s not in mine)
    mismatch = sorted(s for s in stock if s in mine and mine[s] != stock[s])
    ok = sorted(s for s in stock if s in mine and mine[s] == stock[s])

    print()
    print(f"  ✅ CRC 一致      : {len(ok)}")
    print(f"  ❌ CRC 不符      : {len(mismatch)}")
    print(f"  ⛔ 我方未导出    : {len(missing)}")
    print()

    if mismatch:
        print("  ---- CRC 不符明细（前 60）----")
        for s in mismatch[:60]:
            print(f"     {s:44s} stock={stock[s]:#010x}  ours={mine[s]:#010x}")
    if missing:
        print("  ---- 未导出明细（前 60）----")
        for s in missing[:60]:
            print(f"     {s}")
    if sys.argv[-1] == '--list' and ok:
        print("  ---- 一致样本（前 20）----")
        for s in ok[:20]:
            print(f"     {s:44s} {stock[s]:#010x}")

    os.makedirs(os.path.dirname(RESULT_JSON), exist_ok=True)
    json.dump({'ok': len(ok), 'mismatch': mismatch, 'missing': missing},
              open(RESULT_JSON, 'w'), indent=1)
    # 退出码：0 全对，1 有问题
    return 0 if (not mismatch and not missing) else 1


if __name__ == '__main__':
    sys.exit(main())
