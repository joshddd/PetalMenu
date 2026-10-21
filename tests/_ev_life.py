# -*- coding: utf-8 -*-
"""启动 Everything，报告窗口存活时长与退出码。"""
import ctypes
import subprocess
import sys
import time

u32 = ctypes.windll.user32
EXE = r"C:\Program Files\Everything\Everything.exe"


def win():
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(128)
        u32.GetClassNameW(h, b, 128)
        if b.value == "EVERYTHING":
            out.append(h)
        return True

    u32.EnumWindows(cb, None)
    return out


args = sys.argv[1:]
p = subprocess.Popen([EXE] + args, creationflags=0x00000008)
t0 = time.time()
seen = False
while time.time() - t0 < 150:
    time.sleep(1)
    alive = p.poll() is None
    w = win()
    if w:
        seen = True
    print("%3.0fs proc=%s rc=%s win=%d" % (time.time() - t0, "alive" if alive else "dead",
                                           p.poll(), len(w)), flush=True)
    if not alive:
        print("EXITED after %.1fs rc=%s (window_seen=%s)" % (time.time() - t0, p.poll(), seen))
        break
