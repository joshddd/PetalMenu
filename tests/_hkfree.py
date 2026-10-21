# -*- coding: utf-8 -*-
"""探测组合键是否已被别的程序 RegisterHotKey 占用（只注册不做事，探完就注销）"""
import ctypes
import sys

MOD_ALT, MOD_CTRL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
MOD_NOREPEAT = 0x4000

u = ctypes.windll.user32
u.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
u.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]

COMBOS = [
    ("alt+z", MOD_ALT | MOD_NOREPEAT, 0x5A),
    ("ctrl+alt+v", MOD_CTRL | MOD_ALT | MOD_NOREPEAT, 0x56),
    ("ctrl+alt+p", MOD_CTRL | MOD_ALT | MOD_NOREPEAT, 0x50),
    ("ctrl+alt+o", MOD_CTRL | MOD_ALT | MOD_NOREPEAT, 0x4F),
    ("ctrl+alt+d", MOD_CTRL | MOD_ALT | MOD_NOREPEAT, 0x44),
    ("ctrl+alt+m", MOD_CTRL | MOD_ALT | MOD_NOREPEAT, 0x4D),
    ("ctrl+alt+i", MOD_CTRL | MOD_ALT | MOD_NOREPEAT, 0x49),
    ("ctrl+alt+a", MOD_CTRL | MOD_ALT | MOD_NOREPEAT, 0x41),
]

bad = []
for i, (name, mods, vk) in enumerate(COMBOS):
    ok = u.RegisterHotKey(None, 0xB000 + i, mods, vk)
    err = ctypes.get_last_error() if hasattr(ctypes, "get_last_error") else 0
    if ok:
        u.UnregisterHotKey(None, 0xB000 + i)
    else:
        bad.append(name)
    print("  %-12s %s" % (name, "空闲" if ok else "被占用"), flush=True)

print("\n被占用: %s" % (bad or "无"), flush=True)
print("ctrl+alt+o %s" % ("可用，可以留给 open_auto" if "ctrl+alt+o" not in bad else "被占用，请换一个"), flush=True)
sys.exit(0)
