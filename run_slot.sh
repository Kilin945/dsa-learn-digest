#!/bin/zsh
# 一個備稿時段要做的事：每日課程一定備，週報只在週五／週六備。
# 由 launchd 在 12:00 / 13:00 觸發。
#
# 為什麼合成一個 job 而不是 prepare 與 prepare-weekly 各排同一個整點：
#   兩個 job 同時觸發會同時對 ../state 這個 worktree 做 git pull，
#   互搶 index.lock，先到的成功、後到的莫名其妙失敗。依序跑就沒有這個問題。
#
# 週報時程：週五備稿 → 週六 08:00 雲端寄出。週六這兩班是補救用，
# 若早上已經寄成，run_learn.sh 會看到 marker 直接跳過。
#
# 觸發來源有兩種：
#   1. launchd StartCalendarInterval — 12:00 / 13:00 兩個固定班
#   2. launchd WatchPaths — 網路設定一變（例如熱點接上）就觸發
#
# 有 (2) 是因為固定班會漏。7/27 那天機器「醒著且有網路」的時間是 12:04–12:29，
# 兩個固定班一個早了 4 分鐘、一個晚了 31 分鐘，都沒踩進那個窗口。
#
# 時間窗比 ai-news 寬很多，因為這裡備的是「明天早上 08:00 要寄的課」，
# 跟今天幾點備完全無關，晚上補到也有效。窗內重複觸發無害：已備妥會秒退。
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/.run_slot.pid"

# ── 讀真正的界限常數 ─────────────────────────────────────────────────
# SLOT_MAX_SECONDS 曾經固定 1800 秒（見 compute_default_slot_max_seconds 的
# 說明）。這裡借用 run_learn.sh 給測試用的 LEARN_LIB_ONLY 閘門，只載入函式
# 與常數（NET_WAIT_MAX／GIT_NET_TIMEOUT／MAX_TRIES／CLAUDE_TIMEOUT）、不跑
# 任何班次，換到跟 run_learn.sh 真正會用到的同一份數字，不必兩邊各記一份、
# 也不會兩邊改一個忘了改另一個。
LEARN_LIB_ONLY=1 source "$DIR/run_learn.sh" __lib_only__

# 一輪 do_prepare（或 do_prepare_weekly）的最壞情況要多久，公式對應
# run_learn.sh 裡真正的邏輯：
#   wait_for_network：最多 NET_WAIT_MAX 輪，每輪 curl --max-time 5 落空
#     再 sleep 5。
#   git_pull()：最多 3 次嘗試，每次 GIT_NET_TIMEOUT 頂到底，中間 2 次 sleep 5。
#   run_claude 重試迴圈：MAX_TRIES 次，每次 CLAUDE_TIMEOUT 頂到底，
#     中間 sleep 30。
#   git_push_state()：先一次 rebase pull（GIT_NET_TIMEOUT 頂到底），
#     再最多 3 次 push（同 git_pull 的公式）。
# do_prepare_weekly 比 do_prepare 多等一次網路（產生前再檢查一次斷線），
# 其餘公式相同；run_slot.sh 在週五／週六會依序跑完 prepare 再跑
# prepare-weekly，兩輪的預算要疊加，不能只算一輪。
compute_default_slot_max_seconds() {  # $1=是否為週報備稿日（0/1）
  local is_weekly_day="${1:-0}"
  local net_wait_worst=$(( NET_WAIT_MAX * 10 ))
  local git_pull_worst=$(( GIT_NET_TIMEOUT * 3 + 5 * 2 ))
  local git_push_worst=$(( GIT_NET_TIMEOUT + git_pull_worst ))
  local claude_loop_worst=$(( CLAUDE_TIMEOUT * MAX_TRIES + 30 * (MAX_TRIES - 1) ))
  # 本地緩衝：build_lesson.py／apply_result.py 等本地 python 呼叫、
  # git add/commit/rev-list 這些不靠網路但仍要花時間的步驟，不要讓誤差
  # 吃掉安全邊際。
  local local_slack=300
  local daily_worst=$(( net_wait_worst + git_pull_worst + claude_loop_worst + git_push_worst + local_slack ))
  if [ "$is_weekly_day" = 1 ]; then
    # prepare-weekly 額外的一輪（見上方說明），也含它自己的本地緩衝。
    local weekly_extra=$(( net_wait_worst + git_pull_worst + claude_loop_worst + git_push_worst + local_slack ))
    echo $(( daily_worst + weekly_extra ))
  else
    echo "$daily_worst"
  fi
}

# ── 上一輪殘留的偵測：不能再用 pgrep -f 配路徑字串 ──────────────────────
# 舊版用 `pgrep -f "$DIR/run_slot.sh"` 找上一輪，這是配「整條命令列裡有沒有
# 出現這串路徑」，配到的不只是真的在跑這支 script 的殼：vim 開著這個檔案、
# less 在看它、grep 掃過它、隨便一支把它當參數印出來的 wrapper，全部都會
# 中獎。kill -9 -pgid 收掉的又是整個 process group，使用者開著在編輯這支
# 檔案的編輯器會連整個前景群組一起被收掉，事前不會問、事後也救不回沒存的
# 東西。
#
# 改用 pidfile：每一輪一開始就把自己的 pid 寫進 $PIDFILE，下一輪只信這個
# pid，而且動手前要把它從頭到尾驗過一遍，任何一關沒過就留著不動、只記
# log 說明為什麼——殘留的舊輪沒收掉頂多是下一次還要再判斷一次，跟殺掉
# 使用者的編輯器比起來，前者的代價小得多。
_etime_to_seconds() {  # 把 ps -o etime= 的格式（[[dd-]hh:]mm:ss）換算成秒數
  local etime="$1" days=0 rest="$1"
  case "$etime" in
    *-*) days="${etime%%-*}"; rest="${etime#*-}" ;;
  esac
  local -a parts
  parts=(${(s.:.)rest})
  local hh=0 mm=0 ss=0
  case ${#parts[@]} in
    3) hh="${parts[1]}"; mm="${parts[2]}"; ss="${parts[3]}" ;;
    2) hh=0; mm="${parts[1]}"; ss="${parts[2]}" ;;
    1) hh=0; mm=0; ss="${parts[1]}" ;;
    *) echo 0; return ;;
  esac
  # 去掉可能的前導零造成的八進位誤判（10# 強制十進位，同檔案其他地方的慣例）。
  echo $(( 10#$days*86400 + 10#$hh*3600 + 10#$mm*60 + 10#$ss ))
}

# 這個候選 pid 是不是「真的是卡住的舊 run_slot.sh」，要三關都過：
#   1. comm 是殼（zsh/bash/sh），不是任何隨便撿到路徑字串的程式
#      （vim/less/grep/tail 的 comm 都不會是殼）。
#   2. argv 恰好是「殼 這支 script」兩個字，跟我們自己這條路徑完全相等——
#      不是「命令列裡有出現這個字串」（pgrep -f 出包的原因），也不是隨便
#      一支同樣叫殼、但在跑別支腳本的 wrapper。
#   3. 活得比這一輪的預算還久——沒活那麼久，可能只是正常還在跑，不能碰。
_is_stale_run_slot() {  # $1=候選 pid
  local pid="$1" comm args age
  kill -0 "$pid" 2>/dev/null || return 1
  comm="$(ps -o comm= -p "$pid" 2>/dev/null)"
  case "$comm" in
    */zsh|zsh|*/bash|bash|*/sh|sh|*/ksh|ksh) ;;
    *) return 1 ;;
  esac
  args="$(ps -o args= -p "$pid" 2>/dev/null)"
  local -a words
  words=(${(z)args})
  [ ${#words[@]} -eq 2 ] || return 1
  [ "${words[2]}" = "$DIR/run_slot.sh" ] || return 1
  age="$(_etime_to_seconds "$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')")"
  [ -n "$age" ] || return 1
  [ "$age" -gt "$SLOT_MAX_SECONDS" ] || return 1
  return 0
}

reap_stale_round() {
  [ -f "$PIDFILE" ] || return 0
  local prev_pid prev_pgid
  prev_pid="$(cat "$PIDFILE" 2>/dev/null | tr -d ' \n')"
  case "$prev_pid" in
    ''|*[!0-9]*) return 0 ;;   # 空的或不是純數字，pidfile 壞掉就當沒有，不猜
  esac
  [ "$prev_pid" = "$$" ] && return 0

  prev_pgid="$(ps -o pgid= -p "$prev_pid" 2>/dev/null | tr -d ' ')"
  if [ -z "$prev_pgid" ]; then
    return 0   # 已經不在了，沒事可做
  fi
  if [ "$prev_pgid" = "$SLOT_PGID" ]; then
    return 0   # 本輪自己人（launchd 包在外面的 caffeinate 也在同個 group）
  fi
  if ! [ "$prev_pgid" -gt 1 ] 2>/dev/null; then
    log "WARN: pidfile 記的上一輪 pid=$prev_pid 的 pgid=$prev_pgid 太危險（<=1），不動它。"
    return 0
  fi
  if ! _is_stale_run_slot "$prev_pid"; then
    log "INFO: pidfile 記的 pid=$prev_pid 沒通過『真的是卡住的舊 run_slot.sh』檢查，留著不動（可能只是還在正常跑，或 pid 已被別的程序複用）。"
    return 0
  fi
  log "WARN: 發現上一輪殘留（pid=$prev_pid, pgid=$prev_pgid），先收掉再開工。"
  kill -9 -"$prev_pgid" 2>/dev/null
}

# 測試用：只載入函式與常數、不觸發任何真正的班次（同 run_learn.sh 的
# LEARN_LIB_ONLY 閘門，見 tests/test_run_slot_stale_round_safety.sh）。
[ -n "${SLOT_LIB_ONLY:-}" ] && return 0

# 測試用：只需要一個「argv／comm 長得跟真正在跑的 run_slot.sh 一模一樣、
# 但不做任何正事」的長壽命行程，拿來測 _is_stale_run_slot／reap_stale_round
# 對「真的是卡住的舊一輪」與「只是剛好撿到路徑字串」的判斷力
#（見 tests/test_run_slot_stale_round_safety.sh）。跟 SLOT_LIB_ONLY 的差別：
# 這裡要真的用 `zsh run_slot.sh` 這樣執行、留一個活著的行程可以被別的
# 測試行程觀察，不是被 source 進呼叫者自己的殼。只認這個環境變數，正常
# launchd 執行路徑不會設它。
if [ -n "${SLOT_TEST_HANG_SECONDS:-}" ]; then
  sleep "$SLOT_TEST_HANG_SECONDS"
  exit 0
fi

# ./run_slot.sh status —— 今天寄了沒、下一篇備了沒？不用翻 run.log。
if [ "${1:-}" = "status" ]; then
  exec python3 "$DIR/apply_result.py" --status
fi

WINDOW_START=800
WINDOW_END=2300
NOW="$((10#$(date +%H%M)))"   # 10# 強制十進位，免得 0900 這種前導零被當八進位
if [ "$NOW" -lt "$WINDOW_START" ] || [ "$NOW" -gt "$WINDOW_END" ]; then
  # 刻意不寫進 run.log：網路設定一天會變很多次，窗外觸發若每次記一行，
  # 幾百行雜訊會把真正要看的 RESULT 淹掉。改成覆寫一個時間戳檔，
  # 想確認「WatchPaths 到底有沒有在動」時看它就好，檔案不會長大。
  date '+%Y-%m-%d %H:%M:%S 窗外觸發，未動作' > "$DIR/.last-trigger.log"
  exit 0
fi

DOW="$(date +%u)"          # 1=週一 … 5=週五 6=週六 7=週日
IS_WEEKLY_DAY=0
if [ "$DOW" = 5 ] || [ "$DOW" = 6 ]; then
  IS_WEEKLY_DAY=1
fi

# ── 卡死防護 ─────────────────────────────────────────────────────────
# 2026-09-04 18:08 那班卡在 git pull 底下的 ssh 整整 17 小時。launchd 不會啟動
# 前一次仍活著的同 label job，所以隔天一整天的班次全部沒跑，而且完全沒有通知
# （卡在 pull 裡，走不到 notify）。單一 git 指令有 git_timeout 顧，這裡顧的是「整輪」：
# 就算日後冒出新的、沒人預料到的卡點，時間到一樣收場，不必事先知道會卡在哪。
SLOT_MAX_SECONDS="${SLOT_MAX_SECONDS:-$(compute_default_slot_max_seconds "$IS_WEEKLY_DAY")}"
SLOT_PGID="$(ps -o pgid= -p $$ | tr -d ' ')"

# 第二層：上一輪若還活著就先收掉（見上方 reap_stale_round 的說明）。
reap_stale_round

# 記下這一輪自己的 pid，供「下一輪」判斷這一輪日後是否殘留。
echo "$$" > "$PIDFILE" 2>/dev/null

# 正常結束時把 pidfile 清掉：不留著一個「已經死掉的 pid」，降低日後那個
# pid 被系統回收給別的程序、剛好又長得很像的機率（雖然 _is_stale_run_slot
# 的三關檢查已經讓這個機率低到可以忽略）。
_cleanup_pidfile() {
  local cur
  cur="$(cat "$PIDFILE" 2>/dev/null | tr -d ' \n')"
  [ "$cur" = "$$" ] && rm -f "$PIDFILE"
}

# 第一層：本輪超時就收掉整個 process group，連 launchd 包在外面的 caffeinate 一起
# （昨天那支 caffeinate 陪著卡了 17 小時，順便讓機器整晚沒睡）。
# 殺 group 而不是單一 pid：真正卡住的是孫子輩的 ssh，只殺自己救不了場。
#
# 不能簡單一句 `kill -9 -"$SLOT_PGID"`：這個 watchdog 子殼本身也在同一個
# process group 裡，那樣會連自己也一起收掉，導致它來不及寫下面那行 WARN
# log（自己把自己的筆砍斷）。所以改成列出這個 pgid 底下的每個 pid、逐一
# kill -9，跳過 watchdog 自己這個 pid，最後才視「有沒有真的殺到誰」決定
# 要不要記 log。
#
# 跟 finding 6（run_learn.sh 的 git_timeout／git_capture）同一個道理：WARN
# 只能在 kill -9 真的送出且生效之後才記，不能先看一眼「還有誰在」、隔了
# 一拍才動手——那個空檔裡本輪隨時可能正常結束，會記出一筆「明明跑完了卻
# 說被強制中止」的假 WARN。這裡用「這一個 pid 的 kill -9 有沒有成功」本身
# 當閘門，不是另外先查一次。
#
# 不用 pgrep -g：pgrep/pkill 預設會排除「呼叫者自己與它所有的祖先行程」
# （man pgrep 的 --a 段），而這個 watchdog 子殼的祖先正好包含我們要殺的
# 那個主行程 $$，會被 pgrep 自動濾掉，反而抓不到真正要殺的對象。改用
# `ps -axo pid=,pgid=` 自己過濾，不受這個排除規則影響。
if [ -n "$SLOT_PGID" ] && [ "$SLOT_PGID" -gt 1 ]; then
  ( sleep "$SLOT_MAX_SECONDS"
    zmodload zsh/system 2>/dev/null
    self="${sysparams[pid]:-$$}"
    killed=0
    for gpid in $(ps -axo pid=,pgid= 2>/dev/null | awk -v want="$SLOT_PGID" '$2==want {print $1}'); do
      [ "$gpid" = "$self" ] && continue
      kill -9 "$gpid" 2>/dev/null && killed=1
    done
    [ "$killed" = 1 ] && echo "$(date '+%Y-%m-%d %H:%M:%S') WARN: 本輪超過 ${SLOT_MAX_SECONDS}s 仍未結束，強制收場（避免卡住吃掉後續班次）。" >> "$DIR/run.log"
  ) >/dev/null 2>&1 &
  SLOT_WD=$!
  trap '_cleanup_pidfile; kill "$SLOT_WD" 2>/dev/null' EXIT
else
  trap '_cleanup_pidfile' EXIT
fi

"$DIR/run_learn.sh" prepare

if [ "$IS_WEEKLY_DAY" = 1 ]; then
  "$DIR/run_learn.sh" prepare-weekly
fi

exit 0
