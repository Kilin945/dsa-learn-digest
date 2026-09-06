import send_email as se


def test_load_config_reads_file_and_env(tmp_path, monkeypatch):
    cfg = tmp_path / "config.env"
    cfg.write_text('GMAIL_USER="a@gmail.com"\nKEYCHAIN_SERVICE="dsa-learn-gmail"\n', encoding="utf-8")
    monkeypatch.setattr(se, "_CONFIG_PATH", str(cfg))
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("MAIL_TO", raising=False)
    conf = se.load_config()
    assert conf["GMAIL_USER"] == "a@gmail.com"
    assert conf["MAIL_TO"] == "a@gmail.com"          # 未設 MAIL_TO → 回退成寄給自己
    assert conf["KEYCHAIN_SERVICE"] == "dsa-learn-gmail"


def test_env_overrides_file(tmp_path, monkeypatch):
    cfg = tmp_path / "config.env"
    cfg.write_text('GMAIL_USER="file@gmail.com"\n', encoding="utf-8")
    monkeypatch.setattr(se, "_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("GMAIL_USER", "env@gmail.com")
    assert se.load_config()["GMAIL_USER"] == "env@gmail.com"


def test_build_message_without_images_is_plain_html():
    # 回歸測試：沒有圖時的 MIME 結構必須跟改動前一模一樣。
    msg = se.build_message("<p>hi</p>", "主旨", "a@gmail.com", "b@gmail.com")
    assert msg.get_content_type() == "text/html"
    assert msg["Subject"] == "主旨"
    assert msg["To"] == "b@gmail.com"
    assert "a@gmail.com" in msg["From"]


def test_build_message_with_image_is_multipart_related(tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    msg = se.build_message('<img src="cid:d1">', "主旨", "a@gmail.com", "b@gmail.com",
                           [("d1", str(png))])
    assert msg.get_content_type() == "multipart/related"
    parts = msg.get_payload()
    assert parts[0].get_content_type() == "text/html"
    assert parts[1].get_content_type() == "image/png"
    assert parts[1]["Content-ID"] == "<d1>"


def test_build_message_degrades_when_image_unreadable(tmp_path, capsys):
    # 圖讀不到絕不能讓寄信失敗——降級成純文字，把 <img> 一併拿掉免得變破圖。
    msg = se.build_message('<p>內文</p><img src="cid:d1">', "主旨",
                           "a@gmail.com", "b@gmail.com",
                           [("d1", str(tmp_path / "missing.png"))])
    assert msg.get_content_type() == "text/html"
    body = msg.get_payload(decode=True).decode("utf-8")
    assert "<img" not in body
    assert "<p>內文</p>" in body
    assert "WARN" in capsys.readouterr().err


def test_build_message_degrades_on_unsupported_extension(tmp_path, capsys):
    # 副檔名不在支援表裡（例如 .webp）不能被靜默猜成 PNG 送出——
    # 讀不到內容一樣要整批放棄、剝掉 <img>、寄純文字並警告。
    webp = tmp_path / "a.webp"
    webp.write_bytes(b"RIFF" + b"\x00" * 32 + b"WEBP")
    msg = se.build_message('<p>內文</p><img src="cid:d1">', "主旨",
                           "a@gmail.com", "b@gmail.com",
                           [("d1", str(webp))])
    assert msg.get_content_type() == "text/html"
    body = msg.get_payload(decode=True).decode("utf-8")
    assert "<img" not in body
    assert "<p>內文</p>" in body
    assert "WARN" in capsys.readouterr().err


def test_build_message_gif_subtype(tmp_path):
    gif = tmp_path / "a.gif"
    gif.write_bytes(b"GIF89a" + b"\x00" * 32)
    msg = se.build_message('<img src="cid:d1">', "s", "a@g.com", "b@g.com",
                           [("d1", str(gif))])
    assert msg.get_payload()[1].get_content_type() == "image/gif"


def test_build_message_strips_cid_tags_when_no_images_passed():
    # 最終審查抓到的案例：零張圖（沒選圖、或雲端跑舊版程式碼對上新版 outbox）
    # 不能只因為「沒有 --image」就整段跳過剝除，否則 cid: <img> 會原封不動寄出去，
    # 收件匣看到一張破圖。無論 images=[] 還是 images=None 都要剝乾淨。
    for images in ([], None):
        msg = se.build_message('<p>x</p><img src="cid:d1">', "主旨",
                               "a@gmail.com", "b@gmail.com", images)
        assert msg.get_content_type() == "text/html"
        body = msg.get_payload(decode=True).decode("utf-8")
        assert "<img" not in body
        assert "<p>x</p>" in body


def test_parse_image_args():
    assert se.parse_image_args(["d1=/tmp/a.png", "d2=/tmp/b.png"]) == [
        ("d1", "/tmp/a.png"), ("d2", "/tmp/b.png")]
    assert se.parse_image_args([]) == []
    assert se.parse_image_args(["壞掉的沒有等號"]) == []
