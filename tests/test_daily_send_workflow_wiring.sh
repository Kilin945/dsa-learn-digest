#!/bin/sh
# 檢查 .github/workflows/daily-send.yml 有沒有把 --outbox-images 的結果轉成
# send_email.py 的 --image 參數。這是雲端那一半的接線，跟 run_learn.sh（本機、
# zsh）各自獨立維護——CLAUDE.md「圖不能擋信；送信兩處要一起改」講的就是這兩處
# 各自都要有守門，改一處沒改另一處，隔天早上才爆。
# 每一條斷言都要能真的抓到對應的退化，不是隨便找個子字串矇混過去。
set -eu
DIR="$(cd "$(dirname "$0")/.." && pwd)"
W="${1:-$DIR/.github/workflows/daily-send.yml}"
fail=0

check() {  # 正面斷言：$1 必須出現在 $W，用固定字串比對（-F），不當 regex 解讀
  if grep -qF -- "$1" "$W"; then
    echo "ok   : $2"
  else
    echo "FAIL : $2（找不到：$1）"; fail=1
  fi
}

check 'apply_result.py --outbox-images'                   '寄信前會讀 --outbox-images'
check "IFS=\$'\\t' read -r cid path"                       '用真正的 tab 分隔（不是空白或其他字元）'
check '[ -n "$cid" ] && IMGS+=(--image "$cid=$path")'      '空行有擋掉，不會生出垃圾 --image 參數'
check 'send_email.py "每日 DSA" "${IMGS[@]+"${IMGS[@]}"}"' '把 IMGS 轉發給 send_email.py（沒圖時在 set -u 下也不會炸掉）'

# 退化偵測：如果 IMGS 轉發被拿掉，"每日 DSA" 那個引號後面會直接斷行結束，
# 不會再接 "${IMGS[@]...}"。用行尾錨點（-E 搭 $）而不是子字串比對（-F）——
# 正確版本本來就包含「送 email.py "每日 DSA"」這段子字串，純子字串比對永遠會
# 誤判成「有問題」，抓不到真正的退化。
if grep -E '"每日 DSA"[[:space:]]*$' "$W" >/dev/null; then
  echo 'FAIL : daily 呼叫沒有把 IMGS 轉發出去（"每日 DSA" 後面沒接東西就斷行了）'; fail=1
else
  echo 'ok   : daily 呼叫沒有退化成漏轉發 IMGS 的寫法'
fi

exit $fail
