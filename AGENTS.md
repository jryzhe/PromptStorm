# AGENTS.md

## 專案概覽

PromptStorm CLI — 透過 Vercel AI Gateway 讓兩個 AI 模型在終端機進行辯論/討論/對話。使用者擔任裁判。

## 架構

```
src/promptstorm/    ← 套件原始碼 (src-layout)
main.py             ← CLI 進入點，會把 src/ 注入 sys.path
tests/              ← unittest 測試
data/               ← 辯論歷史 (CSV) 與逐回合紀錄 (JSONL)，已 gitignore
```

**執行進入點**：
- `promptstorm` 主控台指令 → `promptstorm.cli:main`
- `python3 main.py` 直接執行（不須安裝套件，`main.py` 會自動把 `src/` 加到路徑）
- `python3 -m promptstorm` 依賴套件已安裝

## 常用指令

```bash
source .venv/bin/activate
python3 -m pip install -e .

# 執行全部測試
.venv/bin/python -m unittest discover -s tests -v

# 語法檢查（非 mypy/ruff，純 compileall）
.venv/bin/python -m compileall src tests main.py

# 煙霧測試
python3 main.py --stats
python3 -m promptstorm --help
```

## 關鍵注意事項

- **`.env` 解析是自訂實作**，不使用 `python-dotenv`。參見 `src/promptstorm/config.py`。環境變數會覆蓋 `.env` 檔案的值。
- **模型預設值有兩套**：`.env.example` 和 `config.py` 中的 `DEFAULT_*` 常數不同。以 `config.py` 的程式碼常數為準。
- **三種模式**定義在 `src/promptstorm/modes.py` 作為 frozen dataclass：`debate`、`discussion`（協作分析）、`dialogue`（角色對話）。不要假設所有模式都是辯論。
- **速率限制重試**在 `cli.py:101-103` 設定（`rate_limit_retries=2`, `rate_limit_retry_delay_seconds=30`），不在 `config.py`。
- **語言偵測**在 `modes.py:detect_output_language()`，自動判斷繁體中文 vs 英文。基於主題和使用者輸入中的 CJK 字元比例。
- **對話模式清洗邏輯**在 `engine.py:clean_response()` 中有特殊處理：移除思考標籤、禮貌語、舞台指示、說話者標籤，並只取 `「...」` 中的第一段。
- **測試僅用 `unittest`**，無 pytest、無 CI workflow、無 pre-commit。測試使用 `tempfile` 和 `unittest.mock.patch`，無外部固定檔案（fixtures）。
- **`data/` 和 `reports/` 目錄已被 gitignore**。不要在這些目錄中放置需要版本控制的檔案。
- **套件名稱是 `promptstorm`**（`import promptstorm`），但 PyPI 專案名稱是 `promptstorm-cli`（`pyproject.toml`）。
- **`__main__.py`** 支援 `python3 -m promptstorm`。

## 新增模式

若需新增第四種模式，需修改：
1. `src/promptstorm/modes.py` — 新增 `ModeProfile` dataclass 實例並加到 `MODES` dict
2. 測試需覆蓋新模式的名稱、提示詞和輸出格式