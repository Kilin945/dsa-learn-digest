# -*- coding: utf-8 -*-
"""diagram_notes.json 是圖說唯一的事實來源，這裡守住它的產生方式與內容品質。

背景：產稿的模型看不到圖，只拿到路徑。2026-09-07 那封信就是憑檔名猜圖說，
猜出「空間複雜度只算暫存空間」，跟它自己貼的圖（統計範圍含輸出空間）矛盾。
"""
import os
import re
import json

import pytest

import diagrams as dg
import build_diagram_notes as bdn

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPACE_TYPES = "chapter_computational_complexity/space_complexity.assets/space_types.png"
ARRAY_DEF = "chapter_array_and_linkedlist/array.assets/array_definition.png"


@pytest.fixture(scope="module")
def notes():
    return dg.load_notes()


# ---------- 檔案本身 ----------

def test_notes_file_is_in_sync_with_vendored_markdown():
    """章節原文改了就要重跑 build_diagram_notes.py，不然 note 會是舊的。"""
    assert bdn.main(["--check"]) == 0


def test_chapter_markdown_is_vendored():
    """note 的來源必須跟著 repo 走，不能靠上網抓——雲端寄信是離線流程。"""
    mds = []
    for root, _dirs, files in os.walk(dg.ASSETS_ROOT):
        mds += [f for f in files if f.endswith(".md") and f != "README.md"]
    assert len(mds) == 67, f"章節原文數量變了：{len(mds)}"


def test_no_syllabus_topic_loses_all_its_images(notes):
    """過濾掉沒有原文依據的圖之後，每個有登記配圖目錄的主題都還要撈得到圖。

    這是「寧可少一張圖，不要沒有依據的圖說」這條取捨的下界：可以變少，
    不可以變成零——那等於整個主題突然沒圖，而且是靜默發生的。
    """
    import state_store as ss
    dmap = dg.load_map()
    topics = ss.load_syllabus(os.path.join(HERE, "syllabus.txt"))
    dry = [t for t in topics
           if (dmap.get(t) or [])
           and not dg.candidates_for(t, dmap, dg.ASSETS_ROOT, notes)]
    assert dry == [], f"這些主題過濾後一張圖都不剩：{dry}"


def test_animation_frames_after_the_first_are_excluded(notes):
    """動畫分格圖只有第一格上面有敘述，後面幾格沒有自己的說明。

    把第一格的總說明掛到每一格上，模型挑到第 7 格就會用總說明去描述那一格
    ——那是「圖說沒有依據」的另一種形式。所以只留第一格。
    """
    first = "chapter_sorting/merge_sort.assets/merge_sort_step1.png"
    assert first in notes
    for n in range(2, 9):
        rel = f"chapter_sorting/merge_sort.assets/merge_sort_step{n}.png"
        assert os.path.isfile(os.path.join(dg.ASSETS_ROOT, rel)), rel
        assert rel not in notes, f"{rel} 不該有 note（它是第 {n} 格，沒有自己的敘述）"


def test_notes_shape(notes):
    assert len(notes) == 231
    for key, val in notes.items():
        assert isinstance(val, dict), key
        assert isinstance(val.get("alt"), str), key
        assert isinstance(val.get("text"), str) and val["text"], key


# ---------- 內容品質 ----------

def test_the_sentence_that_would_have_prevented_the_2026_09_07_bug(notes):
    """這張圖的原文必須明講輸出空間也算。這是整個機制的存在理由。"""
    text = notes[SPACE_TYPES]["text"]
    assert "統計範圍" in text
    assert "輸出空間" in text or "輸出資料" in text


def test_inline_html_tags_are_stripped_but_their_text_kept(notes):
    """hello-algo 用 <u>術語</u> 標定義，那是最有價值的句子——標籤剝掉、文字留下。

    原型曾因為「開頭是 < 就丟掉整段」而讓這張圖完全沒有 note。
    """
    text = notes[ARRAY_DEF]["text"]
    assert "<u>" not in text and "</u>" not in text
    assert "線性資料結構" in text
    assert "連續的記憶體空間" in text


def test_no_latex_leaks_into_notes(notes):
    """$O(n)$ 照抄進信裡會變成字面的錢字號。"""
    bad = [k for k, v in notes.items() if "$" in v["text"] or "\\begin" in v["text"]]
    assert bad == [], f"note 殘留 LaTeX：{bad[:5]}"


def test_no_source_code_leaks_into_notes(notes):
    """mkdocs 分頁區塊裡的各語言實作不是圖的敘述。"""
    code = re.compile(r"\bfunc \w+\(|\bpublic static|\bvoid \w+\(\w|\bfn \w+\(")
    bad = [k for k, v in notes.items() if code.search(v["text"])]
    assert bad == [], f"note 殘留程式碼：{bad[:5]}"


def test_notes_are_capped(notes):
    over = [k for k, v in notes.items() if len(v["text"]) > bdn.MAX_NOTE_CHARS + 1]
    assert over == [], f"note 超過字數上限：{over[:5]}"


# ---------- 抽取邏輯 ----------

def test_extraction_stops_at_the_previous_image():
    """越過前一張圖往上撈，撈到的是別張圖的說明。"""
    lines = [
        "上面那張圖在講平方階。",
        "",
        "![前一張圖](x.assets/prev.png)",
        "",
        "這一段在講指數階。",
        "",
        "![這張圖](x.assets/cur.png)",
    ]
    paras = bdn.paragraphs_before(lines, 6)
    assert paras == ["這一段在講指數階。"]


def test_extraction_stops_at_a_previous_image_glued_to_its_tab_label():
    """hello-algo 的動畫分格圖，分頁標籤與圖片行之間沒有空行。

    兩行會併成同一個 block，開頭是 `=== `。如果只看 block 開頭是不是圖片，
    這個 block 會被當成結構性內容跳過，於是越過前一張圖，撈到最上面那段
    總說明——實測 merge_sort_step2~step8 全都拿到 step1 上面那段文字。
    """
    lines = [
        "如下圖所示，劃分階段從頂至底遞迴切分。",
        "",
        '=== "<1>"',
        "    ![合併排序步驟](merge_sort.assets/merge_sort_step1.png)",
        "",
        '=== "<2>"',
        "    ![merge_sort_step2](merge_sort.assets/merge_sort_step2.png)",
    ]
    assert bdn.paragraphs_before(lines, 6) == []
    assert bdn.paragraphs_before(lines, 3) == ["如下圖所示，劃分階段從頂至底遞迴切分。"]


def test_extraction_skips_structural_blocks_but_keeps_looking():
    """定義句與圖之間常夾一份分點清單，跳過清單但要繼續往上找到定義句。"""
    lines = [
        "## 標題",
        "",
        "這是定義句。",
        "",
        "| 表格 | 欄 |",
        "|---|---|",
        "",
        "![圖](x.assets/a.png)",
    ]
    assert "這是定義句。" in bdn.paragraphs_before(lines, 7)


def test_mask_code_blanks_fenced_lines_only():
    """圍欄內每一行都要遮掉；admonition 的縮排正文不能遮。"""
    lines = [
        "!!! question",
        "",
        "    這是題目敘述，縮排四格但是正文。",
        "",
        "    ```java",
        "    void f() {}",
        "",
        "    int x = 1;",
        "    ```",
        "",
        "接著看圖。",
    ]
    masked = bdn.mask_code(lines)
    assert masked[2].strip() == "這是題目敘述，縮排四格但是正文。"
    assert masked[4] == "" and masked[5] == "" and masked[7] == "" and masked[8] == ""
    assert masked[10] == "接著看圖。"


def test_trim_keeps_the_text_nearest_the_image():
    """超長就從最前面裁——靠近圖的那幾句才是在講這張圖。"""
    out = bdn._trim("A" * 50 + "尾巴", limit=10)
    assert out.endswith("尾巴")
    assert out.startswith("…")
    assert len(out) == 11


def test_no_html_entities_leak_into_notes(notes):
    """hello-algo 的表格標題用 &nbsp; 排版，照抄進信裡會是字面的 "&nbsp;"。"""
    bad = [k for k, v in notes.items() if re.search(r"&[a-z]+;|&#\d+;", v["text"])]
    assert bad == [], f"note 殘留 HTML entity：{bad[:5]}"
