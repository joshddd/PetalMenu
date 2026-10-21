# -*- coding: utf-8 -*-
"""只读探针：跨进程读取 Everything 结果列表(SysListView32)的列名与选中行文本"""
import ctypes, ctypes.wintypes as wt

u = ctypes.windll.user32
k = ctypes.windll.kernel32
log = lambda *a: print(*a, flush=True)

LVM_FIRST = 0x1000
LVM_GETITEMCOUNT   = LVM_FIRST + 4
LVM_GETSELECTEDCOUNT = LVM_FIRST + 50
LVM_GETNEXTITEM    = LVM_FIRST + 12
LVM_GETITEMTEXTW   = LVM_FIRST + 115
LVNI_SELECTED      = 0x0002
HDM_GETITEMCOUNT   = 0x1200

u.SendMessageW.restype = ctypes.c_ssize_t
u.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]


class LVITEMW(ctypes.Structure):
    _fields_ = [("mask", ctypes.c_uint), ("iItem", ctypes.c_int),
                ("iSubItem", ctypes.c_int), ("state", ctypes.c_uint),
                ("stateMask", ctypes.c_uint), ("pszText", ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int), ("iImage", ctypes.c_int),
                ("lParam", ctypes.c_ssize_t), ("iIndent", ctypes.c_int),
                ("iGroupId", ctypes.c_int), ("cColumns", ctypes.c_uint),
                ("puColumns", ctypes.c_void_p), ("piColFmt", ctypes.c_void_p),
                ("iGroup", ctypes.c_int)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def find_everything():
    res = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, l):
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(h, cls, 64)
        if cls.value == "EVERYTHING" and u.IsWindowVisible(h):
            res.append(h)
        return True
    u.EnumWindows(EnumProc(cb), 0)
    return res[0] if res else None


def find_child(parent, cls_name):
    found = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, l):
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(h, cls, 64)
        if cls.value == cls_name:
            found.append(h)
        return True
    u.EnumChildWindows(parent, EnumProc(cb), 0)
    return found


class Remote:
    def __init__(self, hwnd):
        pid = wt.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        self.pid = pid.value
        self.h = k.OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, self.pid)
        if not self.h:
            raise OSError(f"OpenProcess 失败 {ctypes.GetLastError()}")
        self.buf = k.VirtualAllocEx(self.h, None, 8192, 0x3000, 0x04)
        if not self.buf:
            raise OSError(f"VirtualAllocEx 失败 {ctypes.GetLastError()}")
        self.text_addr = self.buf + 1024
        self.item_addr = self.buf
        self.size = ctypes.sizeof(LVITEMW)

    def get_text(self, hwnd_list, row, col):
        li = LVITEMW()
        li.mask = 0x0001          # LVIF_TEXT
        li.iItem = row
        li.iSubItem = col
        li.pszText = ctypes.c_void_p(self.text_addr)
        li.cchTextMax = 512
        k.WriteProcessMemory(self.h, ctypes.c_void_p(self.item_addr),
                             ctypes.byref(li), self.size, None)
        n = u.SendMessageW(hwnd_list, LVM_GETITEMTEXTW, row, self.item_addr)
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(512)
        k.ReadProcessMemory(self.h, ctypes.c_void_p(self.text_addr),
                            buf, 1024, None)
        return buf.value

    def close(self):
        k.VirtualFreeEx(self.h, ctypes.c_void_p(self.buf), 0, 0x8000)
        k.CloseHandle(self.h)


hwnd = find_everything()
log(f"Everything 主窗口 hwnd={hwnd}")
lists = find_child(hwnd, "SysListView32") if hwnd else []
log(f"SysListView32: {lists}")
if lists:
    lv = lists[0]
    n = u.SendMessageW(lv, LVM_GETITEMCOUNT, 0, 0)
    sel = u.SendMessageW(lv, LVM_GETSELECTEDCOUNT, 0, 0)
    log(f"行数={n} 选中数={sel}")
    headers = find_child(lv, "SysHeader32")
    ncol = u.SendMessageW(headers[0], HDM_GETITEMCOUNT, 0, 0) if headers else 0
    log(f"列数={ncol}")

    rm = Remote(lv)
    log("\n--- 第 0 行各列 ---")
    for c in range(ncol):
        log(f"  col{c}: {rm.get_text(lv, 0, c)!r}")

    idx = u.SendMessageW(lv, LVM_GETNEXTITEM, 0xFFFFFFFF, LVNI_SELECTED)
    log(f"\n首个选中索引={idx}")
    if idx >= 0:
        log("--- 选中行各列 ---")
        for c in range(ncol):
            log(f"  col{c}: {rm.get_text(lv, idx, c)!r}")
    # 再扫一遍全部选中索引
    cur = u.SendMessageW(lv, LVM_GETNEXTITEM, 0xFFFFFFFF, LVNI_SELECTED)
    picked = []
    while cur >= 0 and len(picked) < 20:
        picked.append(cur)
        cur = u.SendMessageW(lv, LVM_GETNEXTITEM, cur, LVNI_SELECTED)
    log(f"\n全部选中索引: {picked}")
    rm.close()
log("完成")
