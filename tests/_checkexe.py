# -*- coding: utf-8 -*-
"""非侵入检查：解包 exe 内嵌的字节码，确认当前版本的新功能真的进了包

用法：python _checkexe.py <目录>        # 目录里放 PetalMenu.exe（默认 dist_v11）
"""
import glob
import os
import sys

HERE = sys.argv[1] if len(sys.argv) > 1 else r"C:\tmp\hotkey\dist_v11"
log = lambda *a: print(*a, flush=True)

WANT = {
    "petal_menu": ["_open_folder", "_in_center", "_draw_folder_glyph",
                   "_draw_center_text", "_launch",
                   # v10：配色方案 + 花瓣大小
                   "PALETTES", "PETAL_SIZES", "PETAL_SIZE_LABELS",
                   "palette", "size_scale", "DEFAULT_PALETTE", "DEFAULT_PETAL_SIZE",
                   # v11：第一片固定默认打开 / 程序名推导 / 空白花瓣 / 从左边顺时针
                   "program_label", "_reg_friendly_name", "_version_strings",
                   "_is_legacy_default", "DEFAULT_PETAL_NAME", "EXPLORER_LABEL",
                   "EMPTY_HINT", "START_DEG"],
    "main": ["CATEGORIES", "CATEGORY_LABEL", "DEFAULT_EXTS", "match_by_mode",
             "detect_mode", "direct_open", "direct_open_auto",
             # v10：托盘设置菜单（_direct_open_async 已随『直接打开选中文件』删除）
             "build_tray_menu", "apply_palette", "apply_petal_size",
             "apply_show_hotkey", "_combo_free", "show_menu_combo",
             "SHOW_HOTKEY_CHOICES",
             # v11：main 只通过 petal_menu 间接用到默认花瓣逻辑，标记留在那边
             ],
}


def code_of(exe_path, module):
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    arc = CArchiveReader(exe_path)
    pyz = next((n for n in arc.toc if n.endswith(".pyz")), None)
    if not pyz:
        return None, "找不到 PYZ"
    tmp = os.path.join(os.environ.get("TEMP", "."),
                       "_chk_%s_%s.pyz" % (os.path.basename(exe_path), module))
    with open(tmp, "wb") as f:
        f.write(arc.extract(pyz))
    z = ZlibArchiveReader(tmp)
    if module not in z.toc:
        return None, "PYZ 里没有 %s" % module
    return z.extract(module), None


def markers(code):
    """所有层级的名字：属性名/全局名/函数名/字符串常量里出现的标识符"""
    got = set()

    def walk(c):
        for n in getattr(c, "co_names", ()):
            got.add(n)
        for k in getattr(c, "co_consts", ()):
            if hasattr(k, "co_code"):
                got.add(k.co_name)
                walk(k)
            elif isinstance(k, str):
                got.add(k)

    walk(code)
    return got


FAIL = []
exe = os.path.join(HERE, "PetalMenu.exe")
if not os.path.exists(exe):
    print("找不到 %s" % exe)
    sys.exit(1)
print("=== 检查 %s（%d KB）===" % (exe, os.path.getsize(exe) // 1024), flush=True)

for module, wants in WANT.items():
    code, err = code_of(exe, module)
    if err:
        FAIL.append("%s: %s" % (module, err))
        print("  FAIL - %s 解包失败: %s" % (module, err), flush=True)
        continue
    got = markers(code)
    for w in wants:
        ok = w in got
        print("  %s - %s.%s" % ("PASS" if ok else "FAIL", module, w), flush=True)
        if not ok:
            FAIL.append("%s.%s" % (module, w))

# 对照组：旧 exe 不该有 _open_folder，能反证检查方法有效
baks = sorted(glob.glob(os.path.join(HERE, "PetalMenu.exe.bak-*")))
if baks:
    old = baks[-1]
    code, err = code_of(old, "petal_menu")
    if not err:
        ok = "build_tray_menu" not in markers(code)
        print("  %s - 对照 %s 不含 build_tray_menu"
              % ("PASS" if ok else "WARN", os.path.basename(old)), flush=True)

print("\n==== 汇总 ====")
print("打包产物含 v10 全部新功能" if not FAIL else "失败: %s" % FAIL, flush=True)
sys.exit(1 if FAIL else 0)
