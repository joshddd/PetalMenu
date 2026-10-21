# -*- coding: utf-8 -*-
"""非侵入检查：解包 exe 内嵌的 petal_menu 字节码，确认修复代码已打包
对比新旧 exe（dist\\PetalMenu.exe vs dist\\PetalMenu.exe.bak-*）
"""
import sys, os, glob, marshal, dis

HERE = sys.argv[1] if len(sys.argv) > 1 else r"C:\tmp\hotkey\dist"

log = lambda *a: print(*a, flush=True)

def get_code_objects(exe_path, module="petal_menu"):
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    arc = CArchiveReader(exe_path)
    pyz_name = next((n for n in arc.toc if n.endswith(".pyz")), None)
    if not pyz_name:
        return None, "找不到 PYZ"
    data = arc.extract(pyz_name)
    tmp = os.path.join(os.environ.get("TEMP", "."), "_chk_" + os.path.basename(exe_path) + ".pyz")
    with open(tmp, "wb") as f:
        f.write(data)
    z = ZlibArchiveReader(tmp)
    entry = z.toc.get(module)
    if not entry:
        return None, f"PYZ 里没有 {module}"
    code = z.extract(module)
    return code, None

def names_of(code):
    out = set()
    def walk(c):
        for n in getattr(c, "co_names", ()): out.add(n)
        for k in getattr(c, "co_consts", ()):
            if hasattr(k, "co_code"): walk(k)
    walk(code)
    return out

def top_funcs(code):
    out = []
    for k in code.co_consts:
        if hasattr(k, "co_name") and k.co_name != "<module>":
            out.append(k.co_name)
    return out

MARKERS = ["visible_petals", "_show_dialog", "_force_foreground",
           "_OPEN_DIALOGS", "EditPetalDialog", "SetCountDialog", "match_count"]

def inspect(path, module="petal_menu"):
    log(f"\n--- {os.path.basename(path)} ({os.path.getsize(path)//1024} KB) ---")
    code, err = get_code_objects(path, module)
    if err:
        log(f"  错误: {err}")
        return None
    n = names_of(code)
    fns = top_funcs(code)
    log(f"  顶层定义: {', '.join(fns)}")
    hit = [m for m in MARKERS if m in n or m in fns]
    log(f"  标记命中: {hit}")
    return set(hit)

log_path = os.path.join(HERE, "PetalMenu.exe")
log("=== 检查打包产物 ===")
new = inspect(log_path)
old = None
baks = sorted(glob.glob(os.path.join(HERE, "PetalMenu.exe.bak-*")))
if baks:
    old = inspect(baks[-1])

FAIL = []
if new is None:
    FAIL.append("新 exe 解析失败")
else:
    for m in ["visible_petals", "_show_dialog", "_force_foreground", "_OPEN_DIALOGS"]:
        ok = m in new
        print(f"  {'PASS' if ok else 'FAIL'} - 新 exe 含 {m}", flush=True)
        if not ok: FAIL.append(m)
    if old is not None:
        ok = "visible_petals" not in old
        print(f"  {'PASS' if ok else 'FAIL'} - 旧 exe 不含 visible_petals（对照组）", flush=True)

# main 模块里的 Everything 支持
mcode, merr = get_code_objects(log_path, "main")
if merr:
    FAIL.append("main 模块解析失败: " + merr)
    print(f"  FAIL - main 模块解析失败: {merr}", flush=True)
else:
    mn = names_of(mcode)
    mfn = top_funcs(mcode)
    print(f"  main 顶层定义: {', '.join(mfn)}", flush=True)
    for m in ["everything_selected_files", "detect_source", "_path_from_cells",
              "_RemoteLVText", "_find_child_class"]:
        ok = m in mn or m in mfn
        print(f"  {'PASS' if ok else 'FAIL'} - 新 exe 含 {m}", flush=True)
        if not ok: FAIL.append(m)

print("\n==== 汇总 ====")
print("打包产物已是修复版" if not FAIL else f"失败: {FAIL}", flush=True)
sys.exit(1 if FAIL else 0)
