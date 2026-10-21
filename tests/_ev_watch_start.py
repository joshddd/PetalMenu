# -*- coding: utf-8 -*-
"""启动 Everything 并观察 UI 进程是否存活。"""
import ctypes
import subprocess
import time

u32 = ctypes.windll.user32
EXE = r"C:\Program Files\Everything\Everything.exe"


def wins():
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(128)
        u32.GetClassNameW(h, b, 128)
        if b.value == "EVERYTHING":
            t = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(h, t, 256)
            out.append((h, t.value, bool(u32.IsWindowVisible(h))))
        return True

    u32.EnumWindows(cb, None)
    return out


p = subprocess.Popen([EXE], creationflags=0x00000008)
print("launched pid", p.pid, flush=True)
for i in range(24):
    time.sleep(0.5)
    print("%.1fs rc=%s wins=%s" % ((i + 1) * 0.5, p.poll(), wins()), flush=True)
