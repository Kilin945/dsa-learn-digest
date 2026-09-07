import os
import json
import pytest

import diagrams as dg


@pytest.fixture
def fake_assets(tmp_path):
    """造一個假圖庫：兩個章節目錄，各放幾張圖。"""
    root = tmp_path / "assets"
    d1 = root / "chapter_a/x.assets"
    d2 = root / "chapter_a/y.assets"
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)
    (d1 / "b.png").write_bytes(b"\x89PNG")
    (d1 / "a.png").write_bytes(b"\x89PNG")
    (d1 / "notes.md").write_text("不是圖", encoding="utf-8")
    (d2 / "c.gif").write_bytes(b"GIF89a")
    return str(root)


def test_candidates_are_sorted_and_image_only(fake_assets):
    dmap = {"主題甲": ["chapter_a/x.assets"]}
    assert dg.candidates_for("主題甲", dmap, fake_assets) == [
        "chapter_a/x.assets/a.png",
        "chapter_a/x.assets/b.png",
    ]


def test_candidates_spans_multiple_dirs(fake_assets):
    dmap = {"主題甲": ["chapter_a/x.assets", "chapter_a/y.assets"]}
    got = dg.candidates_for("主題甲", dmap, fake_assets)
    assert "chapter_a/y.assets/c.gif" in got
    assert len(got) == 3


def test_topic_not_in_map_returns_empty(fake_assets):
    assert dg.candidates_for("沒登記的主題", {}, fake_assets) == []


def test_missing_dir_is_skipped_not_raised(fake_assets):
    dmap = {"主題甲": ["chapter_a/x.assets", "chapter_zzz/nope.assets"]}
    got = dg.candidates_for("主題甲", dmap, fake_assets)
    assert got == ["chapter_a/x.assets/a.png", "chapter_a/x.assets/b.png"]


def test_format_available_lists_paths():
    out = dg.format_available(["chapter_a/x.assets/a.png"])
    assert out.startswith("AVAILABLE_DIAGRAMS:")
    assert "- chapter_a/x.assets/a.png" in out


def test_format_available_empty_tells_model_not_to_emit():
    out = dg.format_available([])
    assert "AVAILABLE_DIAGRAMS:" in out
    assert "不要輸出 diagrams" in out


def test_load_map_missing_file_returns_empty(tmp_path):
    assert dg.load_map(str(tmp_path / "nope.json")) == {}


def test_load_map_broken_json_returns_empty(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{ not json", encoding="utf-8")
    assert dg.load_map(str(p)) == {}


def _res(html, diags=None):
    r = {"html": html, "topic_complete": False,
         "today_summary": "s", "archive_markdown": "m"}
    if diags is not None:
        r["diagrams"] = diags
    return r


@pytest.fixture
def one_image(tmp_path):
    root = tmp_path / "assets"
    d = root / "chapter_a/x.assets"
    d.mkdir(parents=True)
    (d / "a.png").write_bytes(b"\x89PNG")
    (d / "b.png").write_bytes(b"\x89PNG")
    return str(root)


def test_cid_refs_finds_all_cids():
    html = '<img src="cid:d1"><p>x</p><img alt="y" src=\'cid:d2\' width="10">'
    assert dg.cid_refs(html) == ["d1", "d2"]


def test_strip_img_tags_removes_only_cid_imgs():
    html = '<p>a</p><img src="cid:d1"><img src="https://x/y.png">'
    out = dg.strip_img_tags(html)
    assert "cid:d1" not in out
    assert "https://x/y.png" in out
    assert "<p>a</p>" in out


def test_sanitize_keeps_valid_diagrams(one_image):
    res = _res('<img src="cid:d1"> CC BY-NC-SA 4.0',
               [{"cid": "d1", "path": "chapter_a/x.assets/a.png", "caption": "圖說"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is True
    assert out["diagrams"][0]["path"] == "chapter_a/x.assets/a.png"
    assert "cid:d1" in out["html"]


def test_sanitize_no_images_at_all_is_fine():
    out, ok = dg.sanitize(_res("<p>純文字</p>"))
    assert ok is True
    assert "diagrams" not in out


def test_sanitize_drops_when_file_missing(one_image):
    res = _res('<img src="cid:d1">',
               [{"cid": "d1", "path": "chapter_a/x.assets/nope.png", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "diagrams" not in out
    assert "<img" not in out["html"]


def test_sanitize_drops_when_html_references_unknown_cid(one_image):
    res = _res('<img src="cid:d1"><img src="cid:d9">',
               [{"cid": "d1", "path": "chapter_a/x.assets/a.png", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "diagrams" not in out
    assert "<img" not in out["html"]


def test_sanitize_drops_when_diagram_never_referenced(one_image):
    res = _res("<p>沒放圖</p>",
               [{"cid": "d1", "path": "chapter_a/x.assets/a.png", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "diagrams" not in out


def test_sanitize_drops_when_over_max(one_image):
    diags = [{"cid": f"d{i}", "path": "chapter_a/x.assets/a.png", "caption": "c"}
             for i in range(dg.MAX_DIAGRAMS + 1)]
    html = "".join(f'<img src="cid:d{i}">' for i in range(dg.MAX_DIAGRAMS + 1))
    out, ok = dg.sanitize(_res(html, diags), one_image)
    assert ok is False


def test_sanitize_rejects_path_traversal(one_image, tmp_path):
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"\x89PNG")
    res = _res('<img src="cid:d1">',
               [{"cid": "d1", "path": "../secret.png", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "diagrams" not in out


def test_sanitize_drops_on_malformed_entry(one_image):
    res = _res('<img src="cid:d1">', [{"cid": "d1"}])  # 缺 path
    assert dg.sanitize(res, one_image)[1] is False
    res = _res('<img src="cid:d1">', "不是 list")
    assert dg.sanitize(res, one_image)[1] is False


def test_sanitize_does_not_mutate_input(one_image):
    res = _res('<img src="cid:d1">',
               [{"cid": "d1", "path": "chapter_a/x.assets/nope.png", "caption": "c"}])
    before = dict(res)
    dg.sanitize(res, one_image)
    assert res == before


def test_abs_paths_joins_assets_root(one_image):
    got = dg.abs_paths([{"cid": "d1", "path": "chapter_a/x.assets/a.png"}], one_image)
    assert got == [("d1", os.path.join(one_image, "chapter_a/x.assets/a.png"))]


def test_abs_paths_of_none_is_empty():
    assert dg.abs_paths(None) == []


def test_sanitize_rejects_null_byte_path_without_raising(one_image):
    # embedded null 讓 os.path.realpath/isfile 直接丟 ValueError；
    # 這裡必須被吃掉當成「不合格」，而不是往上炸穿整個呼叫鏈。
    res = _res('<img src="cid:d1">',
               [{"cid": "d1", "path": "a\x00b", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "diagrams" not in out


@pytest.mark.parametrize("bad_html", [5, ["x"], {"a": 1}, True])
def test_sanitize_non_string_html_returns_cleanly(one_image, bad_html):
    # html 不是字串（呼叫者略過 parse_result 的保證）也不該讓 regex 炸掉。
    res = {"html": bad_html, "topic_complete": False,
           "today_summary": "s", "archive_markdown": "m",
           "diagrams": [{"cid": "d1", "path": "chapter_a/x.assets/a.png", "caption": "c"}]}
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "diagrams" not in out
    # 決定：html 本來就不是字串就沒東西好剝——原樣留著，不用空字串蓋掉呼叫者的值。
    assert out["html"] == bad_html


@pytest.mark.parametrize("bad_html", [5, ["x"], {"a": 1}, True])
def test_sanitize_non_string_html_with_no_diagrams_is_left_untouched(bad_html):
    res = {"html": bad_html, "topic_complete": False,
           "today_summary": "s", "archive_markdown": "m"}
    out, ok = dg.sanitize(res)
    assert ok is True
    assert "diagrams" not in out
    assert out["html"] == bad_html


# ── fix 1: <img src=cid:d1> without quotes is valid HTML and must still be caught ──

def test_cid_refs_finds_unquoted_src():
    assert dg.cid_refs("<img src=cid:d1>") == ["d1"]


def test_strip_img_tags_removes_unquoted_cid_img():
    html = '<p>a</p><img src=cid:d1><p>b</p>'
    out = dg.strip_img_tags(html)
    assert "cid:d1" not in out
    assert "<p>a</p>" in out and "<p>b</p>" in out


def test_strip_img_tags_removes_single_quoted_cid_img():
    html = "<p>a</p><img src='cid:d1'><p>b</p>"
    out = dg.strip_img_tags(html)
    assert "cid:d1" not in out
    assert "<p>a</p>" in out and "<p>b</p>" in out


def test_strip_img_tags_removes_double_quoted_cid_img():
    html = '<p>a</p><img src="cid:d1"><p>b</p>'
    out = dg.strip_img_tags(html)
    assert "cid:d1" not in out
    assert "<p>a</p>" in out and "<p>b</p>" in out


def test_strip_img_tags_leaves_non_cid_img_alone():
    html = '<p>a</p><img src="https://x/y.png" alt="z"><p>b</p>'
    out = dg.strip_img_tags(html)
    assert out == html


def test_sanitize_drops_and_strips_unquoted_img_leaving_no_broken_tag(one_image):
    # 這是最終審查抓到的具體案例：sanitize 判定要剝圖時，strip_img_tags 必須真的
    # 把沒加引號的 <img src=cid:d1> 拿掉，不能因為 regex 只認引號而留下破圖標籤。
    res = _res("<p>x</p><img src=cid:d1>",
               [{"cid": "d1", "path": "chapter_a/x.assets/nope.png", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "<img" not in out["html"]
    assert "<p>x</p>" in out["html"]


# ── fix 3: strip 必須連同 data-fig 標記的整個圖說區塊一起拿掉 ──

_MARKED_BLOCK = (
    '<div style="margin:12px 0;" data-fig="d1">'
    '<img src="cid:d1" alt="圖說">'
    '<div style="font-size:12.5px;">針對這張圖的解說文字。</div>'
    '<div style="font-size:10.5px;">圖：Hello 算法 · CC BY-NC-SA 4.0</div>'
    '</div>'
)

# code review finding 1 的第二輪修正加了大小門檻（見 diagrams.py 的
# _MAX_MARKED_BLOCK_FRACTION）：區塊占整封信超過一半就不整塊拿掉。
# 真實案例裡正常的圖說區塊約占整封信 7.9%——這裡的測試不能只用
# 「before/after 兩個短字串」當信件本文，那樣任何區塊（不管標記得對不對）
# 占比都接近 100%，測不出大小門檻真正要分辨的情況。用這段填充內容陪襯，
# 讓比例貼近真實信件的樣子。
_LESSON_FILLER = "<p>" + "這是佔位用的一般教學內容，用來讓測試裡的比例貼近真實信件的樣子。" * 30 + "</p>"


def test_strip_img_tags_removes_whole_marked_block():
    html = f'<p>before</p>{_LESSON_FILLER}{_MARKED_BLOCK}{_LESSON_FILLER}<p>after</p>'
    out = dg.strip_img_tags(html)
    assert out == f'<p>before</p>{_LESSON_FILLER}{_LESSON_FILLER}<p>after</p>'
    assert "先看圖" not in out and "解說文字" not in out
    assert "CC BY-NC-SA" not in out


def test_strip_img_tags_without_marker_falls_back_to_bare_img_only():
    # 舊格式的 outbox／舊信沒有 data-fig 屬性：只能拔掉 <img> 本身，
    # 周圍的圖說文字與署名原樣留著——這是改動前信件的既有行為，不能被這次改動弄壞。
    html = ('<div style="margin:12px 0;">'
            '<img src="cid:d1" alt="圖說">'
            '<div>針對這張圖的解說文字。</div>'
            '<div>圖：Hello 算法 · CC BY-NC-SA 4.0</div>'
            '</div>')
    out = dg.strip_img_tags(html)
    assert "<img" not in out
    assert "解說文字" in out           # 舊格式沒有標記可用，文字留著
    assert "CC BY-NC-SA" in out


# ── code review finding 1: data-fig 標記位置錯誤時的兩種失效模式 ──

def test_strip_img_tags_mode_a_marker_without_img_keeps_caption_drops_stray_img():
    # Mode A：data-fig="d1" 標到的區塊本身沒有 <img>（模型標錯位置），
    # 圖真正的 <img> 落在區塊外面。修好前：整段標記區塊（含說明文字）被
    # 當成圖說整塊刪掉，但外面那顆孤兒 <img> 沒人管，破圖 tag 留在信裡；
    # 修好後：沒圖的標記區塊不算數、原樣留著，孤兒 <img> 靠無條件的裸圖
    # 清除拔掉。
    html = '<div data-fig="d1">說明</div><p>內文</p><img src="cid:d1">'
    out = dg.strip_img_tags(html)
    assert out == '<div data-fig="d1">說明</div><p>內文</p>'
    assert "<img" not in out
    assert "說明" in out


def test_strip_img_tags_mode_b_marker_on_outer_card_keeps_lesson_body():
    # Mode B：模型把 data-fig="d1" 點到外層的大卡片而不是圖說本身的小
    # wrapper。這個大卡片裡確實包著這個 cid 的 <img>——單看「span 裡有沒有
    # 這個 cid 的圖」這一條，跟正常的小 wrapper 沒有兩樣，光憑這一條沒辦法
    # 從純文字結構分辨「這是圖說本身」還是「這是包了整堂課內容的外層卡片」。
    #
    # 早期修法曾經多加一條「span 裡要有 CC BY-NC-SA 署名才算數」想分辨這兩
    # 種情況，結果引入了更糟的迴歸：凡是圖說湊巧沒把署名複製進那個 span
    # （例如下面 test_strip_img_tags_removes_marked_block_even_without_
    # attribution_line 那個案例），明明是正常小 wrapper 也會被誤判成不算數
    # 而留著不刪，於是那條規則被拿掉了。
    #
    # 後來第二輪 review 抓到：光靠「有沒有圖」這一條，真的遇到外層卡片時
    # 還是會整塊清空，而外層卡片幾乎就是整封信的本文——真實案例量過，正常
    # 圖說區塊約占整封信 7.9%，誤點到外層卡片則是 90%+。改用「這個區塊占
    # 整封信多少比例」當結構訊號：大小不會因為模型的措辭而變，不會重蹈
    # CC BY-NC-SA 那個迴歸的覆轍。這裡的 html 就是這個案例的整個文件本身
    # （卡片占比 100%），遠遠超過 _MAX_MARKED_BLOCK_FRACTION，因此整塊留著
    # 不動，只清裡面的裸 <img>——教學內容保住了。
    html = ('<div class="card" data-fig="d1"><h3>今日小步</h3>'
            '<img src="cid:d1"><p>整堂課</p></div>')
    out = dg.strip_img_tags(html)
    assert out == '<div class="card" data-fig="d1"><h3>今日小步</h3><p>整堂課</p></div>'
    assert "<img" not in out
    assert "今日小步" in out
    assert "整堂課" in out


def test_strip_img_tags_size_guard_falls_back_to_bare_img_when_block_dominates():
    # 跟上面同一個道理，換一個更接近真實信件的比例：卡片占了信件本文
    # 80% 以上，一樣該整塊留著。
    filler = "<p>" + "頭尾一點點內容。" * 3 + "</p>"
    card = ('<div class="card" data-fig="d1"><h3>今日小步</h3>'
            '<img src="cid:d1">' + "<p>今天要講的教學正文。</p>" * 20 + '</div>')
    html = f'{filler}{card}{filler}'
    assert len(card) / len(html) > 0.8
    out = dg.strip_img_tags(html)
    assert "<img" not in out
    assert "今日小步" in out
    assert "今天要講的教學正文。" in out


def test_strip_img_tags_removes_marked_block_even_without_attribution_line():
    # 迴歸測試：正常、data-fig 標對位置的小 wrapper，只是這個 span 裡剛好
    # 沒有署名字串（例如署名寫在別的地方，或這筆測試資料單純沒附）。
    # 只要 span 裡有這個 cid 的圖、而且區塊占比夠小，就該整塊拿掉——不能因為
    # 沒看到署名字串就誤判成「不算數」而讓應該被剝乾淨的圖說文字留在信裡。
    block = ('<div style="margin:12px 0;" data-fig="d1">'
             '<img src="cid:d1"><div>圖說</div></div>')
    html = f'{_LESSON_FILLER}{block}{_LESSON_FILLER}<p>內文</p>'
    out = dg.strip_img_tags(html)
    assert out == f'{_LESSON_FILLER}{_LESSON_FILLER}<p>內文</p>'


def test_strip_img_tags_two_figures_only_one_marked():
    # 兩張圖：d1 有正確的 data-fig 標記（含署名），d2 只是一顆裸 <img>，
    # 沒有任何標記。d1 的整塊圖說要連署名一起清掉；d2 靠無條件的裸圖
    # 清除單獨拔掉，不受 d1 的標記邏輯影響。
    html = f'<p>a</p>{_LESSON_FILLER}{_MARKED_BLOCK}<p>b</p><img src="cid:d2"><p>c</p>{_LESSON_FILLER}'
    out = dg.strip_img_tags(html)
    assert out == f'<p>a</p>{_LESSON_FILLER}<p>b</p><p>c</p>{_LESSON_FILLER}'
    assert "<img" not in out
    assert "CC BY-NC-SA" not in out


def test_sanitize_drop_removes_whole_marked_block(one_image):
    html = f'<p>before</p>{_LESSON_FILLER}{_MARKED_BLOCK}{_LESSON_FILLER}<p>after</p>'
    res = _res(html, [{"cid": "d1", "path": "chapter_a/x.assets/nope.png", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert out["html"] == f'<p>before</p>{_LESSON_FILLER}{_LESSON_FILLER}<p>after</p>'


# ── fix 4: 沒有留下署名子字串 CC BY-NC-SA，diagrams 就要被剝掉 ──

def test_sanitize_drops_when_attribution_missing(one_image):
    res = _res('<img src="cid:d1">（沒有署名）',
               [{"cid": "d1", "path": "chapter_a/x.assets/a.png", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "diagrams" not in out


def test_sanitize_tolerates_attribution_wording_variation(one_image):
    # 只認短字串 "CC BY-NC-SA"：署名整句的措辭／連結文字有變化也不該讓圖被剝掉，
    # 否則文案上無傷大雅的差異就會白白讓信少了圖，比它想防的問題還糟。
    html = '<img src="cid:d1">圖片來源：Hello 算法，授權 CC BY-NC-SA 4.0 國際版'
    res = _res(html, [{"cid": "d1", "path": "chapter_a/x.assets/a.png", "caption": "c"}])
    out, ok = dg.sanitize(res, one_image)
    assert ok is True
    assert out["diagrams"][0]["cid"] == "d1"


# ── fix 9: 副檔名不在 _IMAGE_EXTS 就不合格（例如選到 LICENSE） ──

def test_sanitize_rejects_non_image_extension(tmp_path):
    root = tmp_path / "assets"
    root.mkdir()
    (root / "LICENSE").write_text("MIT-ish licence text", encoding="utf-8")
    res = _res('<img src="cid:d1"> CC BY-NC-SA 4.0',
               [{"cid": "d1", "path": "LICENSE", "caption": "c"}])
    out, ok = dg.sanitize(res, str(root))
    assert ok is False
    assert "diagrams" not in out


def test_abs_paths_uses_get_not_bracket_indexing():
    # 缺 key 時要回傳 None／組出帶空字串的路徑，而不是 KeyError 往上炸穿。
    got = dg.abs_paths([{"cid": "d1"}], "/assets")
    assert got == [("d1", "/assets/")]


# ── code review finding 5：sanitize 剝圖時，archive_markdown 要跟 html 一起剝 ──

def test_strip_hello_algo_images_from_markdown_removes_image_and_attribution():
    md = (
        "## Day 1\n\n"
        "一些說明文字。\n\n"
        "![說明](https://raw.githubusercontent.com/krahets/hello-algo/main/"
        "zh-hant/docs/made_up.png)\n"
        "圖：[Hello 算法](https://www.hello-algo.com/) · CC BY-NC-SA 4.0\n\n"
        "後續內容。"
    )
    out = dg.strip_hello_algo_images_from_markdown(md)
    assert "made_up.png" not in out
    assert "CC BY-NC-SA" not in out
    assert "hello-algo.com" not in out
    assert "## Day 1" in out
    assert "一些說明文字。" in out
    assert "後續內容。" in out


def test_strip_hello_algo_images_from_markdown_leaves_legit_images_and_links():
    # 保守：只清 hello-algo raw URL 的圖片＋緊接的署名行，模型自己寫的其他
    # 圖片與連結原封不動——這條規則不該連帶清掉跟 hello-algo 無關的內容。
    md = (
        "![別的圖](https://example.com/other.png)\n"
        "參考 [某篇文件](https://example.com/doc) 有更多說明。\n"
        "![孤立的 hello-algo 圖，沒有署名行](https://raw.githubusercontent.com/"
        "krahets/hello-algo/main/zh-hant/docs/x.png)\n"
        "這行不是署名，不該被一起清掉。"
    )
    out = dg.strip_hello_algo_images_from_markdown(md)
    assert "![別的圖](https://example.com/other.png)" in out
    assert "[某篇文件](https://example.com/doc)" in out
    # 圖片行本身仍然是 hello-algo raw URL，一樣會被清掉；但因為下一行不是
    # 署名行的形狀，那一行必須原封不動地留著。
    assert "x.png" not in out
    assert "這行不是署名，不該被一起清掉。" in out


def test_strip_hello_algo_images_from_markdown_handles_non_string_and_empty():
    assert dg.strip_hello_algo_images_from_markdown(None) is None
    assert dg.strip_hello_algo_images_from_markdown("") == ""
    assert dg.strip_hello_algo_images_from_markdown(5) == 5


def test_sanitize_drop_also_strips_archive_markdown(one_image):
    # 這是 finding 5 的具體重現：bogus path → ok=False、html 剝乾淨了，
    # 但改動前 archive_markdown 還留著同一張圖的 markdown 語法與署名。
    md = (
        "## Day 1\n\n"
        "![說明](https://raw.githubusercontent.com/krahets/hello-algo/main/"
        "zh-hant/docs/made_up.png)\n"
        "圖：[Hello 算法](https://www.hello-algo.com/) · CC BY-NC-SA 4.0\n\n"
        "其餘課程內容。"
    )
    res = {
        "html": '<img src="cid:d1">',
        "topic_complete": False,
        "today_summary": "s",
        "archive_markdown": md,
        "diagrams": [{"cid": "d1", "path": "chapter_a/x.assets/nope.png", "caption": "c"}],
    }
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "<img" not in out["html"]
    assert "made_up.png" not in out["archive_markdown"]
    assert "CC BY-NC-SA" not in out["archive_markdown"]
    assert "其餘課程內容。" in out["archive_markdown"]


def test_sanitize_drop_leaves_non_hello_algo_markdown_image_untouched(one_image):
    # 自我審查要求的具體案例：合法、跟 hello-algo 無關的圖片／連結不該被
    # sanitize 的剝圖邏輯連帶清掉。
    md = (
        "說明文字，附一張跟 hello-algo 無關的圖。\n"
        "![截圖](https://example.com/screenshot.png)\n"
        "也參考 [官方文件](https://example.com/docs)。"
    )
    res = {
        "html": '<img src="cid:d1">',
        "topic_complete": False,
        "today_summary": "s",
        "archive_markdown": md,
        "diagrams": [{"cid": "d1", "path": "chapter_a/x.assets/nope.png", "caption": "c"}],
    }
    out, ok = dg.sanitize(res, one_image)
    assert ok is False
    assert "![截圖](https://example.com/screenshot.png)" in out["archive_markdown"]
    assert "[官方文件](https://example.com/docs)" in out["archive_markdown"]


def test_sanitize_keeps_archive_markdown_untouched_when_diagrams_are_valid(one_image):
    md = (
        "![說明](https://raw.githubusercontent.com/krahets/hello-algo/main/"
        "zh-hant/docs/chapter_a/x.assets/a.png)\n"
        "圖：[Hello 算法](https://www.hello-algo.com/) · CC BY-NC-SA 4.0"
    )
    res = {
        "html": '<img src="cid:d1"> CC BY-NC-SA 4.0',
        "topic_complete": False,
        "today_summary": "s",
        "archive_markdown": md,
        "diagrams": [{"cid": "d1", "path": "chapter_a/x.assets/a.png", "caption": "c"}],
    }
    out, ok = dg.sanitize(res, one_image)
    assert ok is True
    assert out["archive_markdown"] == md
