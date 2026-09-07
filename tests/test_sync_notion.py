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
