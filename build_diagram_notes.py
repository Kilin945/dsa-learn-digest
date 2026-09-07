#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""從 vendored 的 hello-algo 章節原文，抽出每張圖的權威敘述，產出 diagram_notes.json。

為什麼需要這支：產稿的模型看不到圖，只拿到檔案路徑。沒有原文的話它只能憑
`space_types.png` 這種檔名猜圖說——2026-09-07 那封信就是這樣寫出「空間複雜度
只算暫存空間」，跟它自己貼的那張圖（大括號涵蓋暫存＋輸出）直接矛盾。

原文就在圖的正上方。hello-algo 的章節 markdown 長這樣：

    一般情況下，空間複雜度的統計範圍是“暫存空間”加上“輸出空間”。
    ...
    在分析一段程式的空間複雜度時，**我們通常統計暫存資料、堆疊幀空間和輸出資料
    三部分**，如下圖所示。

    ![演算法使用的相關空間](space_complexity.assets/space_types.png)

所以「圖片 alt ＋ 緊接在前的幾段」就是這張圖的權威敘述。

用法：
  build_diagram_notes.py            # 寫回 diagram_notes.json
  build_diagram_notes.py --check    # 只檢查是否與現有檔案一致（給測試用），不寫檔
"""
import os
import re
import sys
import json
import html
import argparse

import diagrams as dg

# 往上最多收幾個段落。實測 2 段會漏掉更上面那句更精準的定義
# （space_types.png 的「統計範圍是暫存空間加上輸出空間」在第 4 段），
# 4 段能涵蓋 hello-algo 慣用的「定義 → 分點 → 如下圖所示」結構。
MAX_BLOCKS = 4

# note 文字上限。中位數 154 字、平均 173 字，但最長的一則有 1548 字；
# 每天最多兩張圖，但 AVAILABLE_DIAGRAMS 會列出當天主題的全部候選圖
# （最多的「背包問題」有 47 張），不設上限會讓 prompt 膨脹得沒必要。
MAX_NOTE_CHARS = 400

_IMG = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<path>[^)\s]+)\)')

# 程式碼不是敘述。hello-algo 用 mkdocs 的分頁區塊放各語言實作：
#
#     === "Swift"
#
#         ```swift title=""
#         func recur(n: Int) { ... }
#         ```
#
# 區塊內容整體縮排 4 格，而且裡面有空行，所以「把整段接起來再看開頭是不是 ```」
# 會讓中間的程式碼片段被當成獨立的敘述段落——實測 Swift 的 func recur 就這樣
# 進了 space_complexity_common_types.png 的 note。要逐行追蹤圍欄狀態，把
# ``` 之內的每一行都遮掉。
#
# 只追圍欄、不用「縮排 >= 4 格就當程式碼」那條規則：mkdocs 的 admonition
# （`!!! question` 的題目敘述）內容也縮排 4 格，那是不能遮的正文——遮掉會讓
# chapter_greedy 那幾張題目示例圖失去唯一的敘述來源。實測只靠圍欄追蹤已經
# 是 484 張圖、0 殘留程式碼。
_FENCE = re.compile(r'^\s*```')

# 這些開頭代表結構性區塊（標題、程式碼圍欄、mkdocs 的 tabbed/admonition、
# 表格），不是敘述文字，往上找的時候跳過但繼續往上找——hello-algo 常在
# 定義句與圖之間夾一份分點清單或一段程式碼。
_STRUCTURAL_PREFIXES = ('#', '```', '===', '!!!', '???', '|')

# 碰到前一張圖就**停止**，不是跳過。一個章節裡有好幾張圖，越過前一張圖
# 繼續往上撈，撈到的是在講另一張圖的文字：實測 space_complexity_exponential.png
# 的 note 會混進線性階、平方階的敘述，那些是別張圖的說明。
#
# 用 search 而不是 match：圖片引用不一定自己獨占一個 block。hello-algo 的
# 動畫分格圖長這樣，分頁標籤與圖片行之間沒有空行——
#
#     === "<2>"
#         ![merge_sort_step2](merge_sort.assets/merge_sort_step2.png)
#
# 兩行會被併成同一個 block，開頭是 `===`，用 match 就會被當成結構性內容跳過、
# 越過這張圖繼續往上撈，於是 step2~step8 全都拿到 step1 上面那段總說明。
# 這個判斷也必須排在結構性判斷之前，否則同樣被 `===` 攔掉。
_IMG_ANY = re.compile(r'!\[[^\]]*\]\(')

# LaTeX 不能原樣進信裡。行內的 $O(n)$ 剝掉錢字號留 O(n)；display math
# （$$ … $$）整段丟掉，那是公式排版、不是圖的敘述。
_DISPLAY_MATH = re.compile(r'\$\$.*?\$\$', re.S)
_INLINE_MATH = re.compile(r'\$([^$]*)\$')
_LATEX_CMD = re.compile(r'\\[A-Za-z]+\s*')

# hello-algo 用 <u>術語（term）</u> 標定義，那正是最有價值的句子。
# 只剝掉 inline 標籤本身，不要因為段落開頭是 '<' 就把整段丟掉——
# 原型就是這樣漏掉 array_definition.png 的定義句。
_INLINE_TAG = re.compile(r'</?[A-Za-z][^>]*>')


def _clean(text):
    """去掉 inline HTML 標籤、entity、markdown 強調符號與 LaTeX，留純敘述。"""
    text = _INLINE_TAG.sub('', text)
    # hello-algo 的表格標題用 &nbsp; 排版，照抄進信裡會是字面的 "&nbsp;"。
    text = html.unescape(text)
    text = _DISPLAY_MATH.sub('', text)
    text = _INLINE_MATH.sub(lambda m: m.group(1), text)
    text = _LATEX_CMD.sub('', text)
    text = text.replace('**', '').replace('`', '')
    return re.sub(r'\s+', ' ', text).strip()


def mask_code(lines):
    """回傳同長度的 lines 副本，屬於程式碼的行換成空字串。

    空字串在 paragraphs_before 眼中就是空行——只當段落分隔，永遠不會被
    收進敘述文字。圖片引用行不受影響，「碰到前一張圖就停」的判斷照樣成立。
    """
    out = []
    in_fence = False
    for line in lines:
        if _FENCE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def paragraphs_before(lines, idx, max_blocks=MAX_BLOCKS):
    """idx 這行之前最近的敘述段落，由遠到近排列，最多 max_blocks 段。

    「一段」是連續的非空行。結構性區塊跳過但不中斷搜尋——hello-algo 常在
    定義句與圖之間夾一份分點清單。
    """
    out = []
    i = idx - 1
    while i >= 0 and len(out) < max_blocks:
        while i >= 0 and not lines[i].strip():
            i -= 1
        if i < 0:
            break
        block = []
        while i >= 0 and lines[i].strip():
            block.append(lines[i].strip())
            i -= 1
        para = " ".join(reversed(block))
        if _IMG_ANY.search(para):
            break                       # 前一張圖，再往上就是別張圖的說明
        if para.startswith(_STRUCTURAL_PREFIXES):
            continue
        cleaned = _clean(para)
        if cleaned:
            out.append(cleaned)
    return list(reversed(out))


def _trim(text, limit=MAX_NOTE_CHARS):
    """超長就從最前面裁掉——靠近圖的那幾句才是在講這張圖。"""
    if len(text) <= limit:
        return text
    return "…" + text[-limit:]


def build(assets_root=None):
    """走過 assets_root 底下的章節 markdown，回傳 {圖片相對路徑: {alt, text}}。

    圖片路徑的 key 與 diagrams.candidates_for() 產出的格式一致
    （`chapter_x/y.assets/f.png`），這樣 format_available() 才對得起來。
    """
    assets_root = dg.ASSETS_ROOT if assets_root is None else assets_root
    notes = {}
    for root, _dirs, files in os.walk(assets_root):
        for fn in sorted(files):
            if not fn.endswith('.md') or fn == 'README.md':
                continue
            chapter = os.path.relpath(root, assets_root)
            with open(os.path.join(root, fn), encoding='utf-8') as f:
                lines = f.read().split('\n')
            prose = mask_code(lines)
            for ln, line in enumerate(lines):
                for m in _IMG.finditer(line):
                    ipath = m.group('path')
                    if '.assets/' not in ipath:
                        continue
                    if not ipath.lower().endswith(dg._IMAGE_EXTS):
                        continue
                    key = os.path.normpath(os.path.join(chapter, ipath))
                    if not os.path.isfile(os.path.join(assets_root, key)):
                        continue  # 上游有引用但圖沒 vendor 進來，跳過
                    paras = paragraphs_before(prose, ln)
                    if not paras:
                        continue  # 沒依據的圖不登記；candidates_for 會排除它
                    notes[key] = {
                        "alt": _clean(m.group('alt')),
                        "text": _trim(" ".join(paras)),
                    }
    return notes


def main(argv=None):
    ap = argparse.ArgumentParser(description="產出 diagram_notes.json")
    ap.add_argument("--check", action="store_true",
                    help="只比對現有檔案是否已是最新，不寫檔；不一致回傳 1")
    args = ap.parse_args(argv)

    notes = build()
    payload = json.dumps(notes, ensure_ascii=False, indent=1, sort_keys=True) + "\n"

    if args.check:
        try:
            with open(dg.NOTES_PATH, encoding='utf-8') as f:
                current = f.read()
        except OSError:
            print("diagram_notes.json 不存在或讀不到", file=sys.stderr)
            return 1
        if current != payload:
            print("diagram_notes.json 與章節原文不同步，請重跑 build_diagram_notes.py",
                  file=sys.stderr)
            return 1
        print(f"diagram_notes.json 已同步（{len(notes)} 張圖）")
        return 0

    with open(dg.NOTES_PATH, "w", encoding='utf-8') as f:
        f.write(payload)
    print(f"寫入 {dg.NOTES_PATH}（{len(notes)} 張圖）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
