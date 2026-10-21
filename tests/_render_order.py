# -*- coding: utf-8 -*-
"""渲染 v11 的花瓣顺序/命名：默认打开 + 程序名 + 空白花瓣，肉眼看一眼。

跑法：/mnt/d/ComfyUI-aki-v1.6/python/python.exe tests/_render_order.py
输出：tests/_out/order.png
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QFontDatabase

import petal_menu as pm

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT_DIR, exist_ok=True)

app = QApplication.instance() or QApplication([])
for _p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(_p):
        QFontDatabase.addApplicationFont(_p)

FILES = ["a.mp4"]
POTPLAYER = r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe"
MPV = r"M:\software\mpv-v0.41.0-dev-gfffe7a23a-39086651352-x86_64-w64-mingw32-full\mpv.exe"

CASES = [
    ("3 片：默认打开 + PotPlayer + 空位", [
        {"name": "PotPlayer", "program": POTPLAYER},
    ], 3),
    ("4 片：默认打开 + PotPlayer + mpv + 打开所在目录", [
        {"name": "PotPlayer", "program": POTPLAYER},
        {"name": "mpv", "program": MPV},
        {"name": "所在文件夹", "program": "__explorer__"},
    ], 4),
    ("5 片：夹一个没配程序的空白花瓣", [
        {"name": "PotPlayer", "program": POTPLAYER},
        {"name": "空白", "program": ""},
        {"name": "mpv", "program": MPV},
        {"name": "所在文件夹", "program": "__explorer__"},
    ], 5),
    ("6 片：xlarge 大小", [
        {"name": "PotPlayer", "program": POTPLAYER},
        {"name": "mpv", "program": MPV},
        {"name": "所在文件夹", "program": "__explorer__"},
        {"name": "空白A", "program": ""},
        {"name": "空白B", "program": ""},
    ], 6),
]

COL_W, ROW_H = 620, 560
sheet = QPixmap(COL_W * 2, ROW_H * 2)
sheet.fill(QColor("#101014"))
sp = QPainter(sheet)
sp.setRenderHint(QPainter.RenderHint.Antialiasing)
sp.setFont(QFont("Microsoft YaHei UI", 10))
sp.setPen(QColor("#B8BEC6"))

for i, (title, cfg, count) in enumerate(CASES):
    cx, cy = (i % 2) * COL_W, (i // 2) * ROW_H
    size = "xlarge" if "xlarge" in title else "normal"
    m = pm.PetalMenu(FILES, cfg, petal_count=count, palette_name="classic",
                     size_name=size)
    m._scale = 1.0
    m.resize(m._size, m._size)
    m.show()
    app.processEvents()
    labels = [p.get("_label") or "(空白)" for p in m.petals]
    print(i, labels)
    sp.drawText(cx + 12, cy + 22, title)
    sp.drawText(cx + 12, cy + 42, " -> ".join(labels))
    img = m.grab()
    sp.drawPixmap(cx + (COL_W - img.width()) // 2, cy + 60, img)
    m.close()
sp.end()

path = os.path.join(OUT_DIR, "order.png")
sheet.save(path)
print("saved:", path, sheet.width(), "x", sheet.height())
