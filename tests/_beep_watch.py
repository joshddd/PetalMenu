# -*- coding: utf-8 -*-
"""后台监听一段时间的系统音量表，把每次“响了一下”记录下来。

用法：python.exe C:/tmp/hotkey/tests/_beep_watch.py 75
日志：C:/tmp/hotkey/tests/beep_watch.log
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _beep_probe import SystemSoundsMeter  # noqa: E402
import _beep_e2e as E  # noqa: E402

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beep_watch.log")
FLOOR = 0.004


def menu_state():
    hwnd, _cls, _t = E.find_window(lambda c, t: "PetalMenu" in t or "PetalMenu" in c)
    return bool(hwnd)


def fg_info():
    fg = E.user32.GetForegroundWindow()
    cls = E.ctypes.create_unicode_buffer(256)
    txt = E.ctypes.create_unicode_buffer(256)
    E.user32.GetClassNameW(fg, cls, 256)
    E.user32.GetWindowTextW(fg, txt, 256)
    return cls.value, txt.value


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    m = SystemSoundsMeter()
    t_end = time.time() + seconds
    events = []
    peak_max = 0.0
    prev_loud = False
    t_loud_start = None
    lines = []
    with open(LOG, "w", encoding="utf-8") as fh:
        fh.write("start=%s seconds=%.1f\n" % (time.strftime("%H:%M:%S"), seconds))
        while time.time() < t_end:
            p = m.peak()
            now = time.time()
            peak_max = max(peak_max, p)
            loud = p > FLOOR
            if loud and not prev_loud:
                t_loud_start = now
                cls, txt = fg_info()
                fh.write("%s SOUND start peak=%.4f menu=%s fg=%s|%s\n"
                         % (time.strftime("%H:%M:%S"), p, menu_state(), cls, txt))
                fh.flush()
            elif not loud and prev_loud and t_loud_start:
                fh.write("%s SOUND end   dur=%.2fs\n"
                         % (time.strftime("%H:%M:%S"), now - t_loud_start))
                fh.flush()
                events.append(now - t_loud_start)
            prev_loud = loud
            time.sleep(0.012)
        fh.write("end=%s peak_max=%.4f sounds=%d\n"
                 % (time.strftime("%H:%M:%S"), peak_max, len(events)))
    print("watched %.0fs peak_max=%.4f sound_events=%d durations=%s"
          % (seconds, peak_max, len(events), [round(d, 2) for d in events]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
