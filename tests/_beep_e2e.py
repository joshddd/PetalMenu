# -*- coding: utf-8 -*-
"""检测热键路径有没有真的“响一声”。

用法（Windows python，参数写 C:/ 形式）：
    python.exe C:/tmp/hotkey/tests/_beep_e2e.py probe     # 只在自建探针窗口里按 alt+q / alt+z
    python.exe C:/tmp/hotkey/tests/_beep_e2e.py explorer [folder]
                                                          # 资源管理器选中文件后按 alt+z

判定方式：WASAPI 主音量表每 15ms 采样，先标定一声人工 MessageBeep，再测目标动作；
目标动作期间出现能量突起 = 会响。
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _beep_probe import Meter, report  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_CLOSE, WM_DESTROY = 0x0010, 0x0002

# ---------------------------------------------------------------- SendInput
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


assert ctypes.sizeof(INPUT) == 40


def send(vk, up=False):
    i = INPUT(type=1)
    i.ki = KEYBDINPUT(vk, 0, 0x0002 if up else 0, 0, 0)
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))


def combo(*vks):
    for vk in vks:
        send(vk)
        time.sleep(0.03)
    for vk in reversed(vks):
        send(vk, up=True)
        time.sleep(0.03)


# ---------------------------------------------------------------- 窗口工具
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]


def list_windows():
    out = []

    def cb(hwnd, _lp):
        cls = ctypes.create_unicode_buffer(256)
        txt = ctypes.create_unicode_buffer(512)
        user32.GetClassNameW(hwnd, cls, 256)
        user32.GetWindowTextW(hwnd, txt, 512)
        out.append((hwnd, cls.value, txt.value))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def find_window(pred):
    for hwnd, cls, txt in list_windows():
        if pred(cls, txt):
            return hwnd, cls, txt
    return None, None, None


def grab_focus(hwnd):
    fg = user32.GetForegroundWindow()
    tid_fg = user32.GetWindowThreadProcessId(fg, None)
    tid_me = kernel32.GetCurrentThreadId()
    attached = tid_fg != tid_me
    if attached:
        user32.AttachThreadInput(tid_me, tid_fg, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.SetFocus(hwnd)
    if attached:
        user32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.15)
    return user32.GetForegroundWindow() == hwnd


# ---------------------------------------------------------------- 探针窗口
class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
SEEN = []


def _wndproc(hwnd, msg, wp, lp):
    SEEN.append((msg, wp))
    if msg == WM_CLOSE:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        return 0
    return user32.DefWindowProcW(hwnd, msg, wp, lp)


_WNDPROC_KEEP = WNDPROC(_wndproc)


def make_probe_window():
    hinst = kernel32.GetModuleHandleW(None)
    cls = "BeepProbeWnd"
    wc = WNDCLASSW()
    wc.lpfnWndProc = ctypes.cast(_WNDPROC_KEEP, ctypes.c_void_p)
    wc.hInstance = hinst
    wc.lpszClassName = cls
    if not user32.RegisterClassW(ctypes.byref(wc)):
        if ctypes.get_last_error() not in (0, 1410):
            raise OSError("RegisterClassW err=%d" % ctypes.get_last_error())
    hwnd = user32.CreateWindowExW(0x00000008, cls, "beep probe",
                                  0x00CF0000, 300, 300, 400, 180,
                                  None, None, hinst, None)
    if not hwnd:
        raise OSError("CreateWindowExW err=%d" % ctypes.get_last_error())
    user32.ShowWindow(hwnd, 5)
    grab_focus(hwnd)
    return hwnd


def pump(seconds):
    msg = wt.MSG()
    t0 = time.time()
    while time.time() - t0 < seconds:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.005)


def measure_action(meter, tag, action, seconds=1.2):
    meter.sample(0.25)
    action()
    return report(tag, meter.sample(seconds))


def stage_probe(m):
    import winsound
    hwnd = make_probe_window()
    print("probe window ready, foreground=%s" % (user32.GetForegroundWindow() == hwnd))

    meter_ok = measure_action(m, "calibration MessageBeep",
                              lambda: winsound.MessageBeep(winsound.MB_ICONASTERISK), 0.9)
    if not meter_ok:
        print("!! 标定失败，后面的结论不可信")
    time.sleep(0.3)

    results = {}
    for tag, vks in (("bare z", (0x5A,)),
                     ("alt+q", (0xA4, 0x51)),
                     ("alt+z", (0xA4, 0x5A)),
                     ("alt+x", (0xA4, 0x58)),
                     ("alt+c", (0xA4, 0x43))):
        SEEN.clear()
        results[tag] = measure_action(m, tag, lambda v=vks: combo(*v), 1.2)
        pump(0.3)
        print("    window key msgs: %s"
              % [hex(msg) for msg, _wp in SEEN if msg in (0x100, 0x101, 0x102, 0x104, 0x105, 0x106)])
        time.sleep(0.2)

    print("SUMMARY %s" % results)
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    pump(0.2)


def stage_explorer(m, folder):
    import winsound
    hwnd, cls, txt = find_window(lambda c, t: c == "CabinetWClass" and "\\" in t)
    if not hwnd:
        print("打开资源管理器：%s" % folder)
        subprocess.Popen(["explorer", folder])
        for _ in range(60):
            time.sleep(0.2)
            hwnd, cls, txt = find_window(lambda c, t: c == "CabinetWClass")
            if hwnd:
                break
    print("explorer hwnd=%s cls=%s title=%s" % (hwnd, cls, txt))
    if not hwnd:
        print("没找到资源管理器窗口")
        return
    print("focus=%s" % grab_focus(hwnd))
    time.sleep(0.4)
    combo(0x11, 0x41)               # Ctrl+A 全选
    time.sleep(0.5)

    meter_ok = measure_action(m, "calibration MessageBeep",
                              lambda: winsound.MessageBeep(winsound.MB_ICONASTERISK), 0.9)
    if not meter_ok:
        print("!! 标定失败，后面的结论不可信")
    time.sleep(0.3)

    def press():
        combo(0xA4, 0x5A)

    hit = measure_action(m, "alt+z (explorer)", press, 1.8)
    time.sleep(0.4)
    pm, pm_cls, pm_txt = find_window(lambda c, t: "PetalMenu" in t or "PetalMenu" in c)
    print("menu window: hwnd=%s cls=%s title=%s" % (pm, pm_cls, pm_txt))
    print("SUMMARY beep=%s menu_opened=%s" % (hit, bool(pm)))


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "probe").lower()
    m = Meter()
    if mode == "explorer":
        folder = sys.argv[2] if len(sys.argv) > 2 else "C:\\tmp\\hotkey\\tests"
        stage_explorer(m, folder)
    else:
        stage_probe(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
