# -*- coding: utf-8 -*-
"""启动 PetalMenu exe（可带 PETALMENU_HOOK_DEBUG=1），并清空 hook.log。

用法：python _launch_pm.py <dist_dir> [--debug]
"""
import os
import subprocess
import sys
import time

dist = sys.argv[1] if len(sys.argv) > 1 else "dist_v8"
debug = "--debug" in sys.argv
exe = os.path.join(r"C:\tmp\hotkey", dist, "PetalMenu.exe")
env = dict(os.environ)
if debug:
    env["PETALMENU_HOOK_DEBUG"] = "1"
log = os.path.expandvars(r"%APPDATA%\PetalMenu\hook.log")
if debug:
    for p in (log, log + ".old"):
        try:
            os.remove(p)
        except OSError:
            pass
subprocess.Popen([exe], env=env, creationflags=0x00000008)
time.sleep(4)
print("exe:", exe, "exists:", os.path.exists(exe))
if os.path.exists(log):
    tail = open(log, encoding="utf-8", errors="replace").read().splitlines()[-8:]
    print("hook.log tail(%d lines):" % len(tail))
    for line in tail:
        print("  " + line)
else:
    print("hook.log: (none)")
