# -*- coding: utf-8 -*-
"""把新增的文件类别/热键键合并进 config.yaml（项目模板 + APPDATA 实际配置）

默认值从 main.py 的 DEFAULT_EXTS / DEFAULT_HOTKEYS / CATEGORIES 里读，
保证只有一份真值。已有的 petals / petal_count / 用户填过的热键都保留。
"""
import ast
import os
import shutil
import sys

import yaml

PROJ_DIR = r"C:\tmp\hotkey"
PROJ_CFG = os.path.join(PROJ_DIR, "config.yaml")
APP_CFG = os.path.join(os.environ["APPDATA"], "PetalMenu", "config.yaml")

src = open(os.path.join(PROJ_DIR, "main.py"), encoding="utf-8").read()
found = {}
for node in ast.parse(src).body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id in ("DEFAULT_EXTS", "DEFAULT_HOTKEYS", "CATEGORIES"):
            found[node.targets[0].id] = ast.literal_eval(node.value)
EXTS = found["DEFAULT_EXTS"]
HK = found["DEFAULT_HOTKEYS"]
CATS = found["CATEGORIES"]

cur = yaml.safe_load(open(APP_CFG, encoding="utf-8")) or {}
print("现有 petals:", [(p.get("name"), p.get("program")) for p in cur.get("petals", [])])
print("现有 petal_count:", cur.get("petal_count"))

out = {}
hk = {}
for k, v in HK.items():
    hk[k] = str(cur.get("hotkeys", {}).get(k, v) or "")
out["hotkeys"] = hk
for key, label, ext_key in CATS:
    out[ext_key] = list(cur.get(ext_key) or EXTS[key])
progs = {}
for key, label, ext_key in CATS:
    progs[key] = str(cur.get("programs", {}).get(key, "") or "")
out["programs"] = progs
out["petal_count"] = cur.get("petal_count", 0)
out["petals"] = cur.get("petals", [])

text = yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=200)
print("\n---- 合并结果 ----\n" + text)

for path, name in ((PROJ_CFG, "项目模板"), (APP_CFG, "APPDATA")):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak-cat")
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    print("已写入 %s: %s" % (name, path))

# 回读校验
for path, name in ((PROJ_CFG, "项目模板"), (APP_CFG, "APPDATA")):
    chk = yaml.safe_load(open(path, encoding="utf-8"))
    ok = (len(chk["petals"]) == len(cur.get("petals", []))
          and all(len(chk[k]) > 0 for _a, _b, k in CATS)
          and set(chk["programs"]) == {k for k, _b, _c in CATS})
    print("%s 回读 %s" % (name, "OK" if ok else "FAIL"))
    if not ok:
        sys.exit(1)
