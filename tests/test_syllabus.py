import os
import json
import state_store as ss

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYLLABUS = os.path.join(HERE, "syllabus.txt")
PROGRESS = os.path.join(HERE, "state", "progress.json")

# 凍結規則不是「前兩行」這種寫死的快照，而是相對 current_index 的：
# syllabus.txt 裡索引 <= current_index 的每一行都已經被寄出過或正在教，
# 動它的文字、或在它前面插入新的非註解行，都會讓 progress.json 的 index
# 對錯主題——這條凍結線會隨 current_index 每隔幾天往前推進一次，不是釘死
# 在某個行數（過去釘死在「前兩行」的寫法，current_index 一過就直接失效
# 卻還是綠燈，等於沒守到）。
#
# 下面這份清單記錄「目前已知被凍結」的每一行原文。current_index 往前推進、
# 多凍結一行時，要把新凍結的那一行加進來——如果忘了加，_frozen_len() 算出的
# 凍結長度會超過這份清單，比較長度不同就會讓下面的測試炸掉，逼你回來補。
PINNED = [
    "Big-O 複雜度：怎麼估一段程式的快慢",
    "陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處",
    "空間複雜度：記憶體也要算，遞迴呼叫堆疊的隱藏成本",
]

# state/progress.json 是連到 ../state worktree 的 symlink，CI checkout 通常看不到它
# （這裡也只讀不寫）。看不到或壞掉就退回原本寫死的前兩行——那兩個主題已經寄出去
# 完全教完，不管 current_index 走到哪都永遠凍結；沒有 state 就沒辦法確認再往後
# 幾行是不是也該凍結，所以保守只守這兩行，而不是猜一個可能太寬或太窄的數字。
_FALLBACK_FROZEN = 2


def _frozen_len():
    if not os.path.exists(PROGRESS):
        return _FALLBACK_FROZEN
    try:
        with open(PROGRESS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _FALLBACK_FROZEN
    idx = data.get("current_index") if isinstance(data, dict) else None
    if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
        return _FALLBACK_FROZEN
    return idx + 1


def test_pinned_prefix_through_current_index_unchanged():
    topics = ss.load_syllabus(SYLLABUS)
    n = _frozen_len()
    assert topics[:n] == PINNED[:n]


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
