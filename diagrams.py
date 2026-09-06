#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""課程配圖：主題 → 候選圖，以及 claude 選圖結果的驗證與剝除。

圖庫是 vendored 的 hello-algo 繁中圖（assets/hello-algo/），CC BY-NC-SA 4.0。
貫穿全檔的原則：圖是加分項，任何圖片相關的失敗都不得阻擋信件寄出 ——
撈不到就當沒圖，驗不過就整批剝掉，信照常走。
"""
import os
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_ROOT = os.path.join(_HERE, "assets", "hello-algo")
MAP_PATH = os.path.join(_HERE, "diagram_map.json")
MAX_DIAGRAMS = 2

_IMAGE_EXTS = (".png", ".gif", ".jpg")


def load_map(path=MAP_PATH):
    """讀 diagram_map.json；不存在或壞掉都回傳空 dict（當作全部主題都沒圖）。"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def candidates_for(topic, dmap=None, assets_root=ASSETS_ROOT):
    """該主題可用的圖，回傳相對 assets_root 的路徑清單（排序穩定）。"""
    dmap = load_map() if dmap is None else dmap
    out = []
    for d in dmap.get(topic) or []:
        full = os.path.join(assets_root, d)
        if not os.path.isdir(full):
            continue  # 上游改名或圖庫沒更新，跳過而不是炸掉
        for name in sorted(os.listdir(full)):
            if name.lower().endswith(_IMAGE_EXTS):
                out.append(f"{d}/{name}")
    return out


def format_available(paths):
    """組出餵給 claude 的 AVAILABLE_DIAGRAMS 段落。"""
    if not paths:
        return "AVAILABLE_DIAGRAMS: （無，今天沒有可用的圖，不要輸出 diagrams 欄位）"
    lines = "\n".join(f"- {p}" for p in paths)
    return f"AVAILABLE_DIAGRAMS:\n{lines}"
