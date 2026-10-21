# -*- coding: utf-8 -*-
"""验证热键是否被钩子吞掉（= 前台窗口收不到 WM_SYSCHAR/WM_CHAR）。

用法（Windows python，参数必须写 C:/ 形式）：
    python.exe C:/tmp/hotkey/tests/_swallow_test.py <mode> [hook_combo] [send_combo]
      mode       : on | off | nohook
      hook_combo : 钩子注册的组合，默认 alt+z
      send_combo : 实际注入的组合，默认同 hook_combo

为什么看 WM_SYSCHAR：不吞键时组合键会落到前台窗口；窗口不处理、交给
DefWindowProc 时 Windows 就放默认提示音。所以「窗口收到 WM_SYSCHAR/WM_CHAR」
= 「会响」，收不到 = 「安静」。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODE = (sys.argv[1] if len(sys.argv) > 1 else "on").strip().lower()
COMBO = sys.argv[2] if len(sys.argv) > 2 else "alt+z"
SEND_COMBO = sys.argv[3] if len(sys.argv) > 3 else COMBO
if MODE == "off":
    os.environ["PETALMENU_SWALLOW"] = "0"
else:
    os.environ.pop("PETALMENU_SWALLOW", None)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_CHAR, WM_SYSCHAR = 0x0102, 0x0106
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105

RECEIVED = []
HITS = []


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t


def _wndproc(hwnd, msg, wp, lp):
    RECEIVED.append((msg, wp))
    if msg == WM_CLOSE:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        return 0
    return user32.DefWindowProcW(hwnd, msg, wp, lp)


# 必须留一个强引用：ctypes 回调被 GC 掉后窗口过程指针悬空，
# 现象是消息只收到一两条、后面的全丢（真踩过）。
_WNDPROC_KEEP = WNDPROC(_wndproc)


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


assert ctypes.sizeof(INPUT) == 40, ctypes.sizeof(INPUT)

_MOD_VK = {"alt": 0xA4, "ctrl": 0xA2, "shift": 0xA0, "win": 0x5B}


def send(vk, up=False):
    i = INPUT(type=1)
    i.ki = KEYBDINPUT(vk, 0, 0x0002 if up else 0, 0, 0)
    if user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT)) != 1:
        print("SendInput failed err=%d vk=0x%02X" % (ctypes.get_last_error(), vk))


def pump(seconds):
    msg = wt.MSG()
    t0 = time.time()
    while time.time() - t0 < seconds:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.005)


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
    return user32.GetForegroundWindow() == hwnd


def split_combo(combo, parse_combo):
    mods, keys = [], []
    for p in combo.lower().split("+"):
        p = p.strip()
        if not p:
            continue
        if p in _MOD_VK:
            mods.append(_MOD_VK[p])
        else:
            keys.append(parse_combo(p)[1])
    return mods, keys[0]


def main():
    from hotkey_hook import HotkeyManager, SWALLOW_HOTKEYS, parse_combo

    hinst = kernel32.GetModuleHandleW(None)
    cls_name = "SwallowProbeWnd"
    wc = WNDCLASSW()
    wc.lpfnWndProc = ctypes.cast(_WNDPROC_KEEP, ctypes.c_void_p)
    wc.hInstance = hinst
    wc.lpszClassName = cls_name
    if not user32.RegisterClassW(ctypes.byref(wc)):
        err = ctypes.get_last_error()
        if err not in (0, 1410):          # 1410 = 类已存在
            print("RegisterClassW failed err=%d" % err)
            return 1

    hwnd = user32.CreateWindowExW(0x00000008, cls_name, "swallow probe",
                                  0x00CF0000, 240, 240, 420, 200,
                                  None, None, hinst, None)
    if not hwnd:
        print("CreateWindowExW failed err=%d" % ctypes.get_last_error())
        return 1
    user32.ShowWindow(hwnd, 5)
    fg_ok = grab_focus(hwnd)
    pump(0.3)

    print("MODE=%s HOOK=%s SEND=%s SWALLOW_HOTKEYS=%s fg_ok=%s"
          % (MODE, COMBO, SEND_COMBO, SWALLOW_HOTKEYS, fg_ok))

    hk = None
    if MODE != "nohook":
        hk = HotkeyManager()
        hk.set_hotkeys([(COMBO, lambda: HITS.append(time.time()))])
        hk.start()
        pump(0.2)

    mods, main_vk = split_combo(SEND_COMBO, parse_combo)

    RECEIVED.clear()
    HITS.clear()
    grab_focus(hwnd)
    pump(0.05)

    # 先按一次普通字母，确认注入通道和窗口收键正常（应为 KEYDOWN/CHAR/KEYUP）
    send(0x41)
    send(0x41, up=True)
    pump(0.12)
    sanity = [m for m, _ in RECEIVED if m in (WM_KEYDOWN, WM_CHAR, WM_KEYUP)]
    RECEIVED.append(("MARK", 0))

    for m in mods:
        send(m)
        pump(0.04)
    send(main_vk)
    pump(0.06)
    send(main_vk, up=True)
    pump(0.04)
    for m in reversed(mods):
        send(m, up=True)
        pump(0.04)
    pump(0.4)

    tbl = {WM_KEYDOWN: "KEYDOWN", WM_KEYUP: "KEYUP",
           WM_SYSKEYDOWN: "SYSKEYDOWN", WM_SYSKEYUP: "SYSKEYUP",
           WM_CHAR: "CHAR", WM_SYSCHAR: "SYSCHAR"}
    cut = 0
    for i, (m, _wp) in enumerate(RECEIVED):
        if m == "MARK":
            cut = i + 1
    keyed = [(m, wp) for m, wp in RECEIVED[cut:] if m in tbl]
    msgs = ["%s(0x%02X)" % (tbl[m], wp) for m, wp in keyed]
    print("sanity_plain_keys=%d (3=注入正常)" % len(sanity))
    print("hotkey_hits=%d" % len(HITS))
    print("window_msgs=%s" % (" ".join(msgs) if msgs else "[]"))
    beep_gate = [m for m, _ in keyed if m in (WM_SYSCHAR, WM_CHAR)]
    print("VERDICT=%s" % ("BEEP-RISK" if beep_gate else "SILENT"))
    if hk is not None:
        hk.stop()
    user32.DestroyWindow(hwnd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
