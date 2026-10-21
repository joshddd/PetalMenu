# -*- coding: utf-8 -*-
"""占位花瓣逻辑验证（用临时 APPDATA，不动真实配置）"""
import os, sys, shutil, yaml, glob

SRC = os.path.join(os.environ["APPDATA"], "PetalMenu", "config.yaml")
TMP = r"C:\tmp\hotkey\_padtest"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(os.path.join(TMP, "PetalMenu"), exist_ok=True)
shutil.copy2(SRC, os.path.join(TMP, "PetalMenu", "config.yaml"))
os.environ["APPDATA"] = TMP
HERE = r"C:\tmp\hotkey"
sys.path.insert(0, HERE); os.chdir(HERE)

log = lambda *a: print(*a, flush=True)
FAIL = []
def check(c, m):
    log(f"  {'PASS' if c else 'FAIL'} - {m}")
    if not c: FAIL.append(m)

from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv[:1]); app.setQuitOnLastWindowClosed(False)

import main as M
import petal_menu as pm

petals = M.CONFIG["petals"]
log(f"配置: {len(petals)} 个打开方式, petal_count={M.CONFIG['petal_count']}")
for p in petals:
    log(f"   - {p['name']} exts={p.get('exts')}")

mp4 = [r"C:\v\a.mp4"]; jpg = [r"C:\v\a.jpg"]

log("\n=== 1) mp4: 真实候选已够 3 个 ===")
got = pm.build_petals(petals, mp4, 3)
log("   " + ", ".join(p["name"] for p in got))
check(len(got) == 3, f"显示 3 个花瓣 -> {len(got)}")
check(not any(p.get("_placeholder") for p in got), "没有占位花瓣")

log("\n=== 2) jpg: 只有 2 个能匹配，要求 3 个 -> 补占位 ===")
got = pm.build_petals(petals, jpg, 3)
log("   " + ", ".join(p["name"] for p in got))
check(len(got) == 3, f"显示 3 个花瓣 -> {len(got)}")
check(got[-1].get("_placeholder") is True, "第 3 个是「未配置」占位")
check(got[-1]["_files"] == jpg, "占位花瓣带上了当前文件列表")

log("\n=== 3) 菜单实例与数量对话提示 ===")
menu = pm.PetalMenu(jpg, petals, petal_count=3)
check(len(menu.petals) == 3, f"菜单 petals 数 -> {len(menu.petals)}")
d = pm.SetCountDialog(len(petals), 3, 2)
d.spin.setValue(4)
check("未配置" in d.hint.text(), f"提示语: {d.hint.text()}")
d.close()

log("\n=== 4) 右键占位花瓣 -> 新建花瓣并绑定程序 ===")
menu2 = pm.PetalMenu(jpg, M.CONFIG["petals"], petal_count=3)
ph = [p for p in menu2.petals if p.get("_placeholder")]
check(bool(ph), "菜单里存在占位花瓣")
menu2._add_petal()
from PyQt6.QtCore import QTimer
import time
def pump(sec=1.2):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents(); time.sleep(0.03)
pump()
dlg = next((w for w in QApplication.topLevelWidgets()
           if isinstance(w, pm.EditPetalDialog) and w.isVisible()), None)
check(dlg is not None, "新建花瓣对话框弹出")
if dlg:
    check(dlg.name_edit is not None, "对话框带名称输入框")
    dlg.name_edit.setText("画图")
    dlg.edit.setText(r"C:\Windows\System32\mspaint.exe")
    dlg.accept()
    pump()

with open(os.path.join(TMP, "PetalMenu", "config.yaml"), encoding="utf-8") as f:
    saved = yaml.safe_load(f)
names = [p["name"] for p in saved["petals"]]
log(f"   保存后的 petals: {names}")
check("画图" in names, "新花瓣已写入 config.yaml")
new = next((p for p in saved["petals"] if p["name"] == "画图"), None)
check(new and new.get("exts") == [".jpg"], f"新花瓣只对 .jpg 生效: {new}")
check(len(saved["petals"]) == 4, f"原有 3 个花瓣保留 + 新增 1 个: {len(saved['petals'])}")

log("\n=== 5) 再开菜单：jpg 现在有 3 个真实花瓣 ===")
M.CONFIG = {}
M.load_config()
got = pm.build_petals(M.CONFIG["petals"], jpg, 3)
log("   " + ", ".join(p["name"] for p in got))
check(len(got) == 3 and not any(p.get("_placeholder") for p in got),
      "3 个都是真实花瓣，不再有占位")

log("\n==== 汇总 ====")
log("全部通过" if not FAIL else f"失败 {len(FAIL)} 项: {FAIL}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
