import sync_notion as sn

# ── code review finding 4：md_to_blocks／rich_text 要能渲染新的圖片＋署名 ──
# 這兩行是 prompt_daily.txt 現在真的會要求模型寫進 archive_markdown 的內容
# （逐字照抄，不是簡化過的示意）。

_IMG_LINE = ("![演算法執行時的記憶體空間分類]"
             "(https://raw.githubusercontent.com/krahets/hello-algo/main/"
             "zh-hant/docs/chapter_computational_complexity/"
             "space_complexity.assets/space_types.png)")
_ATTR_LINE = "圖：[Hello 算法](https://www.hello-algo.com/) · CC BY-NC-SA 4.0"


def test_image_line_becomes_external_image_block():
    blocks = sn.md_to_blocks(_IMG_LINE)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["type"] == "image"
    assert b["image"]["type"] == "external"
    assert b["image"]["external"]["url"] == (
        "https://raw.githubusercontent.com/krahets/hello-algo/main/"
        "zh-hant/docs/chapter_computational_complexity/"
        "space_complexity.assets/space_types.png"
    )
    assert b["image"]["caption"][0]["text"]["content"] == "演算法執行時的記憶體空間分類"


def test_image_line_with_empty_caption_omits_caption_key():
    blocks = sn.md_to_blocks("![](https://example.com/x.png)")
    assert blocks[0]["image"].get("caption", []) == []


def test_attribution_line_becomes_paragraph_with_real_link():
    blocks = sn.md_to_blocks(_ATTR_LINE)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["type"] == "paragraph"
    rt = b["paragraph"]["rich_text"]
    texts = [r["text"]["content"] for r in rt]
    assert texts == ["圖：", "Hello 算法", " · CC BY-NC-SA 4.0"]
    link_piece = next(r for r in rt if r["text"]["content"] == "Hello 算法")
    assert link_piece["text"]["link"]["url"] == "https://www.hello-algo.com/"
    # 純文字片段不該無端多出 link 欄位
    assert "link" not in rt[0]["text"]


def test_both_lines_together_in_one_document():
    md = f"## Day 1\n\n{_IMG_LINE}\n{_ATTR_LINE}\n\n一般段落。"
    blocks = sn.md_to_blocks(md)
    types = [b["type"] for b in blocks]
    assert types == ["heading_2", "image", "paragraph", "paragraph"]


def test_rich_text_still_handles_bold_and_code():
    # 舊行為不能被新分支弄壞。
    out = sn.rich_text("**粗體** 一般 `code`")
    assert [o["text"]["content"] for o in out] == ["粗體", " 一般 ", "code"]
    assert out[0].get("annotations", {}).get("bold") is True
    assert out[2].get("annotations", {}).get("code") is True
    assert "annotations" not in out[1] or not out[1]["annotations"]


def test_rich_text_handles_link_mixed_with_bold():
    out = sn.rich_text("**重點**：見 [文件](https://example.com/doc)。")
    contents = [o["text"]["content"] for o in out]
    assert contents == ["重點", "：見 ", "文件", "。"]
    assert out[2]["text"]["link"]["url"] == "https://example.com/doc"


def test_non_image_markdown_link_in_paragraph_is_not_treated_as_image():
    # 一般連結（非圖片語法）不該被圖片分支誤吃。
    blocks = sn.md_to_blocks("參考 [Hello 算法](https://www.hello-algo.com/) 的說明。")
    assert blocks[0]["type"] == "paragraph"


def test_properties_downgrades_to_plain_text():
    # .properties 不在 Notion 語言清單，必須降級，否則整頁 POST 400
    assert sn._norm_lang("properties") == "plain text"


def test_known_alias_maps():
    assert sn._norm_lang("yml") == "yaml"
    assert sn._norm_lang("js") == "javascript"
    assert sn._norm_lang("sh") == "shell"


def test_direct_valid_lang_passes_through():
    # _LANG_MAP 沒列但 Notion 合法的語言應直接通過
    assert sn._norm_lang("rust") == "rust"
    assert sn._norm_lang("go") == "go"


def test_unknown_lang_downgrades():
    assert sn._norm_lang("brainfuck") == "plain text"


def test_case_insensitive():
    assert sn._norm_lang("Java") == "java"
    assert sn._norm_lang("YAML") == "yaml"


# ── 網址的三種寫法都要變成可點的連結 ──
# prompt_daily.txt 只要求之後的信寫 [文字](url)，管不到 lessons/ 裡已歸檔的舊課程。
# 2026-09-07 那頁同步後，LeetCode 連結在 Notion 上顯示成 `\<https://…\>`，點不動。

def _links(rich):
    """[(顯示文字, link url)]，只取真的有 link 的片段。"""
    return [(r["text"]["content"], r["text"]["link"]["url"])
            for r in rich if (r["text"].get("link") or {}).get("url")]


def test_angle_bracket_autolink_consumes_the_brackets():
    """`<url>` 要整段吃掉，角括號不能留成字面文字。

    只驗「有沒有連結」是抓不到迴歸的：裸網址那一支本來就會配到角括號裡面的
    網址（`>` 不在它的字元集裡），連結照樣成立，但前後留下 `<` 和 `>` 兩個字，
    Notion 上會轉義顯示成 `\<https://…\>`。所以要驗重組後的完整文字。
    """
    url = "https://leetcode.com/problems/remove-duplicates-from-sorted-array/"
    rich = sn.rich_text(f"<{url}>")
    assert _links(rich) == [(url, url)]
    assert "".join(r["text"]["content"] for r in rich) == url


def test_bare_url_becomes_a_link():
    url = "https://leetcode.com/problems/remove-element/"
    assert _links(sn.rich_text(url)) == [(url, url)]


def test_markdown_link_still_wins_over_bare_url():
    """裸網址那一支若排在前面，會把 `](url)` 裡的網址吃掉、連結文字散掉。

    這是署名行的形狀，CC BY-NC-SA 要求的署名不能壞。
    """
    rich = sn.rich_text("圖：[Hello 算法](https://www.hello-algo.com/) · CC BY-NC-SA 4.0")
    assert _links(rich) == [("Hello 算法", "https://www.hello-algo.com/")]
    assert "".join(r["text"]["content"] for r in rich) == \
        "圖：Hello 算法 · CC BY-NC-SA 4.0"


def test_mixed_link_forms_in_one_line():
    rich = sn.rich_text("看 [這裡](https://a.com) 或 https://b.com 都行")
    assert _links(rich) == [("這裡", "https://a.com"), ("https://b.com", "https://b.com")]


def test_bold_and_code_survive_alongside_a_bare_url():
    rich = sn.rich_text("**粗體** 和 `code` 混排 https://c.com 結尾")
    assert _links(rich) == [("https://c.com", "https://c.com")]
    bold = [r["text"]["content"] for r in rich if r.get("annotations", {}).get("bold")]
    code = [r["text"]["content"] for r in rich if r.get("annotations", {}).get("code")]
    assert bold == ["粗體"] and code == ["code"]


def test_every_archived_lesson_link_resolves():
    """lessons/ 裡每一行網址，不管哪種寫法，都必須變成可點連結。

    這是「在 Notion 正確顯示」的驗收條件，不是風格偏好。
    """
    import glob, os, re
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    unlinked = []
    for path in sorted(glob.glob(os.path.join(here, "lessons", "*.md"))):
        for n, line in enumerate(open(path, encoding="utf-8"), 1):
            if not re.search(r"https?://", line):
                continue
            if line.lstrip().startswith("!["):
                continue          # 圖片行由 md_to_blocks 的 image 分支處理
            if not _links(sn.rich_text(line.strip())):
                unlinked.append(f"{os.path.basename(path)}:{n}")
    assert unlinked == [], f"這些行的網址不會變成連結：{unlinked}"
