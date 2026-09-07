<!-- LAST VERIFIED: 2026-09-07 -->

# dsa-learn-digest

每天寄一封 DSA 學習信，本機備稿 → git → 雲端寄出。架構與時刻表看 README，這裡只寫容易改壞的事。

## 課綱凍結前綴是禁區

`progress.json` 的 `current_index` 是凍結線：索引 <= current_index 的每一行都不能動文字、
前面也不能插新的非註解行——這條線隨 current_index 定期前進，不是釘死在某個行數。
<!-- @assert:cmd python3 -m pytest tests/test_syllabus.py -q -->

## html 版型最外層 `<div>` 的白底不能拿掉

`background:#ffffff` 看起來像多餘樣式，容易被「整理版型」順手砍掉。標題／副標／頁尾都在
卡片外直接繼承這層色；Gmail 四平台皆不支援 dark-mode opt-out，拿掉它＝深色模式下標題消失。
<!-- @assert:cmd grep -q 'background:#ffffff' prompt_daily.txt -->

## 課綱與 diagram_map.json 必須同步

`diagram_map.json` 的 key 是課綱主題字串，逐字相同，改課綱就要同步改它。
<!-- @assert:cmd python3 -m pytest tests/test_diagram_map.py -q -->

## 圖不能擋信；送信兩處要一起改

`diagrams` 是選用欄位，不在 `apply_result.REQUIRED` 裡，任何圖片失敗都要降級成純文字信。
`run_learn.sh`（本機）與 `.github/workflows/daily-send.yml`（雲端）各自呼叫 `apply_result.py
--outbox-images` 轉給 `send_email.py`；改一處沒改另一處，或忘了 push master，隔天早上就爆。

## 圖片：授權與私有

`assets/hello-algo/` 是 vendored 的 hello-algo 繁中圖，**CC BY-NC-SA 4.0**：署名照
`prompt_daily.txt` 既有格式、原圖不裁切不加工。本 repo 與 `dsa-learn-state` 須維持私有。
<!-- @assert:path assets/hello-algo/LICENSE -->

## `x or 預設值` 在這裡炸過三次

`x or fallback` 只擋 falsy 值，型別錯但值是 truthy（如錯形狀的非空 dict）會直接穿透，炸在下一行——已修好 `diagrams.sanitize`、`apply_result.py --outbox-images` 分支，改用 `isinstance`；
`apply_result.py:174` 的 `_replay_queue` 還留著舊寫法，刻意不動。

## 兩位讀者、不是準備面試

`prompt_daily.txt` / `prompt_weekly.txt` 寫給兩位讀者（工程師＋無工程背景的產品同事），
目標是理解與應用、不是面試——這兩點都被使用者明確改過，改內容前先確認沒有倒退
（尤其是抄自 `java-learn-digest` 的舊素材）。
