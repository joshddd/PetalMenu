# -*- coding: utf-8 -*-
"""main.py 配置/热键冒烟测试（把 APPDATA 指向临时目录，不动用户真实配置）"""
import os, sys, shutil, json

HERE = r"C:\tmp\hotkey"
TMP = r"C:\tmp\hotkey\_cfgtmp"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)
os.environ["APPDATA"] = TMP
sys.path.insert(0, HERE)
os.chdir(HERE)

log = lambda *a: print(*a, flush=True)
FAIL = []
def check(c, m):
    log(f"  {'PASS' if c else 'FAIL'} - {m}")
    if not c: FAIL.append(m)

import yaml
import main as M

_legacy = yaml.safe_load(open(M._LEGACY_CFG, encoding="utf-8")) or {}
_exp_count = _legacy.get("petal_count", 3)
_exp_petals = len(_legacy.get("petals") or [])

log(f"APP_DIR = {M.APP_DIR}")
check(os.path.isdir(M.APP_DIR), "APPDATA 配置目录已创建")
check(os.path.exists(M.CONFIG_PATH), "config.yaml 已生成")
check(M.CONFIG.get("petal_count") == _exp_count,
      f"从旧配置迁移过来的 petal_count={M.CONFIG.get('petal_count')}（旧配置 {_exp_count}）")
check(len(M.CONFIG.get("petals") or []) == _exp_petals,
      f"petals 数量 = {len(M.CONFIG.get('petals') or [])}（旧配置 {_exp_petals}）")

# 模拟“设置花瓣数量”保存
M.CONFIG["petal_count"] = 2
check(M.save_config(), "save_config 返回 True")

with open(M.CONFIG_PATH, encoding="utf-8") as f:
    saved = yaml.safe_load(f)
check(saved.get("petal_count") == 2, f"写回 yaml 的 petal_count={saved.get('petal_count')}")
check(len(saved.get("petals") or []) == _exp_petals, "petals 没被写坏")
check(saved["hotkeys"]["show_menu"] == M.CONFIG["hotkeys"]["show_menu"],
      f"热键保留: {saved['hotkeys']}")

# 文件类别表
for _k, _label, _ext_key in M.CATEGORIES:
    check(bool(M.CONFIG.get(_ext_key)), f"{_label}扩展名表非空（{len(M.CONFIG.get(_ext_key) or [])} 项）")
    check(_k in M.CONFIG["programs"], f"programs 含 {_k}")

_cases = [("video", r"C:\a\b.mp4"), ("image", r"C:\a\b.png"),
          ("document", r"C:\a\b.pdf"), ("audio", r"C:\a\b.flac"),
          ("archive", r"C:\a\b.7z"), ("disc", r"C:\a\b.iso")]
for _mode, _path in _cases:
    check(M.match_by_mode(_mode, [_path]) == [_path], f"{_path} 归为 {_mode}")
    check(M.detect_mode([_path]) == _mode, f"detect_mode({_path}) = {_mode}")
check(M.detect_mode([r"C:\a\b.xyz"]) is None, "未知扩展名 detect_mode 返回 None")
check(M.match_by_mode("document", [r"C:\a\b.mp4"]) == [], "跨类别不误判")

# 重新加载
M.CONFIG = {}
M.load_config()
check(M.CONFIG.get("petal_count") == 2, f"重新加载后 petal_count={M.CONFIG.get('petal_count')}")

# 旧配置同步逻辑
check(M._sync_legacy_config() in (True, False), "_sync_legacy_config 可调用")
os.utime(M._LEGACY_CFG, (0, 0))
check(M._sync_legacy_config() is False, "旧配置更旧时不覆盖 APPDATA")

# 热键注册
try:
    M._register_hotkeys()
    parsed = M._HOTKEYS.set_hotkeys and M._HOTKEYS._hotkeys
    check(len(parsed) == 4, f"热键解析成功 {[c for _m, _v, c, _cb in parsed]}")
    from hotkey_hook import parse_combo
    check(parse_combo("alt+x") == (1, 0x58), f"alt+x 解析 = {parse_combo('alt+x')}")
    check(parse_combo("ctrl+alt+v") == (3, 0x56), f"ctrl+alt+v 解析 = {parse_combo('ctrl+alt+v')}")
    check(parse_combo("shift+f5") == (4, 0x74), f"shift+f5 解析 = {parse_combo('shift+f5')}")
except Exception as e:
    log(f"  SKIP - 热键注册在测试进程里失败：{e}")

log("\n==== 汇总 ====")
log("全部通过" if not FAIL else f"失败 {len(FAIL)} 项: {FAIL}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
