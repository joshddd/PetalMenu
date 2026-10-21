# -*- coding: utf-8 -*-
"""托盘右键设置菜单测试（打桩，不碰真实配置、不注册真实热键）。

跑法：/mnt/d/ComfyUI-aki-v1.6/python/python.exe tests/_settings_test_win.py
"""
import os
import sys
import tempfile
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 关键：必须在 import main 之前把 APPDATA 指到临时目录，
# 否则测试会把用户正在跑的 %APPDATA%\PetalMenu\config.yaml 改掉。
TMP = tempfile.mkdtemp(prefix="pm_settings_")
os.environ["APPDATA"] = TMP
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import yaml
from PyQt6.QtWidgets import QApplication

import petal_menu as pm
import main

FAILED = []
PASSED = []


def check(name, cond, extra=""):
    if cond:
        PASSED.append(name)
        print("  ok   %s" % name)
    else:
        FAILED.append(name + ((" | " + str(extra)) if extra else ""))
        print("  FAIL %s %s" % (name, extra))


def sub_actions(menu):
    return [a for a in menu.actions() if a.menu() is not None]


def action_texts(menu):
    return [a.text() for a in menu.actions()]


def read_cfg():
    with open(main.CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


app = QApplication.instance() or QApplication([])

print("\n== 配色 / 尺寸数据表 ==")
check("有 5 套配色", len(pm.PALETTES) == 5, list(pm.PALETTES))
labels = [p["label"] for p in pm.PALETTES.values()]
check("配色含 中式/和式/莫兰迪/清新",
      all(x in labels for x in ("中式", "和式", "莫兰迪", "清新")), labels)
check("每套配色字段齐全",
      all(set(("label", "colors", "text", "center", "center_text",
               "ph_border", "ph_fill")) <= set(p) and len(p["colors"]) >= 6
          for p in pm.PALETTES.values()))
check("有 4 档花瓣大小", len(pm.PETAL_SIZES) == 4, list(pm.PETAL_SIZES))

print("\n== PetalMenu 应用配色与尺寸 ==")
m = pm.PetalMenu([], [], palette_name="morandi", size_name="large")
check("morandi 配色生效", m._pal["label"] == "莫兰迪", m._pal["label"])
check("large 半径放大 1.26", abs(m.r_out - pm.R_OUTER * 1.26) < 1e-6, m.r_out)
check("内半径同比放大", abs(m.r_in - pm.R_INNER * 1.26) < 1e-6, m.r_in)
check("窗口尺寸跟着变大", m._size > 2 * (pm.R_OUTER + 36), m._size)
m2 = pm.PetalMenu([], [], palette_name="不存在", size_name="也不存在")
check("非法配色回落经典", m2._pal["label"] == "经典", m2._pal["label"])
check("非法尺寸回落 1.0", abs(m2.r_out - pm.R_OUTER) < 1e-6, m2.r_out)

print("\n== 托盘菜单结构 ==")
menu = main.build_tray_menu(app)
tops = [t for t in action_texts(menu) if t]
check("顶层只剩 4 项", tops == ["呼出花瓣菜单的快捷键", "配色方案", "花瓣大小", "退出"], tops)
allt = " ".join(action_texts(menu))
check("已删掉『直接打开选中文件』", "直接打开选中文件" not in allt)
check("已删掉『重新加载配置』", "重新加载配置" not in allt)
check("已删掉『打开配置目录』", "打开配置目录" not in allt)
check("保留『退出』", "退出" in action_texts(menu))

subs = sub_actions(menu)
check("三个子菜单", len(subs) == 3, [a.text() for a in subs])
hk_menu, pal_menu, size_menu = subs

check("配色子菜单 5 项", len(pal_menu.menu().actions()) == 5,
      action_texts(pal_menu.menu()))
check("配色勾选跟随 CONFIG",
      any(a.isChecked() and a.text() == pm.PALETTES[main.CONFIG["palette"]]["label"]
          for a in pal_menu.menu().actions()), main.CONFIG.get("palette"))
size_txt = action_texts(size_menu.menu())
check("大小子菜单 4 项", len(size_txt) == 4, size_txt)
check("大小项带百分比", all("%" in t for t in size_txt), size_txt)
hk_txt = action_texts(hk_menu.menu())
check("快捷键含当前值", main.show_menu_combo() in hk_txt, hk_txt)
check("快捷键有自定义入口", any("自定义" in t for t in hk_txt), hk_txt)

print("\n== 改设置会写回配置 ==")
check("apply_palette 成功", main.apply_palette("fresh") is True)
check("配置里 palette=fresh", read_cfg().get("palette") == "fresh",
      read_cfg().get("palette"))
check("apply_palette 拒绝非法值", main.apply_palette("nope") is False)
check("配置没被非法值污染", read_cfg().get("palette") == "fresh")
check("apply_petal_size 成功", main.apply_petal_size("small") is True)
check("配置里 petal_size=small", read_cfg().get("petal_size") == "small",
      read_cfg().get("petal_size"))
check("apply_petal_size 拒绝非法值", main.apply_petal_size("huge") is False)

print("\n== 改快捷键（打桩：不注册真钩子）==")
main._register_hotkeys = lambda: None
main._combo_free = lambda c: c != "alt+q"   # 假装 alt+q 被别的程序占了
old = main.show_menu_combo()
check("改成空闲组合成功", main.apply_show_hotkey("ctrl+alt+z") is True)
check("配置已写入 ctrl+alt+z", read_cfg()["hotkeys"]["show_menu"] == "ctrl+alt+z",
      read_cfg()["hotkeys"].get("show_menu"))
check("被占用的组合被拒", main.apply_show_hotkey("alt+q") is False)
check("被拒后配置没变", read_cfg()["hotkeys"]["show_menu"] == "ctrl+alt+z")
check("非法组合被拒", main.apply_show_hotkey("ctrl+alt+这不是键") is False)
check("超长组合被拒", main.apply_show_hotkey("") is False)

print("\n== 菜单重建后勾选状态同步 ==")
menu2 = main.build_tray_menu(app)
hk_menu2, pal_menu2, size_menu2 = sub_actions(menu2)
main.apply_palette("chinese")
menu3 = main.build_tray_menu(app)
_, pal_menu3, _ = sub_actions(menu3)
checked = [a.text() for a in pal_menu3.menu().actions() if a.isChecked()]
check("新菜单勾选中式", checked == ["中式"], checked)
size_checked = [a.text() for a in sub_actions(menu3)[2].menu().actions() if a.isChecked()]
check("大小勾选小（78%）", size_checked and "78%" in size_checked[0], size_checked)
hk_checked = [a.text() for a in sub_actions(menu3)[0].menu().actions() if a.isChecked()]
check("快捷键勾选当前值", hk_checked == ["ctrl+alt+z"], hk_checked)

print("\n== 真正点菜单项（QAction.trigger）==")
main._combo_free = lambda c: True
menu4 = main.build_tray_menu(app)
hk4, pal4, size4 = sub_actions(menu4)
act_map = {a.text(): a for a in pal4.menu().actions()}
act_map["和式"].trigger()
check("点『和式』写进配置", read_cfg().get("palette") == "japanese",
      read_cfg().get("palette"))
smap = {a.text(): a for a in size4.menu().actions()}
[lab for lab in smap if "126%" in lab][0:1] and smap[[lab for lab in smap if "126%" in lab][0]].trigger()
check("点『大126%』写进配置", read_cfg().get("petal_size") == "large",
      read_cfg().get("petal_size"))
hmap = {a.text(): a for a in hk4.menu().actions()}
hmap["alt+w"].trigger()
check("点『alt+w』写进配置", read_cfg()["hotkeys"]["show_menu"] == "alt+w",
      read_cfg()["hotkeys"].get("show_menu"))
menu5 = main.build_tray_menu(app)
_, pal5, size5 = sub_actions(menu5)
check("重建后勾选和式",
      [a.text() for a in pal5.menu().actions() if a.isChecked()] == ["和式"],
      [a.text() for a in pal5.menu().actions() if a.isChecked()])
check("重建后勾选大（126%）",
      any(a.isChecked() and "126%" in a.text() for a in size5.menu().actions()))

print("\n== 托盘图标跟随配色 ==")
def top_pixel(icon):
    img = icon.pixmap(64, 64).toImage()
    return img.pixelColor(32, 10).name()

cols = [top_pixel(main.make_tray_icon(n)) for n in ("classic", "chinese", "fresh")]
check("三套配色图标颜色各不相同", len(set(cols)) == 3, cols)
check("中式图标是朱红系", cols[1].lower().startswith("#c0"), cols[1])

shutil.rmtree(TMP, ignore_errors=True)

print("\n通过 %d 项" % len(PASSED))
if FAILED:
    print("失败 %d 项：" % len(FAILED))
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL OK")
