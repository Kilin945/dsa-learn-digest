"""把 tests/*.sh 的接線檢查掛進 python3 -m pytest。

這兩支 shell script 各自守著「--outbox-images 的結果有沒有真的轉發成
send_email.py 的 --image 參數」——一支管本機的 run_learn.sh，一支管雲端的
.github/workflows/daily-send.yml。改動前這兩支 sh 都不在 README 的測試指令、
不在任何 @assert:cmd、也沒被 pytest 收集，等於形同虛設。這裡只是薄薄一層轉發：
真正的斷言邏輯留在各自的 .sh 裡（保留原本可以獨立執行、獨立除錯的用法）。
"""
import os
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))

_SCRIPTS = [
    "test_send_images_wiring.sh",
    "test_daily_send_workflow_wiring.sh",
]


@pytest.mark.parametrize("script", _SCRIPTS)
def test_wiring_script_passes(script):
    r = subprocess.run(["sh", os.path.join(_HERE, script)],
                        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
