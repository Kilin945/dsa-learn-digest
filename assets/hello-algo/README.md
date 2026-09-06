# hello-algo 繁中圖解（vendored）

來源：<https://github.com/krahets/hello-algo> 的 `zh-hant/docs/`，只取圖檔，保留原目錄結構。
授權：CC BY-NC-SA 4.0（見同目錄 `LICENSE`）。

## 使用規則

- **署名**：每張圖在信件與歸檔 markdown 裡都必須附 `圖：Hello 算法 · CC BY-NC-SA 4.0`，
  連結 <https://www.hello-algo.com/>。
- **不改作**：原封不動使用，不裁切、不加工、不重繪。一旦改作，衍生物也要掛同一個授權。
- **非商業**：本專案是寄給本人一人的學習信，屬非商業使用。
- **repo 必須維持私有**。私有 repo 沒有散布行為，授權壓力最小。
  若日後轉公開、或啟用 Notion 同步並把頁面分享出去，須確保署名仍在。

## 更新方式

```bash
rm -rf /tmp/hello-algo
git clone --depth 1 --filter=blob:none --sparse https://github.com/krahets/hello-algo.git /tmp/hello-algo
git -C /tmp/hello-algo sparse-checkout set zh-hant/docs LICENSE
rsync -am --delete --include='*/' --include='*.png' --include='*.gif' --include='*.jpg' --exclude='*' \
  /tmp/hello-algo/zh-hant/docs/ assets/hello-algo/
cp /tmp/hello-algo/LICENSE assets/hello-algo/LICENSE
python3 -m pytest tests/test_assets.py tests/test_diagram_map.py -v
```

`--delete` 會移除上游刪除的圖，而 `LICENSE` 和 `README.md` 因被 filter 排除，在刪除時受保護。

更新後兩個測試都要重跑：圖數會變（要改 `test_assets.py` 的期待值），
`diagram_map.json` 指到的目錄也可能被上游改名。
