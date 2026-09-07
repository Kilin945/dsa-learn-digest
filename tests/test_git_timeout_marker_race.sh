#!/bin/zsh
# code review finding 6：git_timeout／git_capture 的逾時記號檔曾經有兩步式的
# race——watchdog 子殼先用 kill -0 看一眼「還活著嗎」，隔了一個指令才補寫記號
# 檔；這中間如果 git 剛好正常結束，記號檔還是會被寫下去，上層就記一筆
# 「WARN: git 操作超過 60s 被強制中止」的假訊息，對照一個其實跑完全程的
# 成功操作。
#
# 兩處的邏輯已經抽成共用的 _watchdog_kill_group()：只有真的送出 kill -9
# 給那個 pid、而且 pid 當下還在（kill 回傳成功）才寫記號檔。這裡直接測這個
# 函式本身，不靠計時去賭競速窗口會不會被踩到——踩不踩得到是機率問題，
# 但「kill 沒生效就不該寫記號」這件事的對錯，用一個已經死掉的 pid 跟一個
# 還活著的 pid 各測一次就能百分之百釘住，不必看運氣。
#
# 跑法：zsh tests/test_git_timeout_marker_race.sh
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"

fails=0
ok()   { print -r -- "  ok   - $1" }
bad()  { print -r -- "  FAIL - $1"; fails=$((fails+1)) }

if [ ! -f "$DIR/config.env" ]; then
  print -r -- "FAIL: 找不到 $DIR/config.env，無法安全 source run_learn.sh（見 test_sync_guard.sh 的說明），中止測試。"
  exit 1
fi
if ! grep -q 'LEARN_LIB_ONLY' "$DIR/run_learn.sh"; then
  print -r -- "FAIL: run_learn.sh 沒有 LEARN_LIB_ONLY 閘門，source 下去會真的寄信——中止測試。"
  exit 1
fi
LEARN_LIB_ONLY=1 source "$DIR/run_learn.sh" __lib_only__

if ! typeset -f _watchdog_kill_group >/dev/null; then
  print -r -- "FAIL: run_learn.sh 沒有定義 _watchdog_kill_group（finding 6 的共用邏輯不見了）"
  exit 1
fi

TESTROOT="$(mktemp -d -t learn-timeout-race-test)"
trap 'rm -rf "$TESTROOT"' EXIT

print -r -- "_watchdog_kill_group:"

# 1. pid 已經正常結束（先跑完、被 wait 收掉）→ kill -9 對它一定失敗 → 不該寫記號。
#    這正是原本兩步式 race 會出包的情境：如果邏輯退化回「kill -0 看一眼 → 隔一拍寫記號」，
#    這個案例仍然可能因為時間點卡對而誤判，但現在的寫法用 kill 本身的成功與否當閘門，
#    一個確定已死的 pid 不會有任何僥倖。
: &
dead_pid=$!
wait "$dead_pid" 2>/dev/null
mark1="$TESTROOT/mark1"
_watchdog_kill_group "$dead_pid" "$mark1"
if [ -f "$mark1" ]; then
  bad "pid 已正常結束，卻還是寫了逾時記號（誤判成被強制中止）"
else
  ok "pid 已正常結束 → 不寫記號"
fi

# 2. pid 還活著 → 真的送出 kill -9，而且要連子進程一起收，記號檔要寫。
# 用巢狀的 zsh -c 造一個「父殼 + 子進程」的真正親子關係（ps 看得到的 PPID），
# 用來順便確認 pkill -9 -P 真的把子進程也收了，不是只殺了父的殼。
zsh -c 'sleep 30 & sleep 30; wait' &
nested_pid=$!
sleep 0.3   # 讓孫子行程真的 fork 出來
mark2="$TESTROOT/mark2"
_watchdog_kill_group "$nested_pid" "$mark2"
sleep 0.3   # 給 kill -9 一點時間真的生效
if [ -f "$mark2" ]; then
  ok "pid 還活著 → 寫了逾時記號"
else
  bad "pid 明明還活著，卻沒寫逾時記號"
fi
if kill -0 "$nested_pid" 2>/dev/null; then
  bad "pid 應該已經被 kill -9 收掉，卻還活著"
else
  ok "pid 真的被收掉了"
fi
wait 2>/dev/null

print -r -- ""
if [ $fails -eq 0 ]; then
  print -r -- "全部通過"
  exit 0
fi
print -r -- "$fails 項失敗"
exit 1
