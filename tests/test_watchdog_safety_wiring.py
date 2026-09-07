"""把 code review 6 個 finding 裡「watchdog／run_slot.sh 安全性」相關的
tests/*.sh 掛進 python3 -m pytest，跟 test_send_images_wiring.py 是同一個道理：
真正的斷言邏輯留在各自的 .sh 裡（保留獨立執行、獨立除錯的用法），這裡只是
薄薄一層轉發，讓 `python3 -m pytest` 一次就能連這些行為測試一起收集、一起看到
失敗。

這兩支都需要 zsh（source run_learn.sh／run_slot.sh 取函式、用到 zsh 專屬語法），
跟 test_send_images_wiring.py 那兩支可以直接用 /bin/sh 跑的不一樣，所以另外
開一個檔案、明確用 zsh 呼叫，不跟那邊的 _SCRIPTS 混在一起。
"""
import os
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))

_SCRIPTS = [
    "test_git_timeout_marker_race.sh",       # finding 6：逾時記號檔的兩步式 race
    "test_run_slot_stale_round_safety.sh",   # finding 2：不誤殺編輯器／不誤殺無關程序
]


@pytest.mark.parametrize("script", _SCRIPTS)
def test_wiring_script_passes(script):
    r = subprocess.run(["zsh", os.path.join(_HERE, script)],
                        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
