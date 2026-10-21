# -*- coding: utf-8 -*-
"""Windows 实机验证：右键中心 -> 设置花瓣数量 -> 改数字 -> OK 保存 -> 重建菜单
鼠标用真实 SendInput（SetCursorPos + mouse_event），键盘用 keybd_event。
坐标走 Win32 ClientToScreen + dpr，避免逻辑/物理像素换算误差。
"""
import sys, os, ctypes, math, types

HERE = r"C:\tmp\hotkey"
sys.path.insert(0, HERE)
os.chdir(HERE)

from PyQt6.QtWidgets import QApplication, QSpinBox, QDialogButtonBox, QPushButton
from PyQt6.QtWidgets import QStyle, QStyleOptionSpinBox
from PyQt6.QtCore import QTimer, QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6 import sip

u = ctypes.windll.user32
u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]

log = lambda *a: print(*a, flush=True)
FAIL = []
def check(cond, msg):
    log(f"  {'PASS' if cond else 'FAIL'} - {msg}")
    if not cond:
        FAIL.append(msg)

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def wrect(widget):
    r = RECT()
    u.GetWindowRect(int(widget.window().winId()), ctypes.byref(r))
    return r

def phys(widget, rel):
    win = widget.window()
    dpr = win.devicePixelRatioF()
    p = POINT(0, 0)
    u.ClientToScreen(int(win.winId()), ctypes.byref(p))
    q = widget.mapTo(win, rel)
    return (int(round(p.x + q.x() * dpr)), int(round(p.y + q.y() * dpr)))

def click(xy, right=False):
    u.SetCursorPos(int(xy[0]), int(xy[1]))
    QTest.qWait(150)
    down, up = (0x0008, 0x0010) if right else (0x0002, 0x0004)
    u.mouse_event(down, 0, 0, 0, 0); QTest.qWait(60)
    u.mouse_event(up, 0, 0, 0, 0);   QTest.qWait(400)

def win_center_click(widget, right=False):
    r = wrect(widget)
    click(((r.left + r.right) // 2, (r.top + r.bottom) // 2), right=right)

def key(vk):
    u.keybd_event(vk, 0, 0, 0); QTest.qWait(40)
    u.keybd_event(vk, 0, 2, 0); QTest.qWait(150)

# ---------- 桩 main ----------
STUB = types.ModuleType("main")
STUB.CONFIG = {"petal_count": 3, "petals": [
    {"name": "默认打开", "program": ""},
    {"name": "PotPlayer", "program": r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe",
     "exts": [".mp4", ".mkv", ".avi"]},
    {"name": "XnView", "program": r"C:\tools\xnview\xnview.exe", "exts": [".jpg", ".png"]},
    {"name": "所在文件夹", "program": "__explorer__"}]}
STUB.calls = []
STUB.save_config = lambda: (STUB.calls.append("save_config"), True)[1]
STUB.load_config = lambda: STUB.calls.append("load_config")
STUB.reshow_menu = lambda: STUB.calls.append("reshow_menu")
STUB.notify = lambda t, m: log(f"   [notify] {m}")
sys.modules["main"] = STUB

import petal_menu as pm

app = QApplication(sys.argv[:1])
app.setQuitOnLastWindowClosed(False)
petals = STUB.CONFIG["petals"]
log(f"dpr={app.primaryScreen().devicePixelRatio()} platform={app.platformName()}")

# ---------- 1) petal_count 语义 ----------
log("\n=== 1) petal_count 语义（先按类型过滤，再取前 N）===")
for fn, cnt, exp in [("a.mp4", 3, ["默认打开", "PotPlayer", "所在文件夹"]),
                     ("a.jpg", 3, ["默认打开", "XnView", "所在文件夹"]),
                     ("a.mp4", 2, ["默认打开", "PotPlayer"]),
                     ("a.mp4", 0, ["默认打开", "PotPlayer", "所在文件夹"])]:
    got = [p["name"] for p in pm.visible_petals(petals, [rf"C:\v\{fn}"], cnt)]
    check(got == exp, f"{fn} count={cnt} -> {got}")

# ---------- 2) 真实右键中心 ----------
log("\n=== 2) 真实右键中心 -> 对话框可操作 ===")
dlg = None
menu = None
for attempt in range(3):
    menu = pm.PetalMenu([r"C:\v\a.mp4"], petals, petal_count=3)
    u.SetCursorPos(900, 560); QTest.qWait(250)
    menu.show_at_cursor(); QTest.qWait(700)
    win_center_click(menu, right=True)
    QTest.qWait(700)
    dlg = next((w for w in QApplication.topLevelWidgets()
                if isinstance(w, pm.SetCountDialog) and w.isVisible()), None)
    log(f"   attempt={attempt} 对话框={dlg is not None} 菜单仍在={menu.isVisible()}")
    if dlg:
        break
    menu.close(); QTest.qWait(200)
check(dlg is not None, "数量对话框弹出且存活")

if dlg:
    check(not menu.isVisible(), "花瓣菜单已关闭")
    spin = dlg.findChild(QSpinBox)
    hwnd_dlg = int(dlg.winId())
    log(f"  初始值={spin.value()} 前台={u.GetForegroundWindow() == hwnd_dlg} "
        f"active={dlg.isActiveWindow()} 焦点={type(QApplication.focusWidget()).__name__}")
    check(spin.value() == 3, f"初始值读到配置里的 3 -> {spin.value()}")

    spin.setFocus(); spin.selectAll(); QTest.qWait(150)
    key(0x32)                                   # 真实按 '2'
    check(spin.value() == 2, f"真实键盘输入 2 -> {spin.value()}")

    r = spin.rect()
    opt = QStyleOptionSpinBox(); spin.initStyleOption(opt)
    up = spin.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, opt,
                                     QStyle.SubControl.SC_SpinBoxUp, spin)
    dn = spin.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, opt,
                                     QStyle.SubControl.SC_SpinBoxDown, spin)
    click(phys(spin, up.center()))
    check(spin.value() == 3, f"真实点『+』-> {spin.value()}")
    click(phys(spin, dn.center()))
    check(spin.value() == 2, f"真实点『-』-> {spin.value()}")

    bm = next((b for b in dlg.findChildren(QPushButton)
               if b.text().startswith("匹配到的全部")), None)
    if bm:
        click(phys(bm, bm.rect().center()))
        check(spin.value() == 3, f"点『匹配到的全部』-> {spin.value()}")

    spin.setFocus(); spin.selectAll(); QTest.qWait(120)
    key(0x32)
    bb = dlg.findChild(QDialogButtonBox)
    ok = bb.button(QDialogButtonBox.StandardButton.Ok)
    click(phys(ok, ok.rect().center()))
    QTest.qWait(600)
    check(sip.isdeleted(dlg) or not dlg.isVisible(), "点 OK 后对话框关闭")
    check(STUB.CONFIG["petal_count"] == 2,
          f"配置已写入 petal_count={STUB.CONFIG['petal_count']}（期望 2）")
    check("save_config" in STUB.calls, f"save_config 已调用")
    check("reshow_menu" in STUB.calls, f"保存后自动刷新菜单 calls={STUB.calls}")

# ---------- 3) 新配置立即生效 ----------
log("\n=== 3) 保存后菜单按新数量渲染 ===")
got = [p["name"] for p in pm.visible_petals(STUB.CONFIG["petals"], [r"C:\v\a.mp4"],
                                            STUB.CONFIG["petal_count"])]
check(got == ["默认打开", "PotPlayer"], f"渲染结果 -> {got}")
menu2 = pm.PetalMenu([r"C:\v\a.mp4"], STUB.CONFIG["petals"],
                     petal_count=STUB.CONFIG["petal_count"])
u.SetCursorPos(900, 560); QTest.qWait(150)
check(menu2.show_at_cursor(), "新菜单能弹出"); QTest.qWait(300)
menu2.close(); QTest.qWait(200)

# ---------- 4) 右键花瓣：编辑程序 ----------
log("\n=== 4) 真实右键花瓣 -> 编辑程序对话框 ===")
STUB.calls.clear()
menu3 = pm.PetalMenu([r"C:\v\a.mp4"], petals, petal_count=0)
u.SetCursorPos(900, 560); QTest.qWait(200)
menu3.show_at_cursor(); QTest.qWait(600)
n = len(menu3.petals)
c = menu3.rect().center()
ang = math.radians(360.0 / n * 0.5)
r_mid = (pm.R_INNER + pm.R_OUTER) / 2
pt = QPoint(int(c.x() + r_mid * math.cos(ang)), int(c.y() - r_mid * math.sin(ang)))
click(phys(menu3, pt), right=True)
QTest.qWait(700)
edlg = next((w for w in QApplication.topLevelWidgets()
             if isinstance(w, pm.EditPetalDialog) and w.isVisible()), None)
check(edlg is not None, "编辑花瓣对话框弹出且存活")
if edlg:
    le = edlg.edit
    log(f"  前台={u.GetForegroundWindow() == int(edlg.winId())} "
        f"active={edlg.isActiveWindow()} 焦点={type(QApplication.focusWidget()).__name__}")
    click(phys(le, le.rect().center()))
    le.selectAll(); QTest.qWait(150)
    key(0x41)                                   # 真实按 'a'
    check(le.text() == "a", f"编辑框能输入 -> {le.text()!r}")
    edlg.reject(); QTest.qWait(200)

log("\n==== 汇总 ====")
log("全部通过" if not FAIL else f"失败 {len(FAIL)} 项: {FAIL}")
QTimer.singleShot(300, app.quit)
app.exec()
sys.exit(1 if FAIL else 0)
