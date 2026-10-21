# -*- coding: utf-8 -*-
"""检测“系统提示音”(MessageBeep / 默认提示音) 是否真的响了。

原理：拿默认播放设备的 IAudioMeterInformation（WASAPI 主音量表）每 15ms 采一次
峰值。系统提示音走同一个渲染设备，只要它响了就会看到一段明显的能量突起。
先用 winsound.MessageBeep 做一次标定，确认检测链路有效，再测热键路径。

用法：
    python.exe C:/tmp/hotkey/tests/_beep_probe.py            # 标定 + 3 次测量
    python.exe C:/tmp/hotkey/tests/_beep_probe.py --meters 12
    python.exe C:/tmp/hotkey/tests/_beep_probe.py --quiet     # 只打印是否有声
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

ole32 = ctypes.WinDLL("ole32")

CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
IID_IAudioMeterInformation = "{C02216F6-8C67-4B5B-9D00-D008E73E0064}"
CLSCTX_ALL = 23
eRender, eConsole = 0, 0


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


def guid(s):
    g = GUID()
    ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
    return g


def _vtbl_call(obj, index, restype, *argtypes):
    """按 vtable 索引取 COM 方法，返回一个已绑定 this 的可调用对象。"""
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    fn = proto(vtbl[index])

    def call(*args):
        return fn(obj, *args)

    return call


def com_init():
    """每个使用 COM 的线程都要初始化；用 MTA(0) 以便多个线程共享接口指针。"""
    try:
        ole32.CoInitializeEx(None, 0)
    except Exception:
        pass


class Meter:
    def __init__(self):
        hr = ole32.CoInitializeEx(None, 0)
        self._co = True
        enum = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(ctypes.byref(guid(CLSID_MMDeviceEnumerator)), None,
                                    CLSCTX_ALL, ctypes.byref(guid(IID_IMMDeviceEnumerator)),
                                    ctypes.byref(enum))
        if hr != 0:
            raise OSError("CoCreateInstance(MMDeviceEnumerator) hr=0x%08X" % (hr & 0xFFFFFFFF))
        self.enum = enum
        dev = ctypes.c_void_p()
        hr = _vtbl_call(enum, 4, ctypes.c_long, ctypes.c_int, ctypes.c_int,
                        ctypes.POINTER(ctypes.c_void_p))(eRender, eConsole, ctypes.byref(dev))
        if hr != 0:
            raise OSError("GetDefaultAudioEndpoint hr=0x%08X" % (hr & 0xFFFFFFFF))
        self.dev = dev
        meter = ctypes.c_void_p()
        hr = _vtbl_call(dev, 3, ctypes.c_long, ctypes.POINTER(GUID), wt.DWORD,
                        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
            ctypes.byref(guid(IID_IAudioMeterInformation)), CLSCTX_ALL, None,
            ctypes.byref(meter))
        if hr != 0:
            raise OSError("Activate(IAudioMeterInformation) hr=0x%08X" % (hr & 0xFFFFFFFF))
        self.meter = meter
        self._get_peak = _vtbl_call(meter, 3, ctypes.c_long,
                                    ctypes.POINTER(ctypes.c_float))

    def peak(self):
        v = ctypes.c_float(0.0)
        hr = self._get_peak(ctypes.byref(v))
        return v.value if hr == 0 else 0.0

    def sample(self, seconds, interval=0.015):
        out = []
        t0 = time.time()
        while time.time() - t0 < seconds:
            out.append((time.time() - t0, self.peak()))
            time.sleep(interval)
        return out


IID_IAudioSessionManager2 = "{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}"
IID_IAudioSessionControl2 = "{BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D}"


def _default_render_device():
    enum = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(guid(CLSID_MMDeviceEnumerator)), None,
                                CLSCTX_ALL, ctypes.byref(guid(IID_IMMDeviceEnumerator)),
                                ctypes.byref(enum))
    if hr != 0:
        raise OSError("CoCreateInstance(MMDeviceEnumerator) hr=0x%08X" % (hr & 0xFFFFFFFF))
    dev = ctypes.c_void_p()
    hr = _vtbl_call(enum, 4, ctypes.c_long, ctypes.c_int, ctypes.c_int,
                    ctypes.POINTER(ctypes.c_void_p))(eRender, eConsole, ctypes.byref(dev))
    if hr != 0:
        raise OSError("GetDefaultAudioEndpoint hr=0x%08X" % (hr & 0xFFFFFFFF))
    return dev


def _activate(dev, iid_str):
    obj = ctypes.c_void_p()
    hr = _vtbl_call(dev, 3, ctypes.c_long, ctypes.POINTER(GUID), wt.DWORD,
                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
        ctypes.byref(guid(iid_str)), CLSCTX_ALL, None, ctypes.byref(obj))
    if hr != 0:
        raise OSError("Activate(%s) hr=0x%08X" % (iid_str, hr & 0xFFFFFFFF))
    return obj


def _query_interface(obj, iid_str):
    out = ctypes.c_void_p()
    hr = _vtbl_call(obj, 0, ctypes.c_long, ctypes.POINTER(GUID),
                    ctypes.POINTER(ctypes.c_void_p))(
        ctypes.byref(guid(iid_str)), ctypes.byref(out))
    return out if hr == 0 else None


class SystemSoundsMeter:
    """只测“系统声音”这个音频会话，不受 Chrome/音乐等其它进程影响。

    音量表本身是“最近 ~10ms 的峰值”，系统提示音走 System Sounds 会话，
    所以这个表能干净地回答“刚才是不是响了一声”。
    """

    def __init__(self):
        ole32.CoInitializeEx(None, 0)
        self.dev = _default_render_device()
        self.mgr = _activate(self.dev, IID_IAudioSessionManager2)
        self.meter = None
        self._next_scan = 0.0
        self._get_peak = None

    def _resolve(self):
        enum = ctypes.c_void_p()
        hr = _vtbl_call(self.mgr, 5, ctypes.c_long,
                        ctypes.POINTER(ctypes.c_void_p))(ctypes.byref(enum))
        if hr != 0:
            self.meter = None
            return False
        count = ctypes.c_int(0)
        if _vtbl_call(enum, 3, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(
                ctypes.byref(count)) != 0:
            self.meter = None
            return False
        for i in range(count.value):
            ctl = ctypes.c_void_p()
            if _vtbl_call(enum, 4, ctypes.c_long, ctypes.c_int,
                          ctypes.POINTER(ctypes.c_void_p))(i, ctypes.byref(ctl)) != 0:
                continue
            ctl2 = _query_interface(ctl, IID_IAudioSessionControl2) or ctl
            # index 15 = IsSystemSoundsSession，S_OK 表示这就是系统声音会话
            if _vtbl_call(ctl2, 15, ctypes.c_long)() == 0:
                meter = _query_interface(ctl2, IID_IAudioMeterInformation)
                if meter:
                    self.meter = meter
                    self._get_peak = _vtbl_call(meter, 3, ctypes.c_long,
                                                ctypes.POINTER(ctypes.c_float))
                    return True
        self.meter = None
        return False

    def peak(self):
        now = time.time()
        if self.meter is None and now >= self._next_scan:
            self._next_scan = now + 0.25
            self._resolve()
        if self.meter is None:
            return 0.0
        v = ctypes.c_float(0.0)
        hr = self._get_peak(ctypes.byref(v))
        if hr != 0:
            self.meter = None
            return 0.0
        return v.value

    def sample(self, seconds, interval=0.015):
        out = []
        t0 = time.time()
        while time.time() - t0 < seconds:
            out.append((time.time() - t0, self.peak()))
            time.sleep(interval)
        return out


def summarize(samples, floor=0.002):
    """返回 (max_peak, 有声音的采样数)。floor 以下视为静音。"""
    peaks = [p for _t, p in samples]
    loud = [p for p in peaks if p > floor]
    return (max(peaks) if peaks else 0.0), len(loud)


def report(tag, samples):
    mx, n = summarize(samples)
    print("%-28s max_peak=%.4f loud_samples=%d/%d -> %s"
          % (tag, mx, n, len(samples), "HAS SOUND" if n else "silent"))
    return n > 0


def main():
    import winsound
    quiet = "--quiet" in sys.argv
    reps = 3
    if "--meters" in sys.argv:
        reps = int(sys.argv[sys.argv.index("--meters") + 1])

    m = Meter()
    print("device meter ready; idle floor check:")
    report("idle baseline", m.sample(0.8))

    # 标定：手动放一声默认提示音
    m.sample(0.2)
    winsound.MessageBeep(winsound.MB_ICONASTERISK)
    cal = m.sample(1.0)
    ok = report("calibration (MessageBeep)", cal)
    if not ok:
        print("!! 标定失败：检测链路或音量有问题，后面的结论不可信")
    time.sleep(0.4)

    results = []
    for i in range(reps):
        m.sample(0.2)
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        results.append(report("repeat beep #%d" % (i + 1), m.sample(1.0)))
        time.sleep(0.3)
    print("calibration all_ok=%s" % all(results))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
