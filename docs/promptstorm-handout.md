# PromptStorm CLI 講義

## 一、作品簡介

PromptStorm 是一個可以在終端機中同時操作兩個大語言模型的 CLI 工具。使用者輸入兩個角色或立場，再輸入一個主題，系統就會讓 Player A 與 Player B 輪流回應，形成討論、辯論或角色對話。過程中，使用者可以隨時選擇目前比較支持哪一方、補充自己的意見、繼續更多回合，或輸出最後整理。

這個工具的核心想法是把平常手動做的「把 A LLM 的答案丟給 B LLM，再把 B 的答案丟回 A」自動化，讓多模型互相激盪的流程變成一個可以持續互動的終端機體驗。**最終目的是透過多角度討論，得出比單一模型更好的結果。**

## 二、動機

在 vibe coding 的時代，很多人都有類似的使用經驗：先問一個 LLM 得到答案，再把這個答案貼給另一個 LLM，請它批判、補充或提出不同觀點。這種做法很有用，因為不同模型通常有不同的語氣、推理方式與盲點；讓它們互相討論，常常可以得到比單一模型更完整的答案。

但是手動來回複製貼上有幾個問題：

- 流程很中斷：每一輪都要自己整理上下文、貼到另一個模型。
- 很容易遺漏內容：討論越長，越難維持完整 transcript。
- 不容易控制方向：如果某一方觀點比較有幫助，使用者還需要手動改 prompt 來引導。
- 缺少結論整理：最後常常要再另外請模型總結整段討論。

因此我做了 PromptStorm CLI：它讓兩個大語言模型可以在同一個 terminal session 中輪流發言，使用者則扮演主持人，負責決定討論方向、加入補充資訊，以及要求系統輸出最後結論。

## 三、製作過程：Vibe Coding

這個專案的製作方式主要是 vibe coding，也就是先把想要的使用體驗描述清楚，再透過 AI 輔助逐步產生、修改和整理程式碼。

### 1. 先定義使用情境

一開始先確定工具要解決的問題：使用者想要在終端機裡快速開一場「兩個模型互相討論」的 session。最基本的使用流程是：

```bash
promptstorm discussion
```

接著輸入：

```text
Player A persona >
Player B persona >
Topic >
```

系統開始讓 A 與 B 依序發言，使用者再透過控制選單決定下一步。

### 2. 逐步拆出模組

專案不是把所有邏輯都寫在一個檔案，而是拆成幾個清楚的模組：

- `cli.py`：處理終端機指令、使用者輸入、控制選單與畫面輸出。
- `engine.py`：處理回合流程、prompt 組裝、對話紀錄與重試機制。
- `provider.py`：處理實際呼叫模型 API 的細節。
- `models.py`：定義資料結構。
- `modes.py`：定義 discussion、debate、dialogue 三種模式。
- `reporter.py`：負責輸出最後結論或 fallback summary。
- `config.py`：處理 API key 與模型設定。

這樣拆分的好處是：CLI 只負責使用者介面，engine 只負責流程，provider 只負責模型呼叫。未來如果想換模型平台或增加新模式，不需要重寫整個工具。

### 3. 接上 OpenAI SDK 與 Vercel AI Gateway

PromptStorm 使用兩層串接來呼叫模型：**OpenAI Python SDK** 與 **Vercel AI Gateway**。

**SDK** 是 Software Development Kit（軟體開發套件）的縮寫，簡單來說就是一組別人寫好的程式庫，讓開發者不用從零處理 API 細節，直接呼叫 SDK 提供的函式就能使用某個服務。在這裡，我們使用 OpenAI 提供的 Python SDK（`openai` 套件）來處理 API 請求格式、串流接收與錯誤處理。

但我們不是直接連到 OpenAI，而是把 SDK 的 `base_url` 指到 Vercel AI Gateway：

```text
https://ai-gateway.vercel.sh/v1
```

Vercel AI Gateway 是一個 API 代理層，收到請求後轉發到指定的上游模型（Gemini、Qwen、GPT 等），再把結果送回。這樣的好處是：程式只需要用同一套 OpenAI SDK 的寫法，就能串接不同廠商的模型，而不需要為每個模型分別接不同的 SDK。

### 4. 加入互動控制

一般 chatbot 是一問一答，但 PromptStorm 的重點是「主持一場多模型討論」。因此在初始回合後，CLI 會顯示控制選單：

```text
[A] 我目前支持 A，讓雙方再討論 N 回合
[B] 我目前支持 B，讓雙方再討論 N 回合
[R] 我目前都不支持，讓雙方再討論 N 回合
[I] 我想補充一句話
[O] 輸出結論並結束
```

這讓使用者可以在過程中調整討論方向，而不是被動等待模型自己聊完。

### 5. 補上錯誤處理與 fallback

實際呼叫模型時可能遇到 rate limit、API 錯誤或 conclusion model 失敗。程式中加入了幾個保護：

- 模型限流時可以重試。
- 某一輪模型失敗時，保存目前 transcript，不讓整場 session 消失。
- 最後結論模型失敗時，改用本地 fallback，把已經產生的 transcript 整理輸出。

## 四、專案結構

目前專案主要檔案如下：

```text
PromptStorm/
├── README.md
├── pyproject.toml
├── main.py
└── src/
    └── promptstorm/
        ├── __init__.py
        ├── __main__.py
        ├── cli.py
        ├── config.py
        ├── engine.py
        ├── modes.py
        ├── models.py
        ├── provider.py
        └── reporter.py
```

### `pyproject.toml`

這是 Python 專案的封裝設定。裡面定義：

- 專案名稱：`promptstorm-cli`
- Python 版本需求：`>=3.11`
- 套件依賴：`openai>=1.0.0`
- CLI 指令入口：

```toml
[project.scripts]
promptstorm = "promptstorm.cli:main"
```

這代表安裝完成後，使用者在終端機輸入 `promptstorm`，實際上會執行 `src/promptstorm/cli.py` 裡的 `main()` 函式。

### `main.py`

`main.py` 是本地開發時使用的入口。它會把 `src` 加入 Python import path，讓開發者可以直接執行：

```bash
python3 main.py discussion
```

這對尚未正式安裝套件時很方便。

### `src/promptstorm/__main__.py`

這個檔案支援：

```bash
python3 -m promptstorm
```

它只是把執行權交給 `cli.main()`，讓套件可以用 module 的方式啟動。

## 五、主要資料結構：`models.py`

`models.py` 使用 `dataclass` 定義 PromptStorm 在執行中需要保存的資料。

### `PromptStormConfig`

```python
@dataclass
class PromptStormConfig:
    api_key: str
    player_a_model: str
    player_b_model: str
    report_model: str
```

這個結構保存模型設定：

- `api_key`：Vercel AI Gateway 的 API key。
- `player_a_model`：Player A 使用的模型。
- `player_b_model`：Player B 使用的模型。
- `report_model`：最後整理結論用的模型。

重點是 Player A、Player B 和 report model 是分開設定的，所以討論模型和總結模型可以不同。

### `ModelResponse`

```python
@dataclass
class ModelResponse:
    text: str
```

這是 provider 回傳的統一格式：

- `text`：模型生成的文字。

這樣 engine 不需要知道底層 API 回傳格式，只要拿到 `ModelResponse` 就能繼續處理。

### `DebateTurn`

```python
@dataclass
class DebateTurn:
    session_id: str
    round: int
    speaker: str
    persona: str
    model: str
    response_text: str
    timestamp: str
    status: str = "ok"
    error: str | None = None
```

`DebateTurn` 代表一次發言。它記錄：

- 這是哪一場 session。
- 第幾回合。
- 誰在說話：`A`、`B` 或 `USER`。
- 當時使用的 persona。
- 使用哪個模型。
- 回應內容。
- 時間。
- 呼叫狀態與錯誤訊息。

這個結構是整個 transcript 的基本單位。每次模型或使用者發言，都會變成一筆 `DebateTurn`。

### `DebateSession`

```python
@dataclass
class DebateSession:
    session_id: str
    timestamp: str
    player_a: str
    player_b: str
    topic: str
    turns: list[DebateTurn] = field(default_factory=list)
```

`DebateSession` 是整場討論的容器，包含：

- session ID
- 開始時間
- Player A persona
- Player B persona
- 討論主題
- 所有回合紀錄

可以把它想成一份完整會議紀錄：裡面保存整場對話的所有狀態。

### `normalize_verdict()`

```python
def normalize_verdict(raw_value: str) -> str:
    value = raw_value.strip().upper()
    if value in {"A", "B"}:
        return value
    if value in {"C", "TIE", "DRAW"}:
        return "TIE"
    raise ValueError("Verdict must be A, B, or C.")
```

這個函式把使用者最後的選擇標準化。A 和 B 保持不變，C、TIE、DRAW 都被視為平手或無明確方向。這讓後面的 conclusion writer 不需要處理太多不同輸入格式。

## 六、設定管理：`config.py`

`config.py` 負責讀寫 API key 和預設模型。

### 預設模型

```python
DEFAULT_PLAYER_A_MODEL = "google/gemini-3.1-flash-lite"
DEFAULT_PLAYER_B_MODEL = "alibaba/qwen-3-32b"
DEFAULT_REPORT_MODEL = "openai/gpt-oss-120b"
```

這裡定義三個預設模型。使用者 setup 時可以修改；如果沒有修改，就會使用預設值。

### 設定來源

設定可以從兩個地方讀取：

1. 使用者全域設定，例如 `~/.config/promptstorm/.env`
2. 目前資料夾底下的 `.env`

而且環境變數會覆蓋檔案設定：

```python
for key in CONFIG_KEYS:
    if os.environ.get(key):
        values[key] = os.environ[key]
```

這個設計很實用：全域設定可以放常用 API key，但特定專案資料夾也可以用自己的 `.env` 覆蓋。

### `.env` 解析

專案沒有依賴 `python-dotenv`，而是自己實作簡單的 `.env` 解析：

```python
key, value = line.split("=", 1)
values[key.strip()] = _unquote(value.strip())
```

它會忽略空行、註解和沒有 `=` 的行，也支援把 `'value'` 或 `"value"` 外層引號拿掉。

## 七、模式設定：`modes.py`

`modes.py` 是 PromptStorm 很重要的設計。它把不同 session 類型抽象成 `ModeProfile`。

### `ModeProfile`

```python
@dataclass(frozen=True)
class ModeProfile:
    name: str
    help_text: str
    title: str
    identity_label: str
    counterpart_label: str
    default_persona_template: str
    system_instruction: str
    opening_instruction: str
    continuation_instruction: str
    support_contexts: Mapping[str, str]
    control_lines: tuple[str, ...]
    output_label: str
    final_state_label: str
    conclusion_system: str
    conclusion_instruction: str
```

這個資料結構描述一種模式需要的所有 prompt 和 UI 文案。Discussion 是主線模式——它最符合工具的核心動機。例如：

- `discussion` 強調合作分析和整合，從不同角度補足盲點。
- `debate` 強調攻防和反駁，適合測試論點強度。
- `dialogue` 強調角色扮演和自然對話。

這代表 engine 不需要知道自己正在跑哪一種互動風格，只要拿到對應的 `ModeProfile`，就可以用同一套回合流程運作。

### 三種模式

目前有三種模式（Discussion 是主線）：

```python
MODES = {
    DISCUSSION.name: DISCUSSION,
    DEBATE.name: DEBATE,
    DIALOGUE.name: DIALOGUE,
}
```

#### `discussion`

適合共同分析問題。兩方不是互相攻擊，而是從不同角度補足盲點，最後輸出 synthesis。這是 PromptStorm 預設推薦的模式。

#### `debate`

適合對立觀點辯論。A 和 B 會互相挑戰，使用者最後可以選擇支持 A、支持 B，或沒有明確支持方。

#### `dialogue`

適合兩個角色進行情境對話。這個模式有額外限制：每次只輸出該角色的一句簡短台詞，避免模型一次把整段戲寫完。

### 語言偵測

`detect_output_language()` 會根據主題和使用者補充判斷輸出語言：

- 如果文字要求英文，輸出 English。
- 如果文字要求中文，輸出 Traditional Chinese。
- 如果中文字符比例高，輸出 Traditional Chinese。
- 如果英文字母較多，輸出 English。

這可以讓模型回應更貼近使用者輸入語言。

## 八、模型呼叫：`provider.py`

`provider.py` 負責把 PromptStorm 和實際 LLM API 接起來。

### `ModelProvider` Protocol

```python
class ModelProvider(Protocol):
    def complete(
        self,
        model: str,
        messages: Sequence[dict[str, str]],
    ) -> ModelResponse:
        """Collect one model response."""
```

這是一個介面定義。只要某個 provider 有 `complete()` 方法，就可以被 engine 使用。

這樣做的好處是：

- 未來可以換成 OpenAI、Anthropic、本地模型或其他 gateway。
- 測試時可以用假的 provider，不需要真的呼叫 API。
- engine 不依賴單一服務商。

### `VercelGatewayProvider`

`VercelGatewayProvider` 是目前實際使用的 provider。它的底層就是 OpenAI Python SDK——透過 `OpenAI(api_key=..., base_url="https://ai-gateway.vercel.sh/v1")` 建立 client，後續所有模型呼叫都走同一套 SDK 介面。它做了幾件事：

1. 延遲建立 OpenAI client（第一次呼叫才初始化）。
2. 透過 SDK 的 streaming API 呼叫 Vercel AI Gateway。
3. 逐段收集模型輸出。
4. 每收到一段文字就透過 callback 即時送回 CLI 顯示。

核心呼叫邏輯是：

```python
stream = client.chat.completions.create(
    model=model,
    messages=list(messages),
    stream=True,
)
```

這裡的 `client` 是 OpenAI SDK 的 `OpenAI` 實例，`stream=True` 讓 SDK 以串流模式接收回應。使用 streaming 的好處是，CLI 可以即時印出模型文字，而不是等完整回應產生完才顯示。

## 九、核心流程：`engine.py`

`engine.py` 是 PromptStorm 的核心。它負責建立 session、控制回合、組 prompt、呼叫 provider、清理模型輸出，最後把結果存進 transcript。

### `DebateEngine.__init__()`

```python
def __init__(
    self,
    provider: ModelProvider,
    rounds: int = 3,
    mode: str = "discussion",
    rate_limit_retries: int = 0,
    rate_limit_retry_delay_seconds: float = 0,
    sleep: Callable[[float], None] = default_sleep,
):
```

初始化時會傳入：

- `provider`：實際呼叫模型的物件。
- `rounds`：初始要跑幾回合。
- `mode`：使用 discussion、debate 或 dialogue。
- `rate_limit_retries`：遇到 rate limit 要重試幾次。
- `rate_limit_retry_delay_seconds`：重試前等待多久。
- `sleep`：等待函式，做成參數可以讓測試時替換。

### `run()`

`run()` 負責建立一場新的 `DebateSession`，然後呼叫 `_run_rounds()` 開始初始回合。

```python
session = DebateSession(
    session_id=session_id or _new_session_id(),
    timestamp=_now(),
    player_a=_display_persona(player_a_persona, "A", self.mode_profile),
    player_b=_display_persona(player_b_persona, "B", self.mode_profile),
    topic=topic,
)
```

如果使用者沒有輸入 persona，就會用模式中的預設 persona，例如 `Point of View A`。

### `continue_debate()`

當使用者在控制選單選擇 A、B 或 R 後，CLI 會呼叫 `continue_debate()`，讓現有 session 繼續跑更多回合。

它不是建立新 session，而是在原本的 `session.turns` 後面繼續追加內容。

### `add_human_input()`

當使用者選擇 `[I] 我想補充一句話` 時，這段補充會被存成 speaker 為 `USER` 的 `DebateTurn`。

```python
speaker="USER",
persona="Human",
model="human",
```

這很重要，因為使用者補充會進入 transcript，下一輪模型就能根據這些補充調整回答。

### `_run_rounds()`

`_run_rounds()` 是最核心的迴圈：

```python
for round_number in range(start_round, start_round + max(0, rounds)):
    for speaker in speaker_order:
        ...
```

每一回合中，A 和 B 依序發言。每次發言的流程是：

1. 決定這次 speaker 是 A 還是 B。
2. 找出該 speaker 的 persona。
3. 找出該 speaker 使用的 model。
4. 用 `_build_messages()` 組出 system prompt 和 user prompt。
5. 呼叫 provider 取得模型回應。
6. 用 `clean_response()` 清理輸出。
7. 把結果印到 terminal。
8. 建立 `DebateTurn`，存回 `session.turns`。

這個函式也使用 callback，例如 `on_turn_start`、`on_response`、`on_turn_end`。這代表 engine 本身不直接負責畫面輸出，而是把「發生了什麼事」通知 CLI。這讓核心邏輯和使用者介面比較分離。

### `_complete_with_retries()`

這個函式包住 provider 呼叫，處理 rate limit 重試。

```python
if attempts >= self.rate_limit_retries or not _is_rate_limit_error(error):
    raise
```

只有錯誤看起來像 rate limit 時才重試；其他錯誤會直接往外丟。這避免程式遇到真正的設定錯誤時一直無意義等待。

### `clean_response()`

不同模型常會輸出一些不需要的內容，例如：

- `<think>...</think>` 推理區塊
- `Round 1 [A: ...]` 這種多餘前綴
- 「好的，我明白你的意思了。」這類禮貌開場
- dialogue 模式中多餘的角色名、括號動作、整段敘事

`clean_response()` 會清掉這些雜訊，讓 terminal 中顯示的是更乾淨的發言內容。

### `_build_messages()`

這是 prompt 組裝的核心函式。它會根據：

- 主題 topic
- 目前回合 round number
- 目前 speaker
- speaker persona
- 對手 persona
- 目前 transcript
- 使用者目前支持方向
- 模式 profile
- 輸出語言

組成模型需要的 messages。

如果 transcript 還是空的，代表是第一輪開場，會使用 `opening_instruction`。如果已經有 transcript，就會把先前發言全部放進 prompt，並使用 `continuation_instruction` 要求模型接續討論。

這也是 PromptStorm 可以讓兩個 LLM 互相討論的關鍵：每一輪模型看到的不只是 topic，還包含前面所有人說過的話。

### transcript 格式化

`_format_transcript()` 會把 `session.turns` 轉成純文字 transcript。例如：

```text
Round 1 [A: Point of View A] ...
Round 1 [B: Point of View B] ...
Human input after Round 1: ...
```

這份 transcript 會被放進下一次模型呼叫，也會被 conclusion writer 使用。

## 十、終端機介面：`cli.py`

`cli.py` 是使用者實際接觸最多的部分。

### `main()`

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
```

`main()` 會解析指令。支援的指令包含：

- `setup`
- `discussion`
- `debate`
- `dialogue`

如果使用者輸入 `setup`，就執行設定流程；如果輸入 session mode，就啟動對應模式。

### `build_parser()`

`build_parser()` 使用 Python 標準函式庫 `argparse` 建立 CLI 指令。

它會從 `SESSION_MODE_NAMES` 自動建立模式指令，因此如果未來在 `modes.py` 增加新模式，CLI 可以比較容易擴充。

### `run_setup()`

`run_setup()` 負責建立或更新 `.env`：

1. 讀取目前設定。
2. 用 `getpass.getpass()` 讓使用者輸入 API key。
3. 讓使用者選擇 Player A、Player B 和 report model。
4. 呼叫 `save_api_key()` 寫入設定檔。

使用 `getpass` 的好處是 API key 不會直接顯示在 terminal 上。

### `run_session()`

`run_session()` 是 CLI 啟動一場 session 的主要流程：

1. 取得模式 profile。
2. 讀取設定。
3. 如果沒有 API key，就要求使用者輸入。
4. 讀取 Player A persona、Player B persona 和 Topic。
5. 建立 `VercelGatewayProvider`。
6. 建立 `DebateEngine`。
7. 設定 callback，負責印出回合標題、模型文字和錯誤提示。
8. 呼叫 `engine.run()` 開始初始討論。
9. 進入控制迴圈。
10. 使用 `ConclusionWriter` 輸出最後結果。

這個函式像是整個 CLI 的導演，負責把設定、engine、provider、reporter 串起來。

### `run_control_loop()`

初始回合結束後，控制權回到使用者：

```python
choice = input("請選擇 > ").strip().upper()
```

使用者可以選：

- `A`：目前支持 A。
- `B`：目前支持 B。
- `R`：目前沒有支持方。
- `I`：加入自己的補充。
- `O`：輸出結論並結束。

如果使用者選 A、B 或 R，程式會詢問要繼續幾回合，接著呼叫 `continue_from_control_choice()`。

如果使用者選 I，補充內容會被存進 session，然後使用者可以選擇立刻繼續一回合、改變方向，或直接輸出結論。

### `continue_from_control_choice()`

這個函式把使用者選項轉換成 engine 需要的參數。特別是 dialogue 模式：

```python
if profile.name == "dialogue" and control_choice == "B":
    return ("B", "A")
```

如果使用者希望 B 更主動，dialogue 模式會讓 B 先發言，再輪到 A。這讓角色對話的節奏更自然。

### 錯誤摘要

`summarize_model_error()` 會把太長的錯誤訊息縮短，並特別處理 429 rate limit。這是 CLI 工具常見的小細節：錯誤訊息要有用，但不能把 terminal 洗滿。

## 十一、結論輸出：`reporter.py`

`reporter.py` 負責最後整理。

### `ConclusionWriter.generate_conclusion()`

這個函式會：

1. 取得目前 mode profile。
2. 標準化使用者 verdict。
3. 根據 topic 和 human input 偵測輸出語言。
4. 呼叫 report model。
5. 回傳 conclusion 文字。

report model 會拿到完整 transcript，因此它不是憑空總結，而是根據整場討論整理。

### `build_fallback_conclusion()`

如果 conclusion model 呼叫失敗，程式不會直接崩潰，而是產生本地 fallback：

- 說明 conclusion model 為什麼失敗。
- 顯示 final state。
- 顯示完整 transcript。

這樣至少可以保住使用者已經進行的討論內容。

## 十二、完整執行流程

以下是 PromptStorm 一次 `discussion` session 的流程：

```text
使用者輸入 promptstorm discussion
        |
        v
cli.main() 解析指令
        |
        v
run_session() 載入設定與 API key
        |
        v
輸入 Player A persona、Player B persona、Topic
        |
        v
建立 VercelGatewayProvider 和 DebateEngine
        |
        v
engine.run() 建立 DebateSession
        |
        v
_run_rounds() 讓 A/B 輪流發言
        |
        v
每次發言都用 _build_messages() 組 prompt
        |
        v
provider.complete() 串流呼叫模型
        |
        v
clean_response() 清理模型輸出
        |
        v
新增 DebateTurn 到 session.turns
        |
        v
run_control_loop() 讓使用者決定下一步
        |
        v
輸出 conclusion 或 synthesis
```

## 十三、設計重點整理

### 1. 把模型呼叫抽象成 provider

`engine.py` 不直接呼叫 Vercel，而是透過 `ModelProvider`。這讓核心流程不綁死在單一 API。

### 2. 把不同互動風格抽象成 mode profile

debate、discussion、dialogue 的差異主要放在 `modes.py` 的文字設定，而不是複製三份流程。這讓擴充更容易。

### 3. 用 dataclass 保存 session 狀態

`DebateSession` 和 `DebateTurn` 讓 transcript 結構清楚，也方便後續總結、儲存或測試。

### 4. 使用 callback 分離 engine 和 CLI

engine 透過 `on_turn_start`、`on_response`、`on_turn_end` 通知外部，不直接處理所有 terminal 顯示。這讓核心邏輯比較乾淨。

### 5. 使用 transcript 作為模型之間的共享上下文

每一輪模型都會看到前面的完整 transcript，因此 A 和 B 不是各說各話，而是真的根據對方前一輪內容回應。

### 6. 使用者是主持人，不只是旁觀者

控制選單讓使用者可以介入討論方向，這是 PromptStorm 和單純「兩個 bot 自動聊天」最大的差異。

### 7. 有基本容錯

rate limit 重試、模型錯誤紀錄、fallback conclusion 都讓工具在真實 API 環境中更可用。

## 十四、可以改進的地方

目前專案已經能完成基本多模型討論，但還可以繼續改進：

- 增加測試，特別是 engine、config、mode profile 和 error handling。
- 支援更多 provider，例如直接串 OpenAI、Anthropic 或本地模型。
- 讓使用者可以在 CLI 中切換模型，而不只是在 setup 時設定。

## 十五、這份講義還缺什麼（自我評估）

以下是對照程式碼後，發現這份講義尚未涵蓋或可以補充的部分：

### 1. 安裝與使用流程

講義從動機直接跳到架構，沒有說明使用者如何實際安裝與執行。README 中有 `pipx install`、`promptstorm setup` 等安裝與初始化步驟，這些應該補上。

### 2. `.env.example` 與設定優先順序

專案支援三層設定覆蓋：全域 `~/.config/promptstorm/.env` → 專案 `.env` → 環境變數。講義只提到「環境變數會覆蓋檔案設定」，但沒有說明完整的層級關係。

### 3. 測試架構

`tests/` 目錄下有 `test_engine_streaming.py` 與 `test_no_token_accounting.py`，但講義完全沒有提到測試如何執行、測試了哪些行為。沒有 testing strategy 的描述。

### 4. ANSI 顏色與終端機輸出格式

`cli.py` 使用 `CYAN`（Player A）和 `MAGENTA`（Player B）區分雙方發言，還有 `BOLD`、`TURN_DIVIDER` 等格式。講義沒有說明這些視覺設計。

### 5. Dialogue 模式的特殊 speaker 順序

在 `cli.py:_speaker_order_for_control_choice()` 中，如果使用者在 dialogue 模式選擇「讓 B 更主動」，發言順序會變成 B 先講再換 A。這是 dialogue 特有的行為，講義沒有提及。

### 6. 人類補充（`[I]`）的完整流程

講義只說使用者補充會被存成 `DebateTurn`，但實際上選 I 之後還有子選單：按 Enter 直接繼續 1 回合，或輸入 A/B/R/O 改變方向。這個流程比講義描述的更複雜。

### 7. 各模式的預設回合數差異

`dialogue` 初始只有 1 回合，`debate` 和 `discussion` 是 3 回合。這個差異源於對話模式需要更緊密的輪替節奏，但講義沒有說明。

### 8. Session ID 格式

Session ID 是 `YYYYMMDD-HHMMSS-{8位UUID hex}`，這在除錯和辨識 session 時有用，講義未提及。

### 9. 具體的錯誤類型處理

程式會區分 rate limit（429）、其他 API 錯誤、conclusion model 失敗等不同錯誤，並有對應的處理策略（重試 vs. 直接中斷 vs. fallback）。講義只概括提到「錯誤處理」，沒有說明這些判斷邏輯。

### 10. 預設模型的選擇理由

`google/gemini-3.1-flash-lite` 作為 Player A（輕量快速）、`alibaba/qwen-3-32b` 作為 Player B（不同生態系）、`openai/gpt-oss-120b` 作為總結模型（品質優先）——這個搭配背後有策略考量，講義沒有解釋。

### 11. `data/` 與 `reports/` 目錄

這兩個目錄存在於專案中，但講義和程式碼都沒有說明它們的用途，可能是不再使用或尚未實作的功能。

### 12. ModelProvider Protocol 的測試意圖

`ModelProvider` 被定義為 Protocol，目的是讓測試時可以 inject mock provider。這是 engine 可測試性的關鍵設計，但講義只在八-1 簡略提到，沒有深入說明 testing strategy。

## 十六、心得

（暫時留空）


