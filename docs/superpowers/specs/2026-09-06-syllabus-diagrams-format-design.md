# 課綱改版、課程配圖、信件格式改版

日期：2026-09-06
狀態：待 review

## 為什麼要做

三件事一起改，因為它們互相牽動：

1. **課綱偏了。** 現在的 24 條把「解題技巧」（雙指標、滑動視窗、前綴和）當成獨立主題，卻整章缺席排序演算法、分治、平衡樹、雜湊原理。目標是系統性學 DSA，不是面試解題訓練。
2. **課程沒有圖。** DSA 的核心概念（記憶體連續配置、指標移動、樹的結構）本質上是視覺的，純文字描述效率低。
3. **LeetCode 區塊沒有作用。** 現在只推薦題號跟一句理由，實際上不會去寫。使用者的原話：「看得到答案的抄一遍，遠勝於看不到答案就不寫。」

改課綱會改變每天的主題，配圖要依主題選，格式要容納圖跟擴充後的解題區塊 —— 所以合成一份設計。

## 不做什麼

- 不自己畫圖（不引入 Graphviz / Mermaid / matplotlib）。用現成圖庫。
- 不改「昨日複習」區塊。解答維持印在題目正下方（使用者明確要求不改）。
- 不加進度列（全課綱 44 條的分母對使用者沒意義；每個主題幾步的分母技術上算不出來）。
- 不處理 Notion 圖片同步。本專案預設不啟用 Notion（`NOTION_PARENT_PAGE_ID` 未設），列為 out of scope。
- 不做「缺口主題自己畫圖」。先讓現成圖庫上線跑一段時間，實際感受「沒圖的日子」是否扎眼，再決定要不要投資自畫管線。

---

## 一、課綱改版

### 硬約束：前兩行不能動

`state_store.current_topic()` 用 `progress.json` 的 `current_index` 去索引**課綱裡非註解行的序號**。目前：

- `current_index: 0` → `Big-O 複雜度：怎麼估一段程式的快慢`（已完成，記在 `completed_topics`）
- `current_index: 1` → `陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處`（進行中，`step: 4`）
- outbox 佇列有 1 篇備妥待寄，標記 `index=1, step=4`

**這兩行的文字與順序必須逐字保持不變，也不得在其之前插入任何非註解行。** 否則 `current_index` 會指向錯誤主題，且 `outbox_ready()` 的 index 比對會失敗 —— README 已記載這個地雷：庫存跟進度對不上時整串庫存都寄不出去。

第 3 行（含）之後可以自由改動，不需要碰任何 state。

### 新課綱（44 條）

```
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

### 設計決定：技巧併進模組，但不併進同一條主題行

使用者選擇「技巧併進它依附的結構章節」。實作上是**掛在同一個模組（M）底下、緊接在結構主題之後，成為獨立的一條主題行**，而不是塞進同一條主題行。

理由：一條主題行的步數由 claude 依 `COVERED_SO_FAR` 判斷何時收尾。「陣列」已走 4 步，再吞下雙指標、滑動視窗、前綴和會變成 12 步以上、`covered` 累積十幾條，收尾判斷會失準。拆成獨立行後因果順序仍保留（先學陣列 → 再學陣列上的掃描技巧），粒度也健康。

### 後果

- 主題數 24 → 44，期程約從 4 個月拉到 7 個月（依 Big-O 花 5 步的節奏估）。
- `空間複雜度` 與 `迭代與遞迴` 被排在陣列之後而非最前面，純粹是因為前兩行動不得。教學上可接受：有陣列當實體例子再談空間複雜度與呼叫堆疊，比一開始空談具體。

---

## 二、課程配圖

### 圖片來源

[krahets/hello-algo](https://github.com/krahets/hello-algo)，開源演算法圖解書。

- **授權 CC BY-NC-SA 4.0**（repo 根目錄 `LICENSE`）。
- `zh-hant/docs/` 底下有 **506 張繁體中文 PNG，共 12.1 MB，平均 25 KB**，多數 1280×720。
- 圖上文字為繁體中文且中英術語對照，與 `prompt_daily.txt` 的「英文為主、中文輔助」原則一致。
- 檔名語意清楚（`array_insert_element.png`、`hash_table_chaining.png`），且大量提供分解步驟圖（`binary_search_step1..7`），與「一天一小步」的課綱天然契合。

### 授權合規

| 條款 | 做法 |
|---|---|
| BY 署名 | 每張圖下方固定一行小字：`圖：Hello 算法 · CC BY-NC-SA 4.0`，連結 <https://www.hello-algo.com/> |
| NC 非商業 | 寄給本人一人的學習信，非商業用途 |
| SA 相同方式分享 | 圖原封不動使用、不裁切不加工，不產生衍生作品 |

**風險點：`dsa-learn-digest` 與 `dsa-learn-state` 兩個 repo 必須維持私有。** 私有 repo 沒有散布行為，授權壓力最小。若日後轉公開，或啟用 Notion 同步並分享頁面，須確保署名仍在。此條寫入 `CLAUDE.md`。

### 圖檔存放：進 repo，不走 base64

**決定：把 `zh-hant` 的 506 張圖 vendored 進主 repo 的 `assets/hello-algo/`（12.1 MB，一次性）。**

替代方案是備稿時按需下載、base64 塞進 `outbox.json`。不採用，理由：

- 備稿在本機、寄出在雲端，圖必須在備稿階段就取得。批次備稿 12 篇（出遠門情境）時要一次抓 12～24 張圖，多一個網路失敗點。
- base64 會讓 `outbox.json` 從純文字膨脹成每篇多出數十 KB，且 git diff 完全不可讀。
- 圖進了 repo，GitHub Actions `checkout` 時本來就一併拿到 —— **所以 outbox 只需要存圖的相對路徑，schema 改動最小。**

保留原始目錄結構（`assets/hello-algo/chapter_xxx/yyy.assets/zzz.png`），方便日後 `git subtree` 或腳本更新。附一份 `assets/hello-algo/LICENSE` 與 `README.md` 說明來源。

### 主題 → 候選圖的對應

新增 `diagram_map.json`：課綱主題字串 → 一或多個 `assets/hello-algo/` 底下的目錄。

```json
{
  "陣列 Array 與動態陣列 ArrayList：連續記憶體的代價與好處": [
    "chapter_array_and_linkedlist/array.assets",
    "chapter_array_and_linkedlist/ram_and_cache.assets"
  ],
  "Binary Search 基礎：邊界條件寫對的固定套路": [
    "chapter_searching/binary_search.assets"
  ]
}
```

課綱 44 條裡約 38 條有對應章節。以下 6 條沒有對應圖（hello-algo 是資料結構教科書，不收解題技巧章）：陣列上的掃描技巧、字串 String、拓撲排序、最短路徑入門、樹的經典題型（LCA/直徑）、答案空間二分。這些主題 `diagram_map.json` 給空陣列，那幾天的信就是純文字。

### 資料流

```
build_lesson.py daily
  ├─ 依 current topic 查 diagram_map.json
  ├─ 列出候選圖檔（相對路徑 + 檔名）
  └─ 在 context 尾端加一段 AVAILABLE_DIAGRAMS

claude（prompt_daily）
  └─ 從候選中挑 0~2 張最貼今日這一小步的，輸出：
       html      —— 內含 <img src="cid:d1"> / <img src="cid:d2">
       diagrams  —— [{"cid":"d1","path":"chapter_.../x.png","caption":"這張圖在講…"}]

apply_result.py --to-outbox
  └─ 驗證：每個 html 裡引用的 cid 都有對應 diagrams 項目，
           且 assets/hello-algo/<path> 檔案確實存在。
           任一項不符 → 丟棄整個 diagrams 並移除 html 裡的 <img> 標籤，
           信照常存進 outbox（純文字）。絕不因為圖而擋信。

apply_result.py --outbox-html    → HTML（含 cid: 引用）
apply_result.py --outbox-images  → 每行 "<cid>\t<絕對路徑>" 的清單（無圖則無輸出）

run_learn.sh / GitHub Actions
  └─ 讀 --outbox-images，組成 --image cid=path 參數傳給 send_email.py

send_email.py
  ├─ 無 --image  → 維持現狀 MIMEText（行為完全不變）
  └─ 有 --image  → MIMEMultipart('related')：HTML part + 每張圖一個
                    MIMEImage，Content-ID 設為 <cid>
```

### 為什麼是 CID 而不是別的

Gmail 不支援 `<img src="data:...">` base64 內嵌，也不支援 SVG。可行的只有 CID 內嵌附件與外部託管 URL。選 CID：不需要額外維運公開託管空間，信件自足，離線也看得到。

### 失敗處理

| 情況 | 行為 |
|---|---|
| 主題無對應圖 | `AVAILABLE_DIAGRAMS: （無）`，claude 不放圖，信純文字 |
| claude 選了不存在的檔案 | 備稿當下驗證失敗 → 剝掉圖、信照常存進 outbox |
| `html` 引用的 cid 沒有對應 diagrams 項目 | 同上 |
| 圖檔讀取失敗（寄出時） | send_email 降級成純 MIMEText 寄出，stderr 記一行警告 |

原則：**圖是加分項，任何圖片相關的失敗都不得阻擋信件寄出。**

因此 `diagrams` **不加入 `apply_result.REQUIRED`**，它是選用欄位。缺少時視為「今天沒圖」，不是錯誤。這也讓 outbox 裡既有的那篇舊格式（無 `diagrams` 欄位）能照常寄出。

---

## 三、信件格式改版

改的是 `prompt_daily.txt` 的版型與教學原則。

### 圖片區塊（新增）

- 位置：「今日小步」卡片內，英文概念標題與一句中文之後、中文解說之前。**先看圖再讀字。**
- 數量上限 2 張，通常 1 張。
- **每張圖下方必須有一段針對那張圖的文字**，指出這張圖在講什麼、要看哪裡。不得圖歸圖、文歸文各講各的。（使用者明確要求）
- 圖下方固定署名小字。
- `<img>` 需設 `style="max-width:100%;height:auto;display:block;"`，避免手機被撐爆。

### LeetCode 區塊（大改）

從「一句話推薦」擴成完整解題導引。標題改為「🎯 動手寫 · LeetCode」。內容依序：

1. **題號、題名、難度、連結**
2. **題目在說什麼** —— 白話翻譯，讓人不用點進去就知道在幹嘛
3. **怎麼用今天學的東西解** —— 條列步驟，把今日概念跟這題的關聯講明
4. **複雜度** —— 時間與空間，各附一句「為什麼」
5. **完整 Java 解答** —— 就放在題目正下方，關鍵行加註解

補充規則：

- 有多種解法時，**只寫最容易理解的那一種**，不列舉全部。
- 不做「藏答案」。Email 無法摺疊（Gmail 不支援 `<details>` 展開），白字反白的做法在手機 Gmail 深色模式下會失效。使用者權衡後選擇「看得到答案的抄一遍，勝過看不到答案就不寫」。

### 維持不變

- 副標仍為「主題「X」· 第 N 步 · 今天搞懂一件事就好」，不加進度列。
- 「昨日複習」區塊完全不動，解答仍印在題目正下方。
- 術語表、頁尾、配色機制不動。

### 篇幅

原本的「5 分鐘讀完」改為軟性原則：**該長才長，不湊字數。** 圖應該取代一部分文字描述而非疊加。LeetCode 區塊擴充後信必然變長，這是刻意的。

### archive_markdown

同步加入圖片，但**用 hello-algo 的公開 raw URL，不用本地相對路徑**：

```markdown
![陣列在記憶體中是連續配置](https://raw.githubusercontent.com/krahets/hello-algo/main/zh-hant/docs/<path>)
```

理由：`lessons/` 是 `../dsa-learn-state/lessons` 的 symlink，圖卻放在 `dsa-learn-digest/assets/`，相對路徑會跨 repo，在 GitHub 上與 Notion 上都 render 不出來。hello-algo 本身是公開 repo，raw URL 永遠可讀，三邊（本地、GitHub、Notion）行為一致。署名同樣要寫進 markdown。

信件用 CID、歸檔用 raw URL，兩者路徑同源（`diagrams[].path` 加不同前綴），不會分歧。

---

## 影響的檔案

| 檔案 | 改動 |
|---|---|
| `syllabus.txt` | 換成新的 44 條（前兩行逐字不動） |
| `assets/hello-algo/**` | 新增，vendored 506 張 PNG + LICENSE + README |
| `diagram_map.json` | 新增，主題 → 候選圖目錄 |
| `build_lesson.py` | daily context 尾端加 `AVAILABLE_DIAGRAMS` |
| `prompt_daily.txt` | 新增 `diagrams` 輸出欄位、圖片版型、改寫 LeetCode 區塊、放寬篇幅 |
| `apply_result.py` | 驗證 diagrams、新增 `--outbox-images`、失敗時剝圖降級 |
| `send_email.py` | 新增可重複的 `--image CID=PATH`，有圖時走 `MIMEMultipart('related')` |
| `run_learn.sh` | 寄信處串接 `--outbox-images` → `--image` |
| `.github/workflows/daily-send.yml` | 同上 |
| `CLAUDE.md` | 新增（本 repo 目前沒有）：記錄課綱前兩行禁區、圖片授權與私有 repo 要求 |
| `tests/` | 補測試（見下） |

## 測試

沿用既有 pytest 佈局。要涵蓋的行為：

- `build_lesson.py`：主題有圖時列出候選、無圖時輸出「（無）」。
- `apply_result.py`：
  - diagrams 合法 → 原樣存進 outbox
  - 引用不存在的檔案 → 剝圖、信仍存進 outbox
  - html 有 `cid:` 但 diagrams 缺對應項 → 剝圖、信仍存進 outbox
  - `--outbox-images` 的輸出格式；無圖時輸出為空
- `send_email.py`：
  - 無 `--image` → 產出的 message 是 `text/html`（回歸測試，確保現狀不變）
  - 有 `--image` → 產出 `multipart/related`，Content-ID 正確
  - 圖檔不存在 → 降級成純 HTML 寄出，不拋例外
- 既有測試全數必須維持綠燈。

## 上線順序

課綱與格式的改動會立刻影響「明天要寄的那篇」，圖片管線則牽動本機與雲端兩端，風險不同，分開上：

1. **課綱＋格式**（不含圖）—— 只改 `syllabus.txt` 與 `prompt_daily.txt`。跑一次 `run_learn.sh daily` 確認產出正常。這一步不碰任何程式，可獨立驗證。
2. **圖片管線** —— vendored 圖庫、`diagram_map.json`、四支程式的改動、測試。本機用 `prepare` 產一篇有圖的信、實際寄一封測試信到 Gmail（網頁版與手機 App 都要看），確認圖真的顯示。
3. **雲端串接** —— 改 workflow，用 `test_send` 手動觸發驗證。

現有 outbox 那 1 篇是舊格式（無圖），會照舊寄出，不受影響。

## 待確認

無。設計已逐節與使用者確認。
