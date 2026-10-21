# -*- coding: utf-8 -*-
"""定位 on_show_menu 失败原因：前台窗口类名 + PowerShell 读取选中项。"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _beep_e2e as E  # noqa: E402

CLS = {}


def fg_info():
    u = E.user32
    h = u.GetForegroundWindow()
    buf = E.ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, buf, 256)
    t = E.ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(h, t, 256)
    return h, buf.value, t.value


hwnd, cls, txt = E.find_window(lambda c, t: c == "CabinetWClass")
print("explorer hwnd=%s cls=%s txt=%s" % (hwnd, cls, txt))
print("foreground before:", fg_info())
print("grab_focus:", E.grab_focus(hwnd))
time.sleep(0.4)
E.combo(0x11, 0x41)
time.sleep(0.5)
print("foreground after:", fg_info())

script = """
$shell = New-Object -ComObject Shell.Application
$doc = $null
foreach ($w in $shell.Windows()) {
    if ($w.HWND -eq %d) { $doc = $w.Document; break }
}
if ($null -eq $doc) { exit 1 }
$items = @($doc.SelectedItems() | ForEach-Object { $_.Path })
if ($items.Count -eq 0) { exit 2 }
$items -join "`n"
""" % hwnd
r = subprocess.run(["powershell", "-NoProfile", "-STA", "-NonInteractive", "-Command", script],
                   capture_output=True, text=True, timeout=30)
print("ps exit=%s" % r.returncode)
print("ps out=%r" % r.stdout[:400])
print("ps err=%r" % r.stderr[:300])
