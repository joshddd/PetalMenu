# -*- coding: utf-8 -*-
"""复现：右键花瓣改程序 -> 是否真的写进 config.yaml（真实 main + 真实对话框逻辑）"""
import os, shutil, sys, time, glob

HERE = r"C:\tmp\hotkey"
TMP = r"C:\tmp\hotkey\_edittmp"
sys.path.insert(0, HERE)
os.chdir(HERE)

shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)
APP = os.path.join(TMP, "PetalMenu")
os.makedirs(APP, exist_ok=True)

SRC = os.path.join(os.environ.get("APPDATA"), "PetalMenu", "config.yaml")
shutil.copy2(SRC, os.path.join(APP, "config.yaml"))
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
from PyQt6.QtWidgets import QApplication

log(f"CONFIG_PATH = {M.CONFIG_PATH}")
M.load_config()

app = QApplication(sys.argv[:1])
app.setQuitOnLastWindowClosed(False)

VLC = r"C:\Program Files\VideoLAN\VLC\vlc.exe"


def pump(sec=1.5):
    t0 = time.time()
    while time.time() - t0 < sec:
        app.processEvents()
        time.sleep(0.02)


def find_dlg():
    return next((w for w in QApplication.topLevelWidgets()
                 if isinstance(w, pm.EditPetalDialog) and w.isVisible()), None)


def disk_petals():
    with open(M.CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f).get("petals", [])


def prog_of(name, petals):
    return next((p.get("program") for p in petals if p.get("name") == name), "<缺失>")


menu = pm.PetalMenu([r"C:\v\a.mp4"], M.CONFIG["petals"], petal_count=3)
log(f"菜单花瓣: {[p['name'] for p in menu.petals]}")
log(f"_all_petals_cfg 与 CONFIG['petals'] 同一对象? {menu._all_petals_cfg is M.CONFIG['petals']}")

for target in ("PotPlayer", "默认打开"):
    log(f"\n=== 编辑花瓣「{target}」的程序为 VLC ===")
    petal = next((p for p in menu.petals if p["name"] == target), None)
    if petal is None:
        log(f"  跳过：菜单里没有 {target}")
        continue
    log(f"  菜单里的 petal 对象: {petal}")
    menu._edit_petal(petal)
    pump(1.2)
    dlg = find_dlg()
    check(dlg is not None, "编辑对话框出现")
    if not dlg:
        continue
    from PyQt6.QtWidgets import QLineEdit
    edit = dlg.findChildren(QLineEdit)[0]
    log(f"  对话框初始内容={edit.text()!r}")
    edit.setText(VLC)
    dlg.accept()                       # 等价于点“确定”
    pump(1.5)

    d = disk_petals()
    got = prog_of(target, d)
    check(got == VLC, f"config.yaml 里「{target}」的 program = {got!r}")
    got_mem = prog_of(target, M.CONFIG.get("petals", []))
    check(got_mem == VLC, f"内存 CONFIG 里「{target}」的 program = {got_mem!r}")

# 模拟重启：重新 load_config
log("\n=== 模拟重启后重新读配置 ===")
M.load_config()
for name in ("PotPlayer", "默认打开"):
    got = prog_of(name, M.CONFIG.get("petals", []))
    log(f"  重启后「{name}」-> {got!r}")

# 菜单重新渲染时能否拿到新程序
menu2 = pm.PetalMenu([r"C:\v\a.mp4"], M.CONFIG["petals"], petal_count=3)
for p in menu2.petals:
    log(f"  新菜单花瓣: {p['name']!r} program={p.get('program')!r}")

log("\n==== 汇总 ====")
log("全部通过" if not FAIL else f"失败 {len(FAIL)} 项: {FAIL}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
