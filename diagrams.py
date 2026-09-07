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
NOTES_PATH = os.path.join(_HERE, "diagram_notes.json")
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


def load_notes(path=None):
    """讀 diagram_notes.json；不存在或壞掉都回傳空 dict。

    空 dict 的語意是「沒有原文可用」，candidates_for 會據此**不做過濾**、
    format_available 也只印路徑——退回這個改動之前的行為。圖是加分項，
    note 檔案壞掉不該讓整封信沒圖，更不該擋信。
    """
    path = NOTES_PATH if path is None else path
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def candidates_for(topic, dmap=None, assets_root=None, notes=None):
    """該主題可用的圖，回傳相對 assets_root 的路徑清單（排序穩定）。

    只回傳「在 diagram_notes.json 裡有原文敘述」的圖：模型看不到圖，沒有
    原文它只能憑檔名猜圖說，猜出來的圖說會跟圖矛盾（2026-09-07 那封信）。
    寧可少一張圖，也不要一段沒有依據的圖說。

    例外：notes 整份是空的（檔案不存在或解析失敗）時不過濾，否則一個壞掉的
    JSON 會讓所有主題都突然沒圖。實際會被排除的只有 assets/covers/ 與
    index.assets/ 底下的封面插畫與首頁 banner——它們不在 diagram_map.json
    任何主題底下，本來就撈不到。

    dmap / assets_root / notes 三者要成套傳：它們描述的是同一個圖庫。只換
    assets_root 而讓 notes 落回全域檔案，等於拿真圖庫的對照表比對另一個圖庫
    的路徑，一張都對不上、回傳空清單（測試用假圖庫時就會踩到，見
    tests/test_diagrams.py 的 fake_notes fixture）。
    """
    dmap = load_map() if dmap is None else dmap
    assets_root = ASSETS_ROOT if assets_root is None else assets_root
    notes = load_notes() if notes is None else notes
    out = []
    for d in dmap.get(topic) or []:
        full = os.path.join(assets_root, d)
        if not os.path.isdir(full):
            continue  # 上游改名或圖庫沒更新，跳過而不是炸掉
        for name in sorted(os.listdir(full)):
            if not name.lower().endswith(_IMAGE_EXTS):
                continue
            rel = f"{d}/{name}"
            if notes and rel not in notes:
                continue
            out.append(rel)
    return out


def format_available(paths, notes=None):
    """組出餵給 claude 的 AVAILABLE_DIAGRAMS 段落，每張圖附上 hello-algo 原文。

    原文是圖說唯一的依據來源（prompt_daily.txt 據此要求圖說不得寫出原文
    沒支持的斷言）。撈不到原文的圖只印路徑，不編造。
    """
    if not paths:
        return "AVAILABLE_DIAGRAMS: （無，今天沒有可用的圖，不要輸出 diagrams 欄位）"
    notes = load_notes() if notes is None else notes
    lines = []
    for p in paths:
        lines.append(f"- {p}")
        note = notes.get(p) if isinstance(notes, dict) else None
        if not isinstance(note, dict):
            continue
        alt = note.get("alt")
        text = note.get("text")
        if isinstance(alt, str) and alt:
            lines.append(f"  圖名：{alt}")
        if isinstance(text, str) and text:
            lines.append(f"  原文：{text}")
    return "AVAILABLE_DIAGRAMS:\n" + "\n".join(lines)


def cid_refs(html):
    """html 裡引用到的 cid，依出現順序。"""
    return [m.group("cid") for m in _IMG_CID.finditer(html or "")]


def _cid_img_re(cid):
    """單一 cid 的 <img src=cid:cid> regex（引號可有可無，見 _IMG_CID 的說明）。"""
    return re.compile(
        r'<img\b[^>]*?\bsrc\s*=\s*(?P<q>["\']?)cid:%s(?P=q)[^>]*>' % re.escape(cid),
        re.I,
    )


# 一個真正的圖說 wrapper（圖＋解說＋署名）在整封信裡只占一小塊。如果
# data-fig 誤點到包住整堂課內容的外層卡片，那一個區塊會占掉信件本文的
# 絕大部分——用「這個區塊占整封信多少比例」當結構訊號，不看內容文字：
# 真實案例裡，正確標記的圖說區塊約占整封信 7.9%，誤點到外層卡片則是
# 90%+，中間留了很大的安全邊際，門檻切在 0.5（50%）不影響判斷結果，
# 也不會像「span 裡要有 CC BY-NC-SA 署名」那樣，因為模型措辭的無傷大雅
# 差異而誤判——大小不會因為文字寫法變。超過門檻就不整塊拿掉，退回只清
# 裡面的裸 <img>，其餘教學內容留著，是遠比整塊清空更小的degradation。
_MAX_MARKED_BLOCK_FRACTION = 0.5


def strip_img_tags(html):
    """把每張 cid 圖從 html 拿掉，其餘內容原封不動。

    優先整塊拿掉 `data-fig="cid"` 標記的 wrapper（連圖、圖說解說、CC BY-NC-SA
    署名一起清掉）——不然只拔 <img> 會留下一段指著空氣的圖說文字。

    但標記到的 wrapper 要滿足兩個條件才能整塊拿掉：

    1. 裡面真的有這個 cid 的 <img>——模型可能把 data-fig 點到不含圖的區塊上
       （圖說被誤刪、破圖卻留著），這種情況下整塊留著不動，只靠下面無條件
       的裸圖清除把破圖拔掉。
    2. 這個區塊占整封信的比例沒有超過 _MAX_MARKED_BLOCK_FRACTION——模型也
       可能把 data-fig 點到包住整堂課內容的外層卡片，那個區塊雖然「裡面
       有圖」，但占了信件本文的絕大部分（見上方常數的說明）；整塊拿掉會把
       教學內容也一起清空，比破圖本身嚴重得多。這種情況下一樣整塊留著、
       只清裡面的裸 <img>。

    這裡刻意不驗證區塊裡的其他內容文字（例如是不是也有署名字串）——多加
    的內容判斷曾經在這裡引入過一個更糟的迴歸：只要區塊裡的圖說湊巧沒把
    署名複製進來，整塊就被誤判成「不算數」而留著不刪，於是驗證失敗、理應
    被剝乾淨的圖說文字反而原封不動地留在信裡。「有沒有圖」與「占多少比例」
    都是結構訊號、不受模型措辭影響，這才是這支函式能可靠回答的問題。

    這兩關都不是萬無一失：極端情況下（例如整封信本來就只有這一個區塊）
    這裡仍可能整塊拿掉、甚至把內文清空——send_email.py 在組好信件之後
    另外有一道「內文不能是空的」的把關，那才是真正兜住「不管什麼原因，
    寄出去的信不能是空的」這個不變量的最後一道防線，這裡的兩關只是盡量
    讓內容不要被錯誤地清掉，減少走到那道防線的機會。

    不管有沒有整塊拿掉，最後都無條件再跑一次「裸 <img>」的刪除——這樣
    wrapper 沒有這個 cid 的圖、或因為占比過大而被保留時，圖本身還是會被
    清掉（不管它落在哪裡）；wrapper 兩關都過而整塊刪掉時，這裡是沒東西
    可刪的 no-op。落單在標記範圍外的 <img> 不會漏網。

    找不到標記（沒有 data-fig 屬性的舊格式 outbox／舊信）就退回原本的做法，
    只拿掉 <img> 本身，其餘文字不動——這樣改動前產生的信不會被這支新邏輯弄壞。
    """
    html = html or ""
    total_len = len(html)
    for cid in cid_refs(html):
        img_re = _cid_img_re(cid)
        span = _marked_block_span(html, cid)
        if span:
            start, end = span
            block = html[start:end]
            fits = total_len == 0 or len(block) <= total_len * _MAX_MARKED_BLOCK_FRACTION
            if img_re.search(block) and fits:
                html = html[:start] + html[end:]
        html = img_re.sub("", html, count=1)
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


# archive_markdown 裡的 hello-algo 配圖行長這樣（見 prompt_daily.txt）：
#   ![圖說](https://raw.githubusercontent.com/krahets/hello-algo/main/zh-hant/docs/<path>)
#   圖：[Hello 算法](https://www.hello-algo.com/) · CC BY-NC-SA 4.0
_HELLO_ALGO_RAW_PREFIX = "https://raw.githubusercontent.com/krahets/hello-algo/"
_MD_HELLO_ALGO_IMAGE = re.compile(
    r'^!\[[^\]]*\]\(' + re.escape(_HELLO_ALGO_RAW_PREFIX) + r'\S*\)\s*$'
)
_MD_HELLO_ALGO_ATTRIBUTION = re.compile(
    r'^.*\[[^\]]*\]\(https://www\.hello-algo\.com/?\).*CC BY-NC-SA.*$'
)


def strip_hello_algo_images_from_markdown(markdown):
    """把 archive_markdown 裡指向 hello-algo raw URL 的圖片行、與緊接在後的
    署名行拿掉。

    用途：sanitize() 因為 diagrams 驗證沒過而剝掉 html 裡的圖時，
    archive_markdown 原本沒有跟著剝——html 乾乾淨淨變回純文字，但
    lessons/<date>.md 跟 Notion 上還留著一張 404 的圖跟一行指著空氣的
    圖說，兩份產出就對不起來了。

    刻意保守：只認「整行就是一個指向 hello-algo raw URL 的 markdown 圖片」
    這個形狀，而且只在緊接著這一行的下一行同時符合「署名行」的形狀
    （連結指向 hello-algo.com 且含 CC BY-NC-SA）才一併拿掉——不是任何
    模型寫的 markdown 圖片或連結都清，只清 diagrams 驗證失敗時真正需要清
    的那兩行，模型自己寫的其他圖片、連結原封不動。
    """
    if not isinstance(markdown, str) or not markdown:
        return markdown
    lines = markdown.split("\n")
    out = []
    i, n = 0, len(lines)
    while i < n:
        if _MD_HELLO_ALGO_IMAGE.match(lines[i].strip()):
            i += 1
            if i < n and _MD_HELLO_ALGO_ATTRIBUTION.match(lines[i].strip()):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


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
        # archive_markdown 要跟 html 一致地剝掉圖：這裡剝的是 hello-algo 圖片
        # 驗證沒過（模型自己編或寫錯 path，正是這個驗證要擋的情況）——html
        # 已經變回純文字，archive_markdown 不能還留著同一張圖的 markdown
        # 語法與署名，不然 lessons/<date>.md 跟 Notion 上的歸檔筆記會有一張
        # 404 的圖、一行指著空氣的圖說，跟當天實際寄出的純文字信對不起來。
        raw_md = out.get("archive_markdown")
        if isinstance(raw_md, str):
            out["archive_markdown"] = strip_hello_algo_images_from_markdown(raw_md)
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
