# -*- coding: utf-8 -*-
"""在 Everything 搜索框里查询，返回结果条数与前几条文件名（用于验证索引是否过期）。

⚠️ 危险：`LVM_GETITEMTEXTW` 不走跨进程消息编组，用 SendMessage 从外部进程读
Everything 的虚拟列表会让 Everything 崩（0xc000041d / COMCTL32.dll）。
留作踩坑记录，别再跑。

用法: python _ev_query.py '<搜索词>' [n]
"""
import ctypes
import sys
import time

u32 = ctypes.windll.user32
u32.SendMessageW.restype = ctypes.c_ssize_t
u32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]

WM_SETTEXT = 0x000C
LVM_GETITEMCOUNT = 0x1004
LVM_GETITEMTEXTW = 0x1073
LVIF_TEXT = 0x0001
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04


class LVITEMW(ctypes.Structure):
    _fields_ = [("mask", ctypes.c_uint), ("iItem", ctypes.c_int), ("iSubItem", ctypes.c_int),
                ("state", ctypes.c_uint), ("stateMask", ctypes.c_uint),
                ("pszText", ctypes.c_void_p), ("cchTextMax", ctypes.c_int),
                ("iImage", ctypes.c_int), ("lParam", ctypes.c_ssize_t),
                ("iIndent", ctypes.c_int), ("iGroupId", ctypes.c_int),
                ("cColumns", ctypes.c_uint), ("puColumns", ctypes.c_void_p),
                ("piColFmt", ctypes.c_void_p), ("iGroup", ctypes.c_int)]


def find(cls="EVERYTHING"):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(128)
        u32.GetClassNameW(h, b, 128)
        if b.value == cls:
            out.append(h)
        return True

    u32.EnumWindows(cb, None)
    return out


def child_of(hwnd, cls):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(128)
        u32.GetClassNameW(h, b, 128)
        if cls in b.value:
            out.append(h)
        return True

    u32.EnumChildWindows(hwnd, cb, None)
    return out


def main():
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    wins = find()
    if not wins:
        print("Everything not running")
        return 2
    h = wins[0]
    edits = child_of(h, "Edit")
    if not edits:
        print("no search edit found")
        return 2
    u32.SendMessageW(edits[0], WM_SETTEXT, 0, ctypes.cast(
        ctypes.create_unicode_buffer(q), ctypes.c_void_p))
    time.sleep(1.5)
    lv = child_of(h, "SysListView32")
    if not lv:
        print("no listview")
        return 2
    total = u32.SendMessageW(lv[0], LVM_GETITEMCOUNT, 0, None)
    print("query=%r rows=%d" % (q, total))
    if total <= 0:
        return 0
    pid = ctypes.c_ulong()
    u32.GetWindowThreadProcessId(lv[0], ctypes.byref(pid))
    k32 = ctypes.windll.kernel32
    hp = k32.OpenProcess(PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE, False, pid)
    addr = k32.VirtualAllocEx(hp, None, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    buf = ctypes.create_unicode_buffer(1024)
    for i in range(min(n, total)):
        it = LVITEMW()
        it.mask = LVIF_TEXT
        it.iItem = i
        it.iSubItem = 0
        it.pszText = ctypes.c_void_p(addr + 2048)
        it.cchTextMax = 512
        k32.WriteProcessMemory(hp, ctypes.c_void_p(addr), ctypes.byref(it), ctypes.sizeof(it), None)
        u32.SendMessageW(lv[0], LVM_GETITEMTEXTW, i, ctypes.c_void_p(addr))
        k32.ReadProcessMemory(hp, ctypes.c_void_p(addr + 2048), buf, 1024, None)
        print("  %d: %s" % (i, buf.value))
    k32.VirtualFreeEx(hp, ctypes.c_void_p(addr), 0, MEM_RELEASE)
    k32.CloseHandle(hp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
