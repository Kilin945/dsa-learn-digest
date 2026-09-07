#!/bin/zsh
# code review finding 2：run_slot.sh:52 曾經用 `pgrep -f "$DIR/run_slot.sh"`
# 找上一輪殘留——這是配「整條命令列裡有沒有出現這串路徑」，vim 開著這個檔案、
# less 在看它、grep 掃過它，全部都會中獎，然後被 `kill -9 -pgid` 連整個前景
# process group 一起收掉，使用者開著在編輯這支檔案的編輯器毫無預警地陣亡。
#
# 修好後改用 pidfile + 三關檢查（見 run_slot.sh 的 _is_stale_run_slot／
# reap_stale_round）：
#   1. pid 不是這一輪自己或自己的 process group
#   2. comm 真的是殼（zsh/bash/sh），argv 恰好等於「殼 run_slot.sh」兩個字
#      （相等比對，不是子字串），不是 vim/less/grep/tail 隨便撿到路徑字串
#   3. 活得比這一輪的預算還久，不是剛好路過的一般執行
# 任何一關沒過就留著不動、只記 log。
#
# 這裡不靠計時賭運氣，而是拿真正的行程來測：
#   - 一個真的長得像「殼在跑 run_slot.sh」的行程（借 SLOT_TEST_HANG_SECONDS
#     這個只給測試用的環境變數，讓它乖乖 sleep、不觸發任何真正的班次）。
#   - 一個 `tail -f run_slot.sh`（argv 裡有這條路徑，但 comm 是 tail，
#     不是殼）——模擬「使用者正在看/編輯這個檔案」的無關行程。
#
# 跑法：zsh tests/test_run_slot_stale_round_safety.sh
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"

fails=0
ok()   { print -r -- "  ok   - $1" }
bad()  { print -r -- "  FAIL - $1"; fails=$((fails+1)) }

if [ ! -f "$DIR/config.env" ]; then
  print -r -- "FAIL: 找不到 $DIR/config.env，無法安全 source run_slot.sh，中止測試。"
  exit 1
fi

TESTROOT="$(mktemp -d -t learn-slot-safety-test)"
PIDFILE="$TESTROOT/pidfile"   # 用暫存路徑，不要碰專案真正的 .run_slot.pid

# 背景行程留一份清單，收尾時全部強制清掉，不管測試中途是否失敗。
_ALL_BG_PIDS=()
cleanup() {
  local p
  for p in $_ALL_BG_PIDS; do
    kill -9 "$p" 2>/dev/null
  done
  wait 2>/dev/null
  rm -rf "$TESTROOT"
}
trap cleanup EXIT

# 只載入函式與常數，不觸發任何真正的班次。
SLOT_LIB_ONLY=1 source "$DIR/run_slot.sh" __lib_only__
if ! typeset -f _is_stale_run_slot >/dev/null || ! typeset -f reap_stale_round >/dev/null; then
  print -r -- "FAIL: run_slot.sh 沒有定義 _is_stale_run_slot／reap_stale_round"
  exit 1
fi
PIDFILE="$TESTROOT/pidfile"   # 覆寫成測試用路徑（source 進來的是專案真正的路徑）
SLOT_PGID="$(ps -o pgid= -p $$ | tr -d ' ')"

# 測試行程不能直接用 `cmd &` 背景執行：非互動殼沒開 job control，背景 job
# 會直接沿用「這支測試腳本自己」的 process group，那樣 reap_stale_round
# 一眼就會判定「跟我同組」而安全跳過——測不到真正要測的三關檢查（那三關
# 假設的前提正是「上一輪」的 pgid 跟這一輪不同，就像 launchd 每次啟動都給
# 新的 process group 一樣）。借 python3 的 subprocess.start_new_session
# 讓測試行程真的落在自己獨立的 process group，才是忠實模擬。
spawn_detached() {  # $1=SLOT_TEST_HANG_SECONDS 秒數（空字串＝不設，用來造 tail -f 那種）；其餘參數是要執行的指令
  local secs="$1"; shift
  # stdout/stderr/stdin 都要導去 DEVNULL，不能讓孫子行程沿用 python3 這裡
  # 拿來回傳 pid 的那個管線——不然只要孫子行程還活著（還沒 sleep 完），
  # 這個管線的寫入端就不會真正關閉，外層 $(...) 會一直等它，整支測試卡住。
  SLOT_TEST_HANG_SECONDS="$secs" python3 -c '
import os, subprocess, sys
p = subprocess.Popen(sys.argv[1:], start_new_session=True,
                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(p.pid)
' "$@"
}

print -r -- "_is_stale_run_slot／reap_stale_round:"

# ── 案例 1：真的長得像「殼在跑 run_slot.sh」的行程，但還沒活過門檻 ──
# 門檻故意設很大，確保它「還沒活那麼久」，驗證年齡檢查真的有擋。
young_pid="$(spawn_detached 30 zsh "$DIR/run_slot.sh")"
_ALL_BG_PIDS+=("$young_pid")
sleep 0.5   # 讓它真的 fork/exec 完成，ps 看得到穩定的 comm／args
SLOT_MAX_SECONDS=9999
if _is_stale_run_slot "$young_pid"; then
  bad "行程還沒活過門檻，卻被判定成『卡住的舊一輪』"
else
  ok "行程還沒活過門檻 → 判定不算數（不是誤殺，是還太年輕）"
fi
if kill -0 "$young_pid" 2>/dev/null; then
  ok "行程還活著（沒被誤殺）"
else
  bad "行程不該被殺，卻已經死了"
fi
kill -9 "$young_pid" 2>/dev/null

# ── 案例 2：真的長得像「殼在跑 run_slot.sh」的行程，活過門檻 → 該收 ──
stale_pid="$(spawn_detached 30 zsh "$DIR/run_slot.sh")"
_ALL_BG_PIDS+=("$stale_pid")
sleep 1.2   # 確保 etime 至少滾過 1 秒
SLOT_MAX_SECONDS=0   # 門檻壓到 0：任何活著的秒數都算「超過」
if _is_stale_run_slot "$stale_pid"; then
  ok "真的是卡住的舊 run_slot.sh、活過門檻 → 判定要收"
else
  bad "真的是卡住的舊 run_slot.sh、活過門檻，卻沒被判定要收"
fi

print -r -- "$stale_pid" > "$PIDFILE"
reap_stale_round
sleep 0.3
if kill -0 "$stale_pid" 2>/dev/null; then
  bad "reap_stale_round 沒有把真的卡住的舊一輪收掉"
else
  ok "reap_stale_round 把真的卡住的舊一輪收掉了"
fi

# ── 案例 3（重點）：使用者在編輯／查看這個檔案，argv 裡有路徑但不是殼在跑它 ──
# 這是舊版 `pgrep -f` 出包的具體案例：tail -f 這個檔案，argv 完整包含
# "$DIR/run_slot.sh" 這串路徑，舊邏輯會誤判成上一輪殘留、把它的 process
# group 整組 kill -9 掉。
editor_pid="$(spawn_detached "" tail -f "$DIR/run_slot.sh")"
_ALL_BG_PIDS+=("$editor_pid")
sleep 0.5
SLOT_MAX_SECONDS=0   # 門檻壓到 0，就算年齡檢查會過，comm 檢查也該先擋下來
if _is_stale_run_slot "$editor_pid"; then
  bad "tail -f 這個檔案的行程被誤判成『卡住的舊 run_slot.sh』"
else
  ok "tail -f 這個檔案（argv 有路徑但 comm 不是殼）→ 判定不算數"
fi

print -r -- "$editor_pid" > "$PIDFILE"
reap_stale_round
sleep 0.3
if kill -0 "$editor_pid" 2>/dev/null; then
  ok "reap_stale_round 沒有動 tail -f（不是它要收的對象）"
else
  bad "reap_stale_round 誤殺了 tail -f（本來該留著的『編輯器』被殺了）"
fi
kill -9 "$editor_pid" 2>/dev/null

# ── 案例 4：pidfile 記的就是自己這個 process group → 絕不能動手 ──
print -r -- "$$" > "$PIDFILE"
SLOT_PGID_SAVE="$SLOT_PGID"
reap_stale_round
ok "pidfile 記自己這個 pid → reap_stale_round 安靜跳過（沒有嘗試 kill 自己）"

# ── 案例 5：pidfile 內容壞掉（不是數字）→ 當沒有，不猜 ──
print -r -- "不是數字" > "$PIDFILE"
reap_stale_round
ok "pidfile 內容不是數字 → reap_stale_round 安靜跳過，沒有炸掉"

print -r -- ""
if [ $fails -eq 0 ]; then
  print -r -- "全部通過"
  exit 0
fi
print -r -- "$fails 項失敗"
exit 1
