# dsa-learn-state

LAST VERIFIED 2026-09-07

`dsa-learn-digest` 的 state 分支 worktree。**這裡沒有程式、沒有測試**——每個檔案都是
排程正在讀的活資料，手改沒有任何安全網。機制與時刻表看 `../dsa-learn-digest/README.md`。

## 這裡只有 `state` 分支

worktree 釘在 `state`，`master` 屬於 `../dsa-learn-digest`。在這裡 commit 到 master
就是把資料寫進程式碼分支。動手前先確認。
<!-- @assert:cmd test "$(git branch --show-current)" = state -->

## 寫檔一律原子性，寫完立刻驗

雲端與本機排程隨時可能讀這些檔。`open(p,"w")` 寫一半被讀到就是截斷的 JSON，
而這裡沒有測試會告訴你。用 `tempfile.mkstemp(dir="state")` + `os.replace()`，
寫完馬上把每一行 `json.loads` 一遍、確認沒有殘留 `.tmp`。
判定失效方式：`git log` 出現「修好被截斷的 progress.json／history.jsonl」這種 commit。
<!-- @assert:cmd python3 -c "import json;json.load(open('state/progress.json'))" -->
<!-- @assert:cmd python3 -c "import json;[json.loads(l) for l in open('state/history.jsonl')]" -->

## 同一句摘要有三份副本，改一份就要改三份

一堂課的重點同時存在三個地方，用途各不相同，改錯一處會在不同時間點爆：

| 檔案 | 用途 | 改錯的後果 |
|---|---|---|
| `lessons/<date>.md` | 歸檔，同步到 Notion | 錯的內容永久留在筆記裡 |
| `state/progress.json` 的 `covered[]` | 這個主題已學過什麼 | 同主題後續每一步都建立在錯的前提上 |
| `state/history.jsonl` 最後一行的 `summary` | 明天的「昨日複習」＋每週回顧 | 明天信的開頭複述錯的話 |

2026-09-07 出過一次：只改了前兩份，`history.jsonl` 漏掉，隔天的信會自己打自己。
文字不必逐字相同（`covered` 可以指圖上的標示，`summary` 不行——隔天配的是別張圖），
但**講的事實必須一致**。
判定失效方式：三份講同一堂課的敘述互相矛盾。

## `state/outbox.json` 是待寄佇列，動它就是動明天寄什麼

陣列，一篇一個 `{kind, index, step, result}`，雲端寄頭部那篇。

`apply_result.outbox_ready()` **只比對 index 與 step 兩個整數，不看內容**。所以已經
排在裡面的稿不會因為 prompt 或程式改了而重產——要讓改動對下一封信生效，必須先把
舊稿丟掉再重跑 prepare。
判定失效方式：改了 `prompt_daily.txt` 卻發現隔天的信沒有反映改動。

**危害優先於成因**：發現佇列裡的稿有問題時，先清掉它、再去修產生它的東西。
2026-09-07 反過來做，結果 14:00 那班照寄了已知有錯的信。清掉前先 `cp` 一份到別處，
下一次 prepare 排在 12:00／13:00（外加網路變動觸發），錯過了就得手動補跑。

## marker 檔決定「還會不會寄」

`state/daily-<date>`、`state/weekly-<ISO週>`、`state/alert-<mode>-<date>` 都是空檔案，
存在就代表那個週期已經寄過、不再寄。刪掉一個 → 重複寄；憑空建一個 → 那封信永遠不寄，
而且不會有任何錯誤訊息。這兩個方向都不會有東西提醒你。
判定失效方式：收到重複的信，或某天完全沒信也沒有警示信。

## 私有性

`lessons/` 與 `state/` 都進版控，內容含 vendored 的 CC BY-NC-SA 素材衍生物。
這個 repo 必須維持私有——理由與圖片授權見
`../dsa-learn-digest/CLAUDE.md`「圖片：授權與私有」，不在這裡重複。
