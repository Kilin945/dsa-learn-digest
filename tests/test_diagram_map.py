import os
import state_store as ss
import diagrams as dg

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYLLABUS = os.path.join(HERE, "syllabus.txt")

# 這些主題 hello-algo 沒有對應章節（解題技巧與總結型主題），刻意留空。
NO_IMAGE_TOPICS = 9


def test_every_syllabus_topic_is_a_key():
    topics = ss.load_syllabus(SYLLABUS)
    dmap = dg.load_map()
    missing = [t for t in topics if t not in dmap]
    assert missing == [], f"課綱有主題沒登記進 diagram_map.json：{missing}"


def test_no_stale_keys():
    topics = set(ss.load_syllabus(SYLLABUS))
    stale = [k for k in dg.load_map() if k not in topics]
    assert stale == [], f"diagram_map.json 有課綱裡已不存在的主題：{stale}"


def test_every_mapped_dir_exists():
    bad = []
    for topic, dirs in dg.load_map().items():
        for d in dirs:
            if not os.path.isdir(os.path.join(dg.ASSETS_ROOT, d)):
                bad.append((topic, d))
    assert bad == [], f"指到不存在的目錄：{bad}"


def test_expected_number_of_topics_have_no_images():
    empty = [t for t, dirs in dg.load_map().items() if not dirs]
    assert len(empty) == NO_IMAGE_TOPICS, f"沒圖的主題：{empty}"


def test_mapped_topics_actually_yield_candidates():
    dmap = dg.load_map()
    dry = [t for t, dirs in dmap.items() if dirs and not dg.candidates_for(t, dmap)]
    assert dry == [], f"有登記目錄卻撈不到任何圖：{dry}"
