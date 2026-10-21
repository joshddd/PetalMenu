"""全局热键（Win32 低级键盘钩子）。

为什么不用 keyboard 库：
    keyboard 0.13.5 的 `_winkeyboard.py` 里有这样一段"忽略重复 Alt"的启发式：

        fake_alt = (LLKHF_INJECTED | 0x20)          # 0x30
        if vk != VK_PACKET and flags & fake_alt != fake_alt:
            process_key(...)

    只要事件的 flags 同时带 injected(0x10) 和 context(0x20) 就被整条丢弃。
    而 ToDesk / RDP / 虚拟键盘 / SendInput 注入按键时恰好会带上这两位：
        Alt 按下  -> flags=0x30  (被丢弃)
        X   按下  -> flags=0x30  (Alt 还按着，SYSKEYDOWN，也被丢弃)
    结果就是所有含 Alt 的组合键在远程会话里完全失效，而普通字母（flags=0x10）正常。

    本模块直接读原始钩子事件，只忽略 VK_PACKET（Unicode 文本注入）和自动重复，
    injected 事件照常匹配，因此物理键盘、ToDesk 远程键盘、软键盘、AHK 发送都能触发。
"""
import ctypes
import ctypes.wintypes as wt
import os
import threading
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
VK_PACKET = 0xE7
LLKHF_INJECTED = 0x10

MOD_ALT, MOD_CTRL, MOD_SHIFT, MOD_WIN = 0x01, 0x02, 0x04, 0x08

# 命中热键后是否吞掉这个按键（钩子返回非 0）。
# 必须吞：不吞的话组合键会继续落到前台窗口，Windows 对「没有对应菜单助记符的
# Alt+字母」会放一声默认提示音（"叮"），而且字母会被真的敲进目标程序。
# PETALMENU_SWALLOW=0 可临时关掉（排障用）。
SWALLOW_HOTKEYS = os.environ.get("PETALMENU_SWALLOW", "1") != "0"

# 用左右分身的虚拟键码判断修饰键真实状态（GetAsyncKeyState 对注入按键同样有效）
_MOD_VKS = (
    (MOD_ALT, (0xA4, 0xA5)),
    (MOD_CTRL, (0xA2, 0xA3)),
    (MOD_SHIFT, (0xA0, 0xA1)),
    (MOD_WIN, (0x5B, 0x5C)),
)

_MOD_ALIASES = {
    "alt": MOD_ALT, "ctrl": MOD_CTRL, "control": MOD_CTRL,
    "shift": MOD_SHIFT, "win": MOD_WIN, "windows": MOD_WIN,
    "super": MOD_WIN, "cmd": MOD_WIN, "meta": MOD_WIN,
}

_NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "tab": 0x09, "backspace": 0x08, "bksp": 0x08,
    "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "ins": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pgup": 0x21,
    "pagedown": 0x22, "pgdn": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "comma": 0xBC, "period": 0xBE, "dot": 0xBE, "slash": 0xBF,
    "backslash": 0xDC, "semicolon": 0xBA, "quote": 0xDE,
    "minus": 0xBD, "equal": 0xBB,
    "bracketleft": 0xDB, "bracketright": 0xDD, "grave": 0xC0, "backtick": 0xC0,
    "capslock": 0x14, "numlock": 0x90, "scrolllock": 0x91,
    "printscreen": 0x2C, "prtsc": 0x2C, "pause": 0x13, "apps": 0x5D, "sleep": 0x5F,
    "multiply": 0x6A, "add": 0x6B, "subtract": 0x6D, "decimal": 0x6E, "divide": 0x6F,
}
for _i in range(1, 25):
    _NAMED_KEYS["f%d" % _i] = 0x6F + _i          # F1=0x70
for _i in range(10):
    _NAMED_KEYS["numpad%d" % _i] = 0x60 + _i


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE


def _debug_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "PetalMenu", "hook.log")


def _debug(msg):
    if not os.environ.get("PETALMENU_HOOK_DEBUG"):
        return
    try:
        with open(_debug_path(), "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def _vk_for(name):
    name = name.strip().lower()
    if name in _NAMED_KEYS:
        return _NAMED_KEYS[name]
    if len(name) == 1:
        ch = name.upper()
        if "A" <= ch <= "Z" or "0" <= ch <= "9":
            return ord(ch)
        vk = user32.VkKeyScanW(name)
        if vk != -1:
            return vk & 0xFF
    raise ValueError("无法识别的按键：%r" % name)


def parse_combo(combo):
    """'ctrl+alt+v' -> (mods_mask, vk)。未识别的组合抛 ValueError。"""
    parts = [p.strip() for p in str(combo).split("+") if p.strip()]
    if not parts:
        raise ValueError("空热键")
    mods = 0
    key = None
    for part in parts:
        low = part.lower()
        if low in _MOD_ALIASES:
            mods |= _MOD_ALIASES[low]
        elif key is None:
            key = part
        else:
            raise ValueError("一个热键只能有一个主键：%r" % combo)
    if key is None:
        raise ValueError("热键缺少主键：%r" % combo)
    return mods, _vk_for(key)


class HotkeyManager:
    """在独立线程里装 WH_KEYBOARD_LL 钩子，按「修饰键集合 + 主键」精确匹配。"""

    def __init__(self):
        self._hotkeys = []          # [(mods, vk, combo, callback)]
        self._lock = threading.RLock()
        self._last_down = {}
        self._down = set()
        self._swallow = set()       # 已吞掉 keydown 的 vk，其 keyup 也要吞掉
        self._hook = None
        self._proc = None
        self._started = threading.Event()
        self._thread = None
        self.error = None

    # ------------------------------------------------------------ 配置
    def set_hotkeys(self, items):
        """items: [(combo, callback), ...]；运行中也能热更新。"""
        parsed = []
        for combo, cb in items:
            try:
                mods, vk = parse_combo(combo)
            except Exception as e:
                _debug("parse fail %r: %s" % (combo, e))
                continue
            parsed.append((mods, vk, combo, cb))
        with self._lock:
            self._hotkeys = parsed
        _debug("hotkeys -> %s" % [(c, hex(v)) for _m, v, c, _cb in parsed])
        return parsed

    def start(self, timeout=3.0):
        self._thread = threading.Thread(target=self._run, name="petalmenu-hotkeys", daemon=True)
        self._thread.start()
        ok = self._started.wait(timeout)
        if self.error:
            raise self.error
        return ok and self._hook is not None

    def stop(self):
        try:
            if self._hook:
                user32.UnhookWindowsHookEx(self._hook)
        except Exception:
            pass
        self._hook = None

    # ------------------------------------------------------------ 钩子
    def _run(self):
        try:
            self._proc = HOOKPROC(self._handle)
            hmod = kernel32.GetModuleHandleW(None)
            self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, hmod, 0)
            if not self._hook:
                self.error = OSError("SetWindowsHookExW 失败，err=%d" % ctypes.get_last_error())
                self._started.set()
                return
            _debug("hook installed")
            self._started.set()
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e:                    # pragma: no cover
            self.error = e
            self._started.set()

    def _handle(self, nCode, wParam, lParam):
        try:
            if nCode == 0:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kb.vkCode
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if self._on_down(vk, kb.flags):
                        # 返回非 0 = 吞掉这次按键，不再传给前台窗口。
                        # 不吞的话 Alt+Z 会落到资源管理器/桌面，系统对「没有对应菜单
                        # 助记符的 Alt+字母」会放一声默认提示音（MessageBeep），
                        # 这就是开菜单时听到的「叮」。
                        return 1
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    self._down.discard(vk)
                    if vk in self._swallow:
                        self._swallow.discard(vk)
                        return 1
        except Exception as e:                    # pragma: no cover
            _debug("hook error: %r" % (e,))
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _current_mods(self):
        mods = 0
        for flag, vks in _MOD_VKS:
            for vk in vks:
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    mods |= flag
                    break
        return mods

    @staticmethod
    def _down_mod_vks():
        """当前真实按下的修饰键 vk 列表（用于吞掉它们的 keyup）。"""
        out = []
        for _flag, vks in _MOD_VKS:
            for vk in vks:
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    out.append(vk)
                    break
        return out

    def _on_down(self, vk, flags):
        """返回 True 表示这次按键已作为热键消费掉，钩子应吞掉它不再下发。"""
        if vk == VK_PACKET:                        # Unicode 文本注入，没有实体键
            return False
        now = time.monotonic()
        prev = self._last_down.get(vk)
        self._last_down[vk] = now
        self._down.add(vk)
        if prev is not None and now - prev < 0.30:
            _debug("repeat vk=0x%02X skipped" % vk)
            return vk in self._swallow            # 热键的连发也一并吞掉
        mods = self._current_mods()
        with self._lock:
            hks = list(self._hotkeys)
        for req_mods, req_vk, combo, cb in hks:
            if req_vk == vk and req_mods == mods:
                _debug("HIT %s vk=0x%02X flags=0x%02X mods=0x%02X injected=%d swallow=%d"
                       % (combo, vk, flags, mods, 1 if flags & LLKHF_INJECTED else 0,
                          1 if SWALLOW_HOTKEYS else 0))
                if SWALLOW_HOTKEYS:
                    self._swallow.add(vk)
                    # 只吞主键，不吞修饰键的 keyup。若把 Alt 的 keyup 也吞掉，
                    # 前台窗口就只收到一次“Alt 按下”而永远等不到抬起，Win32 程序
                    # 会卡在菜单模式里（现象：Everything 里 F2 更名失效）。
                    # 放行 Alt 的 keyup 只是让窗口收到一次普通 Alt 单击，
                    # 不会响（提示音要 Alt+字母才触发）。
                threading.Thread(target=self._safe_call, args=(cb,), daemon=True).start()
                return SWALLOW_HOTKEYS
        # 没命中：清掉可能残留的吞键标记（上一轮的 keyup 丢了），
        # 否则这一次正常按键的 keyup 会被误吞，前台应用会以为键一直按着。
        self._swallow.discard(vk)
        _debug("down vk=0x%02X flags=0x%02X mods=0x%02X (no match)" % (vk, flags, mods))
        return False

    @staticmethod
    def _safe_call(cb):
        try:
            cb()
        except Exception:
            import traceback
            traceback.print_exc()
            _debug("callback error: %s" % traceback.format_exc().replace("\n", " | "))
