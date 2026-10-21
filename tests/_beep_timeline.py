# -*- coding: utf-8 -*-
"""打印音量表时间线：区分“短促一声叮”和“持续音”。

用法：python.exe C:/tmp/hotkey/tests/_beep_timeline.py [explorer|probe]
"""
import os
import sys
import time
import winsound

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _beep_probe import Meter  # noqa: E402
import _beep_e2e as E  # noqa: E402

BUCKET = 0.1


def timeline(tag, samples):
    buckets = {}
    for t, p in samples:
        buckets.setdefault(int(t / BUCKET), []).append(p)
    dur = max(buckets) + 1 if buckets else 0
    row = []
    for i in range(dur):
        mx = max(buckets.get(i, [0.0]))
        row.append("." if mx < 0.002 else ("%X" % min(15, int(mx * 30))))
    loud = sum(1 for v in row if v != ".")
    print("%-14s |%s| loud_buckets=%d/%d max=%.4f"
          % (tag, "".join(row), loud, dur, max(p for _t, p in samples)))
    return loud


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "explorer").lower()
    m = Meter()
    if mode == "probe":
        hwnd = E.make_probe_window()
        print("probe fg=%s" % (E.user32.GetForegroundWindow() == hwnd))
    else:
        hwnd, cls, txt = E.find_window(lambda c, t: c == "CabinetWClass")
        if not hwnd:
            print("没有资源管理器窗口")
            return 1
        print("explorer=%s focus=%s" % (txt, E.grab_focus(hwnd)))
        time.sleep(0.4)
        E.combo(0x11, 0x41)
        time.sleep(0.5)

    m.sample(0.3)
    mark = len(m.sample(0.0))
    samples = []
    t0 = time.time()

    def collect(seconds):
        nonlocal samples
        part = m.sample(seconds)
        base = time.time() - t0 - seconds
        samples += [(base + t, p) for t, p in part]

    winsound.MessageBeep(winsound.MB_ICONASTERISK)
    collect(1.2)
    tl_cal = timeline("calibrate", samples)

    m.sample(0.6)
    samples = []
    t0 = time.time()
    E.combo(0xA4, 0x5A)
    collect(2.5)
    tl_hk = timeline("alt+z", samples)

    pm, pm_cls, pm_txt = E.find_window(lambda c, t: "PetalMenu" in t)
    print("menu_window=%s (%s)" % (bool(pm), pm_cls))
    print("VERDICT sound_on_hotkey=%s" % (tl_hk > 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
