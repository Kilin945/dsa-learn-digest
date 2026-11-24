import os
import json
import state_store as ss

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYLLABUS = os.path.join(HERE, "syllabus.txt")
PROGRESS = os.path.join(HERE, "state", "progress.json")
HISTORY = os.path.join(HERE, "state", "history.jsonl")

# 凍結規則：syllabus.txt 裡索引 <= current_index 的每一行都已經寄出過或正在教，
# 動它的文字、或在它前面插入新的非註解行，都會讓 progress.json 的 index 對錯主題。
#
# 對照的「原文」不手抄，直接讀寄信時留下的紀錄：progress.json 的 completed_topics
# 是每個教完的主題原文（依序），正在教的那一行（current_index）則看 history.jsonl
# 最後一筆的 topic。凍結線隨 current_index 前進時，這兩份紀錄也跟著長，測試不用改。
#
# state/ 是連到 ../state worktree 的 symlink，CI checkout 通常看不到它（這裡也只讀不寫）。
# 看不到或壞掉就只守前兩行：那兩個主題早已教完，不管進度走到哪都永遠凍結；
# 沒有 state 就確認不了再往後幾行，所以保守只守這兩行。
FALLBACK_PINNED = [
    "Big-O 複雜度：怎麼估一段程式的快慢",
    "陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處",
]


def _frozen_reference():
    """回傳凍結區每一行應有的原文；讀不到 state 時回傳 FALLBACK_PINNED。"""
    try:
        with open(PROGRESS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return FALLBACK_PINNED
    if not isinstance(data, dict):
        return FALLBACK_PINNED
    idx = data.get("current_index")
    done = data.get("completed_topics")
    if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0 or not isinstance(done, list):
        return FALLBACK_PINNED
    ref = [c.get("topic") for c in done if isinstance(c, dict)]
    # 正在教的主題已經寄出至少一篇（covered 非空）才算凍結
    if data.get("covered"):
        try:
            with open(HISTORY, encoding="utf-8") as f:
                last = [l for l in f if l.strip()][-1]
            ref.append(json.loads(last)["topic"])
        except (OSError, ValueError, IndexError, KeyError):
            pass
    return ref


def test_pinned_prefix_through_current_index_unchanged():
    topics = ss.load_syllabus(SYLLABUS)
    ref = _frozen_reference()
    assert topics[:len(ref)] == ref


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
