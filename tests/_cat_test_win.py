# -*- coding: utf-8 -*-
"""v9 新功能验证：文件类别识别 + 中心左键打开所在目录

不需要真开资源管理器：把 petal_menu.subprocess.Popen 和 _notify 换掉，
只看它到底拼了什么命令。
"""
import os
import shutil
import sys
import tempfile

HERE = r"C:\tmp\hotkey"
sys.path.insert(0, HERE)

FAIL = []
def check(cond, msg):
    print(("  PASS - " if cond else "  FAIL - ") + msg, flush=True)
    if not cond:
        FAIL.append(msg)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QMouseEvent
from PyQt6.QtCore import QPointF, QEvent, Qt

app = QApplication(sys.argv)

import petal_menu as PM

tmp = tempfile.mkdtemp(prefix="petalmenu_cat_")
f_txt = os.path.join(tmp, "note.txt")
f_pdf = os.path.join(tmp, "doc.pdf")
for p in (f_txt, f_pdf):
    open(p, "w", encoding="utf-8").write("x")
gone = os.path.join(tmp, "gone.7z")          # 不存在，但目录在

calls = []
notices = []
PM.subprocess.Popen = lambda *a, **k: calls.append(a[0] if a else k)
PM._notify = lambda title, msg: notices.append(msg)

petals = [{"name": "默认打开", "program": ""}]
menu = PM.PetalMenu([f_txt, f_pdf], petals, petal_count=2)
menu._scale = 1.0

# 1) 中心左键 -> explorer /select 第一个文件
calls.clear()
menu._open_folder()
check(calls and calls[0] == 'explorer /select,"%s"' % f_txt,
      f"中心左键拼出的命令 = {calls[0] if calls else None}")
check(calls and f_txt in calls[0], "定位到的文件是选中的第一个")

# 2) 文件已不存在但目录还在 -> 直接打开目录
calls.clear()
menu2 = PM.PetalMenu([gone], petals, petal_count=1)
menu2._scale = 1.0
menu2._open_folder()
check(calls and calls[0] == 'explorer "%s"' % tmp, f"文件没了就只开目录 = {calls[0] if calls else None}")

# 3) 目录也不存在 -> 只提示，不乱开
calls.clear()
notices.clear()
menu3 = PM.PetalMenu([os.path.join(tmp, "nodir", "x.iso")], petals, petal_count=1)
menu3._scale = 1.0
ok = menu3._open_folder()
check(ok is False and not calls and notices, f"目录缺失时不开窗口，提示：{notices[:1]}")

# 4) 左键点在中心会关掉菜单（走真实 mousePressEvent）
calls.clear()
menu4 = PM.PetalMenu([f_txt], petals, petal_count=2)
menu4._scale = 1.0
c = menu4._size / 2
ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(c, c), QPointF(c, c),
                 Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                 Qt.KeyboardModifier.NoModifier)
menu4.mousePressEvent(ev)
check(bool(calls), "mousePressEvent 左键点中心触发了打开目录")
check(not menu4.isVisible(), "点完中心菜单已关闭")

# 5) 悬停中心 -> _center_hover 置位，并可绘制文件夹图标
ev2 = QMouseEvent(QEvent.Type.MouseMove, QPointF(c, c), QPointF(c, c),
                  Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                  Qt.KeyboardModifier.NoModifier)
menu4.mouseMoveEvent(ev2)
check(menu4._center_hover is True, "光标在中心时 _center_hover=True")
pm = QPixmap(120, 120)
pm.fill(Qt.GlobalColor.transparent)
pa = QPainter(pm)
pa.translate(60, 60)
menu4._draw_folder_glyph(pa, 28)
menu4._draw_center_text(pa, "打开方式", 28)
pa.end()
check(not pm.isNull(), "中心图标/文字绘制不抛异常")

# 6) 花瓣悬停时不该被当成中心
off = PM._pt(90, (PM.R_INNER + PM.R_OUTER) / 2) if hasattr(PM, "_pt") else None
if off:
    ev3 = QMouseEvent(QEvent.Type.MouseMove, QPointF(c + off[0], c + off[1]),
                      QPointF(c + off[0], c + off[1]), Qt.MouseButton.NoButton,
                      Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    menu4.mouseMoveEvent(ev3)
    check(menu4._center_hover is False, "光标在花瓣上时 _center_hover=False")

shutil.rmtree(tmp, ignore_errors=True)
print("\n==== 汇总 ====")
print("全部通过" if not FAIL else "失败 %d 项: %s" % (len(FAIL), FAIL), flush=True)
sys.exit(1 if FAIL else 0)
