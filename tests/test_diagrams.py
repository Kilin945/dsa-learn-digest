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
