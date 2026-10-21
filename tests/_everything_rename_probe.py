# -*- coding: utf-8 -*-
"""验证假设：热键把 Alt 的 keyup 吞掉后，Everything 窗口卡在「菜单模式」里，F2 更名失效。

步骤：聚焦 Everything -> 选中第一行 -> F2 看有没有出现编辑框
      -> 发一次干净的 Alt 按下/抬起 -> 再 F2 看有没有出现编辑框
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _beep_e2e as E  # noqa: E402

u32 = ctypes.windll.user32
VK_ALT, VK_F2, VK_DOWN, VK_ESC, VK_TAB = 0xA4, 0x71, 0x28, 0x1B, 0x09


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD),
                ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND),
                ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND),
                ("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND),
                ("rcCaret", wt.RECT)]


def focus_info():
    fg = u32.GetForegroundWindow()
    tid = u32.GetWindowThreadProcessId(fg, None)
    gti = GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(GUITHREADINFO)
    ok = u32.GetGUIThreadInfo(tid, ctypes.byref(gti))
    cls = ""
    if ok and gti.hwndFocus:
        b = ctypes.create_unicode_buffer(128)
        u32.GetClassNameW(gti.hwndFocus, b, 128)
        cls = b.value
    fb = ctypes.create_unicode_buffer(128)
    u32.GetClassNameW(fg, fb, 128)
    return {"fg": fb.value, "focus": cls,
            "menu_owner": bool(ok and gti.hwndMenuOwner),
            "flags": gti.flags if ok else None}


def win_titles():
    out = []
    for hwnd, cls, txt in E.list_windows():
        if cls in ("#32770", "Edit", "EditClass") or "重命名" in txt or "Rename" in txt:
            out.append("%s|%s" % (cls, txt))
    return out


hwnd, cls, txt = E.find_window(lambda c, t: c == "EVERYTHING")
print("everything hwnd=%s cls=%s txt=%s" % (hwnd, cls, txt))
print("focus ok:", E.grab_focus(hwnd))
time.sleep(0.6)
E.send(VK_DOWN)
E.send(VK_DOWN, up=True)
time.sleep(0.4)
print("before F2  :", focus_info())

E.send(VK_F2)
E.send(VK_F2, up=True)
time.sleep(0.7)
after1 = focus_info()
print("after F2#1 :", after1)
print("  extra wins:", win_titles())
E.send(VK_ESC)
E.send(VK_ESC, up=True)
time.sleep(0.3)

# 干净的一次 Alt 单击，解除可能的菜单模式
E.send(VK_ALT)
time.sleep(0.08)
E.send(VK_ALT, up=True)
time.sleep(0.5)
print("after alt  :", focus_info())

E.send(VK_DOWN)
E.send(VK_DOWN, up=True)
time.sleep(0.3)
E.send(VK_F2)
E.send(VK_F2, up=True)
time.sleep(0.7)
after2 = focus_info()
print("after F2#2 :", after2)
print("  extra wins:", win_titles())
E.send(VK_ESC)
E.send(VK_ESC, up=True)
print("VERDICT edit#1=%s edit#2=%s"
      % (after1["focus"].lower().startswith("edit"),
         after2["focus"].lower().startswith("edit")))
