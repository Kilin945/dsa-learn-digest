#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""課程配圖：主題 → 候選圖，以及 claude 選圖結果的驗證與剝除。

圖庫是 vendored 的 hello-algo 繁中圖（assets/hello-algo/），CC BY-NC-SA 4.0。
貫穿全檔的原則：圖是加分項，任何圖片相關的失敗都不得阻擋信件寄出 ——
撈不到就當沒圖，驗不過就整批剝掉，信照常走。
"""
import os
import re
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_ROOT = os.path.join(_HERE, "assets", "hello-algo")
MAP_PATH = os.path.join(_HERE, "diagram_map.json")
MAX_DIAGRAMS = 2

_IMAGE_EXTS = (".png", ".gif", ".jpg")

# 只認 <img src=cid:xxx>。外部 URL 的 img 不歸這裡管（也不該出現在信裡）。
# src 的值可以加引號也可以不加（兩者在 HTML 裡都合法）；(?P<q>["\']?) 配 (?P=q) backreference
# 確保「有加引號就一定要用同一種引號收尾」，不會讓 src="cid:d1" 因為引號比對太鬆
# 而吃到後面別的屬性裡的引號。
_IMG_CID = re.compile(
    r'<img\b[^>]*?\bsrc\s*=\s*(?P<q>["\']?)cid:(?P<cid>[A-Za-z0-9_-]+)(?P=q)[^>]*>',
    re.I,
)

# data-fig="cid" 標記的是整個圖說 wrapper（圖＋圖說＋署名）；裡面還有巢狀的 <div>，
# 一般 regex 配不出巢狀的收尾 </div>，所以用計數的方式手動找配對。
_DIV_TAG = re.compile(r'<(/?)div\b[^>]*>', re.I)


def _marked_block_span(html, cid):
    """找 <div ... data-fig="cid" ...>…</div> 的區間（含頭尾），找不到回傳 None。

    只有這個 wrapper 本身巢狀，不是任意巢狀 HTML，所以用簡單的開合計數就夠，
    不需要真的解析 HTML。
    """
    marker = re.compile(r'<div\b[^>]*\bdata-fig=(["\'])%s\1[^>]*>' % re.escape(cid), re.I)
    m = marker.search(html)
    if not m:
        return None
    depth = 1
    for tm in _DIV_TAG.finditer(html, m.end()):
        if tm.group(1):          # </div>
            depth -= 1
            if depth == 0:
                return m.start(), tm.end()
        else:                    # 巢狀的 <div ...>
            depth += 1
    return None                  # 沒配對到收尾，當作沒找到，交給舊的剝法


def load_map(path=None):
    """讀 diagram_map.json；不存在或壞掉都回傳空 dict（當作全部主題都沒圖）。"""
    path = MAP_PATH if path is None else path
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def candidates_for(topic, dmap=None, assets_root=None):
    """該主題可用的圖，回傳相對 assets_root 的路徑清單（排序穩定）。"""
    dmap = load_map() if dmap is None else dmap
    assets_root = ASSETS_ROOT if assets_root is None else assets_root
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


def cid_refs(html):
    """html 裡引用到的 cid，依出現順序。"""
    return [m.group("cid") for m in _IMG_CID.finditer(html or "")]


def strip_img_tags(html):
    """把每張 cid 圖從 html 拿掉，其餘內容原封不動。

    優先整塊拿掉 `data-fig="cid"` 標記的 wrapper（連圖、圖說解說、CC BY-NC-SA
    署名一起清掉）——不然只拔 <img> 會留下一段指著空氣的圖說文字。
    找不到標記（沒有 data-fig 屬性的舊格式 outbox／舊信）就退回原本的做法，
    只拿掉 <img> 本身，其餘文字不動——這樣改動前產生的信不會被這支新邏輯弄壞。
    """
    html = html or ""
    for cid in cid_refs(html):
        span = _marked_block_span(html, cid)
        if span:
            start, end = span
            html = html[:start] + html[end:]
        else:
            html = re.compile(
                r'<img\b[^>]*?\bsrc\s*=\s*(?P<q>["\']?)cid:%s(?P=q)[^>]*>' % re.escape(cid),
                re.I,
            ).sub("", html, count=1)
    return html


def _is_inside(rel, assets_root):
    """rel 必須落在 assets_root 底下、是圖片副檔名、且檔案存在（擋掉 ../ 逃逸與絕對路徑）。

    rel 來自模型輸出，內容不可信——embedded null、過長路徑等都可能讓
    os.path.realpath / os.path.isfile 直接炸掉。這裡一律當「不合格」，
    而不是讓例外往上炸穿整個 sanitize（進而炸穿整個 apply_result 呼叫）。

    副檔名也要檢查：assets_root 底下不是只有圖（例如 LICENSE），單靠
    「檔案存在」會讓模型選到非圖片檔在 prepare 階段就悄悄過關，等雲端
    send_email 真的去讀才炸——這裡先擋掉，失敗要在備稿當下就看得到。
    """
    if not rel.lower().endswith(_IMAGE_EXTS):
        return False
    try:
        root = os.path.realpath(assets_root)
        full = os.path.realpath(os.path.join(root, rel))
        if full != root and not full.startswith(root + os.sep):
            return False
        return os.path.isfile(full)
    except (ValueError, OSError):
        return False


def sanitize(res, assets_root=None):
    """驗證 res['diagrams']；任一項不合格就整批剝掉並移除 html 裡的 <img>。

    回傳 (新的 res, 圖有沒有留下)。不修改傳入的 res。
    全有全無是刻意的：一封信只有兩張圖，留下半套比乾脆沒圖更難看，
    而且圖文是配套寫的，剝掉一張會讓「圖說」指向不存在的東西。
    """
    assets_root = ASSETS_ROOT if assets_root is None else assets_root
    out = dict(res)
    raw_html = out.get("html")
    # 正常流程下 parse_result 已保證 html 是字串；這裡仍用型別而非真假值判斷，
    # 因為 sanitize 是獨立、有文件的函式，不能假設呼叫者一定走過 parse_result。
    html = raw_html if isinstance(raw_html, str) else ""
    refs = cid_refs(html)
    diags = out.get("diagrams")

    if not refs and not diags:
        out.pop("diagrams", None)
        return out, True                      # 本來就沒圖，正常

    def drop():
        # html 本來就不是字串就沒東西好剝——原樣留著，不要用空字串覆蓋掉呼叫者的值。
        if isinstance(raw_html, str):
            out["html"] = strip_img_tags(raw_html)
        out.pop("diagrams", None)
        return out, False

    if not isinstance(diags, list) or not diags or len(diags) > MAX_DIAGRAMS:
        return drop()

    seen = set()
    for d in diags:
        if not isinstance(d, dict):
            return drop()
        cid, path = d.get("cid"), d.get("path")
        if not isinstance(cid, str) or not isinstance(path, str) or not cid or not path:
            return drop()
        if cid in seen or not _is_inside(path, assets_root):
            return drop()
        seen.add(cid)

    if seen != set(refs):                     # html 與 diagrams 必須完全對得上
        return drop()

    # 沒有人在寄出前看信——署名有沒有留著完全靠模型照抄模板，這裡當成硬性條件。
    # 只認短字串 "CC BY-NC-SA"，不比對整句署名文字：整句比對會讓文案上無傷大雅的
    # 措辭差異（例如連結文字、標點）就白白讓一封信沒了圖，比它想防的問題還糟。
    if "CC BY-NC-SA" not in html:
        return drop()
    return out, True


def abs_paths(diagrams_list, assets_root=None):
    """[(cid, 絕對路徑)]，給寄信端組 --image 參數用。

    前提：diagrams_list 必須是已經過 sanitize() 驗證的清單——這裡不再驗證
    每筆元素的形狀，只負責組路徑；沒過 sanitize 就餵進來，缺 key 時用 .get()
    回傳 None 而不是讓 KeyError 往上炸穿整個呼叫鏈。
    """
    assets_root = ASSETS_ROOT if assets_root is None else assets_root
    return [(d.get("cid"), os.path.join(assets_root, d.get("path", "")))
            for d in (diagrams_list or [])]
