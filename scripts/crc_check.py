#!/usr/bin/env python3
"""比对：设备 stock 模块 import 的 (符号, CRC) vs 我们内核 Module.symvers 导出的 (符号, CRC)。

用法: crc_check.py <symvers> [--list]
"""
import os, struct, sys, json, glob

MODULE_NAME_LEN = 56
ENTRY = 8 + MODULE_NAME_LEN
DIRS = [
    '/home/user/xun/_recon/modules',
    '/home/user/xun/_recon/vramdisk/lib/modules',
]


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


def collect_stock():
    ko = []
    for d in DIRS:
        ko += glob.glob(os.path.join(d, '**', '*.ko'), recursive=True)
    ko.sort()
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
        print(__doc__); return 2
    symvers = sys.argv[1]

    ko, nmod, stock, conflicts = collect_stock()
    print(f"[stock] .ko 文件 {len(ko)}，解析成功 {nmod}，符号 {len(stock)}，自冲突 {len(conflicts)}")

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

    json.dump({'ok': len(ok), 'mismatch': mismatch, 'missing': missing},
              open('/home/user/xun/_recon/crc_result.json', 'w'), indent=1)
    # 退出码：0 全对，1 有问题
    return 0 if (not mismatch and not missing) else 1


if __name__ == '__main__':
    sys.exit(main())
