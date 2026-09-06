# 課綱改版、課程配圖、信件格式改版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把課綱從 24 條解題導向改成 44 條系統性 DSA 課綱，每封學習信配上 hello-algo 的繁中圖解，並把 LeetCode 區塊從一句話推薦擴成含完整 Java 解答的解題導引。

**Architecture:** 圖庫（506 張繁中 PNG）vendored 進 `assets/hello-algo/`，所以圖跟著 repo 一起被 GitHub Actions checkout，outbox 只存相對路徑、不存 base64。新增 `diagrams.py` 集中處理「主題→候選圖」與「claude 選圖結果的驗證／剝除」，`build_lesson.py` 把候選清單餵給 claude、`apply_result.py` 驗證並輸出圖清單、`send_email.py` 以 CID 內嵌（Gmail 不支援 data: URI 與 SVG）。任何圖片相關失敗一律降級成純文字信，絕不擋信。

**Tech Stack:** Python 3（僅標準庫，`requirements.txt` 只有 pytest）、zsh（`run_learn.sh`）、bash（GitHub Actions）、Gmail SMTP。

**Spec:** `docs/superpowers/specs/2026-09-06-syllabus-diagrams-format-design.md`

## Global Constraints

- **課綱前兩行逐字不動、不得在其之前插入任何非註解行。** 這兩行是 `Big-O 複雜度：怎麼估一段程式的快慢` 與 `陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處`。`progress.json` 的 `current_index`（目前為 1）索引的是課綱裡**非註解行的序號**；動了它就會指向錯誤主題，且 `outbox_ready()` 的 index 比對會失敗，導致整串庫存都寄不出去。
- **圖是加分項，任何圖片相關的失敗都不得阻擋信件寄出。** 驗證不過就整批剝掉圖、信照常走。
- **`diagrams` 是選用欄位，不得加入 `apply_result.REQUIRED`。** REQUIRED 維持 `("html", "topic_complete", "today_summary", "archive_markdown")`。outbox 裡現存那篇舊格式沒有這個欄位，必須能照常寄出。
- **每封信最多 2 張圖**（`diagrams.MAX_DIAGRAMS = 2`）。
- **圖片授權 CC BY-NC-SA 4.0。** 每張圖下方必須有署名 `圖：Hello 算法 · CC BY-NC-SA 4.0`，連結 <https://www.hello-algo.com/>。圖原封不動使用，不裁切不加工。`dsa-learn-digest` 與 `dsa-learn-state` 兩個 repo 必須維持私有。
- **Gmail 限制**：不支援 `<img src="data:...">`、不支援 SVG、不支援 `<details>` 展開。只能用 CID 內嵌。
- 既有測試全數必須維持綠燈：`python3 -m pytest -v`。
- 只用 Python 標準庫，不新增任何 pip 依賴。

---

### Task 1: 新課綱與信件格式（不含圖）

先上這一步，因為它只改兩個文字檔、不碰任何程式，可以獨立驗證。圖片版型留到 Task 7。

**Files:**
- Modify: `syllabus.txt`（整份換掉，前兩行逐字保留）
- Modify: `prompt_daily.txt`（LeetCode 區塊、篇幅原則）
- Test: `tests/test_syllabus.py`（新增）

**Interfaces:**
- Consumes: 無
- Produces: `syllabus.txt` 的 44 條主題字串，Task 3 的 `diagram_map.json` 的 key 必須與這些字串**逐字相同**。

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_syllabus.py`：

```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_syllabus.py -v`
Expected: FAIL — `test_syllabus_has_44_topics` 會得到 24；`test_sorting_chapter_present` 找不到「快速排序」。

- [ ] **Step 3: 換掉 syllabus.txt**

整份覆寫成以下內容（前兩行逐字保留原樣）：

```
# dsa-learn-digest 課綱：目標 = 有 Java 基礎，系統性學會資料結構與演算法
# 一行一主題，# 為註解/分章。每天教「目前主題的下一小步」，主題走完才換下一行。
#
# ⚠️ 前兩行（Big-O、陣列）對應 progress.json 的 current_index 0 / 1。
#    不要改它們的文字，也不要在它們之前插入任何非註解行 ——
#    current_index 索引的是「非註解行的序號」，位移了會讓 outbox 的 index
#    比對失敗，整串庫存都寄不出去。第 3 行之後可自由增刪。

# ── M1 複雜度：先學會怎麼衡量 ──
Big-O 複雜度：怎麼估一段程式的快慢
陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處
空間複雜度：記憶體也要算，遞迴呼叫堆疊的隱藏成本
迭代與遞迴：兩種重複的形式、呼叫堆疊與尾遞迴

# ── M2 線性結構 ──
陣列上的掃描技巧：雙指標、滑動視窗、前綴和
字串 String：不可變性、StringBuilder 與字元陣列的關係
Linked List 基礎：節點、指標與 dummy head 技巧
鏈結串列的指標技巧：快慢指標找中點與判環、反轉串列
Stack 堆疊：後進先出、括號配對與單調堆疊
Queue 佇列與 Deque：先進先出、環形佇列與雙端佇列

# ── M3 雜湊表 ──
HashMap / HashSet：O(1) 查找的原理與代價
雜湊函式與負載因子：hashCode、擴容與 rehash
雜湊衝突：鏈結法 chaining 與開放定址 open addressing

# ── M4 樹 ──
Binary Tree 基礎：節點、深度與陣列表示法
二元樹走訪：前序/中序/後序 DFS 與 BFS 層序
Binary Search Tree：中序走訪的有序性與插入刪除
平衡樹 AVL：BST 為什麼會退化、旋轉怎麼救回來
樹的經典題型：深度、直徑、最近共同祖先 LCA

# ── M5 堆積 ──
Heap / PriorityQueue：完全二元樹、上浮下沉與 Top-K

# ── M6 圖 ──
圖的表示法：鄰接矩陣與鄰接表的取捨
圖的走訪：DFS / BFS、連通塊與島嶼問題
拓撲排序 Topological Sort：有依賴關係的排程
最短路徑入門：BFS 解無權圖、Dijkstra 概念

# ── M7 搜尋 ──
Binary Search 基礎：邊界條件寫對的固定套路
二分搜尋變形：找左界/右界、插入點、旋轉陣列
答案空間二分：對「答案」而不是「索引」二分
搜尋演算法總覽：線性、二分、雜湊、樹搜尋怎麼選

# ── M8 排序 ──
排序的評價標準：穩定性、原地性、自適應性
基礎排序：選擇、氣泡、插入排序與它們的 O(n²)
快速排序 Quick Sort：分割 partition 與最壞情況
合併排序 Merge Sort：分治的代表作與穩定性
堆積排序 Heap Sort：用堆積把排序做到原地 O(n log n)
線性時間排序：計數、桶、基數排序的適用條件
排序的應用：合併區間、會議室與自訂 Comparator

# ── M9 分治與回溯 ──
分治 Divide and Conquer：把問題切小再合併
回溯 Backtracking：排列、組合、子集的模板
回溯經典題：N 皇后與剪枝

# ── M10 動態規劃 ──
DP 入門：從暴力遞迴到記憶化再到列表格
DP 問題的特徵：最優子結構與無後效性
一維 DP：爬樓梯、打家劫舍套路
背包問題：0-1 背包與完全背包
字串 DP：LCS 與編輯距離

# ── M11 貪婪與收尾 ──
Greedy 貪心：什麼時候可以貪、怎麼證明
面試解題流程總整理：從讀題到說出複雜度
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python3 -m pytest tests/test_syllabus.py -v`
Expected: 4 passed

- [ ] **Step 5: 確認進度沒有被打亂**

Run:
```bash
python3 -c "
import state_store as ss
s = ss.load_syllabus('syllabus.txt')
p = ss.load_progress('state/progress.json')
print('current_index =', p['current_index'], '→', ss.current_topic(s, p))
print('step =', p['step'])
"
python3 apply_result.py --outbox-ready && echo "outbox OK"
```
Expected:
```
current_index = 1 → 陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處
step = 4
outbox OK
```
若 `current_index` 指到別的主題，或 `--outbox-ready` 非 0，**停下來**——課綱前兩行被動到了。

- [ ] **Step 6: 改 prompt_daily.txt 的 LeetCode 區塊與篇幅原則**

在【教學原則】區塊，把這一行：

```
- 篇幅以 5 分鐘讀完為準。
```

改成：

```
- 篇幅：該長才長，不要湊字數，也不要為了短而砍掉必要的解說。
```

把這一行：

```
- 今日小步講完後，推薦 1 題最能練到今天概念的 LeetCode 題（附題號、題名、難度與連結 https://leetcode.com/problems/<slug>/），一句話說明「為什麼是這題」。放在術語表之前，用同樣的卡片風格。
```

改成：

```
- 今日小步講完後，出 1 題最能練到今天概念的 LeetCode 題，並把解法完整寫出來。放在術語表之前。依序寫：
  1) 題號、題名、難度、連結 https://leetcode.com/problems/<slug>/
  2) 「題目在說什麼」——白話翻譯一次，讓人不點進去也知道在幹嘛
  3) 「怎麼用今天學的東西解」——條列步驟，把今日概念跟這題的關聯講明
  4) 複雜度——時間與空間，各附一句「為什麼」
  5) 完整 Java 解答，關鍵行加註解
  有多種解法時只寫最容易理解的那一種，不要列舉全部。不要試圖隱藏答案（信件無法摺疊）——
  看得到答案照著抄一遍，勝過看不到答案就不動手。
```

- [ ] **Step 7: 換掉 prompt_daily.txt 的 LeetCode 版型**

把【html 版型】裡這個區塊：

```html
  <div style="background:#fbfcf8;border:1px solid #e2e6da;border-radius:10px;padding:13px 16px;margin-bottom:14px;">
    <div style="font-size:13px;font-weight:800;color:TXT;margin-bottom:6px;">🎯 今日練習 · LeetCode</div>
    <div style="font-size:13px;color:#2c3340;line-height:1.65;"><a href="題目連結" style="color:#3b6cf6;text-decoration:none;font-weight:700;">#題號 題名</a>（難度）— 一句話說明為什麼這題最能練到今天的概念。</div>
  </div>
```

換成：

```html
  <div style="background:#fbfcf8;border:1px solid #e2e6da;border-radius:10px;padding:13px 16px;margin-bottom:14px;">
    <div style="font-size:13px;font-weight:800;color:TXT;margin-bottom:8px;">🎯 動手寫 · LeetCode</div>
    <div style="font-size:13.5px;margin-bottom:10px;"><a href="題目連結" style="color:#3b6cf6;text-decoration:none;font-weight:700;">#題號 題名</a> <span style="color:#8a909c;font-size:12px;">（難度）</span></div>
    <div style="font-size:12.5px;color:#3b424f;line-height:1.65;margin-bottom:10px;"><b style="color:TXT;">題目在說什麼</b><br>白話翻譯一次。</div>
    <div style="font-size:12.5px;color:#3b424f;line-height:1.65;margin-bottom:10px;"><b style="color:TXT;">怎麼用今天學的東西解</b>
      <ol style="margin:6px 0 0;padding-left:20px;line-height:1.7;"><li>步驟</li></ol>
    </div>
    <div style="font-size:12.5px;color:#3b424f;line-height:1.65;margin-bottom:10px;"><b style="color:TXT;">複雜度</b>　時間 O(?) — 為什麼；空間 O(?) — 為什麼。</div>
    <div style="background:#1f2430;border-radius:8px;padding:12px 14px;overflow-x:auto;"><pre style="margin:0;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:12.5px;line-height:1.6;color:#e6e6e6;">完整 Java 解答</pre></div>
  </div>
```

- [ ] **Step 8: 實跑一次確認 claude 產得出新格式**

Run: `zsh run_learn.sh daily`

檢查 `run.log` 尾端沒有 `RESULT ... FAIL`，且產出的 HTML 含「動手寫 · LeetCode」與一段 Java 程式碼區塊。

**注意**：這會產一篇新的進 outbox。若 outbox 已有備妥的一篇，`run_learn.sh` 的既有邏輯會判斷不需重產。要強制看到新格式，改用不動狀態的方式驗證：

```bash
python3 build_lesson.py daily > /tmp/ctx.txt
{ cat prompt_daily.txt; echo; cat /tmp/ctx.txt; } | claude -p --output-format text > /tmp/out.json
python3 apply_result.py < /tmp/out.json | head -60
```

- [ ] **Step 9: Commit**

```bash
git add syllabus.txt prompt_daily.txt tests/test_syllabus.py
git commit -m "feat: rework syllabus into a systematic DSA curriculum and expand the LeetCode block

The old 24-topic list treated problem-solving techniques (two pointers,
sliding window, prefix sum) as standalone topics while omitting whole
chapters: sorting algorithms, divide and conquer, balanced trees (AVL)
and hashing internals. Techniques now fold into the module of the
structure they depend on, as their own topic line rather than extra
steps piled onto an existing one -- a topic's step count is decided by
the model from COVERED_SO_FAR, and a 12-step topic makes that judgement
unreliable.

The first two lines are pinned verbatim. progress.json current_index
indexes non-comment lines, so shifting them would desync outbox_ready()
and block the whole queue from sending. tests/test_syllabus.py guards
this.

The LeetCode block grows from a one-line recommendation into a full
walkthrough with the Java solution inline. No attempt to hide the
answer: email cannot collapse content, and copying a visible solution
beats skipping the exercise entirely."
```

---

### Task 2: Vendored hello-algo 圖庫

**Files:**
- Create: `assets/hello-algo/**`（506 張 PNG/GIF/JPG，保留原目錄結構）
- Create: `assets/hello-algo/LICENSE`
- Create: `assets/hello-algo/README.md`
- Test: `tests/test_assets.py`（新增）

**Interfaces:**
- Consumes: 無
- Produces: `assets/hello-algo/<chapter_xxx>/<yyy>.assets/<zzz>.png` 的檔案結構。Task 3 的 `diagram_map.json` 的 value 是相對於 `assets/hello-algo/` 的目錄路徑。

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_assets.py`：

```python
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets", "hello-algo")


def _all_images():
    out = []
    for root, _dirs, files in os.walk(ASSETS):
        for name in files:
            if name.lower().endswith((".png", ".gif", ".jpg")):
                out.append(os.path.join(root, name))
    return out


def test_assets_dir_exists():
    assert os.path.isdir(ASSETS)


def test_license_is_vendored():
    # CC BY-NC-SA 4.0 要求署名；授權原文必須跟著圖一起留在 repo 裡。
    with open(os.path.join(ASSETS, "LICENSE"), encoding="utf-8") as f:
        assert "Attribution-NonCommercial-ShareAlike 4.0" in f.read()


def test_image_count():
    assert len(_all_images()) == 506


def test_known_images_present():
    for rel in [
        "chapter_array_and_linkedlist/array.assets/array_definition.png",
        "chapter_searching/binary_search.assets/binary_search_step1.png",
        "chapter_tree/avl_tree.assets/avltree_degradation_and_rotation.png",
    ]:
        assert os.path.isfile(os.path.join(ASSETS, rel)), rel
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_assets.py -v`
Expected: 全部 FAIL — `assets/hello-algo` 還不存在。

- [ ] **Step 3: 抓圖進 repo**

```bash
rm -rf /tmp/hello-algo
git clone --depth 1 --filter=blob:none --sparse https://github.com/krahets/hello-algo.git /tmp/hello-algo
git -C /tmp/hello-algo sparse-checkout set zh-hant/docs LICENSE

mkdir -p assets/hello-algo
rsync -am \
  --include='*/' \
  --include='*.png' --include='*.gif' --include='*.jpg' \
  --exclude='*' \
  /tmp/hello-algo/zh-hant/docs/ assets/hello-algo/
cp /tmp/hello-algo/LICENSE assets/hello-algo/LICENSE

# 對不上就停下來查，別硬幹
echo "圖數：$(find assets/hello-algo -type f \( -name '*.png' -o -name '*.gif' -o -name '*.jpg' \) | wc -l)"
echo "大小：$(du -sh assets/hello-algo | cut -f1)"
```

Expected: 圖數 506，大小約 12M。

若上游有更新導致數字不同，**先確認 `tests/test_assets.py` 的 506 要不要跟著改**，不要直接改測試遷就結果——數字對不上代表上游動過，值得看一眼動了什麼。

- [ ] **Step 4: 寫來源說明**

建立 `assets/hello-algo/README.md`：

```markdown
# hello-algo 繁中圖解（vendored）

來源：<https://github.com/krahets/hello-algo> 的 `zh-hant/docs/`，只取圖檔，保留原目錄結構。
授權：CC BY-NC-SA 4.0（見同目錄 `LICENSE`）。

## 使用規則

- **署名**：每張圖在信件與歸檔 markdown 裡都必須附 `圖：Hello 算法 · CC BY-NC-SA 4.0`，
  連結 <https://www.hello-algo.com/>。
- **不改作**：原封不動使用，不裁切、不加工、不重繪。一旦改作，衍生物也要掛同一個授權。
- **非商業**：本專案是寄給本人一人的學習信，屬非商業使用。
- **repo 必須維持私有**。私有 repo 沒有散布行為，授權壓力最小。
  若日後轉公開、或啟用 Notion 同步並把頁面分享出去，須確保署名仍在。

## 更新方式

```bash
rm -rf /tmp/hello-algo
git clone --depth 1 --filter=blob:none --sparse https://github.com/krahets/hello-algo.git /tmp/hello-algo
git -C /tmp/hello-algo sparse-checkout set zh-hant/docs LICENSE
rsync -am --include='*/' --include='*.png' --include='*.gif' --include='*.jpg' --exclude='*' \
  /tmp/hello-algo/zh-hant/docs/ assets/hello-algo/
cp /tmp/hello-algo/LICENSE assets/hello-algo/LICENSE
python3 -m pytest tests/test_assets.py tests/test_diagram_map.py -v
```

更新後兩個測試都要重跑：圖數會變（要改 `test_assets.py` 的期待值），
`diagram_map.json` 指到的目錄也可能被上游改名。
```

- [ ] **Step 5: 執行測試確認通過**

Run: `python3 -m pytest tests/test_assets.py -v`
Expected: 4 passed

若 `test_known_images_present` 掛在 avl_tree 那張，用 `ls assets/hello-algo/chapter_tree/avl_tree.assets/` 找實際檔名並更正測試（上游檔名可能與本計畫撰寫時不同）。

- [ ] **Step 6: Commit**

```bash
git add assets/hello-algo tests/test_assets.py
git commit -m "chore: vendor 506 Traditional Chinese diagrams from hello-algo

Images come from krahets/hello-algo zh-hant/docs, licensed CC BY-NC-SA
4.0. Vendored rather than fetched on demand: lessons are prepared on the
laptop and sent from GitHub Actions, so the images have to travel
through git anyway. Keeping them as files in the repo means Actions gets
them from checkout and outbox.json only ever stores relative paths --
no base64 bloat, and the diff stays readable.

12.1 MB, average 25 KB per image. The zh-hant set is separately
localized: the text inside each diagram is Traditional Chinese with the
English term alongside, matching the lesson prompt's own convention.

assets/hello-algo/README.md records the attribution requirement, the
no-derivatives constraint we hold ourselves to, and the fact that both
repos must stay private."
```

---

### Task 3: diagram_map.json 與候選圖查詢

**Files:**
- Create: `diagrams.py`
- Create: `diagram_map.json`
- Test: `tests/test_diagrams.py`（新增）、`tests/test_diagram_map.py`（新增）

**Interfaces:**
- Consumes: Task 1 的 `syllabus.txt` 主題字串；Task 2 的 `assets/hello-algo/` 目錄結構
- Produces:
  - `diagrams.ASSETS_ROOT: str`、`diagrams.MAP_PATH: str`、`diagrams.MAX_DIAGRAMS: int = 2`
  - `diagrams.load_map(path=MAP_PATH) -> dict`
  - `diagrams.candidates_for(topic: str, dmap: dict | None = None, assets_root: str = ASSETS_ROOT) -> list[str]`（回傳相對 `assets_root` 的路徑，排序穩定）
  - `diagrams.format_available(paths: list[str]) -> str`

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_diagrams.py`：

```python
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
```

建立 `tests/test_diagram_map.py`：

```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_diagrams.py tests/test_diagram_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'diagrams'`

- [ ] **Step 3: 寫 diagrams.py（本任務只需這三個函式，驗證留到 Task 5）**

建立 `diagrams.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""課程配圖：主題 → 候選圖，以及 claude 選圖結果的驗證與剝除。

圖庫是 vendored 的 hello-algo 繁中圖（assets/hello-algo/），CC BY-NC-SA 4.0。
貫穿全檔的原則：圖是加分項，任何圖片相關的失敗都不得阻擋信件寄出 ——
撈不到就當沒圖，驗不過就整批剝掉，信照常走。
"""
import os
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_ROOT = os.path.join(_HERE, "assets", "hello-algo")
MAP_PATH = os.path.join(_HERE, "diagram_map.json")
MAX_DIAGRAMS = 2

_IMAGE_EXTS = (".png", ".gif", ".jpg")


def load_map(path=MAP_PATH):
    """讀 diagram_map.json；不存在或壞掉都回傳空 dict（當作全部主題都沒圖）。"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def candidates_for(topic, dmap=None, assets_root=ASSETS_ROOT):
    """該主題可用的圖，回傳相對 assets_root 的路徑清單（排序穩定）。"""
    dmap = load_map() if dmap is None else dmap
    out = []
    for d in dmap.get(topic) or []:
        full = os.path.join(assets_root, d)
        if not os.path.isdir(full):
            continue  # 上游改名或圖庫沒更新，跳過而不是炸掉
        for name in sorted(os.listdir(full)):
            if name.lower().endswith(_IMAGE_EXTS):
                out.append(f"{d}/{name}")
    return out


def format_available(paths):
    """組出餵給 claude 的 AVAILABLE_DIAGRAMS 段落。"""
    if not paths:
        return "AVAILABLE_DIAGRAMS: （無，今天沒有可用的圖，不要輸出 diagrams 欄位）"
    lines = "\n".join(f"- {p}" for p in paths)
    return f"AVAILABLE_DIAGRAMS:\n{lines}"
```

- [ ] **Step 4: 寫 diagram_map.json**

建立 `diagram_map.json`（key 必須與 `syllabus.txt` 逐字相同）：

```json
{
  "Big-O 複雜度：怎麼估一段程式的快慢": ["chapter_computational_complexity/time_complexity.assets"],
  "陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處": ["chapter_array_and_linkedlist/array.assets", "chapter_array_and_linkedlist/ram_and_cache.assets"],
  "空間複雜度：記憶體也要算，遞迴呼叫堆疊的隱藏成本": ["chapter_computational_complexity/space_complexity.assets"],
  "迭代與遞迴：兩種重複的形式、呼叫堆疊與尾遞迴": ["chapter_computational_complexity/iteration_and_recursion.assets"],

  "陣列上的掃描技巧：雙指標、滑動視窗、前綴和": [],
  "字串 String：不可變性、StringBuilder 與字元陣列的關係": [],
  "Linked List 基礎：節點、指標與 dummy head 技巧": ["chapter_array_and_linkedlist/linked_list.assets"],
  "鏈結串列的指標技巧：快慢指標找中點與判環、反轉串列": [],
  "Stack 堆疊：後進先出、括號配對與單調堆疊": ["chapter_stack_and_queue/stack.assets"],
  "Queue 佇列與 Deque：先進先出、環形佇列與雙端佇列": ["chapter_stack_and_queue/queue.assets", "chapter_stack_and_queue/deque.assets"],

  "HashMap / HashSet：O(1) 查找的原理與代價": ["chapter_hashing/hash_map.assets"],
  "雜湊函式與負載因子：hashCode、擴容與 rehash": ["chapter_hashing/hash_algorithm.assets"],
  "雜湊衝突：鏈結法 chaining 與開放定址 open addressing": ["chapter_hashing/hash_collision.assets"],

  "Binary Tree 基礎：節點、深度與陣列表示法": ["chapter_tree/binary_tree.assets", "chapter_tree/array_representation_of_tree.assets"],
  "二元樹走訪：前序/中序/後序 DFS 與 BFS 層序": ["chapter_tree/binary_tree_traversal.assets"],
  "Binary Search Tree：中序走訪的有序性與插入刪除": ["chapter_tree/binary_search_tree.assets"],
  "平衡樹 AVL：BST 為什麼會退化、旋轉怎麼救回來": ["chapter_tree/avl_tree.assets"],
  "樹的經典題型：深度、直徑、最近共同祖先 LCA": [],

  "Heap / PriorityQueue：完全二元樹、上浮下沉與 Top-K": ["chapter_heap/heap.assets", "chapter_heap/build_heap.assets", "chapter_heap/top_k.assets"],

  "圖的表示法：鄰接矩陣與鄰接表的取捨": ["chapter_graph/graph.assets"],
  "圖的走訪：DFS / BFS、連通塊與島嶼問題": ["chapter_graph/graph_traversal.assets", "chapter_graph/graph_operations.assets"],
  "拓撲排序 Topological Sort：有依賴關係的排程": [],
  "最短路徑入門：BFS 解無權圖、Dijkstra 概念": [],

  "Binary Search 基礎：邊界條件寫對的固定套路": ["chapter_searching/binary_search.assets"],
  "二分搜尋變形：找左界/右界、插入點、旋轉陣列": ["chapter_searching/binary_search_edge.assets", "chapter_searching/binary_search_insertion.assets"],
  "答案空間二分：對「答案」而不是「索引」二分": [],
  "搜尋演算法總覽：線性、二分、雜湊、樹搜尋怎麼選": ["chapter_searching/searching_algorithm_revisited.assets", "chapter_searching/replace_linear_by_hashing.assets"],

  "排序的評價標準：穩定性、原地性、自適應性": ["chapter_sorting/sorting_algorithm.assets", "chapter_sorting/summary.assets"],
  "基礎排序：選擇、氣泡、插入排序與它們的 O(n²)": ["chapter_sorting/selection_sort.assets", "chapter_sorting/bubble_sort.assets", "chapter_sorting/insertion_sort.assets"],
  "快速排序 Quick Sort：分割 partition 與最壞情況": ["chapter_sorting/quick_sort.assets"],
  "合併排序 Merge Sort：分治的代表作與穩定性": ["chapter_sorting/merge_sort.assets"],
  "堆積排序 Heap Sort：用堆積把排序做到原地 O(n log n)": ["chapter_sorting/heap_sort.assets"],
  "線性時間排序：計數、桶、基數排序的適用條件": ["chapter_sorting/counting_sort.assets", "chapter_sorting/bucket_sort.assets", "chapter_sorting/radix_sort.assets"],
  "排序的應用：合併區間、會議室與自訂 Comparator": [],

  "分治 Divide and Conquer：把問題切小再合併": ["chapter_divide_and_conquer/divide_and_conquer.assets", "chapter_divide_and_conquer/hanota_problem.assets", "chapter_divide_and_conquer/build_binary_tree_problem.assets"],
  "回溯 Backtracking：排列、組合、子集的模板": ["chapter_backtracking/backtracking_algorithm.assets", "chapter_backtracking/permutations_problem.assets", "chapter_backtracking/subset_sum_problem.assets"],
  "回溯經典題：N 皇后與剪枝": ["chapter_backtracking/n_queens_problem.assets"],

  "DP 入門：從暴力遞迴到記憶化再到列表格": ["chapter_dynamic_programming/intro_to_dynamic_programming.assets", "chapter_dynamic_programming/dp_solution_pipeline.assets"],
  "DP 問題的特徵：最優子結構與無後效性": ["chapter_dynamic_programming/dp_problem_features.assets"],
  "一維 DP：爬樓梯、打家劫舍套路": ["chapter_dynamic_programming/intro_to_dynamic_programming.assets"],
  "背包問題：0-1 背包與完全背包": ["chapter_dynamic_programming/knapsack_problem.assets", "chapter_dynamic_programming/unbounded_knapsack_problem.assets"],
  "字串 DP：LCS 與編輯距離": ["chapter_dynamic_programming/edit_distance_problem.assets"],

  "Greedy 貪心：什麼時候可以貪、怎麼證明": ["chapter_greedy/greedy_algorithm.assets", "chapter_greedy/fractional_knapsack_problem.assets", "chapter_greedy/max_capacity_problem.assets"],
  "面試解題流程總整理：從讀題到說出複雜度": []
}
```

- [ ] **Step 5: 執行測試確認通過**

Run: `python3 -m pytest tests/test_diagrams.py tests/test_diagram_map.py -v`
Expected: 13 passed

`test_every_mapped_dir_exists` 若失敗，代表上游目錄名與本計畫不同，用 `ls assets/hello-algo/<chapter>` 對照後修正 `diagram_map.json`。

- [ ] **Step 6: 眼睛看一次抽樣結果**

Run:
```bash
python3 -c "
import diagrams as dg
for t in ['Binary Search 基礎：邊界條件寫對的固定套路',
          '陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處']:
    print(t)
    for p in dg.candidates_for(t): print('   ', p)
"
```
Expected: 二分搜尋列出 `binary_search_step1..7` 等 9 個檔案；陣列列出 `array_definition.png` 等 6 個檔案。

- [ ] **Step 7: Commit**

```bash
git add diagrams.py diagram_map.json tests/test_diagrams.py tests/test_diagram_map.py
git commit -m "feat: map syllabus topics to hello-algo diagram directories

diagrams.candidates_for() turns a topic string into the list of images
the model may choose from. Directories that do not exist are skipped
rather than raised: the vendored library can drift from the map when
upstream renames a chapter, and a missing diagram must never take down
a lesson.

35 of the 44 topics map to a chapter. The 9 that do not are
problem-solving techniques (hello-algo is a data-structures textbook and
has no chapter for two pointers, sliding window, prefix sum, fast/slow
pointers, topological sort, shortest paths) and summary topics with no
single structure to draw. Those get an empty list and a text-only
lesson.

tests/test_diagram_map.py holds the map and the syllabus together in
both directions: every topic is a key, no key outlasts its topic, and
every directory listed actually exists on disk."
```

---

### Task 4: build_lesson.py 把候選圖餵給 claude

**Files:**
- Modify: `build_lesson.py`（`format_daily_context`、`main` 的 daily 分支）
- Test: `tests/test_build_lesson.py`（既有檔案，追加測試）

**Interfaces:**
- Consumes: `diagrams.candidates_for`、`diagrams.format_available`
- Produces: daily context 尾端多一段 `AVAILABLE_DIAGRAMS:`。`format_daily_context` 新增一個具預設值的關鍵字參數 `available=""`，既有呼叫端不受影響。

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_build_lesson.py` 末端追加：

```python
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
```

檔案開頭若還沒 import，補上 `import build_lesson as bl`（既有測試已有則略過）。

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_build_lesson.py -v`
Expected: FAIL — `format_daily_context() got an unexpected keyword argument 'available'`

- [ ] **Step 3: 改 build_lesson.py**

在 import 區塊加入：

```python
import diagrams as dg
```

`format_daily_context` 簽章加參數、結尾串上：

```python
def format_daily_context(goal, topic, step, covered, yesterday, color, today, available=""):
    bg, bar, txt = color
    covered_block = "\n".join(f"- {c}" for c in covered) if covered else "（尚無，這是這個主題的第一步）"
    yest = yesterday if yesterday else "（無，這是第一課）"
    body = (
        f"GOAL: {goal}\n"
        f"DATE: {today}\n"
        f"TOPIC: {topic}\n"
        f"STEP: {step}\n"
        f"COVERED_SO_FAR:\n{covered_block}\n"
        f"YESTERDAY_SUMMARY: {yest}\n"
        f"COLOR_BG: {bg}\n"
        f"COLOR_BAR: {bar}\n"
        f"COLOR_TXT: {txt}"
    )
    return f"{body}\n{available}" if available else body
```

`main` 的 daily 分支，把 `print(format_daily_context(...))` 那段改成：

```python
        history = ss.load_history(args.history)
        print(format_daily_context(
            goal=goal, topic=topic, step=progress.get("step", 1),
            covered=progress.get("covered", []),
            yesterday=ss.last_summary(history),
            color=color, today=today_s,
            # 沒有對應圖的主題會拿到「（無）」，那天的信就是純文字。
            available=dg.format_available(dg.candidates_for(topic)),
        ))
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python3 -m pytest tests/test_build_lesson.py -v`
Expected: all passed

- [ ] **Step 5: 用真實資料看一次**

Run: `python3 build_lesson.py daily | tail -20`
Expected: 尾端出現 `AVAILABLE_DIAGRAMS:` 後面接 6 個 `chapter_array_and_linkedlist/...` 路徑（目前主題是陣列）。

- [ ] **Step 6: Commit**

```bash
git add build_lesson.py tests/test_build_lesson.py
git commit -m "feat: feed the day's candidate diagrams into the lesson context

The daily context gains an AVAILABLE_DIAGRAMS block listing the images
mapped to the current topic. The model picks from that list rather than
naming a file freely, so a lesson can only ever reference an image that
exists on disk.

available defaults to empty and is appended only when non-empty, so the
context is byte-identical to before for topics with no diagrams."
```

---

### Task 5: 驗證 claude 選的圖，不合格就整批剝掉

**Files:**
- Modify: `diagrams.py`（新增 `cid_refs`、`strip_img_tags`、`sanitize`、`abs_paths`）
- Modify: `apply_result.py`（stdin 分支，`res = parse_result(...)` 之後）
- Test: `tests/test_diagrams.py`（追加）、`tests/test_apply_result.py`（追加）

**Interfaces:**
- Consumes: Task 3 的 `diagrams.ASSETS_ROOT`、`MAX_DIAGRAMS`
- Produces:
  - `diagrams.cid_refs(html: str) -> list[str]`
  - `diagrams.strip_img_tags(html: str) -> str`
  - `diagrams.sanitize(res: dict, assets_root: str = ASSETS_ROOT) -> tuple[dict, bool]`——回傳新的 dict 與「圖有沒有留下」；不合格時 `res["html"]` 已剝掉 `<img>`、`res` 已無 `diagrams` 鍵
  - `diagrams.abs_paths(diagrams_list, assets_root=ASSETS_ROOT) -> list[tuple[str, str]]`（Task 6 使用）

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_diagrams.py` 追加：

```python
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
```

在 `tests/test_apply_result.py` 追加（檔案開頭若無則補 `import diagrams as dg`）：

```python
def test_to_outbox_keeps_valid_diagrams(tmp_path, monkeypatch, capsys):
    import diagrams as dg
    assets = tmp_path / "assets"
    (assets / "c/x.assets").mkdir(parents=True)
    (assets / "c/x.assets/a.png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(dg, "ASSETS_ROOT", str(assets))

    payload = json.dumps({
        "html": '<div><img src="cid:d1"></div>',
        "topic_complete": False,
        "today_summary": "s",
        "archive_markdown": "m",
        "diagrams": [{"cid": "d1", "path": "c/x.assets/a.png", "caption": "圖說"}],
    })
    prog = tmp_path / "progress.json"
    prog.write_text('{"current_index": 0, "step": 1, "covered": [], "completed_topics": []}',
                    encoding="utf-8")
    ob = tmp_path / "outbox.json"
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    ar.main(["--to-outbox", "--progress", str(prog), "--outbox", str(ob)])

    saved = json.loads(ob.read_text(encoding="utf-8"))[0]["result"]
    assert saved["diagrams"][0]["cid"] == "d1"


def test_to_outbox_strips_diagrams_when_file_missing(tmp_path, monkeypatch):
    import diagrams as dg
    assets = tmp_path / "assets"
    assets.mkdir()
    monkeypatch.setattr(dg, "ASSETS_ROOT", str(assets))

    payload = json.dumps({
        "html": '<div><img src="cid:d1"><p>內文</p></div>',
        "topic_complete": False,
        "today_summary": "s",
        "archive_markdown": "m",
        "diagrams": [{"cid": "d1", "path": "nope/missing.png", "caption": "c"}],
    })
    prog = tmp_path / "progress.json"
    prog.write_text('{"current_index": 0, "step": 1, "covered": [], "completed_topics": []}',
                    encoding="utf-8")
    ob = tmp_path / "outbox.json"
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    ar.main(["--to-outbox", "--progress", str(prog), "--outbox", str(ob)])

    saved = json.loads(ob.read_text(encoding="utf-8"))[0]["result"]
    assert "diagrams" not in saved          # 圖被剝掉
    assert "<img" not in saved["html"]      # 標籤也移除
    assert "<p>內文</p>" in saved["html"]   # 但信本身照常存進 outbox


def test_diagrams_is_not_required():
    # 舊格式（沒有 diagrams 欄位）必須照常解析成功，否則庫存那篇會寄不出去。
    payload = json.dumps({"html": "<p>x</p>", "topic_complete": False,
                          "today_summary": "s", "archive_markdown": "m"})
    assert ar.parse_result(payload)["html"] == "<p>x</p>"
    assert "diagrams" not in ar.REQUIRED
```

檔案開頭若缺，補 `import io`、`import json`、`import apply_result as ar`。

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_diagrams.py tests/test_apply_result.py -v`
Expected: FAIL — `AttributeError: module 'diagrams' has no attribute 'cid_refs'`

- [ ] **Step 3: 在 diagrams.py 加驗證函式**

在 import 區塊補 `import re`，並在 `_IMAGE_EXTS` 之後加：

```python
# 只認 <img src="cid:xxx">。外部 URL 的 img 不歸這裡管（也不該出現在信裡）。
_IMG_CID = re.compile(r'<img\b[^>]*?\bsrc\s*=\s*["\']cid:([A-Za-z0-9_-]+)["\'][^>]*>', re.I)
```

檔案末端加：

```python
def cid_refs(html):
    """html 裡引用到的 cid，依出現順序。"""
    return _IMG_CID.findall(html or "")


def strip_img_tags(html):
    """移除所有 <img src="cid:...">，其餘內容原封不動。"""
    return _IMG_CID.sub("", html or "")


def _is_inside(rel, assets_root):
    """rel 必須落在 assets_root 底下且檔案存在（擋掉 ../ 逃逸與絕對路徑）。"""
    root = os.path.realpath(assets_root)
    full = os.path.realpath(os.path.join(root, rel))
    if full != root and not full.startswith(root + os.sep):
        return False
    return os.path.isfile(full)


def sanitize(res, assets_root=ASSETS_ROOT):
    """驗證 res['diagrams']；任一項不合格就整批剝掉並移除 html 裡的 <img>。

    回傳 (新的 res, 圖有沒有留下)。不修改傳入的 res。
    全有全無是刻意的：一封信只有兩張圖，留下半套比乾脆沒圖更難看，
    而且圖文是配套寫的，剝掉一張會讓「圖說」指向不存在的東西。
    """
    out = dict(res)
    html = out.get("html", "") or ""
    refs = cid_refs(html)
    diags = out.get("diagrams")

    if not refs and not diags:
        out.pop("diagrams", None)
        return out, True                      # 本來就沒圖，正常

    def drop():
        out["html"] = strip_img_tags(html)
        out.pop("diagrams", None)
        return out, False

    if not isinstance(diags, list) or not diags or len(diags) > MAX_DIAGRAMS:
        return drop()

    seen = set()
    for d in diags:
        if not isinstance(d, dict):
            return drop()
        cid, path = d.get("cid"), d.get("path")
        if not isinstance(cid, str) or not isinstance(path, str) or not cid or not path:
            return drop()
        if cid in seen or not _is_inside(path, assets_root):
            return drop()
        seen.add(cid)

    if seen != set(refs):                     # html 與 diagrams 必須完全對得上
        return drop()
    return out, True


def abs_paths(diagrams_list, assets_root=ASSETS_ROOT):
    """[(cid, 絕對路徑)]，給寄信端組 --image 參數用。"""
    return [(d["cid"], os.path.join(assets_root, d["path"]))
            for d in (diagrams_list or [])]
```

- [ ] **Step 4: 在 apply_result.py 串上 sanitize**

import 區塊加 `import diagrams as dg`。

把 stdin 分支（`apply_result.py:407` 附近）：

```python
    # ── 以下需讀 stdin（claude 輸出）──
    try:
        res = parse_result(sys.stdin.read())
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
```

改成：

```python
    # ── 以下需讀 stdin（claude 輸出）──
    try:
        res = parse_result(sys.stdin.read())
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    # 圖是加分項：選錯檔、對不上 cid 一律整批剝掉，信照常走，絕不因為圖而擋信。
    res, kept = dg.sanitize(res)
    if not kept:
        print("WARN: diagrams 驗證未過，已剝除圖片，信件以純文字寄出。", file=sys.stderr)
```

- [ ] **Step 5: 執行測試確認通過**

Run: `python3 -m pytest tests/test_diagrams.py tests/test_apply_result.py -v`
Expected: all passed

- [ ] **Step 6: 跑全套回歸**

Run: `python3 -m pytest -v`
Expected: all passed（既有測試不得有任何一條變紅）

- [ ] **Step 7: Commit**

```bash
git add diagrams.py apply_result.py tests/test_diagrams.py tests/test_apply_result.py
git commit -m "feat: validate model-chosen diagrams and strip them on any mismatch

sanitize() checks that every cid referenced in the html has a diagrams
entry, that every entry is referenced back, that each path resolves to a
real file inside assets/hello-algo, and that no more than MAX_DIAGRAMS
came back. Any failure drops the whole set and removes the <img> tags,
leaving a text-only lesson that still sends.

All-or-nothing is deliberate. A lesson carries at most two images and
the prose is written around them, so keeping half a set would leave a
caption pointing at nothing.

Paths are resolved with realpath and checked against the assets root, so
a generated ../ cannot reach outside the image library.

diagrams stays out of REQUIRED: the entry already sitting in the outbox
predates this field and has to keep sending."
```

---

### Task 6: apply_result.py --outbox-images

**Files:**
- Modify: `apply_result.py`（模組 docstring、argparse、新分支）
- Test: `tests/test_apply_result.py`（追加）

**Interfaces:**
- Consumes: `diagrams.abs_paths`
- Produces: CLI `python3 apply_result.py --outbox-images`，stdout 每行 `<cid>\t<絕對路徑>`；無圖或 outbox 不存在時輸出為空、exit 0。

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_apply_result.py` 追加：

```python
def _queue_with(tmp_path, result):
    ob = tmp_path / "outbox.json"
    ob.write_text(json.dumps([{"kind": "lesson", "index": 0, "step": 1, "result": result}]),
                  encoding="utf-8")
    return ob


def test_outbox_images_prints_cid_and_path(tmp_path, monkeypatch, capsys):
    import diagrams as dg
    monkeypatch.setattr(dg, "ASSETS_ROOT", "/fake/assets")
    ob = _queue_with(tmp_path, {
        "html": '<img src="cid:d1">', "topic_complete": False,
        "today_summary": "s", "archive_markdown": "m",
        "diagrams": [{"cid": "d1", "path": "c/x.assets/a.png", "caption": "圖說"}],
    })
    ar.main(["--outbox-images", "--outbox", str(ob)])
    out = capsys.readouterr().out
    assert out == "d1\t/fake/assets/c/x.assets/a.png\n"


def test_outbox_images_empty_when_no_diagrams(tmp_path, capsys):
    ob = _queue_with(tmp_path, {"html": "<p>x</p>", "topic_complete": False,
                                "today_summary": "s", "archive_markdown": "m"})
    ar.main(["--outbox-images", "--outbox", str(ob)])
    assert capsys.readouterr().out == ""


def test_outbox_images_empty_when_no_outbox(tmp_path, capsys):
    # 寄信端會無條件呼叫這個指令，outbox 不存在時必須安靜地什麼都不輸出、不報錯。
    ar.main(["--outbox-images", "--outbox", str(tmp_path / "nope.json")])
    assert capsys.readouterr().out == ""
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_apply_result.py -k outbox_images -v`
Expected: FAIL — `unrecognized arguments: --outbox-images`

- [ ] **Step 3: 加 CLI 分支**

在 argparse 的互斥群組裡，`--outbox-html` 之後加：

```python
    g.add_argument("--outbox-images", action="store_true",
                   help="印出 outbox 的圖清單，每行「cid<TAB>絕對路徑」")
```

在 `if args.outbox_html:` 那個區塊之後加：

```python
    if args.outbox_images:
        # 寄信端無條件呼叫這支：沒 outbox、沒圖都輸出空、exit 0，讓呼叫端不必先判斷。
        head = queue_head(load_queue(args.outbox))
        res = (head or {}).get("result") or {}
        for cid, path in dg.abs_paths(res.get("diagrams")):
            print(f"{cid}\t{path}")
        return
```

模組 docstring 的「不讀 stdin 的查詢/動作」清單裡，`--outbox-html` 那行下面補一行：

```
  --outbox-images ：印出 outbox 的圖清單（每行「cid<TAB>絕對路徑」），無圖則無輸出。
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python3 -m pytest tests/test_apply_result.py -v`
Expected: all passed

- [ ] **Step 5: 對現有 outbox 實測**

Run: `python3 apply_result.py --outbox-images; echo "exit=$?"`
Expected: 沒有任何輸出、`exit=0`（目前庫存那篇是舊格式，沒有圖）。

- [ ] **Step 6: Commit**

```bash
git add apply_result.py tests/test_apply_result.py
git commit -m "feat: add --outbox-images to list the queued lesson's diagrams

Prints one cid<TAB>absolute-path line per image so the send step can
build --image arguments without parsing outbox.json itself.

Silent and zero-exit when there is no outbox or no diagrams. The sender
calls this unconditionally on every run, so an empty queue or a
text-only lesson must not look like a failure."
```

---

### Task 7: prompt_daily.txt 的圖片版型與 diagrams 輸出欄位

**Files:**
- Modify: `prompt_daily.txt`

**Interfaces:**
- Consumes: Task 4 餵進 context 的 `AVAILABLE_DIAGRAMS`
- Produces: claude 輸出 JSON 多一個選用的 `diagrams` 欄位，格式為 `[{"cid": "d1", "path": "<AVAILABLE_DIAGRAMS 裡的路徑>", "caption": "圖說"}]`，`html` 內以 `<img src="cid:d1">` 引用。Task 5 的 `sanitize` 驗證這個契約。

- [ ] **Step 1: 在【教學原則】加圖片規則**

在「- 英文為主、中文輔助：概念標題用英文，解說用中文。」之後插入：

```
- 配圖：context 尾端的 AVAILABLE_DIAGRAMS 列出今天可用的圖。從中挑「最貼今天這一小步」的
  0～2 張（通常 1 張，寧缺勿濫），放在「今日小步」卡片裡、英文概念標題之後、中文解說之前——
  先看圖再讀字。若那一段寫著「（無…）」就完全不要輸出 diagrams 欄位。
- 每張圖下方必須有一段針對那張圖的文字，指出這張圖在講什麼、要看哪裡。
  不可以圖歸圖、文歸文各講各的。有了圖之後，原本用來描述同一件事的文字要相應精簡。
- 圖只能從 AVAILABLE_DIAGRAMS 挑，不可以自己編路徑，也不可以引用外部圖片網址。
```

- [ ] **Step 2: 在【輸出 JSON 格式】加 diagrams 欄位**

把輸出格式區塊改成：

```
{
  "html": "<信件 HTML 內文，見下方版型>",
  "topic_complete": true 或 false,
  "today_summary": "用一句話總結今天教的重點（給明天出複習題用）",
  "archive_markdown": "把今天這課寫成乾淨的 markdown（標題用 ## TOPIC · 第 STEP 步，含概念、圖片、程式碼區塊、術語表），供日後歸檔筆記",
  "diagrams": [
    {"cid": "d1", "path": "AVAILABLE_DIAGRAMS 裡的其中一行（原樣照抄）", "caption": "這張圖在講什麼"}
  ]
}

diagrams 是選用欄位：沒有圖就整個省略，不要給空陣列。
cid 用 d1、d2，必須與 html 裡的 <img src="cid:d1"> 一一對應——多一個少一個，
整組圖都會被丟掉，信會變成純文字。
```

- [ ] **Step 3: 在 html 版型加圖片區塊**

在「今日小步」卡片裡，把這一行：

```html
    <div style="font-size:12.5px;color:#7a818d;margin:4px 0 12px;">一句中文點出今天要懂的事</div>
```

之後插入：

```html
    <!-- 配圖：0~2 張。沒有可用的圖就整段省略（連同 diagrams 欄位）。 -->
    <div style="margin:12px 0;">
      <img src="cid:d1" alt="圖說" style="max-width:100%;height:auto;display:block;border-radius:6px;">
      <div style="font-size:12.5px;color:#3b424f;line-height:1.65;margin-top:8px;">針對這張圖的解說：這張圖在講什麼、要看哪裡。</div>
      <div style="font-size:10.5px;color:#a8aeb8;margin-top:4px;">圖：<a href="https://www.hello-algo.com/" style="color:#a8aeb8;text-decoration:none;">Hello 算法</a> · CC BY-NC-SA 4.0</div>
    </div>
```

- [ ] **Step 4: 在 archive_markdown 規則加圖片**

在【教學原則】末端加：

```
- archive_markdown 裡的圖片用 hello-algo 的公開 raw URL，不要用本地路徑：
  ![圖說](https://raw.githubusercontent.com/krahets/hello-algo/main/zh-hant/docs/<path>)
  其中 <path> 就是 diagrams 那筆的 path 原樣。圖片下方同樣要寫一行
  `圖：[Hello 算法](https://www.hello-algo.com/) · CC BY-NC-SA 4.0`。
```

- [ ] **Step 5: 產一篇真的來看**

Run:
```bash
python3 build_lesson.py daily > /tmp/ctx.txt
grep -c 'AVAILABLE_DIAGRAMS' /tmp/ctx.txt          # 應為 1
{ cat prompt_daily.txt; echo; cat /tmp/ctx.txt; } | claude -p --output-format text > /tmp/out.json
python3 -c "
import json, sys, diagrams as dg
res = json.load(open('/tmp/out.json'), strict=False)
print('diagrams =', json.dumps(res.get('diagrams'), ensure_ascii=False, indent=2))
print('cid refs =', dg.cid_refs(res['html']))
out, ok = dg.sanitize(res)
print('sanitize ok =', ok)
"
```
Expected: `diagrams` 有 1～2 筆、`cid refs` 與它們的 cid 相同、`sanitize ok = True`。

若 `sanitize ok = False`，看 `diagrams` 印出來的 path 是否有出現在 `/tmp/ctx.txt` 的 AVAILABLE_DIAGRAMS 清單裡；不在清單裡就回 Step 1 把「只能從清單挑」講得更死。

- [ ] **Step 6: 眼睛看一次 HTML**

Run:
```bash
python3 -c "
import json; print(json.load(open('/tmp/out.json'), strict=False)['html'])
" > /tmp/preview.html
open /tmp/preview.html
```

瀏覽器裡圖會是破圖（cid 只有信件環境認得），這是預期的。要確認的是：圖的位置在概念標題之後、解說之前；圖下方有針對該圖的文字；有署名那一行。

- [ ] **Step 7: Commit**

```bash
git add prompt_daily.txt
git commit -m "feat: teach the lesson prompt to place diagrams and cite them

The model now picks 0-2 images from AVAILABLE_DIAGRAMS and references
them as <img src=\"cid:dN\">, with a matching diagrams array. Images sit
between the English concept heading and the Chinese explanation so the
picture lands before the prose.

Each image must carry its own commentary saying what it shows and where
to look -- a picture and a paragraph that describe the same thing
without referring to each other is worse than either alone. Prose that
the image now covers gets trimmed rather than kept alongside.

Archive markdown cites the upstream raw URL instead of a local path:
lessons/ is a symlink into the state repo while the images live in this
one, so a relative path would resolve nowhere on GitHub or in Notion.

Attribution line is part of the template, not optional -- CC BY-NC-SA
requires it."
```

---

### Task 8: send_email.py 以 CID 內嵌圖片

**Files:**
- Modify: `send_email.py`（新增 `build_message`、`_img_subtype`，`main` 改用 argparse）
- Test: `tests/test_send_email.py`（追加）

**Interfaces:**
- Consumes: `diagrams.strip_img_tags`
- Produces:
  - `send_email.build_message(html_body: str, subject: str, from_user: str, to_addr: str, images: list[tuple[str, str]] | None = None)` → `MIMEText` 或 `MIMEMultipart`
  - CLI 新增可重複的 `--image CID=PATH`；positional subject 維持相容（`send_email.py "每日 DSA"` 照舊可用）

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_send_email.py` 追加：

```python
import os


def test_build_message_without_images_is_plain_html():
    # 回歸測試：沒有圖時的 MIME 結構必須跟改動前一模一樣。
    msg = se.build_message("<p>hi</p>", "主旨", "a@gmail.com", "b@gmail.com")
    assert msg.get_content_type() == "text/html"
    assert msg["Subject"] == "主旨"
    assert msg["To"] == "b@gmail.com"
    assert "a@gmail.com" in msg["From"]


def test_build_message_with_image_is_multipart_related(tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    msg = se.build_message('<img src="cid:d1">', "主旨", "a@gmail.com", "b@gmail.com",
                           [("d1", str(png))])
    assert msg.get_content_type() == "multipart/related"
    parts = msg.get_payload()
    assert parts[0].get_content_type() == "text/html"
    assert parts[1].get_content_type() == "image/png"
    assert parts[1]["Content-ID"] == "<d1>"


def test_build_message_degrades_when_image_unreadable(tmp_path, capsys):
    # 圖讀不到絕不能讓寄信失敗——降級成純文字，把 <img> 一併拿掉免得變破圖。
    msg = se.build_message('<p>內文</p><img src="cid:d1">', "主旨",
                           "a@gmail.com", "b@gmail.com",
                           [("d1", str(tmp_path / "missing.png"))])
    assert msg.get_content_type() == "text/html"
    body = msg.get_payload(decode=True).decode("utf-8")
    assert "<img" not in body
    assert "<p>內文</p>" in body
    assert "WARN" in capsys.readouterr().err


def test_build_message_gif_subtype(tmp_path):
    gif = tmp_path / "a.gif"
    gif.write_bytes(b"GIF89a" + b"\x00" * 32)
    msg = se.build_message('<img src="cid:d1">', "s", "a@g.com", "b@g.com",
                           [("d1", str(gif))])
    assert msg.get_payload()[1].get_content_type() == "image/gif"


def test_parse_image_args():
    assert se.parse_image_args(["d1=/tmp/a.png", "d2=/tmp/b.png"]) == [
        ("d1", "/tmp/a.png"), ("d2", "/tmp/b.png")]
    assert se.parse_image_args([]) == []
    assert se.parse_image_args(["壞掉的沒有等號"]) == []
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_send_email.py -v`
Expected: FAIL — `module 'send_email' has no attribute 'build_message'`

- [ ] **Step 3: 改 send_email.py**

模組 docstring 的用法改成：

```
用法：echo "<html>" | python3 send_email.py ["主旨前綴"] [--image CID=PATH ...]
```

import 區塊改成：

```python
import os
import sys
import ssl
import smtplib
import argparse
import datetime
import subprocess
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

import diagrams as dg
```

在 `get_app_password` 之後、`main` 之前插入：

```python
_SUBTYPES = {".png": "png", ".gif": "gif", ".jpg": "jpeg", ".jpeg": "jpeg"}


def _img_subtype(path):
    return _SUBTYPES.get(os.path.splitext(path)[1].lower(), "png")


def parse_image_args(specs):
    """把 ["d1=/path/a.png"] 拆成 [("d1", "/path/a.png")]，格式不對的整筆略過。"""
    out = []
    for spec in specs or []:
        cid, sep, path = spec.partition("=")
        if sep and cid and path:
            out.append((cid, path))
    return out


def build_message(html_body, subject, from_user, to_addr, images=None):
    """無圖 → text/html；有圖 → multipart/related 以 CID 內嵌。

    Gmail 不吃 data: URI 也不吃 SVG，CID 是唯一能讓圖顯示在信裡的方式。
    任何一張圖讀不到就整批放棄、剝掉 <img> 改寄純文字 —— 圖是加分項，
    不能因為它讓信寄不出去，也不該讓收件匣裡出現一排破圖。
    """
    images = list(images or [])
    loaded = []
    for cid, path in images:
        try:
            with open(path, "rb") as f:
                loaded.append((cid, f.read(), _img_subtype(path)))
        except OSError as e:
            print(f"WARN: 圖片讀取失敗，改以純文字寄出：{path} ({e})", file=sys.stderr)
            loaded = None
            break

    if loaded:
        msg = MIMEMultipart("related")
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        for cid, data, subtype in loaded:
            img = MIMEImage(data, _subtype=subtype)
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtype}")
            msg.attach(img)
    else:
        if images:
            html_body = dg.strip_img_tags(html_body)
        msg = MIMEText(html_body, "html", "utf-8")

    msg["Subject"] = subject
    msg["From"] = formataddr(("DSA Learn Digest", from_user))
    msg["To"] = to_addr
    return msg
```

`main()` 裡，把主旨解析與 message 組裝改掉。原本：

```python
    today = datetime.date.today().strftime("%Y-%m-%d")
    subject_prefix = sys.argv[1] if len(sys.argv) > 1 else "每日 DSA"
    subject = f"{subject_prefix} — {today}"

    app_password = get_app_password(conf["GMAIL_USER"], conf["KEYCHAIN_SERVICE"])

    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("DSA Learn Digest", conf["GMAIL_USER"]))
    msg["To"] = conf["MAIL_TO"]
```

改成：

```python
    today = datetime.date.today().strftime("%Y-%m-%d")
    subject = f"{args.subject_prefix} — {today}"

    app_password = get_app_password(conf["GMAIL_USER"], conf["KEYCHAIN_SERVICE"])

    msg = build_message(html_body, subject, conf["GMAIL_USER"], conf["MAIL_TO"],
                        parse_image_args(args.image))
```

並在 `main()` 開頭（`conf = load_config()` 之前）加參數解析：

```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject_prefix", nargs="?", default="每日 DSA")
    ap.add_argument("--image", action="append", default=[], metavar="CID=PATH",
                    help="以 CID 內嵌一張圖，可重複")
    args = ap.parse_args()

    conf = load_config()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python3 -m pytest tests/test_send_email.py -v`
Expected: all passed

- [ ] **Step 5: 確認 CLI 相容性沒破**

Run:
```bash
echo '<p>x</p>' | python3 send_email.py --help
python3 -c "
import send_email as se, sys
sys.argv = ['send_email.py', '每週 DSA 回顧']
import argparse
" # 只是確認 --help 不報錯
```
Expected: `--help` 顯示 `subject_prefix` 與 `--image`，不報錯。

- [ ] **Step 6: 實際寄一封有圖的測試信**

```bash
IMG="$(pwd)/assets/hello-algo/chapter_array_and_linkedlist/array.assets/array_definition.png"
printf '<div style="font-family:-apple-system,sans-serif"><h3>CID 內嵌測試</h3><img src="cid:d1" style="max-width:100%%;height:auto;display:block;"><p>上面應該看得到一張陣列圖。</p></div>' \
  | python3 send_email.py "CID 內嵌測試" --image "d1=$IMG"
```

**去信箱確認：Gmail 網頁版與手機 App 都要開來看，圖必須真的顯示。** 這是整個計畫唯一無法自動化驗證的一步。若手機看不到，先確認 Gmail 的「顯示外部圖片」設定（CID 內嵌通常不受此限制，但值得排除）。

- [ ] **Step 7: Commit**

```bash
git add send_email.py tests/test_send_email.py
git commit -m "feat: embed lesson diagrams as CID inline attachments

Gmail strips data: URIs and does not render SVG, so CID inline
attachments are the only way to get an image to show up in the body.
With no --image the message is byte-for-byte the plain MIMEText it
always was; a regression test pins that.

If any image fails to read, the whole set is dropped and the <img> tags
go with it. A mail full of broken image placeholders is worse than a
text-only one, and neither is worth failing a send over.

main() moves to argparse. The positional subject keeps working, so
existing callers -- run_learn.sh, the weekly digest, the alert mails --
are unaffected."
```

---

### Task 9: run_learn.sh 串接圖片

**Files:**
- Modify: `run_learn.sh`（`send_html`、`do_send`）
- Test: `tests/test_send_images_wiring.sh`（新增）

**Interfaces:**
- Consumes: Task 6 的 `--outbox-images`、Task 8 的 `--image CID=PATH`
- Produces: `send_html <html> <主旨> [--image ...]`——第三個以後的參數原樣轉給 `send_email.py`

- [ ] **Step 1: 確認 shell 種類**

Run: `head -1 run_learn.sh; grep -n 'set -' run_learn.sh | head -3`

記下結果。若是 zsh，空陣列展開 `"${arr[@]}"` 安全；若是 bash 且有 `set -u`，需改用 `"${arr[@]+"${arr[@]}"}"`。下面 Step 3 的寫法依此調整。

- [ ] **Step 2: 寫失敗測試**

建立 `tests/test_send_images_wiring.sh`（沿用 `tests/test_sync_guard.sh` 的風格，純文字檢查，不真的寄信）：

```bash
#!/bin/sh
# 檢查 run_learn.sh 有把 --outbox-images 的結果轉成 send_email 的 --image 參數。
# 真的寄信無法在 CI 驗證，這裡守的是「線有沒有接上」。
set -eu
DIR="$(cd "$(dirname "$0")/.." && pwd)"
S="$DIR/run_learn.sh"
fail=0

check() {
  if grep -q -- "$1" "$S"; then
    echo "ok   : $2"
  else
    echo "FAIL : $2（找不到：$1）"; fail=1
  fi
}

check 'outbox-images'          'do_send 會讀 --outbox-images'
check 'imgargs+=(--image'      '把每行轉成 --image 參數'
check 'send_html "$html" "$SUBJECT_DAILY"' 'send_html 仍以 html 與主旨開頭'

# send_html 必須把多出來的參數轉給 send_email.py
if grep -A6 '^send_html()' "$S" | grep -q 'shift 2'; then
  echo "ok   : send_html 用 shift 2 收尾巴參數"
else
  echo "FAIL : send_html 沒有轉發額外參數"; fail=1
fi

exit $fail
```

`chmod +x tests/test_send_images_wiring.sh`

- [ ] **Step 3: 執行測試確認失敗**

Run: `sh tests/test_send_images_wiring.sh`
Expected: 多條 FAIL，exit 1

- [ ] **Step 4: 改 send_html 讓它轉發額外參數**

把 `run_learn.sh:280` 附近的 `send_html` 改成：

```bash
send_html() {  # $1=html $2=主旨前綴 $3...=原樣轉給 send_email.py（例如 --image cid=path）
  local html="$1" subject="$2"; shift 2
  local out rc
  out="$(echo "$html" | "$PYTHON" "$DIR/send_email.py" "$subject" "$@" 2>&1)"; rc=$?
  echo "$out" >> "$LOG"
  if [ $rc -ne 0 ]; then
    local reason="$(echo "$out" | grep -iE 'error' | tail -1 | tr -d '"\\' | cut -c1-180)"
    [ -z "$reason" ] && reason="請查看 run.log"
    notify "⚠️ 今日 ${LEARN_NAME} 學習信寄送失敗" "稿件仍在，可手動重寄。"
    log "NOTIFY: 寄送失敗。原因：$reason"
  fi
  return $rc
}
```

- [ ] **Step 5: 改 do_send 組出 --image 參數**

把 `run_learn.sh:472` 附近：

```bash
    local html
    html="$("$PYTHON" "$DIR/apply_result.py" --outbox-html 2>>"$LOG")"
    if send_html "$html" "$SUBJECT_DAILY"; then
```

改成：

```bash
    local html
    html="$("$PYTHON" "$DIR/apply_result.py" --outbox-html 2>>"$LOG")"
    # 圖存在 repo 裡，outbox 只記路徑；沒圖時這裡拿到空輸出，imgargs 保持空陣列。
    local -a imgargs=()
    local _cid _path
    while IFS=$'\t' read -r _cid _path; do
      [ -n "$_cid" ] && imgargs+=(--image "$_cid=$_path")
    done < <("$PYTHON" "$DIR/apply_result.py" --outbox-images 2>>"$LOG")
    if send_html "$html" "$SUBJECT_DAILY" "${imgargs[@]}"; then
```

- [ ] **Step 6: 執行測試確認通過**

Run: `sh tests/test_send_images_wiring.sh`
Expected: 全部 ok，exit 0

- [ ] **Step 7: 語法檢查**

Run: `zsh -n run_learn.sh && echo "語法 OK"`
Expected: 語法 OK

- [ ] **Step 8: 端到端實跑**

Run: `zsh run_learn.sh send`（或依 `run_learn.sh` 實際的子指令名稱；`grep -n '"send"' run_learn.sh` 確認）

若 outbox 裡是舊格式那篇，會走無圖路徑寄出，`run.log` 不應出現任何 `--image` 相關錯誤。

- [ ] **Step 9: Commit**

```bash
git add run_learn.sh tests/test_send_images_wiring.sh
git commit -m "feat: pass queued diagrams from outbox through to the mailer

do_send reads --outbox-images and turns each line into a --image
argument; send_html now forwards everything past the subject straight to
send_email.py. An empty image list expands to nothing, so text-only
lessons take exactly the path they did before.

tests/test_send_images_wiring.sh greps the wiring rather than sending
mail -- the actual SMTP path cannot be exercised in CI, but a silently
unwired flag can."
```

---

### Task 10: GitHub Actions 串接圖片

**Files:**
- Modify: `.github/workflows/daily-send.yml`（「寄出今天備妥的課」那一步）

**Interfaces:**
- Consumes: Task 6 的 `--outbox-images`、Task 8 的 `--image CID=PATH`
- Produces: 雲端寄出時帶上圖

- [ ] **Step 1: 改 workflow**

把 `.github/workflows/daily-send.yml:77` 這一行：

```yaml
          python3 apply_result.py --outbox-html | python3 send_email.py "每日 DSA"
```

改成：

```yaml
          # 圖跟著 repo 一起被 checkout，outbox 只記路徑；沒圖時 IMGS 是空陣列。
          IMGS=()
          while IFS=$'\t' read -r cid path; do
            [ -n "$cid" ] && IMGS+=(--image "$cid=$path")
          done < <(python3 apply_result.py --outbox-images)
          python3 apply_result.py --outbox-html \
            | python3 send_email.py "每日 DSA" "${IMGS[@]+"${IMGS[@]}"}"
```

`"${IMGS[@]+"${IMGS[@]}"}"` 這個寫法是為了在 `set -u` 下讓空陣列安全展開。

- [ ] **Step 2: 本機驗證 workflow 那段 bash**

Run:
```bash
bash -c '
set -euo pipefail
IMGS=()
while IFS=$'"'"'\t'"'"' read -r cid path; do
  [ -n "$cid" ] && IMGS+=(--image "$cid=$path")
done < <(printf "d1\t/tmp/a.png\nd2\t/tmp/b.png\n")
printf "%s\n" "${IMGS[@]+"${IMGS[@]}"}"
'
```
Expected:
```
--image
d1=/tmp/a.png
--image
d2=/tmp/b.png
```

再驗空輸入不炸：
```bash
bash -c '
set -euo pipefail
IMGS=()
while IFS=$'"'"'\t'"'"' read -r cid path; do
  [ -n "$cid" ] && IMGS+=(--image "$cid=$path")
done < <(printf "")
echo "空陣列 OK，共 ${#IMGS[@]} 個參數"
'
```
Expected: `空陣列 OK，共 0 個參數`

- [ ] **Step 3: YAML 語法檢查**

Run: `python3 -c "import sys; print('需要 pyyaml，改用下面的 gh 指令')" ; gh workflow list 2>/dev/null | head`

若沒有 pyyaml，改用 GitHub 端驗證：push 後 Actions 頁面會顯示 workflow 是否可解析。

- [ ] **Step 4: Commit 並推上去**

```bash
git add .github/workflows/daily-send.yml
git commit -m "feat: attach diagrams when the cloud job sends the daily lesson

Images ride along in the repo checkout, so the workflow only has to turn
--outbox-images into --image flags. Empty expansion is guarded for
set -u so a text-only lesson still sends."
git push
```

- [ ] **Step 5: 雲端實測**

到 GitHub → Actions → daily-send → Run workflow → 勾 `test_send`。
Expected: 測試信寄達（`test_send` 只寄測試信、不動狀態、不走圖片路徑）。

真正帶圖的驗證要等本機備出一篇有圖的課之後，隔天 08:00 的主班寄出，或手動不勾 `test_send` 觸發一次。**手動觸發會真的推進進度**，確定要做再做。

---

### Task 11: CLAUDE.md

本 repo 目前沒有 `CLAUDE.md`，`claude-md-guard` hook 會提醒。趁還有 context 補一份。

**Files:**
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: 前面所有任務落地的約束
- Produces: 無程式介面

- [ ] **Step 1: 寫 CLAUDE.md**

依全域規則：上限 40 行，只寫「agent 在這個專案最容易改壞的事」，可驗證的規則加標記，開頭放 `LAST VERIFIED`。

```markdown
<!-- LAST VERIFIED: 2026-09-06 -->

# dsa-learn-digest

每天寄一封 DSA 學習信。本機備稿（claude）→ git → 雲端寄出（GitHub Actions）。
架構與時刻表看 README，這裡只寫容易改壞的事。

## 課綱前兩行是禁區

`progress.json` 的 `current_index` 索引的是 `syllabus.txt` 裡**非註解行的序號**。
改動前兩行的文字、或在它們之前插入非註解行，會讓 `current_index` 指向錯誤主題，
且 `outbox_ready()` 的 index 比對失敗 —— **整串庫存都寄不出去**。第 3 行之後隨意。
改完一定要跑：
<!-- @assert:cmd python3 -m pytest tests/test_syllabus.py -q -->

## 課綱與 diagram_map.json 必須同步

`diagram_map.json` 的 key 是課綱主題字串，逐字相同。改課綱就要改它。
<!-- @assert:cmd python3 -m pytest tests/test_diagram_map.py -q -->

## 圖片：授權與私有

`assets/hello-algo/` 是 vendored 的 hello-algo 繁中圖，**CC BY-NC-SA 4.0**。
- 每張圖在信與歸檔 markdown 都必須附署名 `圖：Hello 算法 · CC BY-NC-SA 4.0`。
- 原封不動使用，不裁切不加工（一改作，衍生物也要掛同一個授權）。
- **這個 repo 與 `dsa-learn-state` 必須維持私有。** 轉公開前先處理授權與署名。
<!-- @assert:path assets/hello-algo/LICENSE -->

## 圖不能擋信

任何圖片相關的失敗都必須降級成純文字信，不得讓寄信失敗。
`diagrams` 是**選用**欄位，不要加進 `apply_result.REQUIRED`。

## 寄信管線的兩端要一起改

`run_learn.sh`（本機）與 `.github/workflows/daily-send.yml`（雲端）各有一份
寄信串接。改了 `send_email.py` 的介面就要同時改這兩處，只改一邊會在隔天早上才爆。

## 內容取捨自己扛

使用者正在學 DSA，還無法判斷課綱編排、教學深度、選哪張圖。這些自己決定、說明理由即可。
要問他的是格式、閱讀體驗、篇幅這類他每天實際感受得到的事。
```

- [ ] **Step 2: 檢查行數**

Run: `wc -l CLAUDE.md`
Expected: ≤ 40。超過就砍——優先砍 README 抄得到的內容。

- [ ] **Step 3: 驗證標記指到的東西真的存在**

Run:
```bash
test -f assets/hello-algo/LICENSE && echo "LICENSE ok"
python3 -m pytest tests/test_syllabus.py tests/test_diagram_map.py -q
```
Expected: `LICENSE ok`，測試全過。

- [ ] **Step 4: 最終全套回歸**

Run: `python3 -m pytest -v && sh tests/test_sync_guard.sh && sh tests/test_send_images_wiring.sh`
Expected: 全綠

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md recording the traps in this repo

Four things an agent can break here without noticing until the next
morning's mail fails to arrive: shifting the pinned syllabus lines,
letting diagram_map.json drift from the syllabus, breaking the
attribution or privacy the vendored images are licensed under, and
changing send_email.py's interface on only one of its two callers.

Also records that curriculum and teaching-depth calls are the agent's to
make -- the user is learning DSA and cannot yet review them; format and
reading experience are what to ask about instead."
```

---

## Self-Review

**Spec coverage：** 逐節對照 —— 課綱改版（Task 1）、圖片來源與授權（Task 2）、圖檔存放（Task 2）、主題→候選圖對應（Task 3）、資料流的 build_lesson 段（Task 4）、apply_result 驗證段（Task 5）、`--outbox-images`（Task 6）、prompt 版型與 diagrams 欄位（Task 7）、send_email CID（Task 8）、失敗處理（Task 5 Step 3 / Task 8 Step 3 分別實作，測試在同任務）、archive_markdown raw URL（Task 7 Step 4）、信件格式三項改動（Task 1 Step 6-7 的 LeetCode 與篇幅、Task 7 Step 3 的圖片區塊）、影響檔案表全數有對應任務、上線順序對應 Task 1 →（2-8）→ 9-10。無遺漏。

**型別一致性：** `diagrams.sanitize` 回傳 `(dict, bool)`，Task 5 的 apply_result 以 `res, kept = dg.sanitize(res)` 接收 ✓。`diagrams.abs_paths` 回傳 `[(cid, path)]`，Task 6 以 `for cid, path in` 解包 ✓，Task 8 的 `build_message(images=...)` 收同樣形狀 ✓。`candidates_for` 回傳 `list[str]`，`format_available` 收 `list[str]` ✓。`ASSETS_ROOT` 在 Task 3 定義、Task 5/6 的測試以 monkeypatch 覆寫 ✓。

**已知需現場確認（非 placeholder，是環境相依）：** Task 2 Step 5 的 avl_tree 檔名、Task 9 Step 1 的 shell 種類、Task 9 Step 8 的子指令名稱 —— 三處都寫明了怎麼查、查到不同時怎麼辦。
