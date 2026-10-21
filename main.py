# -*- coding: utf-8 -*-
"""
PetalMenu：花瓣菜单 + 托盘 + 打包支持
配置目录：%APPDATA%\\PetalMenu\\config.yaml（首次自动生成，可从 exe 同级目录迁移旧配置）
"""
import os
import sys
import shutil
import subprocess
import threading
import ctypes
import queue
import time

import yaml
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import QTimer, Qt

from petal_menu import PetalMenu, COLORS
from hotkey_hook import HotkeyManager

# ---------------------------------------------------------------- 路径
if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(sys.executable)
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

VERSION = "v9"

APP_DIR = os.path.join(os.environ.get("APPDATA", EXE_DIR), "PetalMenu")
os.makedirs(APP_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(APP_DIR, "config.yaml")

# 旧版配置自动迁移 / 同步：exe 同级的 config.yaml 更新时覆盖 APPDATA 里的
_LEGACY_CFG = os.path.join(EXE_DIR, "config.yaml")

DEBUG_LOG = os.path.join(APP_DIR, "debug.log")


def _dbg(msg):
    """轻量排障日志（%APPDATA%\\PetalMenu\\debug.log），超过 256KB 自动只留尾部。"""
    try:
        if os.path.exists(DEBUG_LOG) and os.path.getsize(DEBUG_LOG) > 262144:
            with open(DEBUG_LOG, "r", encoding="utf-8", errors="ignore") as f:
                tail = f.read()[-65536:]
            with open(DEBUG_LOG, "w", encoding="utf-8") as f:
                f.write(tail)
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def _petal_brief(petals):
    try:
        return [(p.get("name"), p.get("program"), p.get("exts")) for p in petals]
    except Exception:
        return str(petals)



def _sync_legacy_config():
    if os.path.abspath(_LEGACY_CFG) == os.path.abspath(CONFIG_PATH):
        return False
    if not os.path.exists(_LEGACY_CFG):
        return False
    try:
        if (not os.path.exists(CONFIG_PATH)
                or os.path.getmtime(_LEGACY_CFG) > os.path.getmtime(CONFIG_PATH) + 1):
            shutil.copy2(_LEGACY_CFG, CONFIG_PATH)
            _dbg("sync_legacy: 用 exe 同级 config.yaml 覆盖了 APPDATA 配置")
            return True
    except Exception:
        pass
    return False

# ---------------------------------------------------------------- 文件类别
# (配置键, 中文名, 扩展名表所在的配置键)
CATEGORIES = (
    ("video",    "视频",     "video_exts"),
    ("image",    "图片",     "image_exts"),
    ("document", "文档",     "document_exts"),
    ("audio",    "音频",     "audio_exts"),
    ("archive",  "压缩包",   "archive_exts"),
    ("disc",     "光盘镜像", "disc_exts"),
)
CATEGORY_LABEL = {key: label for key, label, _e in CATEGORIES}

DEFAULT_EXTS = {
    "video": [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".ts",
              ".webm", ".rmvb", ".mpg", ".mpeg", ".m2ts", ".vob", ".ogv"],
    "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff",
              ".heic", ".avif", ".jxl", ".ico", ".svg", ".raw", ".cr2", ".nef", ".arw"],
    "document": [".pdf", ".doc", ".docx", ".rtf", ".odt", ".txt", ".md", ".log",
                 ".xls", ".xlsx", ".ods", ".csv", ".et", ".ppt", ".pptx", ".odp",
                 ".dps", ".wps", ".epub", ".mobi", ".azw3", ".djvu", ".chm",
                 ".xps", ".pages", ".tex", ".html", ".htm"],
    "audio": [".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".oga", ".opus",
              ".wma", ".ape", ".alac", ".aiff", ".aif", ".mid", ".midi", ".amr",
              ".ac3", ".dts", ".dsf", ".dff", ".mka", ".wv", ".tta"],
    "archive": [".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".tbz2",
                ".xz", ".txz", ".zst", ".cab", ".arj", ".lzh", ".lha",
                ".001", ".r00"],
    "disc": [".iso", ".img", ".bin", ".cue", ".nrg", ".mdf", ".mds", ".ccd",
             ".sub", ".udf", ".toast", ".cso", ".dmg", ".wim", ".vhd", ".vhdx"],
}

DEFAULT_HOTKEYS = {
    "show_menu": "alt+z",
    "open_video": "ctrl+alt+v",
    "open_image": "ctrl+alt+p",
    "open_document": "",
    "open_audio": "",
    "open_archive": "",
    "open_disc": "",
    "open_auto": "ctrl+alt+o",
}

# 首次运行写出的配置：由上面几张表生成，保证「默认值」只有一份，不会两边漂移
_DEFAULT_CONFIG: dict = {"hotkeys": dict(DEFAULT_HOTKEYS)}
_DEFAULT_CONFIG.update({ext_key: list(DEFAULT_EXTS[key])
                        for key, _label, ext_key in CATEGORIES})
_DEFAULT_CONFIG["programs"] = {key: "" for key, _label, _e in CATEGORIES}
_DEFAULT_CONFIG["petal_count"] = 0
_DEFAULT_CONFIG["petals"] = [
    {"name": "默认打开", "program": ""},
    {"name": "所在文件夹", "program": "__explorer__"},
]
DEFAULT_YAML = yaml.safe_dump(_DEFAULT_CONFIG, allow_unicode=True, sort_keys=False)


def load_config():
    global CONFIG
    copied = _sync_legacy_config()
    if not os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(DEFAULT_YAML)
        except Exception as e:
            _raw_notify("PetalMenu", f"无法创建配置文件：{e}")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        new = yaml.safe_load(f) or {}
    new.setdefault("hotkeys", {})
    for _hk, _dev in DEFAULT_HOTKEYS.items():
        new["hotkeys"].setdefault(_hk, _dev)
    for _key, _label, _ext_key in CATEGORIES:
        _cur = new.get(_ext_key)
        if not isinstance(_cur, list) or not _cur:
            new[_ext_key] = list(DEFAULT_EXTS[_key])
    new.setdefault("programs", {})
    for _key, _label, _e in CATEGORIES:
        new["programs"].setdefault(_key, "")
    new.setdefault("petal_count", 0)
    new.setdefault("petals", [])
    # 就地更新：保持 CONFIG 这个 dict 的身份不变，避免菜单/对话框里
    # 已经持有的 CONFIG["petals"] 旧列表变成"改了但存不进去"的孤儿对象。
    if isinstance(CONFIG, dict):
        CONFIG.clear()
        CONFIG.update(new)
    else:
        CONFIG = new
    _dbg("load_config: legacy_copied=%s petals=%s"
         % (copied, _petal_brief(CONFIG.get("petals", []))))


def save_config():
    """把当前 CONFIG 写回 config.yaml"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(CONFIG, f, allow_unicode=True, sort_keys=False)
        _dbg("save_config: OK -> %s petals=%s"
             % (CONFIG_PATH, _petal_brief(CONFIG.get("petals", []))))
        return True
    except Exception as e:
        _dbg("save_config: FAIL %s" % e)
        notify("PetalMenu", f"配置保存失败：{e}")
        return False


CONFIG = {}
load_config()

ACTIONS = queue.Queue()
CURRENT_MENU = None
LAST_FILES = []
_TRAY = None
_HOTKEYS = HotkeyManager()

# ---------------------------------------------------------------- 工具函数

def _raw_notify(title, msg):
    def _show():
        try:
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40 | 0x1000)
        except Exception:
            pass
    threading.Thread(target=_show, daemon=True).start()


def notify(title, msg):
    if _TRAY is not None:
        try:
            _TRAY.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        except Exception:
            pass
    _raw_notify(title, msg)


EVERYTHING_CLASSES = ("EVERYTHING", "EVERYTHING_TASKBAR_NOTIFICATION")


def _win_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def detect_source(hwnd=None):
    """判断前台窗口来源：('explorer'|'everything'|None, hwnd)"""
    u = ctypes.windll.user32
    if hwnd is None:
        hwnd = u.GetForegroundWindow()
    if not hwnd:
        return None, None
    for cand in (hwnd, u.GetAncestor(hwnd, 2)):  # 2 = GA_ROOT
        if not cand:
            continue
        cls = _win_class(cand)
        if cls == "CabinetWClass":
            return "explorer", cand
        if cls in EVERYTHING_CLASSES:
            return "everything", cand
    return None, None


def get_explorer_hwnd():
    kind, hwnd = detect_source()
    return hwnd if kind == "explorer" else None


def get_selected_files(hwnd):
    script = f'''
$shell = New-Object -ComObject Shell.Application
$doc = $null
foreach ($w in $shell.Windows()) {{
    if ($w.HWND -eq {int(hwnd)}) {{ $doc = $w.Document; break }}
}}
if ($null -eq $doc) {{ exit 1 }}
$items = @($doc.SelectedItems() | ForEach-Object {{ $_.Path }})
if ($items.Count -eq 0) {{ exit 2 }}
$items -join "`n"
'''
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=10)
    except Exception as e:
        notify("PetalMenu", f"PowerShell 调用失败：{e}")
        return None
    if r.returncode == 1:
        notify("PetalMenu", "未找到对应的资源管理器窗口")
        return None
    if r.returncode == 2:
        notify("PetalMenu", "没有选中任何文件")
        return None
    if r.returncode != 0:
        notify("PetalMenu", f"获取选中文件出错：{r.stderr.strip()[:200]}")
        return None
    return [p for p in r.stdout.strip().splitlines() if p]


# ---------------------------------------------------------------- Everything 支持
_LVM_FIRST = 0x1000
LVM_GETNEXTITEM = _LVM_FIRST + 12
LVM_GETITEMTEXTW = _LVM_FIRST + 115
LVM_GETSELECTEDCOUNT = _LVM_FIRST + 50
LVNI_SELECTED = 0x0002
HDM_GETITEMCOUNT = 0x1200


class _LVITEMW(ctypes.Structure):
    _fields_ = [("mask", ctypes.c_uint), ("iItem", ctypes.c_int),
                ("iSubItem", ctypes.c_int), ("state", ctypes.c_uint),
                ("stateMask", ctypes.c_uint), ("pszText", ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int), ("iImage", ctypes.c_int),
                ("lParam", ctypes.c_ssize_t), ("iIndent", ctypes.c_int),
                ("iGroupId", ctypes.c_int), ("cColumns", ctypes.c_uint),
                ("puColumns", ctypes.c_void_p), ("piColFmt", ctypes.c_void_p),
                ("iGroup", ctypes.c_int)]


def _find_child_class(parent, cls_name):
    """枚举子窗口，返回所有类名匹配的句柄"""
    found = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_ssize_t)

    def cb(h, _l):
        if _win_class(h) == cls_name:
            found.append(h)
        return True

    ctypes.windll.user32.EnumChildWindows(parent, EnumProc(cb), 0)
    return found


class _RemoteLVText:
    """跨进程读 SysListView32 单元格文本（Everything 结果列表是虚拟列表，必须远端缓冲）"""

    def __init__(self, hwnd):
        self.u = ctypes.windll.user32
        self.k = ctypes.windll.kernel32
        self.hwnd = hwnd
        pid = ctypes.c_ulong()
        self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        self.proc = self.k.OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, pid.value)
        if not self.proc:
            raise OSError("无法打开 Everything 进程")
        self.mem = self.k.VirtualAllocEx(self.proc, None, 8192, 0x3000, 0x04)
        if not self.mem:
            self.k.CloseHandle(self.proc)
            raise OSError("无法在 Everything 进程里分配内存")
        self.item_addr = self.mem
        self.text_addr = self.mem + 1024
        self.u.SendMessageW.restype = ctypes.c_ssize_t
        self.u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                        ctypes.c_size_t, ctypes.c_ssize_t]

    def cell(self, row, col):
        li = _LVITEMW()
        li.mask = 0x0001              # LVIF_TEXT
        li.iItem = row
        li.iSubItem = col
        li.pszText = ctypes.c_void_p(self.text_addr)
        li.cchTextMax = 512
        self.k.WriteProcessMemory(self.proc, ctypes.c_void_p(self.item_addr),
                                  ctypes.byref(li), ctypes.sizeof(li), None)
        n = self.u.SendMessageW(self.hwnd, LVM_GETITEMTEXTW, row, self.item_addr)
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(512)
        self.k.ReadProcessMemory(self.proc, ctypes.c_void_p(self.text_addr), buf, 1024, None)
        return buf.value

    def close(self):
        try:
            self.k.VirtualFreeEx(self.proc, ctypes.c_void_p(self.mem), 0, 0x8000)
        finally:
            self.k.CloseHandle(self.proc)


def _looks_abs(p):
    if not p or len(p) < 3:
        return False
    if p[1] == ":" and p[0].isalpha() and p[2] in "\\/":
        return True
    return p.startswith("\\\\")


def _path_from_cells(cells):
    """第 0 列是文件名，后面某一列是所在文件夹 -> 拼成完整路径"""
    name = (cells[0] or "").strip() if cells else ""
    if not name:
        return ""
    if _looks_abs(name):
        return name
    for v in cells[1:]:
        v = (v or "").strip()
        if _looks_abs(v):
            return os.path.join(v, name)
    return ""


def everything_selected_files(hwnd, limit=64):
    """读取 Everything 结果列表里选中的文件完整路径"""
    u = ctypes.windll.user32
    lists = _find_child_class(hwnd, "SysListView32")
    if lists:
        lv = lists[0]
        rm = None
        try:
            rm = _RemoteLVText(lv)
            headers = _find_child_class(lv, "SysHeader32")
            ncol = u.SendMessageW(headers[0], HDM_GETITEMCOUNT, 0, 0) if headers else 4
            ncol = max(1, min(int(ncol or 4), 16))
            idxs = []
            cur = u.SendMessageW(lv, LVM_GETNEXTITEM, 0xFFFFFFFF, LVNI_SELECTED)
            while cur >= 0 and len(idxs) < limit:
                idxs.append(cur)
                cur = u.SendMessageW(lv, LVM_GETNEXTITEM, cur, LVNI_SELECTED)
            out = []
            for i in idxs:
                p = _path_from_cells([rm.cell(i, c) for c in range(ncol)])
                if p and p not in out:
                    out.append(p)
            if out:
                return out
        except Exception:
            pass
        finally:
            if rm is not None:
                try:
                    rm.close()
                except Exception:
                    pass
    # 兜底：Everything 会把焦点项完整路径放在这个隐藏窗口的标题里
    for h in _find_child_class(hwnd, "EVERYTHING_RESULT_LIST_FOCUS"):
        buf = ctypes.create_unicode_buffer(32768)
        u.GetWindowTextW(h, buf, 32768)
        t = buf.value.strip()
        if _looks_abs(t) and os.path.exists(t):
            return [t]
    return []


def open_with(program, files, label=""):
    if program:
        if os.path.exists(program):
            try:
                subprocess.Popen([program] + files)
            except Exception as e:
                notify("PetalMenu", f"启动失败：{e}")
        else:
            notify("PetalMenu", f"程序不存在（{label or '配置'}）：{program}")
    else:
        for f in files:
            try:
                os.startfile(f)
            except Exception as e:
                notify("PetalMenu", f"打开失败：{e}")


EVERYTHING_HELP = "Everything 里没有选中文件：先点一行结果，再按热键"


def files_or_notify(hwnd=None, fallback=None):
    """取当前选中文件；fallback 用于托盘菜单（点托盘时前台已经不是资源管理器了）"""
    kind, h = detect_source(hwnd)
    if kind == "explorer":
        return get_selected_files(h)
    if kind == "everything":
        files = everything_selected_files(h)
        if not files:
            notify("PetalMenu", EVERYTHING_HELP)
        return files
    if fallback:
        _dbg("files_or_notify: 前台不是资源管理器，回退到上次选中的 %d 个文件" % len(fallback))
        return list(fallback)
    notify("PetalMenu", "当前前台窗口既不是资源管理器，也不是 Everything")
    return None

# ---------------------------------------------------------------- 热键动作

def match_by_mode(mode, files):
    """按类别里配置的扩展名过滤"""
    exts = {str(e).lower() for e in (CONFIG.get(mode + "_exts") or [])}
    return [f for f in files if os.path.splitext(f)[1].lower() in exts]


def detect_mode(files):
    """判断这批文件属于哪个类别（按 CATEGORIES 顺序取第一个命中的），认不出返回 None"""
    for key, _label, _ext_key in CATEGORIES:
        if match_by_mode(key, files):
            return key
    return None


def direct_open(mode, files=None, fallback=None):
    """用 programs.<mode> 打开选中文件里属于该类别的那些"""
    if files is None:
        files = files_or_notify(fallback=fallback)
    if not files:
        return
    matched = match_by_mode(mode, files)
    if not matched:
        notify("PetalMenu", "选中的文件里没有%s格式" % CATEGORY_LABEL.get(mode, mode))
        return
    _dbg("direct_open: mode=%s files=%s" % (mode, matched))
    open_with(CONFIG.get("programs", {}).get(mode, ""), matched,
              label=CATEGORY_LABEL.get(mode, mode) or mode)


def direct_open_auto(files=None, fallback=None):
    """自动识别类别后直开；认不出的类型交给系统默认打开"""
    if files is None:
        files = files_or_notify(fallback=fallback)
    if not files:
        return
    mode = detect_mode(files)
    if mode is None:
        _dbg("direct_open_auto: 未识别类型，交给系统默认 -> %s" % files)
        open_with("", files, label="自动")
        return
    direct_open(mode, files=files)


def on_show_menu():
    files = files_or_notify()
    if files:
        ACTIONS.put(files)


def _register_hotkeys():
    """按配置注册热键；空字符串表示不注册这一类"""
    hk = CONFIG["hotkeys"]
    items: list = [(hk.get("open_" + key), (lambda k=key: direct_open(k)))
                   for key, _label, _ext_key in CATEGORIES]
    items.append((hk.get("open_auto"), direct_open_auto))
    items.append((hk.get("show_menu"), on_show_menu))
    spec = [(combo, cb) for combo, cb in items if str(combo or "").strip()]
    _HOTKEYS.set_hotkeys(spec)
    _dbg("register_hotkeys: %s" % [combo for combo, _cb in spec])
    return spec


def listener_thread():
    try:
        _register_hotkeys()
        if not _HOTKEYS.start():
            _raw_notify("PetalMenu", "热键钩子安装失败，全局热键不可用。")
    except Exception as e:
        _raw_notify("PetalMenu", f"热键注册失败：{e}\n请尝试以管理员身份运行。")

# ---------------------------------------------------------------- 托盘

def make_tray_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(32, 32)
    n = 6
    for i in range(n):
        p.save()
        p.rotate(i * 360 / n)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLORS[i % len(COLORS)]))
        p.drawEllipse(int(-8), int(-26), 16, 22)
        p.restore()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(35, 35, 40))
    p.drawEllipse(int(-9), int(-9), 18, 18)
    p.end()
    return QIcon(pm)


def setup_tray(app):
    global _TRAY
    tray = QSystemTrayIcon(make_tray_icon(), app)
    tray.setToolTip("PetalMenu 花瓣菜单 " + VERSION)
    _TRAY = tray

    menu = QMenu()

    def _direct_open_async(mode):
        # 取选中文件要跑 PowerShell（最长 10s），别卡住托盘和 GUI 线程。
        # 点托盘时前台窗口已经不是资源管理器了，用上次选中过的文件兜底。
        job = (lambda: direct_open_auto(fallback=LAST_FILES)) if mode is None \
            else (lambda: direct_open(mode, fallback=LAST_FILES))
        threading.Thread(target=job, daemon=True).start()

    sub = menu.addMenu("直接打开选中文件")
    for _key, _label, _ext_key in CATEGORIES:
        _combo = str(CONFIG["hotkeys"].get("open_" + _key) or "").strip()
        _act = sub.addAction(_label + (("  [%s]" % _combo) if _combo else ""))
        _act.triggered.connect(lambda _checked=False, k=_key: _direct_open_async(k))
    sub.addSeparator()
    _combo_auto = str(CONFIG["hotkeys"].get("open_auto") or "").strip()
    _act_auto = sub.addAction("自动识别类型" + (("  [%s]" % _combo_auto) if _combo_auto else ""))
    _act_auto.triggered.connect(lambda _checked=False: _direct_open_async(None))

    menu.addSeparator()
    act_reload = menu.addAction("重新加载配置")
    act_open_cfg = menu.addAction("打开配置目录")
    menu.addSeparator()
    act_quit = menu.addAction("退出")

    def _reload():
        try:
            load_config()
            _register_hotkeys()
            notify("PetalMenu", "配置已重新加载（含热键）")
        except Exception as e:
            notify("PetalMenu", f"配置加载失败：{e}")

    def _open_cfg():
        os.startfile(APP_DIR)

    def _quit():
        app.quit()

    act_reload.triggered.connect(_reload)
    act_open_cfg.triggered.connect(_open_cfg)
    act_quit.triggered.connect(_quit)

    tray.setContextMenu(menu)
    tray.show()

# ---------------------------------------------------------------- 主流程

def poll_actions():
    global CURRENT_MENU, LAST_FILES
    if CURRENT_MENU is not None and not CURRENT_MENU.isVisible():
        CURRENT_MENU = None
    try:
        while True:
            files = ACTIONS.get_nowait()
            LAST_FILES = files
            show_menu_for(files)
    except queue.Empty:
        pass


def show_menu_for(files):
    """（重新）在光标处弹出花瓣菜单；供保存设置后刷新用"""
    global CURRENT_MENU
    if not files:
        return
    if CURRENT_MENU is not None:
        try:
            CURRENT_MENU.close()
        except Exception:
            pass
        CURRENT_MENU = None
    CURRENT_MENU = PetalMenu(files, CONFIG.get("petals", []),
                             petal_count=CONFIG.get("petal_count", 0))
    if not CURRENT_MENU.show_at_cursor():
        CURRENT_MENU = None


def reshow_menu():
    """设置保存后立即用新配置重建菜单（改完马上看到效果）"""
    show_menu_for(LAST_FILES)


def main():
    _dbg("=== PetalMenu %s 启动，配置=%s ===" % (VERSION, CONFIG_PATH))
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    setup_tray(app)
    threading.Thread(target=listener_thread, daemon=True).start()

    timer = QTimer()
    timer.timeout.connect(poll_actions)
    timer.start(15)

    print("PetalMenu 运行中：")
    for _key, _label, _ext_key in CATEGORIES:
        _combo = str(CONFIG["hotkeys"].get("open_" + _key) or "").strip()
        print(f"  {_combo or '(未设置)':<14} -> 直开{_label}")
    _auto = str(CONFIG["hotkeys"].get("open_auto") or "").strip()
    print(f"  {_auto or '(未设置)':<14} -> 直开（自动识别类型）")
    print(f"  {str(CONFIG['hotkeys'].get('show_menu') or ''):<14} -> 花瓣菜单")
    print(f"  配置目录: {APP_DIR}")
    app.exec()


if __name__ == "__main__":
    main()