# -*- coding: utf-8 -*-
"""关闭 / 启动 Everything（UI 实例，session 1）。

用法：
    python _everything_ctl.py close
    python _everything_ctl.py start
"""
import ctypes
import os
import subprocess
import sys
import time

u32 = ctypes.windll.user32
EXE = r"C:\Program Files\Everything\Everything.exe"
WM_CLOSE = 0x0010


def find_everything():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _lp):
        buf = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "EVERYTHING":
            found.append(hwnd)
        return True

    u32.EnumWindows(cb, None)
    return found


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "close":
        hwnds = find_everything()
        print("windows:", hwnds)
        for h in hwnds:
            u32.PostMessageW(h, WM_CLOSE, 0, 0)
        for _ in range(40):
            time.sleep(0.25)
            if not find_everything():
                print("closed")
                return 0
        print("still open")
        return 1
    if cmd in ("start", "reindex"):
        args = [EXE] + (["-reindex"] if cmd == "reindex" else [])
        subprocess.Popen(args, creationflags=0x00000008)
        for _ in range(40):
            time.sleep(0.25)
            if find_everything():
                print("%s hwnd=%s" % (cmd, find_everything()[0]))
                return 0
        print("not started")
        return 1
    print("usage: close|start")
    return 2


if __name__ == "__main__":
    sys.exit(main())
