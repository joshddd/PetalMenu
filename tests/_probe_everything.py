# -*- coding: utf-8 -*-
"""探测 Everything 的窗口结构：确认结果列表控件类名、列、选中项数量"""
import ctypes, ctypes.wintypes as wt, subprocess, sys, os

u = ctypes.windll.user32
log = lambda *a: print(*a, flush=True)

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Everything.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True)
log("=== Everything 进程 ===")
log(out.stdout.strip() or "(未运行)")

for cand in [r"C:\Program Files\Everything\Everything.exe",
             r"C:\Program Files (x86)\Everything\Everything.exe"]:
    log(f"  安装路径存在? {cand} -> {os.path.exists(cand)}")

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
targets = []

def pid_of(hwnd):
    p = wt.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
    return p.value

def proc_name(pid):
    try:
        o = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True)
        return o.stdout.split(",")[0].strip('"')
    except Exception:
        return "?"

def enum_children(parent, depth=0, maxdepth=3):
    res = []
    def cb(h, l):
        cls = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, cls, 256)
        txt = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(h, txt, 256)
        vis = bool(u.IsWindowVisible(h))
        res.append((depth, h, cls.value, txt.value, vis))
        if depth < maxdepth:
            res.extend(enum_children(h, depth + 1, maxdepth))
        return True
    u.EnumChildWindows(parent, EnumProc(cb), 0)
    return res

log("\n=== 顶层窗口（属于 Everything 进程的）===")
found = []
def top_cb(h, l):
    pid = pid_of(h)
    if proc_name(pid).lower().startswith("everything"):
        cls = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, cls, 256)
        txt = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(h, txt, 256)
        log(f"  hwnd={h} pid={pid} class={cls.value!r} title={txt.value!r} "
            f"visible={bool(u.IsWindowVisible(h))}")
        found.append((h, cls.value))
    return True
u.EnumWindows(EnumProc(top_cb), 0)

if not found:
    log("  (没有找到 Everything 窗口，可能没启动)")
else:
    for h, cls in found:
        log(f"\n=== {cls} 的子控件树 ({h}) ===")
        for depth, ch, ccls, ctxt, vis in enum_children(h):
            log(f"  {'  ' * depth}- hwnd={ch} class={ccls!r} text={ctxt[:40]!r} vis={vis}")

# 如果找到列表控件，试读
LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETSELECTEDCOUNT = LVM_FIRST + 50
LVM_GETNEXTITEM = LVM_FIRST + 12
LVNI_SELECTED = 0x0002

for h, cls in found:
    for depth, ch, ccls, ctxt, vis in enum_children(h):
        if ccls == "SysListView32":
            n = u.SendMessageW(ch, LVM_GETITEMCOUNT, 0, 0)
            sel = u.SendMessageW(ch, LVM_GETSELECTEDCOUNT, 0, 0)
            first = u.SendMessageW(ch, LVM_GETNEXTITEM, 0xFFFFFFFF, LVNI_SELECTED)
            log(f"\n=== 列表控件 hwnd={ch} 行数={n} 选中数={sel} 首个选中索引={first} ===")
log("\n完成")
