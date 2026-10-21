# -*- coding: utf-8 -*-
"""热键端到端记录：音频时间线 + 菜单窗口出现时刻，对齐到同一时间轴。

用法：
    python.exe C:/tmp/hotkey/tests/_beep_align.py              # 默认 alt+z
    python.exe C:/tmp/hotkey/tests/_beep_align.py alt+q alt+z  # 对照组 + 目标
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _beep_probe import SystemSoundsMeter, com_init  # noqa: E402
import _beep_e2e as E  # noqa: E402

VK_ESC = 0x1B
VK = {"alt": 0xA4, "ctrl": 0x11, "shift": 0x10,
      "z": 0x5A, "q": 0x51, "c": 0x43, "x": 0x58, "esc": 0x1B}


def parse_combo(spec):
    return tuple(VK[p] for p in spec.lower().split("+") if p in VK)


def is_menu_open():
    hwnd, cls, _txt = E.find_window(lambda c, t: "PetalMenu" in t or "PetalMenu" in c)
    return bool(hwnd), cls


def close_menu():
    for _ in range(3):
        if not is_menu_open()[0]:
            return
        E.send(VK_ESC)
        E.send(VK_ESC, up=True)
        time.sleep(0.35)


def press(vks, hold=0.06, wait_menu=False):
    """按下所有键 -> 保持 hold 秒（或等菜单真的出现）-> 逆序抬起。"""
    for vk in vks:
        E.send(vk)
        time.sleep(0.03)
    if wait_menu:
        t0 = time.time()
        while time.time() - t0 < 2.5 and not is_menu_open()[0]:
            time.sleep(0.02)
        time.sleep(0.15)
    else:
        time.sleep(hold)
    for vk in reversed(vks):
        E.send(vk, up=True)
        time.sleep(0.03)


def run_one(m, spec):
    base, _sep, hold = spec.partition("@")
    vks = parse_combo(base)
    wait_menu = hold.lower() == "wait"
    hold_s = float(hold) / 1000.0 if hold and not wait_menu else 0.06
    close_menu()
    audio = []
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            audio.append((time.time(), m.peak()))
            time.sleep(0.012)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()

    t_press = time.time()
    if base.lower() == "beep":
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    else:
        press(vks, hold_s, wait_menu)
    seen, events = False, []
    t0 = time.time()
    while time.time() - t0 < 2.2:
        op, _c = is_menu_open()
        if op and not seen:
            seen = True
            events.append(("menu_open", round(time.time() - t_press, 2)))
        elif not op and seen:
            seen = False
            events.append(("menu_closed", round(time.time() - t_press, 2)))
        time.sleep(0.02)
    time.sleep(0.1)
    stop.set()
    th.join(timeout=1.2)

    buckets = {}
    for t, p in audio:
        buckets.setdefault(int((t - t_press) / 0.1), []).append(p)
    n = max(buckets) + 1 if buckets else 0
    chars = []
    for i in range(n):
        mx = max(buckets.get(i, [0.0]))
        chars.append("." if mx < 0.003 else "%X" % min(15, max(1, int(mx * 300))))
    loud = [i for i, c in enumerate(chars) if c != "."]
    print("%-9s |%s|" % (spec, "".join(chars)))
    print("          events=%s sound_buckets=%d first_at=%s"
          % (events, len(loud), ("%.1fs" % (loud[0] * 0.1)) if loud else "-"))
    return bool(loud), any(k == "menu_open" for k, _v in events)


def main():
    specs = [a for a in sys.argv[1:] if a] or ["alt+z"]
    m = SystemSoundsMeter()
    hwnd, cls, txt = E.find_window(lambda c, t: c == "CabinetWClass")
    if not hwnd:
        print("没有资源管理器窗口")
        return 1
    print("explorer=%s" % txt)
    print("focus=%s" % E.grab_focus(hwnd))
    time.sleep(0.3)
    E.combo(0x11, 0x41)          # Ctrl+A 选中文件
    time.sleep(0.4)

    results = {}
    for spec in specs:
        results[spec] = run_one(m, spec)
        time.sleep(0.5)
    print("SUMMARY " + "  ".join("%s: sound=%s menu=%s" % (k, v[0], v[1])
                                for k, v in results.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
