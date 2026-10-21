# -*- coding: utf-8 -*-
"""把每套配色 × 每档尺寸渲染成一张 PNG，人工/视觉核对效果。

跑法：/mnt/d/ComfyUI-aki-v1.6/python/python.exe tests/_render_palettes.py
输出：tests/_out/palettes.png（5 行 × 4 列）
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import (QPixmap, QPainter, QColor, QFont, QFontDatabase)
from PyQt6.QtCore import Qt

import petal_menu as pm

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT_DIR, exist_ok=True)

FILES = ["a.mp4", "b.png", "c.docx", "d.mp3", "e.zip", "f.iso"]
# 名字用 ASCII：offscreen 平台没有中文字体，中文会渲染成方块，无法判断排版
PETALS = [
    {"name": "PotPlayer", "program": "", "exts": [".mp4"]},
    {"name": "看图工具", "program": "", "exts": [".png"]},
    {"name": "Word", "program": "", "exts": [".docx"]},
    {"name": "音乐播放器", "program": "", "exts": [".mp3"]},
    {"name": "解压", "program": "", "exts": [".zip"]},
    {"name": "虚拟光驱", "program": "", "exts": [".iso"]},
]

app = QApplication.instance() or QApplication([])
# offscreen 平台默认找不到中文字体，手动把 Windows 的 msyh 装上，否则中文全是方块
for _p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(_p):
        print("font:", _p, QFontDatabase.addApplicationFont(_p))
FAM = "Microsoft YaHei UI"

ROW_H = 300
COL_W = 380
rows = list(pm.PALETTES.keys())
cols = list(pm.PETAL_SIZES.keys())

sheet = QPixmap(COL_W * len(cols) + 190, ROW_H * len(rows))
sheet.fill(QColor("#101014"))
sp = QPainter(sheet)
sp.setRenderHint(QPainter.RenderHint.Antialiasing)
sp.setPen(QColor("#9AA0A6"))
f = QFont(FAM, 10)
sp.setFont(f)

for ci, cname in enumerate(cols):
    sp.drawText(190 + ci * COL_W, 22, "%s (%d%%)" % (
        cname, int(round(pm.PETAL_SIZES[cname] * 100))))

for ri, rname in enumerate(rows):
    sp.drawText(12, ri * ROW_H + ROW_H // 2, pm.PALETTES[rname]["label"] + " " + rname)
    for ci, cname in enumerate(cols):
        m = pm.PetalMenu(FILES, PETALS, petal_count=0,
                         palette_name=rname, size_name=cname)
        m._scale = 1.0          # 跳过淡入动画，否则 grab 到的是 scale=0 的空图
        m.resize(m._size, m._size)
        m.show()
        app.processEvents()
        print(rname, cname, "petals=%d" % len(m.petals), "size=%d" % m._size)
        pm_img = m.grab()
        x = 190 + ci * COL_W + (COL_W - pm_img.width()) // 2
        y = ri * ROW_H + (ROW_H - pm_img.height()) // 2
        sp.drawPixmap(x, y, pm_img)
        m.close()
sp.end()

path = os.path.join(OUT_DIR, "palettes.png")
sheet.save(path)
print("saved:", path, sheet.width(), "x", sheet.height())
