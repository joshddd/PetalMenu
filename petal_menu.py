# -*- coding: utf-8 -*-
"""
petal_menu.py - 花瓣菜单（PyQt6 自绘放射状菜单）

v3:
  * 右键中心 -> 设置花瓣数量：数量现在一定“看得见”。
    已配置的打开方式不够 N 个时，补「未配置」占位花瓣（灰底虚线），
    右键占位花瓣即可现场绑定一个程序（会写进 config.yaml 的 petals）。
  * v2 修复保留：数量对话框不能在自己的 popup 事件里 exec()，
    改为先关菜单、再延后非模态弹窗 + 强制前台聚焦。
  * petal_count 语义：先按扩展名过滤，再取前 N 个。
"""
import math
import os
import sys
import subprocess

from PyQt6.QtCore import Qt, QRectF, QVariantAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import (QColor, QPainter, QPainterPath, QFont, QCursor,
                         QFontMetrics, QPen)
from PyQt6.QtWidgets import (QWidget, QApplication, QDialog, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QSpinBox, QDialogButtonBox)

# ---------------- 可调参数 ----------------
R_INNER  = 32
R_OUTER  = 118
GAP_DEG  = 5
DURATION = 160
COLORS = [
    "#6FA8DC", "#93C47D", "#F6B26B", "#E06666",
    "#8E7CC3", "#FFD966", "#76A5AF", "#C27BA0",
]
PLACEHOLDER_NAME = "未配置"

# 非模态对话框必须有人引用，否则会被 Python GC 掉（窗口瞬间消失）
_OPEN_DIALOGS = set()


def _pt(deg, r):
    rad = math.radians(deg)
    return (r * math.cos(rad), -r * math.sin(rad))


def _sector_path(a0, a1, r_in, r_out, segs=24):
    path = QPainterPath()
    outer = [_pt(a0 + (a1 - a0) * i / segs, r_out) for i in range(segs + 1)]
    inner = [_pt(a0 + (a1 - a0) * i / segs, r_in) for i in range(segs + 1)]
    path.moveTo(*outer[0])
    for p in outer[1:]:
        path.lineTo(*p)
    for p in reversed(inner):
        path.lineTo(*p)
    path.closeSubpath()
    return path


def _notify(title, msg):
    try:
        import main as _m
        _m.notify(title, msg)
        return
    except Exception:
        pass
    import ctypes, threading
    def _show():
        try:
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40 | 0x1000)
        except Exception:
            pass
    threading.Thread(target=_show, daemon=True).start()


def _force_foreground(widget):
    """后台进程（热键唤起）在 Windows 上抢不到前台，会导致对话框收不到键盘。
    先按一下 Alt 解锁前台限制，再 SetForegroundWindow。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        hwnd = int(widget.winId())
        u.keybd_event(0x12, 0, 0, 0)      # Alt down
        u.SetForegroundWindow(hwnd)
        u.BringWindowToTop(hwnd)
        u.keybd_event(0x12, 0, 2, 0)      # Alt up
    except Exception:
        pass


def visible_petals(petals, files, petal_count=0):
    """先按扩展名过滤，再取前 N 个；petal_count<=0 表示全部。"""
    out = []
    for p in petals:
        exts = p.get("exts")
        entry = dict(p)
        if exts:
            exts = [str(e).lower() for e in exts]
            match = [f for f in files
                     if os.path.splitext(f)[1].lower() in exts]
            if not match:
                continue
            entry["_files"] = match
        else:
            entry["_files"] = list(files)
        out.append(entry)
    if petal_count and petal_count > 0:
        out = out[:petal_count]
    return out


def build_petals(petals, files, petal_count=0):
    """真实候选 + 数量不足时补「未配置」占位花瓣。

    这样「设置 3 个花瓣」在任何配置下都真的显示 3 个花瓣，
    多出来的占位花瓣右键就能绑定程序。
    """
    out = visible_petals(petals, files, petal_count)
    if not petal_count or petal_count <= 0:
        return out
    while len(out) < petal_count:
        out.append({
            "name": PLACEHOLDER_NAME,
            "program": "",
            "_files": list(files),
            "_placeholder": True,
        })
    return out


# ---------------------------------------------------------------- 对话框

class EditPetalDialog(QDialog):
    """右键花瓣：编辑程序路径（editable_name=True 时兼作“新建花瓣”）"""
    def __init__(self, name, program, parent=None,
                 editable_name=False, title=None):
        super().__init__(parent)
        self._editable = bool(editable_name)
        self.setWindowTitle(title or f"编辑花瓣：{name}")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        if self._editable:
            nrow = QHBoxLayout()
            nrow.addWidget(QLabel("花瓣名称："))
            self.name_edit = QLineEdit("" if name == PLACEHOLDER_NAME else name)
            self.name_edit.setPlaceholderText("例如 PotPlayer、Photoshop")
            nrow.addWidget(self.name_edit, 1)
            lay.addLayout(nrow)
        else:
            self.name_edit = None
            lay.addWidget(QLabel(f"花瓣名称：{name}"))

        row = QHBoxLayout()
        self.edit = QLineEdit(program)
        self.edit.setPlaceholderText("留空 = 系统默认打开；或填 exe 完整路径")
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse)
        row.addWidget(self.edit, 1)
        row.addWidget(btn_browse)
        lay.addLayout(row)

        hint = QLabel("提示：__explorer__ = 打开所在文件夹并选中；留空 = 系统默认程序")
        hint.setStyleSheet("color: gray;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择程序", "", "可执行文件 (*.exe);;所有文件 (*.*)")
        if path:
            self.edit.setText(path)

    def value(self):
        return self.edit.text().strip()

    def petal_name(self):
        if self.name_edit is None:
            return ""
        return self.name_edit.text().strip()


class SetCountDialog(QDialog):
    """右键中心：设置花瓣显示数量"""
    MAX_LIMIT = 32   # 允许设置的硬上限，与 petals 实际数量解耦

    def __init__(self, total, current, matched=None, parent=None):
        super().__init__(parent)
        self._total = total
        self._matched = total if matched is None else matched
        self.setWindowTitle("设置花瓣数量")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(440)

        lay = QVBoxLayout(self)
        tip = QLabel(f"配置里共有 {total} 个打开方式；当前选中文件可匹配 "
                     f"{self._matched} 个。")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        row = QHBoxLayout()
        row.addWidget(QLabel("显示数量："))
        self.spin = QSpinBox()
        self.spin.setRange(0, self.MAX_LIMIT)
        self.spin.setValue(int(current) if current else 0)
        self.spin.setSingleStep(1)
        self.spin.setAccelerated(True)
        self.spin.setKeyboardTracking(True)          # 手动输入即时响应
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.spin.setMinimumWidth(120)
        f = QFont("Microsoft YaHei UI", 14)
        f.setBold(True)
        self.spin.setFont(f)
        self.spin.valueChanged.connect(self._on_change)
        row.addWidget(self.spin)
        row.addWidget(QLabel("（0 = 全部）"))
        row.addStretch(1)
        lay.addLayout(row)

        # 快捷按钮：0 = 全部 / 全部匹配到的
        row2 = QHBoxLayout()
        b0 = QPushButton("全部（0）")
        b0.clicked.connect(lambda: self.spin.setValue(0))
        bm = QPushButton(f"匹配到的全部（{self._matched}）")
        bm.clicked.connect(lambda: self.spin.setValue(self._matched))
        row2.addWidget(b0)
        row2.addWidget(bm)
        row2.addStretch(1)
        lay.addLayout(row2)

        self.hint = QLabel()
        self.hint.setStyleSheet("color: gray;")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._on_change(self.spin.value())
        # 直接打开时焦点就在输入框，键盘输入立即生效
        self.spin.setFocus()
        self.spin.selectAll()
        QTimer.singleShot(50, self.spin.setFocus)
        QTimer.singleShot(50, self.spin.selectAll)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            return
        super().keyPressEvent(event)

    def _on_change(self, v):
        if v == 0:
            self.hint.setText(f"0 = 显示当前文件类型能匹配的全部 {self._matched} 个花瓣。")
        elif v > self._matched:
            extra = v - self._matched
            self.hint.setText(
                f"只有 {self._matched} 个打开方式能用于这种文件，"
                f"多出的 {extra} 个花瓣会显示为「{PLACEHOLDER_NAME}」，"
                f"右键它即可绑定程序。")
        else:
            self.hint.setText(f"保存后菜单显示前 {v} 个花瓣。")

    def value(self):
        self.spin.interpretText()      # 正在输入但还没提交的数字也算
        return self.spin.value()


# ---------------------------------------------------------------- 主控件

class PetalMenu(QWidget):
    def __init__(self, files, petals, petal_count=0, parent=None):
        super().__init__(parent)
        self.files = list(files)
        self._scale = 0.0
        self.hover = -1
        self._center_hover = False             # 光标是不是停在中心（决定中心画提示还是图标）
        self._all_petals_cfg = petals          # 原始配置（用于回写）
        self._petal_count = petal_count or 0

        # 先按 exts 过滤再取前 N 个，不足则补占位花瓣
        self.petals = build_petals(petals, self.files, self._petal_count)

        self._size = 2 * (R_OUTER + 36)
        self.setFixedSize(self._size, self._size)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(DURATION)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_frame)

    # ---------------- 公共接口 ----------------
    def show_at_cursor(self):
        if not self.petals:
            _notify("PetalMenu", "当前文件类型没有可用的打开方式，请在 config.yaml 中配置 petals")
            return False
        pos = QCursor.pos()
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(max(pos.x() - self._size // 2, geo.left()), geo.right() - self._size)
        y = min(max(pos.y() - self._size // 2, geo.top()), geo.bottom() - self._size)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        _force_foreground(self)
        self._anim.start()
        return True

    # ---------------- 内部 ----------------
    def _on_frame(self, v):
        self._scale = float(v)
        self.update()

    def _petal_at(self, pos):
        c = self._size / 2
        dx, dy = pos.x() - c, pos.y() - c
        scale = self._scale if self._scale > 0.001 else 1.0
        r = math.hypot(dx, dy) / scale
        if not (R_INNER < r < R_OUTER):
            return -1
        if not self.petals:
            return -1
        deg = math.degrees(math.atan2(-dy, dx)) % 360
        return int(deg // (360.0 / len(self.petals)))

    def _in_center(self, pos):
        c = self._size / 2
        dx, dy = pos.x() - c, pos.y() - c
        scale = self._scale if self._scale > 0.001 else 1.0
        r = math.hypot(dx, dy) / scale
        return r <= R_INNER

    def _open_folder(self):
        """左键点中心：在资源管理器里打开文件所在目录（多选时取第一个）"""
        files = self.files or []
        if not files:
            _notify("PetalMenu", "没有可定位的文件")
            return False
        target = files[0]
        folder = os.path.dirname(target)
        try:
            if os.path.exists(target):
                # /select 会把目录打开并同时选中该文件。
                # explorer 自己解析命令行，路径带空格时整条必须是一个字符串并加引号，
                # 拆成 ["explorer", "/select,", path] 在带空格的路径上会被截断。
                subprocess.Popen('explorer /select,"%s"' % target.replace('"', ""))
            elif folder and os.path.isdir(folder):
                subprocess.Popen('explorer "%s"' % folder.replace('"', ""))
            else:
                _notify("PetalMenu", f"目录不存在：{folder or target}")
                return False
        except Exception as e:
            _notify("PetalMenu", f"打开目录失败：{e}")
            return False
        return True

    def _launch(self, petal):
        if petal.get("_placeholder"):
            _notify("PetalMenu",
                    f"这个花瓣还没配置程序：右键它选一个程序即可")
            return
        program = petal.get("program", "") or ""
        files = petal.get("_files") or self.files
        try:
            if program == "__explorer__":
                subprocess.Popen('explorer /select,"%s"' % files[0].replace('"', ""))
            elif program:
                if os.path.exists(program):
                    subprocess.Popen([program] + files)
                else:
                    _notify("PetalMenu", f"程序不存在：{program}")
            else:
                for f in files:
                    os.startfile(f)
        except Exception as e:
            _notify("PetalMenu", f"打开失败：{e}")

    # ---------------- 对话框统一入口 ----------------
    def _open_dialog(self, factory):
        """popup 菜单不能在自己的鼠标事件里直接 close()/exec() 对话框：
        popup 的原生鼠标抓取和"关闭时的收尾"会把对话框的输入吞掉或直接搞死
        （表现为窗口弹出但点不动数字）。所以分三步、全部推迟到事件处理结束之后：
           1. 等这次点击（含 mouseRelease）走完
           2. 关掉 popup
           3. 再用非模态窗口弹出对话框
        """
        def _close_menu():
            self.close()
            QTimer.singleShot(0, lambda: self._show_dialog(factory))
        QTimer.singleShot(0, _close_menu)

    @staticmethod
    def _show_dialog(factory):
        dlg = factory()
        dlg.setParent(None)
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dlg.setModal(False)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        _OPEN_DIALOGS.add(dlg)
        dlg.finished.connect(lambda code: _OPEN_DIALOGS.discard(dlg))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        _force_foreground(dlg)
        w = dlg.focusWidget()
        if w is not None:
            w.setFocus()

    # ---------------- 右键：编辑花瓣 ----------------
    def _edit_petal(self, petal):
        import main as m
        name = petal["name"]
        program = petal.get("program", "") or ""
        exts = petal.get("exts")

        def factory():
            dlg = EditPetalDialog(name, program)
            def _done(code):
                if int(code) != int(QDialog.DialogCode.Accepted):
                    return
                new_prog = (dlg.value() or "").strip()
                # 关键：以「实时的」CONFIG["petals"] 为准来定位条目。
                # 菜单里缓存的 _all_petals_cfg 可能在 load_config() 之后
                # 变成孤儿列表，改了也写不进文件（表现为重启后还原）。
                target = None
                found_in_live = False
                for lst in (m.CONFIG.get("petals") or [], self._all_petals_cfg):
                    for cfg in lst:
                        if cfg.get("name") == name and cfg.get("exts") == exts:
                            target = cfg
                            found_in_live = lst is not self._all_petals_cfg
                            break
                    if target is None:
                        for cfg in lst:
                            if cfg.get("name") == name:
                                target = cfg
                                found_in_live = lst is not self._all_petals_cfg
                                break
                    if target is not None:
                        break
                if target is None:
                    entry = {"name": name, "program": new_prog}
                    if exts:
                        entry["exts"] = list(exts)
                    m.CONFIG.setdefault("petals", []).append(entry)
                    target = entry
                else:
                    target["program"] = new_prog
                # 菜单自己那份副本也同步，界面立刻一致
                for old in self._all_petals_cfg:
                    if old.get("name") == name:
                        old["program"] = new_prog
                        break
                ok = m.save_config()
                if hasattr(m, "_dbg"):
                    m._dbg("edit_petal: name=%r exts=%r new=%r live=%s save=%s"
                           % (name, exts, new_prog, found_in_live, ok))
                if ok:
                    m.load_config()
                    if hasattr(m, "reshow_menu"):
                        m.reshow_menu()
                    _notify("PetalMenu", f"已保存花瓣「{name}」的程序路径")
                else:
                    _notify("PetalMenu",
                            f"「{name}」保存失败，请检查配置文件是否可写")
            dlg.finished.connect(_done)
            return dlg
        self._open_dialog(factory)

    # ---------------- 右键：给占位花瓣绑定程序 ----------------
    def _add_petal(self):
        import main as m
        ext = os.path.splitext(self.files[0])[1].lower() if self.files else ""

        def factory():
            dlg = EditPetalDialog(PLACEHOLDER_NAME, "", editable_name=True,
                                  title="新建花瓣：绑定一个打开方式")
            def _done(code):
                if int(code) != int(QDialog.DialogCode.Accepted):
                    return
                prog = dlg.value()
                nm = dlg.petal_name()
                if not nm:
                    nm = (os.path.splitext(os.path.basename(prog))[0]
                          if prog else "新花瓣")
                entry = {"name": nm, "program": prog}
                if ext:
                    entry["exts"] = [ext]
                m.CONFIG.setdefault("petals", []).append(entry)
                if m.save_config():
                    m.load_config()
                    if hasattr(m, "reshow_menu"):
                        m.reshow_menu()
                    _notify("PetalMenu", f"已新增花瓣「{nm}」")
            dlg.finished.connect(_done)
            return dlg
        self._open_dialog(factory)

    # ---------------- 右键：设置花瓣数量 ----------------
    def _edit_count(self):
        import main as m
        petals_cfg = m.CONFIG.get("petals") or self._all_petals_cfg
        total = len(petals_cfg)
        cur = int(m.CONFIG.get("petal_count", 0) or 0)
        matched = len(visible_petals(petals_cfg, self.files, 0))

        def factory():
            dlg = SetCountDialog(total, cur, matched)
            def _done(code):
                if int(code) != int(QDialog.DialogCode.Accepted):
                    return
                val = dlg.value()
                m.CONFIG["petal_count"] = val
                if m.save_config():
                    if hasattr(m, "reshow_menu"):
                        m.reshow_menu()
                    shown = val if val > 0 else matched
                    _notify("PetalMenu",
                            f"花瓣数量已保存：{val if val > 0 else '全部'}"
                            f"（当前显示 {shown} 个）")
            dlg.finished.connect(_done)
            return dlg
        self._open_dialog(factory)

    # ---------------- 事件 ----------------
    def mouseMoveEvent(self, event):
        pos = event.position()
        idx = self._petal_at(pos)
        in_center = idx < 0 and self._in_center(pos)
        if idx != self.hover or in_center != self._center_hover:
            self.hover = idx
            self._center_hover = in_center
            self.update()
            self.setCursor(Qt.CursorShape.PointingHandCursor
                           if (idx >= 0 or in_center) else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if self._scale < 0.9:
            return
        pos = event.position()
        if event.button() == Qt.MouseButton.RightButton:
            # 右键中心 -> 设置数量
            if self._in_center(pos):
                self._edit_count()
                return
            # 右键花瓣 -> 编辑程序 / 占位花瓣 -> 新建
            idx = self._petal_at(pos)
            if 0 <= idx < len(self.petals):
                if self.petals[idx].get("_placeholder"):
                    self._add_petal()
                else:
                    self._edit_petal(self.petals[idx])
                return
            self.close()
            return
        # 左键
        if event.button() == Qt.MouseButton.LeftButton:
            # 左键中心 -> 在资源管理器里打开文件所在目录
            if self._in_center(pos):
                self._open_folder()
                self.close()
                return
            idx = self._petal_at(pos)
            if 0 <= idx < len(self.petals):
                self._launch(self.petals[idx])
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def paintEvent(self, event):
        if not self.petals or self._scale <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self._size / 2, self._size / 2)
        painter.scale(self._scale, self._scale)

        n = len(self.petals)
        span = 360.0 / n

        for i, petal in enumerate(self.petals):
            a0 = i * span + GAP_DEG / 2
            a1 = (i + 1) * span - GAP_DEG / 2
            ph = bool(petal.get("_placeholder"))
            path = _sector_path(a0, a1, R_INNER, R_OUTER)
            if ph:
                pen = QPen(QColor(210, 210, 220, 110))
                pen.setWidth(2)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(QColor(70, 70, 80, 120))
            else:
                color = QColor(COLORS[i % len(COLORS)])
                if i == self.hover:
                    color = color.lighter(130)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
            painter.drawPath(path)

            mid = (a0 + a1) / 2
            tx, ty = _pt(mid, (R_INNER + R_OUTER) / 2)
            painter.save()
            painter.translate(tx, ty)
            painter.rotate(-mid)
            painter.setPen(QColor("white") if not ph else QColor(220, 220, 230))
            font = QFont("Microsoft YaHei UI", 11)
            font.setBold(True)
            painter.setFont(font)
            text = ("＋" + PLACEHOLDER_NAME) if ph else petal["name"]
            painter.drawText(QRectF(-72, -14, 144, 28),
                             int(Qt.AlignmentFlag.AlignCenter), text)
            painter.restore()

        # 中心圆
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(35, 35, 40, 235))
        cr = R_INNER - 4
        painter.drawEllipse(QRectF(-cr, -cr, 2 * cr, 2 * cr))

        # 中心提示：hover 花瓣名 / 中心可点（打开所在目录）
        if 0 <= self.hover < len(self.petals):
            self._draw_center_text(painter, self.petals[self.hover]["name"], cr)
        elif self._center_hover:
            self._draw_folder_glyph(painter, cr)
        else:
            self._draw_center_text(painter, "打开方式", cr)

    def _draw_center_text(self, painter, name, cr):
        font = QFont("Microsoft YaHei UI", 10)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text = fm.elidedText(name, Qt.TextElideMode.ElideRight, int(2 * cr - 8))
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(-cr, -cr, 2 * cr, 2 * cr),
                         int(Qt.AlignmentFlag.AlignCenter), text)

    def _draw_folder_glyph(self, painter, cr):
        """光标进中心时画个文件夹图标：左键 = 在资源管理器里打开所在目录"""
        pen = QPen(QColor(255, 205, 110))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 205, 110, 70))
        w = cr * 1.25
        h = cr * 0.92
        tab_w = w * 0.44
        tab_h = h * 0.26
        painter.drawRoundedRect(
            QRectF(-w / 2, -h / 2 - tab_h * 0.55, tab_w, tab_h), 3, 3)
        painter.drawRoundedRect(QRectF(-w / 2, -h / 2, w, h), 4, 4)
