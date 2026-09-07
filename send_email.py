#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""學習信寄送：從 stdin 讀 HTML，透過 Gmail SMTP (STARTTLS) 寄出。
設定優先序：環境變數 > 同目錄 config.env。App Password 從 macOS Keychain 讀。
用法：echo "<html>" | python3 send_email.py ["主旨前綴"] [--image CID=PATH ...]
"""
import os
import sys
import ssl
import smtplib
import argparse
import datetime
import subprocess
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

import diagrams as dg

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.env")


def load_config():
    cfg = {}
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = os.path.expandvars(v.strip().strip('"').strip("'"))

    def get(key, default=None):
        return os.environ.get(key) or cfg.get(key) or default

    return {
        "GMAIL_USER": get("GMAIL_USER"),
        "MAIL_TO": get("MAIL_TO") or get("GMAIL_USER"),
        "KEYCHAIN_SERVICE": get("KEYCHAIN_SERVICE", "dsa-learn-gmail"),
    }


def get_app_password(gmail_user, service):
    # 雲端（GitHub Actions）讀不到 macOS Keychain，優先吃環境變數；本機則回退 Keychain。
    env_pw = os.environ.get("GMAIL_APP_PASSWORD")
    if env_pw:
        return env_pw.strip()
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-a", gmail_user, "-s", service, "-w"],
            check=True, capture_output=True, text=True,
        )
        return out.stdout.strip()
    except FileNotFoundError:
        print("ERROR: 找不到 security 指令且未設 GMAIL_APP_PASSWORD 環境變數。", file=sys.stderr)
        sys.exit(3)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: 無法從 Keychain 讀取密碼: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(3)


_SUBTYPES = {".png": "png", ".gif": "gif", ".jpg": "jpeg", ".jpeg": "jpeg"}


def _img_subtype(path):
    return _SUBTYPES.get(os.path.splitext(path)[1].lower())


def parse_image_args(specs):
    """把 ["d1=/path/a.png"] 拆成 [("d1", "/path/a.png")]，格式不對的整筆略過。"""
    out = []
    for spec in specs or []:
        cid, sep, path = spec.partition("=")
        if sep and cid and path:
            out.append((cid, path))
    return out


def build_message(html_body, subject, from_user, to_addr, images=None):
    """無圖 → text/html；有圖 → multipart/related 以 CID 內嵌。

    Gmail 不吃 data: URI 也不吃 SVG，CID 是唯一能讓圖顯示在信裡的方式。
    任何一張圖讀不到就整批放棄、剝掉 <img> 改寄純文字 —— 圖是加分項，
    不能因為它讓信寄不出去，也不該讓收件匣裡出現一排破圖。
    """
    images = list(images or [])
    loaded = []
    for cid, path in images:
        try:
            subtype = _img_subtype(path)
            if subtype is None:
                raise OSError("不支援的圖片格式")
            with open(path, "rb") as f:
                loaded.append((cid, f.read(), subtype))
        except OSError as e:
            print(f"WARN: 圖片讀取失敗，改以純文字寄出：{path} ({e})", file=sys.stderr)
            loaded = None
            break

    if loaded:
        msg = MIMEMultipart("related")
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        for cid, data, subtype in loaded:
            img = MIMEImage(data, _subtype=subtype)
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtype}")
            msg.attach(img)
    else:
        # 無條件剝——不能只在「有帶 --image」時才剝：零張圖（沒選圖、或雲端跑的是
        # 舊版程式碼而 outbox 已經是新版寫的）跟「圖讀不到而放棄」是同一種局面，
        # html 裡殘留的 cid: <img> 都必須清掉，否則收件匣會看到一張破圖。
        # strip_img_tags 只動 cid: 的 <img>，週報／警示信這類本來就沒有圖的信
        # 找不到東西可剝，等同 no-op。
        html_body = dg.strip_img_tags(html_body)
        msg = MIMEText(html_body, "html", "utf-8")

    msg["Subject"] = subject
    msg["From"] = formataddr(("DSA Learn Digest", from_user))
    msg["To"] = to_addr
    return msg


def message_html_body(msg):
    """從 build_message() 組好的信件撈出真正的 html 本文文字。

    兩種訊息型態都要能撈到：有圖時是 MIMEMultipart('related')，html 本文
    是裡面 text/html 的那個 part；沒有圖（或圖讀不到而放棄）時整封信本身
    就是一個 MIMEText。供 main() 寄出前的最後一道「內文不能是空的」把關用，
    不管上游是哪條路徑組出這封信，都要能用同一支函式檢查。
    """
    if msg.get_content_maintype() == "multipart":
        for part in msg.get_payload():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject_prefix", nargs="?", default="每日 DSA")
    ap.add_argument("--image", action="append", default=[], metavar="CID=PATH",
                    help="以 CID 內嵌一張圖，可重複")
    args = ap.parse_args()

    conf = load_config()
    if not conf["GMAIL_USER"]:
        print("ERROR: 未設定 GMAIL_USER（請建立 config.env，參考 config.env.example）", file=sys.stderr)
        sys.exit(4)

    html_body = sys.stdin.read()
    stripped = html_body.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        html_body = "\n".join(lines)

    if not html_body.strip():
        print("ERROR: 收到空的內文，停止寄送。", file=sys.stderr)
        sys.exit(2)

    today = datetime.date.today().strftime("%Y-%m-%d")
    subject = f"{args.subject_prefix} — {today}"

    msg = build_message(html_body, subject, conf["GMAIL_USER"], conf["MAIL_TO"],
                        parse_image_args(args.image))

    # 最後一道「內文不能是空的」把關，跟開頭那道 stdin 檢查是兩件事：那道
    # 檢查的是「餵進來的原始字串」，這裡驗的是「組好的信件實際會寄出去的
    # 內容」。diagrams.strip_img_tags 剝圖時（data-fig 標記位置錯誤、或
    # 任何未來新的剝圖 bug）有可能把整段本文清空，那道檢查在 build_message
    # 之前，看不到剝圖之後的結果——真正兜住「寄出去的信不能是空的」這個
    # 不變量的是這裡，不管清空的原因是什麼都擋得住，而不是靠上游每個
    # 剝圖邏輯自己保證不出錯。
    body_text = message_html_body(msg)
    if not body_text.strip():
        print("ERROR: 組好的信內文是空的，停止寄送（可能是圖片驗證失敗、"
              "data-fig 標記位置錯誤，或其他原因把整封信的本文清空了）。",
              file=sys.stderr)
        sys.exit(2)

    app_password = get_app_password(conf["GMAIL_USER"], conf["KEYCHAIN_SERVICE"])

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as s:
            s.starttls(context=ctx)
            s.login(conf["GMAIL_USER"], app_password)
            s.send_message(msg)
        print(f"OK: 寄送成功 -> {conf['MAIL_TO']}（主旨：{subject}）")
    except Exception as e:
        print(f"ERROR: 寄送失敗: {e!r}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
