#!/bin/sh
# 檢查 run_learn.sh 有把 --outbox-images 的結果轉成 send_email 的 --image 參數。
# 真的寄信無法在 CI 驗證，這裡守的是「線有沒有接上」——所以每一條斷言都要能真的抓到
# 對應的退化，而不是隨便找個子字串矇混過去（教訓：舊版 call-site 斷言只認開頭兩個
# 參數，imgargs 忘了轉發也照樣過關）。
set -eu
DIR="$(cd "$(dirname "$0")/.." && pwd)"
S="${1:-$DIR/run_learn.sh}"
fail=0

check() {  # 正面斷言：$1 必須出現在 $S，用固定字串比對（-F），不當 regex 解讀
  if grep -qF -- "$1" "$S"; then
    echo "ok   : $2"
  else
    echo "FAIL : $2（找不到：$1）"; fail=1
  fi
}

refute() {  # 反面斷言：$1 不該出現在 $S——用來抓「退化回舊寫法」這種問題
  if grep -qF -- "$1" "$S"; then
    echo "FAIL : $2（不該出現卻找到：$1）"; fail=1
  else
    echo "ok   : $2"
  fi
}

check 'outbox-images'                                       'do_send 會讀 --outbox-images'
check "IFS=\$'\\t' read -r _cid _path"                       '用真正的 tab 分隔（不是空白或其他字元）'
check '[ -n "$_cid" ] && imgargs+=(--image'                  '空行有擋掉，不會生出垃圾 --image 參數'
check 'send_html "$html" "$SUBJECT_DAILY" "${imgargs[@]}"'   'daily 呼叫 send_html 時真的把 imgargs 轉發出去'
refute 'send_html "$html" "$SUBJECT_DAILY"; then'            'daily 呼叫沒有退化成漏轉發 imgargs 的舊寫法'

# send_html 必須把多出來的參數轉給 send_email.py
if grep -A6 '^send_html()' "$S" | grep -q 'shift 2'; then
  echo "ok   : send_html 用 shift 2 收尾巴參數"
else
  echo "FAIL : send_html 沒有轉發額外參數"; fail=1
fi

exit $fail
