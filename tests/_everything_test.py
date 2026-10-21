# -*- coding: utf-8 -*-
"""Everything 支持验证：单元 + 真实列表选中后读取完整路径"""
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


# ---------- 单元 ----------
check("_looks_abs 盘符", main._looks_abs(r"M:\july2026\a.txt"))
check("_looks_abs UNC", main._looks_abs(r"\\nas\share\a.txt"))
check("_looks_abs 相对", not main._looks_abs(r"july2026\a.txt"))
check("_path_from_cells 名称+文件夹",
      main._path_from_cells([r"a.mp4", r"M:\july2026"]) == os.path.join(r"M:\july2026", "a.mp4"))
check("_path_from_cells 名称已是全路径",
      main._path_from_cells([r"M:\july2026\a.mp4", r"M:\july2026"]) == r"M:\july2026\a.mp4")
check("_path_from_cells 无文件夹列", main._path_from_cells([r"a.mp4", "1,024 KB"]) == "")

# ---------- 找 Everything ----------
hwnd = None
EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_ssize_t)


def cb(h, _l):
    global hwnd
    if main._win_class(h) == "EVERYTHING" and u.IsWindowVisible(h):
        hwnd = h
    return True


u.EnumWindows(EnumProc(cb), 0)
check("找到 Everything 窗口", bool(hwnd), hwnd)
if not hwnd:
    log("Everything 没运行，跳过集成测试")
    sys.exit(1 if fails else 0)

kind, root = main.detect_source(hwnd)
check("detect_source 识别 Everything", kind == "everything" and root == hwnd, (kind, root))

lists = main._find_child_class(hwnd, "SysListView32")
check("找到结果列表", bool(lists), lists)
if not lists:
    sys.exit(1)

lv = lists[0]
LVITEM = main._LVITEMW
LVM_SETITEMSTATE = 0x1000 + 43
LVIS_SELECTED, LVIS_FOCUSED = 0x0002, 0x0001

pid = ctypes.c_ulong()
u.GetWindowThreadProcessId(lv, ctypes.byref(pid))
proc = k.OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, pid.value)
mem = k.VirtualAllocEx(proc, None, 1024, 0x3000, 0x04)
u.SendMessageW.restype = ctypes.c_ssize_t
u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]


def set_state(row, state, mask):
    li = LVITEM()
    li.mask = 0
    li.iItem = row
    li.state = state
    li.stateMask = mask
    k.WriteProcessMemory(proc, ctypes.c_void_p(mem), ctypes.byref(li), ctypes.sizeof(li), None)
    u.SendMessageW(lv, LVM_SETITEMSTATE, row, mem)


def clear_all():
    set_state(-1, 0, 0xFFFF)
    set_state(-1, 0, 0xFFFF)   # 虚拟列表有时需要两次


n_rows = u.SendMessageW(lv, 0x1000 + 4, 0, 0)
log(f"结果列表行数={n_rows}")

clear_all()
set_state(0, LVIS_SELECTED | LVIS_FOCUSED, LVIS_SELECTED | LVIS_FOCUSED)
time.sleep(0.15)
sel_n = u.SendMessageW(lv, main.LVM_GETSELECTEDCOUNT, 0, 0)
log(f"设置后选中数={sel_n}")

files = main.everything_selected_files(hwnd)
check("单行选中读出 1 个路径", len(files) == 1, files)
if files:
    check("读到的路径真实存在", os.path.exists(files[0]), files[0])
    check("路径扩展名正确", os.path.splitext(files[0])[1].lower() in
          (".mp4", ".mkv", ".avi", ".wmv", ".mov", ".flv", ".ts", ".m4v", ".jpg", ".png"),
          files[0])

# 多选
if n_rows >= 2:
    clear_all()
    set_state(0, LVIS_SELECTED, LVIS_SELECTED)
    set_state(1, LVIS_SELECTED | LVIS_FOCUSED, LVIS_SELECTED | LVIS_FOCUSED)
    time.sleep(0.15)
    files2 = main.everything_selected_files(hwnd)
    check("两行选中读出 2 个路径", len(files2) == 2, files2)
    for f in files2:
        check(f"  存在: {os.path.basename(f)}", os.path.exists(f))

# 恢复：清空选中（原来就无选中）
clear_all()
k.VirtualFreeEx(proc, ctypes.c_void_p(mem), 0, 0x8000)
k.CloseHandle(proc)

log("")
log("结果: " + ("全部通过" if not fails else f"{len(fails)} 项失败 -> {fails}"))
sys.exit(0 if not fails else 1)
