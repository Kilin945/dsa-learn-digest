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
    res = _res('<img src="cid:d1">',
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
