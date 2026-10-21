# -*- coding: utf-8 -*-
"""忠实复现用户流程：热键弹菜单 -> 真实右键花瓣 -> 输入 VLC 路径 -> 确定 -> 查 config.yaml
用临时 APPDATA，不碰真实配置。
"""
import os, shutil, sys, time, math, ctypes

HERE = r"C:\tmp\hotkey"
TMP = r"C:\tmp\hotkey\_uitmp"
sys.path.insert(0, HERE)
os.chdir(HERE)

shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(os.path.join(TMP, "PetalMenu"), exist_ok=True)
SRC = os.path.join(os.environ["APPDATA"], "PetalMenu", "config.yaml")
shutil.copy2(SRC, os.path.join(TMP, "PetalMenu", "config.yaml"))
os.environ["APPDATA"] = TMP

log = lambda *a: print(*a, flush=True)
FAIL = []
def check(cond, msg):
    log(f"  {'PASS' if cond else 'FAIL'} - {msg}")
    if not cond:
        FAIL.append(msg)

import main as M
import petal_menu as pm
import yaml
from PyQt6.QtWidgets import QApplication, QLineEdit
from PyQt6.QtTest import QTest
from PyQt6.QtCore import QPoint, Qt
from PyQt6 import sip

u = ctypes.windll.user32
u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

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
    u.mouse_event(up, 0, 0, 0, 0);   QTest.qWait(500)

def pump(sec=1.5):
    t0 = time.time()
    while time.time() - t0 < sec:
        app.processEvents()
        time.sleep(0.02)

VLC = r"C:\Program Files\VideoLAN\VLC\vlc.exe"

M.load_config()
app = QApplication(sys.argv[:1])
app.setQuitOnLastWindowClosed(False)
log(f"配置: {M.CONFIG_PATH}")
log(f"dpr={app.primaryScreen().devicePixelRatio()}")

def disk():
    with open(M.CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

def prog_of(name, petals):
    return next((p.get("program") for p in petals if p.get("name") == name), "<缺失>")

for target_idx, target in [(1, "PotPlayer"), (0, "默认打开")]:
    log(f"\n=== 按用户流程改「{target}」为 VLC ===")
    M.show_menu_for([r"M:\july2026\a.mp4"])
    pump(0.8)
    menu = M.CURRENT_MENU
    check(menu is not None and menu.isVisible(), "菜单已弹出")
    if not menu:
        continue
    log(f"  菜单花瓣: {[p['name'] for p in menu.petals]}")
    n = len(menu.petals)
    c = menu.rect().center()
    ang = math.radians(360.0 / n * target_idx + 360.0 / n * 0.5)
    r_mid = (pm.R_INNER + pm.R_OUTER) / 2
    pt = QPoint(int(c.x() + r_mid * math.cos(ang)), int(c.y() - r_mid * math.sin(ang)))
    click(phys(menu, pt), right=True)
    pump(1.0)
    dlg = next((w for w in QApplication.topLevelWidgets()
                if isinstance(w, pm.EditPetalDialog) and w.isVisible()), None)
    check(dlg is not None, f"「{target}」的编辑对话框出现")
    if not dlg:
        continue
    edit = dlg.findChildren(QLineEdit)[0]
    log(f"  对话框原内容={edit.text()!r}")
    edit.setFocus(); edit.selectAll(); QTest.qWait(150)
    QTest.keyClicks(edit, VLC)
    QTest.qWait(150)
    log(f"  输入后={edit.text()!r}")
    QTest.keyClick(edit, Qt.Key.Key_Return)     # 回车 = 确定
    pump(2.0)
    check(sip.isdeleted(dlg) or not dlg.isVisible(), "对话框已关闭")
    got = prog_of(target, disk().get("petals", []))
    check(got == VLC, f"config.yaml 里「{target}」= {got!r}")
    got_mem = prog_of(target, M.CONFIG.get("petals", []))
    check(got_mem == VLC, f"内存 CONFIG 里「{target}」= {got_mem!r}")
    if M.CURRENT_MENU:
        log(f"  刷新后的菜单: {[(p['name'], p.get('program')) for p in M.CURRENT_MENU.petals]}")
        M.CURRENT_MENU.close()
        pump(0.3)

log("\n=== 模拟重启（重新 load_config）===")
M.load_config()
for name in ("PotPlayer", "默认打开"):
    log(f"  重启后「{name}」-> {prog_of(name, M.CONFIG['petals'])!r}")

log("\n==== 汇总 ====")
log("全部通过" if not FAIL else f"失败 {len(FAIL)} 项: {FAIL}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
