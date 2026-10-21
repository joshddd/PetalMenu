# -*- coding: utf-8 -*-
"""真实前台链路：把 Everything 切到前台 -> files_or_notify() 应返回选中文件"""
import ctypes, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main

u = ctypes.windll.user32
k = ctypes.windll.kernel32
log = lambda *a: print(*a, flush=True)
fails = []


def check(name, cond, extra=""):
    log(("PASS " if cond else "FAIL ") + name + ("  " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


# 找 Everything
hwnd = None
EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_ssize_t)


def cb(h, _l):
    global hwnd
    if main._win_class(h) == "EVERYTHING" and u.IsWindowVisible(h):
        hwnd = h
    return True


u.EnumWindows(EnumProc(cb), 0)
if not hwnd:
    log("Everything 未运行")
    sys.exit(1)

lv = main._find_child_class(hwnd, "SysListView32")[0]
pid = ctypes.c_ulong()
u.GetWindowThreadProcessId(lv, ctypes.byref(pid))
proc = k.OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, pid.value)
mem = k.VirtualAllocEx(proc, None, 1024, 0x3000, 0x04)
u.SendMessageW.restype = ctypes.c_ssize_t
u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
LVM_SETITEMSTATE = 0x1043


def set_state(row, state, mask):
    li = main._LVITEMW()
    li.iItem = row
    li.state = state
    li.stateMask = mask
    k.WriteProcessMemory(proc, ctypes.c_void_p(mem), ctypes.byref(li), ctypes.sizeof(li), None)
    u.SendMessageW(lv, LVM_SETITEMSTATE, row, mem)


# 把 Everything 切到前台
if u.IsIconic(hwnd):
    u.ShowWindow(hwnd, 9)          # SW_RESTORE
    time.sleep(0.3)
orig_fg = u.GetForegroundWindow()


def force_foreground(target):
    """绕过前台锁：把当前前台线程和目标线程的输入队列临时挂接起来"""
    fg = u.GetForegroundWindow()
    fg_tid = u.GetWindowThreadProcessId(fg, None)
    tg_tid = u.GetWindowThreadProcessId(target, None)
    u.AttachThreadInput(fg_tid, tg_tid, True)
    try:
        u.BringWindowToTop(target)
        u.SetForegroundWindow(target)
        u.SetActiveWindow(target)
    finally:
        u.AttachThreadInput(fg_tid, tg_tid, False)


if u.GetForegroundWindow() != hwnd:
    force_foreground(hwnd)
    for _ in range(10):
        if u.GetForegroundWindow() == hwnd:
            break
        time.sleep(0.1)
fg = u.GetForegroundWindow()
log(f"前台窗口={fg}  Everything={hwnd}  类={main._win_class(fg)}")
check("Everything 已在前台", main.detect_source()[0] == "everything", main.detect_source())

# 选中第一行
set_state(-1, 0, 0xFFFF)
set_state(-1, 0, 0xFFFF)
set_state(0, 0x0002 | 0x0001, 0x0002 | 0x0001)
time.sleep(0.2)

files = main.files_or_notify()
log(f"files_or_notify() -> {files}")
check("真实前台走 Everything 分支拿到文件", bool(files) and all(os.path.exists(f) for f in files), files)

# 恢复空选中
set_state(-1, 0, 0xFFFF)
set_state(-1, 0, 0xFFFF)
k.VirtualFreeEx(proc, ctypes.c_void_p(mem), 0, 0x8000)
k.CloseHandle(proc)

# 把焦点还给原来的窗口
if orig_fg and u.GetForegroundWindow() != orig_fg:
    try:
        force_foreground(orig_fg)
    except Exception:
        pass

log("")
log("结果: " + ("全部通过" if not fails else f"{len(fails)} 项失败 -> {fails}"))
sys.exit(0 if not fails else 1)
