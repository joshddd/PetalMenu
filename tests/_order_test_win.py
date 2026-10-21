# -*- coding: utf-8 -*-
"""花瓣顺序 / 命名 / 空白花瓣行为测试（v11）。

跑法：/mnt/d/ComfyUI-aki-v1.6/python/python.exe tests/_order_test_win.py

验证：
1. 第一片固定「默认打开」，走系统默认程序，配置里同名条目的 program 被忽略
2. 第二片起显示名只认 program：系统注册名 > 版本信息 > 文件名
3. 没配程序的花瓣留白，点击只关菜单
4. 花瓣从左边（9 点钟）顺时针排：左→上→右→下
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="pm_order_")
os.environ["APPDATA"] = TMP
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication

import petal_menu as pm

app = QApplication.instance() or QApplication(sys.argv)

FAILED = []
PASSED = []


def check(name, cond, extra=""):
    if cond:
        PASSED.append(name)
        print("  ok   %s" % name)
    else:
        FAILED.append(name + ((" | " + str(extra)) if extra else ""))
        print("  FAIL %s %s" % (name, extra))


POTPLAYER = r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe"
EXPLORER_PETAL = {"name": "所在文件夹", "program": "__explorer__"}
LEGACY = {"name": "默认打开", "program": r"C:\Program Files\VideoLAN\VLC\vlc.exe"}

print("== 第一片：默认打开 ==")
# 配置里那条老「默认打开」带的是 VLC 程序：现在它只是一片普通花瓣，按程序名显示
petals = pm.build_petals([LEGACY, {"name": "PotPlayer", "program": POTPLAYER},
                          EXPLORER_PETAL], ["a.mp4"], 4)
check("总数 = petal_count(4)", len(petals) == 4, len(petals))
check("第一片是默认打开", petals[0]["name"] == pm.DEFAULT_PETAL_NAME, petals[0])
check("第一片 program 为空（走系统默认）", petals[0]["program"] == "", petals[0])
check("第一片带 _default 标记", petals[0].get("_default") is True)
check("第一片显示名 = 默认打开", petals[0].get("_label") == "默认打开", petals[0].get("_label"))
check("第一片的 program 不是配置里那条 VLC",
      petals[0]["program"] != LEGACY["program"], petals[0]["program"])
check("旧「默认打开」条目降级成普通花瓣（按程序名显示 VLC）",
      petals[1]["program"] == LEGACY["program"]
      and petals[1]["_label"].lower().startswith("vlc")
      and petals[1]["_label"] != "默认打开", petals[1])
print("       legacy -> %r" % petals[1].get("_label"))
check("第三片是 PotPlayer", "PotPlayer" in (petals[2].get("_label") or ""),
      petals[2].get("_label"))
check("第四片是所在文件夹", petals[3].get("_label") == "打开所在目录",
      petals[3].get("_label"))
# 名字叫默认打开但没程序的旧条目应被丢掉（否则第一片旁边多一个空白重复）
_dropped = pm.build_petals([{"name": "默认打开", "program": ""},
                            {"name": "P", "program": POTPLAYER}], ["a.mp4"], 2)
check("空的旧「默认打开」条目被丢掉", len(_dropped) == 2
      and _dropped[1].get("_label", "").startswith("Pot"), _dropped)

print("\n== 显示名推导 ==")
lab = pm.program_label(POTPLAYER)
check("存在的 exe 有派生名", bool(lab), lab)
check("派生名不是裸 exe 文件名带后缀", not lab.lower().endswith(".exe"), lab)
print("       PotPlayer -> %r" % lab)
sys32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "notepad.exe")
check("notepad 派生名非空", bool(pm.program_label(sys32)), pm.program_label(sys32))
print("       notepad   -> %r" % pm.program_label(sys32))
check("不存在的 exe -> 文件名（去扩展名）",
      pm.program_label(r"C:\no\such\dir\MyPlayer.exe") == "MyPlayer",
      pm.program_label(r"C:\no\such\dir\MyPlayer.exe"))
check("__explorer__ -> 打开所在目录",
      pm.program_label("__explorer__") == "打开所在目录", pm.program_label("__explorer__"))
check("空 program -> 空字符串", pm.program_label("") == "")
check("带空格的 program 能容错", pm.program_label("  ") == "")
check("program_label 有缓存（同参数同结果）",
      pm.program_label(POTPLAYER) is pm.program_label(POTPLAYER)
      or pm.program_label(POTPLAYER) == pm.program_label(POTPLAYER))

print("\n== 空白花瓣 ==")
petals = pm.build_petals([{"name": "A", "program": ""},
                          {"name": "B", "program": ""}], ["a.mp4"], 4)
check("count=4 有 4 片", len(petals) == 4, len(petals))
check("没配程序的花瓣 _label 为空", petals[1].get("_label") == "", petals[1])
check("没配程序的花瓣带 _blank", petals[1].get("_blank") is True)
check("空位补出来的花瓣也留白",
      all((p.get("_label") or "") == "" for p in petals[2:]), petals[2:])
check("空位保留 _placeholder（右键可绑定）", petals[-1].get("_placeholder") is True,
      petals[-1])

print("\n== 绘制：空白花瓣不写文字 ==")
drawn = []
real_painter = pm.QPainter


class RecordingPainter(real_painter):
    def drawText(self, *args, **kwargs):
        try:
            drawn.append(args[-1] if isinstance(args[-1], str) else None)
        except Exception:
            drawn.append(None)
        return super().drawText(*args, **kwargs)


pm.QPainter = RecordingPainter
try:
    m = pm.PetalMenu(["a.mp4"], [LEGACY, {"name": "P", "program": POTPLAYER}], 3)
    m._scale = 1.0
    m.grab()
    texts = [t for t in drawn if t]
    check("画出来「默认打开」", "默认打开" in texts, texts)
    check("画出来 PotPlayer 的派生名", any("Pot" in (t or "") for t in texts), texts)
    check("没有画出旧版「＋未配置」文案",
          not any((t or "").startswith("＋") for t in texts), texts)
finally:
    pm.QPainter = real_painter

print("\n== 从左边开始顺时针：命中分区 ==")
m = pm.PetalMenu(["a.mp4"], [], 4)          # 1 个默认 + 3 个空位 = 4 片
m._scale = 1.0
r = (m.r_in + m.r_out) / 2.0
c = m._size / 2.0


def hit(dx, dy):
    return m._petal_at(QPointF(c + dx * r, c + dy * r))


check("左边 -> 第 1 片（默认打开）", hit(-1, 0) == 0, hit(-1, 0))
check("上方 -> 第 2 片", hit(0, -1) == 1, hit(0, -1))
check("右方 -> 第 3 片", hit(1, 0) == 2, hit(1, 0))
check("下方 -> 第 4 片", hit(0, 1) == 3, hit(0, 1))
check("左上 -> 仍是第 1 片", hit(-0.7, -0.7) == 0, hit(-0.7, -0.7))
check("右上方（第 1 片起点逆时针方向）不是第 1 片", hit(0.7, -0.7) == 1, hit(0.7, -0.7))

print("\n== 左键点击 ==")
launched = []
orig_launch = pm.PetalMenu._launch
pm.PetalMenu._launch = lambda self, petal: launched.append(petal.get("_label"))
try:
    m = pm.PetalMenu(["a.mp4"], [{"name": "P", "program": POTPLAYER}], 3)
    m._scale = 1.0
    m.show()

    def click(dx, dy):
        pos = QPointF(c + dx * r, c + dy * r)
        gpos = QPointF(m.mapToGlobal(pos.toPoint()))
        ev = QMouseEvent(QEvent.Type.MouseButtonPress, pos, gpos,
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        m.mousePressEvent(ev)

    click(0, 1)          # 第 4 片：空位
    check("点空白花瓣不启动任何程序", launched == [], launched)
    check("点空白花瓣把菜单关了", not m.isVisible())

    m = pm.PetalMenu(["a.mp4"], [{"name": "P", "program": POTPLAYER}], 3)
    m._scale = 1.0
    m.show()
    click(-1, 0)         # 第 1 片：默认打开
    check("点第一片走系统默认程序", launched == ["默认打开"], launched)
finally:
    pm.PetalMenu._launch = orig_launch

print("\n== 右键第一片不改程序 ==")
notes = []
orig_notify = pm._notify
pm._notify = lambda t, msg: notes.append(msg)
try:
    m = pm.PetalMenu(["a.mp4"], [], 3)
    m._scale = 1.0
    pos = QPointF(c - r, c)
    gpos = QPointF(m.mapToGlobal(pos.toPoint()))
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, pos, gpos,
                     Qt.MouseButton.RightButton, Qt.MouseButton.RightButton,
                     Qt.KeyboardModifier.NoModifier)
    m.mousePressEvent(ev)
    check("右键第一片给出提示", any("第一片" in n for n in notes), notes)
finally:
    pm._notify = orig_notify

out = TMP + os.sep + "order_test.log"
with open(out, "w", encoding="utf-8") as fh:
    fh.write("passed=%d failed=%d\n" % (len(PASSED), len(FAILED)))
    for f in FAILED:
        fh.write("FAILED: " + f + "\n")
    fh.write("PotPlayer label: %r\nnotepad label: %r\n"
             % (pm.program_label(POTPLAYER),
                pm.program_label(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                              "System32", "notepad.exe"))))
print("\n%d passed, %d failed" % (len(PASSED), len(FAILED)))
print("log:", out)
for f in FAILED:
    print("  FAILED:", f)
sys.exit(0 if not FAILED else 1)
