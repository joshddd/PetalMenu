# -*- coding: utf-8 -*-
"""读取 Everything 主窗口状态栏文本（用于观察索引/重建进度）。"""
import ctypes
import time

u32 = ctypes.windll.user32
u32.SendMessageW.restype = ctypes.c_ssize_t
u32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]

SB_GETPARTS = 0x0406
SB_GETTEXTLENGTHW = 0x040C
SB_GETTEXTW = 0x040D


def find(cls="EVERYTHING"):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        b = ctypes.create_unicode_buffer(128)
        u32.GetClassNameW(hwnd, b, 128)
        if b.value == cls:
            out.append(hwnd)
        return True

    u32.EnumWindows(cb, None)
    return out


def children(hwnd, cls):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(128)
        u32.GetClassNameW(h, b, 128)
        if b.value == cls:
            out.append(h)
        return True

    u32.EnumChildWindows(hwnd, cb, None)
    return out


def status_text():
    wins = find()
    if not wins:
        return "(Everything not running)"
    h = wins[0]
    bars = children(h, "msctls_statusbar32")
    if not bars:
        return "(no status bar)"
    sb = bars[0]
    n = u32.SendMessageW(sb, SB_GETPARTS, 0, None)
    parts = []
    for i in range(max(0, int(n))):
        ln = u32.SendMessageW(sb, SB_GETTEXTLENGTHW, i, None) & 0xFFFF
        buf = ctypes.create_unicode_buffer(ln + 2)
        u32.SendMessageW(sb, SB_GETTEXTW, i, ctypes.cast(buf, ctypes.c_void_p))
        parts.append(buf.value)
    return " | ".join(p for p in parts if p)


if __name__ == "__main__":
    import sys
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    t0 = time.time()
    last = None
    while True:
        s = status_text()
        if s != last:
            print("%s %s" % (time.strftime("%H:%M:%S"), s), flush=True)
            last = s
        if time.time() - t0 >= secs:
            break
        time.sleep(5)
