import os
import state_store as ss

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYLLABUS = os.path.join(HERE, "syllabus.txt")

# 這兩行對應 progress.json 的 current_index 0 / 1，動了會讓整串庫存寄不出去。
PINNED = [
    "Big-O 複雜度：怎麼估一段程式的快慢",
    "陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處",
]


def test_pinned_first_two_topics_unchanged():
    topics = ss.load_syllabus(SYLLABUS)
    assert topics[:2] == PINNED


def test_syllabus_has_44_topics():
    assert len(ss.load_syllabus(SYLLABUS)) == 44


def test_no_duplicate_topics():
    topics = ss.load_syllabus(SYLLABUS)
    assert len(topics) == len(set(topics))


def test_sorting_chapter_present():
    # 舊課綱整章缺席排序演算法，這是這次改版的主要動機之一。
    topics = ss.load_syllabus(SYLLABUS)
    joined = "\n".join(topics)
    for expected in ["快速排序", "合併排序", "堆積排序", "分治", "平衡樹 AVL"]:
        assert expected in joined
