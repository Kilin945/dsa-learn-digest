import build_lesson as bl


def test_daily_context_contains_topic_step_and_colors():
    ctx = bl.format_daily_context(
        goal="學 Spring Boot",
        topic="IoC 與依賴注入：為什麼不要自己 new",
        step=2,
        covered=["Day1：自己 new 會綁死"],
        yesterday="自己 new 會綁死：難換難測",
        color=("#f2f6e8", "#88a83f", "#6e8c28"),
        today="2026-06-07",
    )
    assert "GOAL: 學 Spring Boot" in ctx
    assert "TOPIC: IoC 與依賴注入" in ctx
    assert "STEP: 2" in ctx
    assert "- Day1：自己 new 會綁死" in ctx
    assert "YESTERDAY_SUMMARY: 自己 new 會綁死：難換難測" in ctx
    assert "COLOR_BG: #f2f6e8" in ctx
    assert "COLOR_BAR: #88a83f" in ctx
    assert "DATE: 2026-06-07" in ctx


def test_daily_context_marks_no_yesterday_for_first_lesson():
    ctx = bl.format_daily_context(
        goal="g", topic="t", step=1, covered=[], yesterday=None,
        color=("#a", "#b", "#c"), today="2026-06-07",
    )
    assert "YESTERDAY_SUMMARY: （無，這是第一課）" in ctx


def test_finished_sentinel():
    assert bl.format_finished() == "STATUS: FINISHED"


def test_weekly_context_lists_week_rows():
    rows = [
        {"date": "2026-06-02", "topic": "IoC", "step": 1, "summary": "s1"},
        {"date": "2026-06-03", "topic": "IoC", "step": 2, "summary": "s2"},
    ]
    ctx = bl.format_weekly_context(goal="g", rows=rows,
                                   color=("#a", "#b", "#c"), today="2026-06-07")
    assert "THIS_WEEK:" in ctx
    assert "2026-06-02 [IoC #1] s1" in ctx
    assert "2026-06-03 [IoC #2] s2" in ctx
    assert "DATE: 2026-06-07" in ctx


def test_daily_context_includes_available_diagrams():
    out = bl.format_daily_context(
        goal="G", topic="T", step=1, covered=[], yesterday=None,
        color=("#bg", "#bar", "#txt"), today="2026-09-06",
        available="AVAILABLE_DIAGRAMS:\n- chapter_a/x.assets/a.png",
    )
    assert "AVAILABLE_DIAGRAMS:" in out
    assert "- chapter_a/x.assets/a.png" in out
    # 既有欄位不能被擠掉
    assert "TOPIC: T" in out
    assert "COLOR_TXT: #txt" in out


def test_daily_context_without_diagrams_is_unchanged():
    kwargs = dict(goal="G", topic="T", step=1, covered=[], yesterday=None,
                  color=("#bg", "#bar", "#txt"), today="2026-09-06")
    assert bl.format_daily_context(**kwargs) == bl.format_daily_context(**kwargs, available="")
    assert "AVAILABLE_DIAGRAMS" not in bl.format_daily_context(**kwargs)


def test_daily_main_emits_available_diagrams(tmp_path, capsys, monkeypatch):
    import diagrams as dg
    syl = tmp_path / "syllabus.txt"
    syl.write_text("主題甲\n", encoding="utf-8")
    prog = tmp_path / "progress.json"
    prog.write_text('{"current_index": 0, "step": 1, "covered": [], "completed_topics": []}',
                    encoding="utf-8")
    hist = tmp_path / "history.jsonl"
    hist.write_text("", encoding="utf-8")

    assets = tmp_path / "assets"
    (assets / "chapter_a/x.assets").mkdir(parents=True)
    (assets / "chapter_a/x.assets/a.png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(dg, "ASSETS_ROOT", str(assets))
    monkeypatch.setattr(dg, "load_map", lambda path=None: {"主題甲": ["chapter_a/x.assets"]})

    bl.main(["daily", "--syllabus", str(syl), "--progress", str(prog), "--history", str(hist)])
    out = capsys.readouterr().out
    assert "AVAILABLE_DIAGRAMS:" in out
    assert "chapter_a/x.assets/a.png" in out
