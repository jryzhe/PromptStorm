# PromptStorm 專案理解檢核題與參考答案

以下 30 題用來區分「真正理解 PromptStorm」與「只背過 README 或講義」的人。好的回答應該能說清楚資料流、模組邊界、錯誤情境、設計取捨，以及修改專案時會牽動哪些地方。

## 1. CLI 到第一個模型輸出

**題目：** 如果使用者執行 `promptstorm debate`，從 CLI 解析指令到第一位模型開始輸出，中間會經過哪些主要函式與物件？請按實際資料流說明。

**參考答案：** 使用者執行 `promptstorm debate` 時，安裝後的 console script 會進入 `promptstorm.cli:main()`。`main()` 透過 `build_parser()` 解析子指令，確認 `debate` 是合法 session mode 後呼叫 `run_session(Path.cwd(), "debate")`。`run_session()` 讀設定、詢問 persona 與 topic，建立 `VercelGatewayProvider` 和 `DebateEngine`，再呼叫 `engine.run()`。`DebateEngine.run()` 建立 `DebateSession`，進入 `_run_rounds()`，由 `_build_messages()` 組 prompt，再由 `_complete_with_retries()` 呼叫 provider。provider 透過 OpenAI SDK 指向 Vercel AI Gateway，第一個 streaming chunk 回來時，callback 會一路回到 CLI 的 `on_response()`，印到 terminal。

更完整地說，資料流可以拆成四層：

- 入口層：`promptstorm` 指令、`python3 -m promptstorm` 或 `main.py` 最後都會進到 `cli.main()`，所以真正的 CLI 控制點只有一個。
- 互動層：`run_session()` 負責讀 config、補 API key、詢問 `Player A persona`、`Player B persona`、`Topic`，並建立 callback 讓 engine 回報 turn start、response chunk、turn end 和 retry。
- 流程層：`DebateEngine.run()` 建立 `DebateSession`，再由 `_run_rounds()` 控制每一輪 A/B 發言、選 model、組 messages、處理重試與錯誤 turn。
- provider 層：`VercelGatewayProvider.stream_complete()` 使用 OpenAI SDK 對 Vercel AI Gateway 發出 streaming chat completion，收到 chunk 後透過 `on_delta` 回到 engine，再回到 CLI 印出。

真正理解的人應該能說出「第一個輸出」不是 engine 自己印的，而是 provider 收到 chunk 後經由 callback 傳回 CLI 的 `on_response()`。如果答成「CLI 呼叫 OpenAI 然後印出」就忽略了 provider 抽象和 engine callback 這兩個關鍵邊界。

## 2. 三種啟動入口

**題目：** `main.py`、`src/promptstorm/__main__.py` 和 `pyproject.toml` 裡的 `promptstorm = "promptstorm.cli:main"` 分別解決什麼啟動情境？為什麼三者不是重複的同一件事？

**參考答案：** `main.py` 是 clone repo 後本地開發的便利入口，會把 `src` 加到 `sys.path`，所以可以直接跑 `python3 main.py debate`。`src/promptstorm/__main__.py` 支援套件形式的 `python3 -m promptstorm`。`pyproject.toml` 的 `[project.scripts]` 則讓安裝後的 shell 指令 `promptstorm` 指到 `promptstorm.cli:main`。三者最後都進同一個 CLI main，但服務的是開發、module 執行和正式安裝三種入口。

可以用使用情境來區分：

- `main.py` 偏 repo 內開發：還沒安裝套件時，開發者可以直接執行它；它手動把 `src` 放進 import path，解決 src-layout 專案的本地 import 問題。
- `src/promptstorm/__main__.py` 偏 Python module 執行：當套件可被 import 時，`python3 -m promptstorm` 會執行這個檔案，然後交給 `cli.main()`。
- `pyproject.toml` 的 script 偏發佈後使用者體驗：pipx 或 pip 安裝後，shell 會多一個 `promptstorm` 指令，背後映射到 `promptstorm.cli:main`。

它們不是三份業務邏輯，而是三種啟動包裝。好的設計是所有入口很薄，最後集中到同一個 `main()`，避免開發入口、module 入口和安裝入口出現不同行為。

## 3. CLI、engine、provider 邊界

**題目：** `cli.py` 為什麼不直接組 prompt 或呼叫 OpenAI SDK，而是把流程交給 `DebateEngine`、把 API 呼叫交給 `VercelGatewayProvider`？

**參考答案：** `cli.py` 負責使用者互動、輸入、顏色輸出和控制選單；`DebateEngine` 負責 session 狀態、回合流程、prompt 組裝和重試；`VercelGatewayProvider` 負責外部模型 API。這樣 CLI 不需要知道 SDK 細節，engine 也不需要知道 terminal 顯示方式。測試時也可以用假的 provider 驗證 engine，而不用真的呼叫模型。

這個拆法背後有幾個實際好處：

- 可測試性：engine 只依賴 `ModelProvider` protocol，測試可以塞 fake provider，驗證回合、streaming、錯誤 turn，而不需要 API key 或網路。
- 可替換性：未來如果不走 Vercel AI Gateway，只要新增另一個 provider，理想上 engine 和 CLI 不必大改。
- 責任清楚：CLI 處理 terminal prompt、顏色、控制選單；engine 處理「誰該在第幾輪說什麼」；provider 處理「怎麼向外部模型拿文字」。
- 錯誤邊界清楚：API 例外先在 engine 被轉成 error turn，CLI 再決定怎麼提示使用者；若 CLI 直接呼叫 SDK，很容易把 UI、重試、session 狀態混在一起。

如果把 prompt 組裝和 SDK 呼叫都塞進 `cli.py`，短期看起來少檔案，但後續新增 mode、寫測試、換 provider、做 fallback 都會變得脆弱。

## 4. 預設 persona

**題目：** `DebateEngine.run()` 建立 `DebateSession` 時，為什麼要先把空白 persona 轉成 mode 的預設 persona？這會影響哪些後續 prompt 或輸出？

**參考答案：** 空白 persona 會透過 `_display_persona()` 轉成該 mode 的預設 persona，例如 debate 的 `Point of View A` 或 dialogue 的 `Character A`。這避免 session、prompt identity、turn heading、transcript 和 conclusion 裡出現空名稱，也讓 `_build_messages()` 可以判斷這是預設 persona，改用「不是在扮演名人」的 identity 說法。

這裡不只是顯示文字的問題，也影響 prompt 語意：

- session 層：`DebateSession.player_a` / `player_b` 會被後續 transcript、conclusion prompt、terminal heading 重複使用，所以不能留下空字串。
- mode 層：不同模式有不同預設身份，debate 是 `Point of View {speaker}`，discussion 是 `Perspective {speaker}`，dialogue 是 `Character {speaker}`，這能讓空 persona 仍符合模式語境。
- prompt 層：`_build_messages()` 如果發現 persona 等於預設 persona，就會說 `You are Point of View A. You are not roleplaying a famous person.`；如果使用者輸入自訂 persona，才會說 `You are Player A: ...` 或 `Character A: ...`。
- 使用者體驗層：turn heading 若顯示 `[A: ]` 會很怪，結論裡也會缺角色名稱；預設 persona 能讓 session 看起來完整。

所以 `_display_persona()` 是資料正規化，不只是 UI 美化。它把「使用者沒填」轉成系統可以穩定推進的有效狀態。

## 5. DebateTurn 與 transcript 格式化

**題目：** 一個模型回合完成後，`DebateTurn` 會記錄哪些資訊？`models.py` 裡的 `format_turn()` / `format_transcript()` 為什麼應該依賴這些結構化欄位，而不是只處理純文字？

**參考答案：** `DebateTurn` 記錄 `session_id`、`round`、`speaker`、`persona`、`model`、`response_text`、`timestamp`、`status` 和 `error`。`models.py` 的 `format_turn()` / `format_transcript()` 正是依賴這些欄位，才能把一般模型回合、`USER` 補充和 `status="error"` 的失敗回合格式化成一致 transcript。如果只留純文字，系統就無法知道哪一輪、哪個 speaker、哪個 model 出錯，也無法在 fallback transcript 中標示模型失敗，更難除錯 rate limit 或 provider 問題。

可以把 `DebateTurn` 看成 transcript 的原子事件：

- `round` 和 `speaker` 告訴系統這句話在對話序列中的位置，這對 `_next_round_number()`、fallback transcript 和 conclusion prompt 都重要。
- `persona` 和 `model` 保留當時發言身份與模型選擇，讓後續分析知道這句話不是抽象的 A/B，而是某 persona 用某 model 產生的。
- `status` 和 `error` 讓失敗也能被保存成事件，而不是讓 exception 直接中斷並丟失上下文。
- `timestamp` 對目前 UI 不是最核心，但它讓未來存檔、排序、除錯、session replay 有基礎資料。

`format_turn()` 之所以放到 `models.py`，是因為 engine 和 reporter 都需要同一種 transcript 表示。若各自格式化，會出現 prompt 裡一種格式、fallback conclusion 裡另一種格式，久了就會產生看似小、但很難追的行為差異。

## 6. 回合狀態來源

**題目：** `continue_debate()` 使用 `_next_round_number(session)` 而不是由 CLI 傳入目前回合數，這個設計避免了什麼狀態不同步問題？

**參考答案：** `continue_debate()` 由 engine 用 `_next_round_number(session)` 計算下一輪，避免 CLI 自己保存一份容易過期的回合狀態。這尤其重要，因為 session 裡可能混有 `USER` turn，也可能在模型錯誤後提前停止。engine 直接看目前 transcript，可以避免重複回合或跳號。

這個設計的核心是「session 是唯一真相來源」：

- 使用者按 `I` 補充時，會新增 `speaker="USER"` 的 turn，但這不代表 debate round 要加一。
- 某個模型失敗時，engine 會寫入 error turn 並停止，下一次是否從下一輪開始要根據已有 A/B turn 判斷，而不是根據 CLI 迴圈跑了幾次。
- 如果 CLI 自己維護 `current_round`，就必須和 engine 裡的 turns 永遠同步；只要一次錯誤處理或補充流程忘了更新，就可能出現 round 重複或跳號。
- `_current_debate_round()` 只看 speaker 是 A/B 的 turn，忽略 USER turn，這正好符合「回合」在產品裡的意思：一輪是模型參與者發言，不是任何事件。

所以這題的好答案應該指出：回合數不是 UI 狀態，而是 transcript 狀態的推導值。

## 7. Human input 的資料建模

**題目：** `add_human_input()` 把使用者補充記成 speaker `USER`，而不是直接拼進下一個 prompt。這對 `format_transcript()`、`human_inputs()`、語言偵測和 fallback summary 有什麼好處？

**參考答案：** 使用者補充被存成 `speaker="USER"` 的 `DebateTurn`，所以它會成為正式 transcript 的一部分。`format_transcript()` 能把它顯示成「Human input after Round N」，`human_inputs(session)` 能穩定抽出人類補充給語言偵測使用，fallback conclusion 也能清楚保留人類介入點，而不是把補充混在某個模型回覆裡。

直接拼進下一個 prompt 會有幾個問題：

- provenance 會消失：後續看 transcript 時，不知道哪段是模型說的、哪段是人類插入的。
- 語言偵測會變差：`human_inputs(session)` 可以精準取得人類補充；如果補充混進模型文字，就無法判斷語言意圖到底來自誰。
- fallback 會變含糊：結論模型失敗時，local fallback 仍能標示 `Human input after Round N`，使用者可以知道主持人在哪裡改變方向。
- prompt 控制更乾淨：下一輪 `_build_messages()` 看到的是格式化後的完整 transcript，而不是臨時把人類補充塞在某個特殊 prompt 字串裡。

因此 `USER` turn 讓「人類主持」成為資料模型的一部分。PromptStorm 不是兩個模型自己聊天，而是人類可以介入、改方向、最後決定輸出的 session。

## 8. ModeProfile 的責任

**題目：** 在 `debate`、`discussion`、`dialogue` 三種模式中，哪些東西由 `ModeProfile` 控制？如果要新增第四種模式，最少要改哪些地方？

**參考答案：** `ModeProfile` 控制 mode 名稱、help text、標題、角色稱呼、預設 persona、system/opening/continuation prompt、human support context、控制選單文字、輸出標籤、final state 標籤和 conclusion prompt。新增第四種模式最少要新增一個 `ModeProfile`，放進 `MODES`，必要時調整 CLI 的特殊回合數或 speaker order 規則。

更細地看，`ModeProfile` 把模式差異集中在資料裡：

- CLI 會用 `help_text` 建 subcommand help，用 `title` 顯示 session 標題，用 `control_lines` 顯示控制選單，用 `output_label` 告訴使用者正在輸出 conclusion/synthesis/wrap-up。
- engine 會用 `identity_label`、`counterpart_label`、`default_persona_template`、`system_instruction`、`opening_instruction`、`continuation_instruction` 和 `support_contexts` 組 prompt。
- reporter 會用 `final_state_label`、`conclusion_system` 和 `conclusion_instruction` 組最後整理 prompt 或 fallback header。
- `SESSION_MODE_NAMES = tuple(MODES)` 讓 CLI 自動支援已註冊的 mode subcommand。

新增第四種模式時，理想上只要加新的 profile 並註冊到 `MODES`。只有當新模式的流程規則不同，例如不是 A/B 輪流、初始回合數不同、或控制選項不同，才需要碰 CLI 或 engine 的流程邏輯。

## 9. 初始回合數差異

**題目：** `dialogue` 的初始回合數為什麼是 1，而 `debate` 和 `discussion` 預設是 3？這反映了三種模式在使用體驗上的什麼差異？

**參考答案：** `dialogue` 是角色對話，每回合 A/B 各一句會推進場景；初始 1 回合就足以讓使用者開始主持方向。`debate` 和 `discussion` 需要多一點來回才能形成初始論點、反駁或分析脈絡，所以預設 3 回合。這反映 dialogue 偏「逐句互動」，debate/discussion 偏「先產生一段可評估的思考」。

這個差異其實是產品節奏的差異：

- debate 需要 A 開場、B 反擊，再多幾輪才看得出雙方主張的強弱；太早進控制選單會讓使用者沒有足夠材料判斷支持誰。
- discussion 不是對抗，但也需要多輪才能產生 tradeoff、盲點補充和初步 synthesis；3 回合給它一段可讀的分析基礎。
- dialogue 的價值在於「一來一往」，如果一開始跑太多回合，場景可能已經發展太遠，使用者反而失去主持節奏。
- CLI 用 `initial_rounds_for_mode()` 把這個差異留在明確函式裡，避免散落在 session 啟動流程中。

所以這不是任意數字，而是根據模式互動密度決定的預設。

## 10. Dialogue 的 speaker order

**題目：** `_speaker_order_for_control_choice()` 為什麼只有在 `dialogue` 且使用者選 B 時會改成 `("B", "A")`？如果 debate 也這樣改，語義會變成什麼？

**參考答案：** 在 dialogue 中，如果使用者選 B，意思是讓 B 更主動，所以 `_speaker_order_for_control_choice()` 讓 B 先說，A 再回應。debate 的選 A/B 不是「誰先講」，而是「目前支持哪個方向」，兩方仍應照 A/B 順序辯。如果 debate 也改 speaker order，使用者支持 B 會被誤解成讓 B 搶先發言，而不只是加強 B 的論點。

這題要分清楚「方向」和「發言順序」：

- 在 debate 裡，選 A 表示人類目前支持 A，prompt context 會要求 A 強化論點、B 嘗試反駁；但流程仍然是一輪 A/B，因為辯論結構重點是雙方交鋒。
- 在 discussion 裡，選 A/B 表示某個角度目前比較有幫助，也不代表那一方一定要先講。
- 在 dialogue 裡，選 B 的控制文案是「讓 B 更主動」，角色對話的主動性常常就是誰先開口、誰推進場景，所以改成 B/A 合理。
- 如果把 debate 也改成 B/A，transcript 的閱讀節奏和使用者語意會混在一起：支持 B 可能只是認同 B 的觀點，不一定希望 B 搶先發言。

好的回答應該指出，這是 mode-specific semantics，不是通用 A/B 偏好邏輯。

## 11. Human support 的共用狀態

**題目：** `human_support` 在不同 mode 裡如何被轉成不同的 prompt context？為什麼 `A/B/TIE` 可以共用為內部狀態，但對使用者顯示成不同語意？

**參考答案：** engine 內部只需要 `A`、`B`、`TIE` 三種 human support 狀態，但每個 mode 用 `support_contexts` 把它轉成不同語意。debate 裡 A/B 是支持哪方，discussion 裡是某角度較有幫助，dialogue 裡是某角色更主動。內部狀態共用可以簡化流程，對外文字則由 mode profile 保持語境正確。

這是把「控制狀態」和「模式語言」分開：

- `run_control_loop()` 只需要把使用者輸入 A/B/R 正規化成 A/B/TIE，engine 不需要知道這是「支持」、「方向」還是「主動性」。
- `ModeProfile.support_context()` 才負責把 A/B/TIE 轉成該模式的 prompt 語句。例如 debate 的 TIE 是「sharpen unresolved conflict」，discussion 的 TIE 是「clarify tradeoffs」，dialogue 的 TIE 是「keep interaction balanced」。
- 這讓控制迴圈可共用，不必為三個 mode 寫三份幾乎一樣的分支。
- 同時，對使用者顯示的 `control_lines` 仍然可以是中文且符合模式語意，不會出現 dialogue 裡還寫「支持 A」這種不自然文案。

若有人只回答「A/B/TIE 是最後結論」就不夠精確，因為它在中途控制回合時也會影響下一輪 prompt。

## 12. 語言偵測資料來源

**題目：** `detect_output_language()` 透過 `human_inputs(session)` 只看 topic 和使用者補充，而不是把全部模型 transcript 都拿來判斷。這個選擇避免了什麼語言漂移問題？

**參考答案：** `detect_output_language()` 看 topic 和 `human_inputs(session)`，是因為使用者才是語言意圖來源。若把模型 transcript 也納入，某個模型一時用了英文或中文，後續整場可能被錯誤帶偏。把人類輸入擷取集中在 `models.py` 也讓 engine 和 reporter 對語言判斷的資料來源一致。

具體來說，這裡防的是「模型輸出污染控制訊號」：

- topic 是使用者一開始明確輸入的任務語言，通常最能代表預期輸出語言。
- `USER` turn 是人類後續補充，也應該被視為語言意圖的一部分。
- A/B 模型回覆可能因上游模型習慣、persona 名稱、引用內容或某一輪失誤而切語言；如果拿它們判斷，下一輪 system instruction 可能跟著漂移。
- engine 和 reporter 都用 `human_inputs(session)`，所以過程回覆和最後 conclusion 的語言判斷基準一致。

它不是完美的自然語言偵測器，而是一個產品取捨：寧可相信人類輸入，也不要讓模型互相影響到整場 session 的語言。

## 13. Language instruction 的位置

**題目：** `format_language_instruction()` 放在 system prompt 中的目的，是語言格式控制還是 persona 控制？如果它放到 user prompt，可能會有什麼差異？

**參考答案：** `format_language_instruction()` 是輸出語言控制，不是 persona 控制。放在 system prompt 中，權重較高，也和角色指令一起成為模型的穩定行為約束。若只放在 user prompt，後續 transcript、角色語氣或模型習慣更可能蓋過語言要求。

它的內容有兩層意思：

- 第一層是硬性輸出語言：`Output language: Traditional Chinese.` 或 `Output language: English.`。
- 第二層是避免 persona 名稱造成誤判：persona names 可能用另一種語言，但不要因為角色名是英文就切成英文回答。
- 放在 system prompt 代表它和 `system_instruction` 一起定義模型行為，而不是一次性的 user request。
- conclusion writer 也用同樣的 `format_language_instruction()`，所以最後整理不會因 transcript 混語言就和前面回合不一致。

如果放在 user prompt，模型可能把它當成當輪內容的一部分，而不是整場行為規則；在長 transcript 下尤其容易被前文沖淡。

## 14. Opening 與 continuation prompt

**題目：** `_build_messages()` 在 transcript 為空與不為空時組出的 user prompt 有什麼不同？這對第一輪發言和後續互動的品質有什麼影響？

**參考答案：** transcript 為空時，user prompt 只包含 topic、round、對手和 opening instruction，要求開場提出清楚立場或角色台詞。transcript 不為空時，prompt 會加入 support context、完整 transcript 和 continuation instruction，要求直接接續前文。這避免第一輪被迫回應不存在的內容，也讓後續回合能針對前面發言互動。

這個分支直接影響生成品質：

- 第一輪沒有 prior claims，所以 opening prompt 應要求「開場」而不是「回應上一段」。
- 後續回合有 transcript，模型需要看到前面所有 A/B/USER/error turn，才能回應對手、整合人類補充或知道討論方向。
- `support_context` 只在 continuation 分支出現，因為人類支持 A/B/TIE 是初始回合後的控制訊號，不適合硬塞進開場。
- `counterpart_label` 也由 mode 決定：debate 是 opponent，discussion 是 other perspective，dialogue 是 scene partner，同一份 `_build_messages()` 因此能服務三種模式。

若把兩種 prompt 合併成一套固定模板，第一輪會顯得尷尬，後續回合又可能缺少足夠上下文。

## 15. 通用回覆清理

**題目：** `clean_response()` 會移除 `<think>` 區塊、回合前綴與禮貌開場。這些清理分別對哪些模型輸出行為做防護？

**參考答案：** `<think>` 清理是防止 reasoning model 把思考區塊吐到終端；回合前綴清理是防止模型自作聰明輸出 `Round 1 [A: ...]`，造成 transcript 重複；禮貌開場清理則移除「好的，我明白」這類低資訊量句子，讓 debate/discussion 更直接。

這裡處理的是「模型常見壞習慣」：

- `<think>...</think>` 可能來自推理模型或某些 gateway 模型的思考區塊，若直接顯示，會讓 terminal 輸出冗長且可能暴露不該呈現的中間推理。
- `_strip_turn_prefix()` 避免模型把 PromptStorm 自己的 transcript 格式當成輸出模板再複製一次，否則最後 transcript 會變成 `Round 1 [A] Round 1 [A] ...`。
- `POLITE_FILLERS` 移除「好的」或 `Sure,`，是因為 PromptStorm 的模式強調高訊號辯論、分析或對話，不希望每輪都先寒暄。
- 清理發生在寫入 `DebateTurn` 之前，所以 transcript 保存的是乾淨版本，而不是 UI 印完後才修飾。

但這些清理也有邊界：它們不應該改寫模型論點，只處理包裝、前綴和低資訊開場。

## 16. Dialogue 回覆清理

**題目：** `dialogue` 模式還會用 `_clean_dialogue_reply()` 額外清理回答。為什麼角色對話比 debate 更需要移除 speaker label、舞台指示或多段文字？

**參考答案：** dialogue 要求每次只輸出該角色的一句 spoken reply。模型很容易輸出角色名、舞台指示、括號動作、多段敘事，甚至替對方續寫。`_clean_dialogue_reply()` 會移除 speaker label、開頭舞台指示，優先取中文引號內台詞，並壓成第一段或第一行，讓 terminal 對話更像一來一往。

dialogue 的清理比一般模式更積極，因為它的成功標準不同：

- debate/discussion 可以接受一段完整分析；dialogue 則需要像劇本中某一個角色當下說的一句話。
- 模型常會輸出 `A: ...`、`角色名：...`、`（微笑）...`、`[走向窗邊]...`，這些對 terminal 逐句對話來說會干擾節奏。
- 若模型輸出 `「台詞」`，程式優先取引號內文字，這對中文角色對話特別有用。
- 若沒有引號，程式會取第一段、第一行，再次移除 speaker label 和 stage direction，降低模型一次續寫整段場景的機率。

這不是完美劇本 parser，而是把模型輸出壓回產品承諾：「只回此角色的一句話」。

## 17. complete 與 streaming 抽象

**題目：** `VercelGatewayProvider.complete()` 其實呼叫 `stream_complete()`。這代表「非 streaming API」在目前實作中是什麼樣的抽象？

**參考答案：** `complete()` 雖然看起來是非 streaming 介面，但目前實作只是呼叫 `stream_complete()` 並等全部 chunk 組完。也就是 provider 對外保留「拿完整 `ModelResponse`」的抽象，內部實際仍使用 streaming API。engine 可以依有沒有 `on_delta` 決定是否讓使用者即時看到 chunk。

這個設計有一點微妙：

- provider protocol 只要求 `complete()`，代表 engine 最基本只需要「給 messages，拿完整文字」。
- `VercelGatewayProvider` 額外提供 `stream_complete()`，engine 用 `getattr()` 動態偵測，有 `on_delta` 且 provider 支援 streaming 時才走 streaming。
- `complete()` 呼叫 `stream_complete()`，讓 provider 實作只有一條真正的 API 路徑，避免 streaming 和 non-streaming 兩套邏輯產生差異。
- 對 conclusion writer 來說，它只呼叫 `provider.complete()`，不需要關心 streaming；對 CLI session 來說，它傳入 `on_response`，所以 engine 會選 streaming path。

所以「非 streaming」在這裡是呼叫端抽象，不代表底層 HTTP 請求真的不是 streaming。

## 18. chunk 與完整回覆

**題目：** 在 `stream_complete()` 裡，為什麼要同時累積 `parts` 並透過 `on_delta` 即時送出 chunk？這分別服務 engine 的哪兩個需求？

**參考答案：** `parts` 用來累積完整文字，最後回傳 `ModelResponse(text=...)` 給 engine 存進 `DebateTurn`。`on_delta` 則讓 CLI 在模型生成時即時印出，不必等整段完成。前者服務資料完整性與 transcript，後者服務互動體驗。

兩者缺一都會壞：

- 只有 `on_delta` 沒有 `parts`，使用者可能看得到串流文字，但 session 無法保存完整回覆，後續 transcript 和 conclusion 都會缺資料。
- 只有 `parts` 沒有 `on_delta`，功能仍可完成，但 terminal 體驗會變成等待整段模型完成，失去 streaming 的即時感。
- `stream_complete()` 在迭代 chunks 時只取有 `choices`、有 `delta.content` 的片段，避免空 chunk 或 metadata 進入文字。
- 最終回傳 `ModelResponse(text="".join(parts))`，讓 engine 不必知道 OpenAI SDK chunk 的 shape。

這正是 provider 抽象的價值：外部 API 是 chunk stream，內部業務邏輯拿到的是穩定的 `ModelResponse`。

## 19. rate limit 重試條件

**題目：** `DebateEngine._complete_with_retries()` 何時會重試 rate limit，何時即使是錯誤也不重試？請特別說明 `emitted_delta` 的作用。

**參考答案：** `_complete_with_retries()` 只在錯誤像 rate limit、尚未超過重試次數、而且還沒有 emit 任何 delta 時重試。若已經 emit delta，代表使用者 terminal 已看見部分內容；此時重試可能造成畫面上有兩份同一回合的開頭。非 rate limit 錯誤或重試用盡也會直接拋出。

重試條件可以拆成三個 gate：

- 錯誤類型 gate：`_is_rate_limit_error()` 只用在 rate limit 或 429 類錯誤，其他錯誤例如 auth、bad request、SDK bug 不應盲目重試。
- 次數 gate：`attempts >= self.rate_limit_retries` 時停止，避免無限等待。
- streaming 一致性 gate：`emitted_delta` 一旦為 true，表示已經有文字交給 UI；此時重試會造成使用者看到的輸出和最後保存的 transcript 不一致。

`on_model_retry` callback 讓 CLI 可以顯示「模型暫時限流，N 秒後重試」，而 `sleep` 可注入則讓測試不用真的等 30 秒。好的回答應該能說出這不只是技術重試，而是在保護 terminal 顯示、transcript 和使用者信任。

## 20. streaming 中斷後不重試

**題目：** 如果模型在 A 已經 streaming 出部分文字後中斷，為什麼目前設計不安全地重試同一回合？這對 terminal 顯示與 transcript 一致性有什麼意義？

**參考答案：** streaming 已輸出部分文字後中斷時，terminal 狀態已經不可回滾。如果自動重試，同一回合可能先顯示半段失敗文字，再顯示重試的新文字，但 transcript 只會存其中一份，造成使用者看到的內容和 session 紀錄不一致。因此目前設計寧可記錄失敗，讓使用者用 partial transcript 繼續或收尾。

這題的關鍵是「副作用已發生」：

- streaming chunk 已印到 terminal，程式沒有可靠方式把它從使用者視野中收回。
- 如果重試並成功，terminal 可能包含失敗前半段加成功後完整段；但 `DebateTurn.response_text` 只能存一段文字。
- 如果把兩段都存進 transcript，又會讓模型下一輪看到一段不完整失敗輸出和一段重試輸出，語意更亂。
- 所以 engine 選擇在 exception path 裡新增 `status="error"` turn，保存失敗事實，再把控制權交回 CLI。

這是一種保守的一致性選擇：寧可 session 知道自己失敗，也不要假裝剛才沒有輸出過部分文字。

## 21. 模型失敗時停止回合

**題目：** `_run_rounds()` 在某個 speaker 發生例外時會新增一個 `status="error"` 的 turn 並立刻 `return`。為什麼不是跳過失敗方繼續下一位？

**參考答案：** 某位 speaker 失敗後 `_run_rounds()` 記錄 error turn 並停止，是因為下一位 speaker 需要以前一位的有效發言作為上下文。若跳過失敗方繼續，後續模型會基於缺口對話，容易產生不連貫或假裝對方已回答。停止可以保住 transcript 的真實性，並把控制權交回使用者。

這裡的 `return` 是刻意的流程控制：

- A 失敗時，B 如果繼續，prompt 裡會看到 A 的 error turn，而不是 A 的有效論點；B 可能開始評論一個不存在的回答。
- B 失敗時，下一輪 A 也會面對缺口；繼續跑多輪只會把錯誤擴散到 transcript 後半段。
- error turn 的 `response_text` 是固定訊息，真正 exception 放在 `error` 欄位，讓格式化時可顯示「Model call failed」並附上 detail。
- CLI 收到 partial transcript 後，可以讓使用者選擇補充、換方向或輸出，這比 engine 自動猜下一步更符合「人類主持」的產品定位。

所以這不是「遇錯就崩」，而是把錯誤轉成 transcript 事件，再停止自動流程。

## 22. 可恢復失敗體驗

**題目：** `cli.py` 偵測 `session_has_model_error(session)` 後，仍然允許使用者補充或輸出目前 transcript。這和「整場 session 失敗就退出」相比，產品體驗差在哪裡？

**參考答案：** 這是「可恢復失敗」的體驗設計。模型錯誤不等於整場討論沒有價值；使用者可能已經得到有用 transcript，可以補充一句、換方向，或直接輸出目前內容。相比直接退出，這保留主持權，也避免因單次 API 問題丟失整場 session。

具體使用者體驗差異很大：

- 直接退出會讓使用者失去已經產生的 A/B 回合，尤其長討論或 rate limit 後很挫折。
- 現在的設計會顯示 `latest_model_error_summary()`，再提示可以繼續操作，而不是只丟 stack trace。
- 使用者可以按 `I` 補充上下文，讓後續模型知道剛才出現中斷；也可以按 `O` 讓 reporter 用現有 transcript 收尾。
- 如果 conclusion model 也失敗，還有 local fallback，因此整個產品有兩層「不丟內容」保護。

這種設計符合 CLI 工具的實用精神：外部服務不可靠時，至少保住使用者已經花時間產生的資料。

## 23. conclusion fallback

**題目：** `write_conclusion_safely()` 為什麼包住 `ConclusionWriter.generate_conclusion()`，而不是讓例外一路往上拋出？

**參考答案：** 結論模型是最後一步，失敗時如果例外往上拋，使用者會失去已經產生的 transcript。`write_conclusion_safely()` 把模型總結失敗轉成 fallback conclusion，讓流程仍能以可讀內容結束。這符合 PromptStorm 的核心保護：外部模型失敗時不丟資料。

它包住 conclusion generation 有幾個原因：

- conclusion model 和 A/B participant model 可能是不同模型，最後一步失敗不代表前面討論失敗。
- `ConclusionWriter.generate_conclusion()` 會呼叫 provider，仍可能遇到 rate limit、auth、gateway、SDK 或模型錯誤。
- `write_conclusion_safely()` 把 exception 轉成 `reason`，交給 `build_fallback_conclusion()`，讓使用者知道為什麼是 local fallback。
- CLI 可以用 `used_fallback` 決定是否額外印出提示，而不是讓例外破壞整個 terminal session。

好的回答應該能指出：這個函式不是為了吞錯，而是為了把不可控的外部錯誤轉成可交付的本地輸出。

## 24. fallback conclusion 與共用 transcript 格式

**題目：** `ConclusionWriter.build_fallback_conclusion()` 不能產生真正的智能總結，但仍然有價值。它現在和 engine 共用 `format_transcript()`，這保證了哪些最低限度的輸出與一致性？

**參考答案：** fallback conclusion 至少保證有標題、session ID、topic、Player A/B、human verdict 或 direction、失敗原因，以及完整 transcript。它不假裝有智能分析，但透過和 engine 共用的 `format_transcript(session.turns)`，能用同一套規則呈現模型回合、人類補充和錯誤回合，避免 fallback summary 與 prompt transcript 格式分岔。

fallback 的價值在於最低保證：

- 它保證 session metadata 還在，包括 session id、topic、player persona、final state。
- 它明確寫出 `Conclusion Generation Status: Terminal Fallback`，避免使用者誤以為這是模型產生的高品質總結。
- 它保留失敗原因，使用者可以知道是 conclusion model 沒產生最終 summary，而不是討論本身消失。
- 它輸出完整 transcript，讓使用者可以自己讀、複製到別的模型、或事後重新整理。
- 共用 `format_transcript()` 後，fallback 裡的 USER turn 和 error turn 表示法會和 engine prompt 裡一致。

因此 fallback 不追求「聰明」，它追求「誠實、完整、可恢復」。

## 25. Verdict 正規化

**題目：** `normalize_verdict()` 接受 `C/TIE/DRAW` 都轉成 `TIE`，但錯誤訊息寫 `A, B, or C`。這透露了 CLI 顯示語意和內部語意之間的什麼歷史或相容性問題？

**參考答案：** 這顯示外部或早期 CLI 語意可能曾用 `C` 表示平手或無明確方向，而內部現在統一成 `TIE`。`normalize_verdict()` 接受 `C/TIE/DRAW` 是為了相容多種輸入，但錯誤訊息還停留在 A/B/C 的使用者語彙。它提醒維護者 CLI 顯示語意與內部模型語意需要同步。

這裡有一個小小的歷史痕跡：

- CLI 控制選單現在用 `R` 表示「都不支持」或「沒有明確方向」，內部 `_support_from_control_choice("R")` 會轉成 `TIE`。
- `normalize_verdict()` 接受 `C`、`TIE`、`DRAW`，代表它可能要兼容舊輸入、測試或 reporter 使用情境。
- 錯誤訊息仍寫 `A, B, or C`，表示人類可見語意還沒完全跟內部 `TIE` 命名同步。
- 這不是嚴重 bug，但如果要整理 API 或文案，就應該決定到底對外要叫 `R`、`C`、`TIE` 還是 `DRAW`。

真正理解的人會把它看成「相容性與命名一致性」問題，而不是單純背出函式會回傳什麼。

## 26. 設定優先順序

**題目：** `config.py` 讀設定時會先讀多個 `.env` 檔，再讓環境變數覆蓋。請說明全域設定、本地專案設定與 shell 環境變數的優先順序。

**參考答案：** `load_config_from_paths()` 依序讀傳入的 `.env` 檔，後讀到的非空值會覆蓋先前值。`run_session()` 傳入的順序是全域 config，再讀當前資料夾 `.env`，所以本地專案設定可以覆蓋全域設定。最後 `_config_from_values()` 會讓 shell 環境變數覆蓋所有檔案設定，因此優先序是環境變數最高，本地 `.env` 次之，全域 `.env` 最低。

可以用三層來記：

- 全域 `.env`：`~/.config/promptstorm/.env` 或 Windows 的 `%APPDATA%\promptstorm\.env`，由 `promptstorm setup` 建立，提供預設 API key 和模型設定。
- 本地 `.env`：目前工作目錄下的 `.env`，如果存在會在全域設定後讀取，所以可以針對某個專案覆蓋模型或 key。
- shell environment：`os.environ` 最後覆蓋所有檔案值，適合 CI、臨時測試或不想寫進檔案的秘密。

這種優先序符合常見 CLI 工具習慣：越靠近當前執行環境，優先權越高。也要注意 `_read_env_file()` 是專案自己的簡單 parser，不依賴 `python-dotenv`，所以只支援基本 `KEY=value` 和簡單引號移除。

## 27. 儲存 API key 時保留模型設定

**題目：** `save_api_key()` 在沒有傳入 model 參數時使用 `setdefault()`，而不是每次都覆蓋成預設模型。這保護了使用者的哪一類既有設定？

**參考答案：** `save_api_key()` 若沒有收到 model 參數，會用 `setdefault()` 只在缺少該 key 時補預設模型。這保護使用者先前在 `.env` 裡設定過的 `PLAYER_A_MODEL`、`PLAYER_B_MODEL` 或 `REPORT_MODEL`，避免只是更新 API key 時把自訂模型靜默改回預設值。

這個行為在兩種流程中特別重要：

- `promptstorm setup` 會明確詢問 Player A、Player B、Report model，這時會傳入 model 參數，所以應該覆蓋成使用者最新輸入。
- `run_session()` 發現缺 API key 時，可能只要求使用者貼 key，然後呼叫 `save_api_key(env_path, key)`；這時若強制寫入預設模型，就會破壞既有自訂模型設定。
- `setdefault()` 的意思是「沒有才補」，不是「每次重設」，符合更新 key 時的最小驚擾原則。
- `_format_env()` 會按 `CONFIG_KEYS` 排序輸出，額外 key 排後面，讓檔案格式穩定。

好的回答可以進一步指出：保護模型設定和保護 API key 一樣重要，因為使用者可能已經根據 Gateway 帳號可用模型調過設定。

## 28. OpenAI SDK 與 Vercel AI Gateway

**題目：** `provider.py` 只依賴 `openai` 套件，但 `base_url` 指向 Vercel AI Gateway。請說明這個設計如何同時降低 SDK 複雜度並保留多模型能力。

**參考答案：** OpenAI Python SDK 已經處理 chat completion 請求格式、streaming iterator 和錯誤型別；把 `base_url` 指到 Vercel AI Gateway 後，同一套 SDK 介面就能呼叫 Gateway 後方的多家模型。程式不必為 Gemini、Qwen、OpenAI 等模型各寫一套 provider，同時仍可透過 model id 選擇不同上游模型。

這個設計的 tradeoff 是：

- 好處是程式碼簡單：provider 只建立 `OpenAI(api_key=..., base_url=...)`，再呼叫 `client.chat.completions.create(...)`。
- 好處是模型可切換：`PLAYER_A_MODEL`、`PLAYER_B_MODEL`、`REPORT_MODEL` 都只是 model id，例如可以讓 A/B 使用不同供應商模型。
- 好處是 streaming 行為集中：不必為每家模型寫不同 chunk parser，只要 Gateway 提供 OpenAI-compatible response。
- 限制是 PromptStorm 依賴 Gateway 的相容層；如果某模型有特殊參數或非 OpenAI-compatible 能力，目前 provider 不會直接暴露。

所以它不是「只支援 OpenAI」，而是「用 OpenAI SDK 作為通用 client，實際模型路由交給 Vercel AI Gateway」。

## 29. 現有測試防止的回歸

**題目：** 現有測試特別確認 streaming chunk 會先被 emit、最後 transcript 存 cleaned 完整文字，還確認資料模型不存 token count。這兩個測試分別在防止什麼回歸？

**參考答案：** streaming 測試防止回歸成「等完整回答結束才印出」，也確認 transcript 存的是完整、清理後的文字，不是 chunk 列表。no token accounting 測試防止資料模型重新引入 `tokens_used` 這類欄位，維持近期設計：PromptStorm 不再追蹤或保存 token 用量。

兩個測試其實守住不同層面的契約：

- streaming 測試用 fake provider 依序 emit `hel`、`lo`，確認 `on_response` 收到 chunk，而 session turn 最後保存的是 `hello`。這同時驗證 UI 即時性和資料完整性。
- 如果有人把 engine 改回只呼叫 `complete()`，這個測試就會抓到 chunk 不再即時 emit。
- no token accounting 測試檢查 `ModelResponse`、`DebateTurn`、`DebateSession` 的 dataclass fields，確保不再有 `tokens_used`。
- 這代表專案目前選擇不做 token accounting，可能是為了降低複雜度、避免不準確的跨模型 token 統計，或因 Gateway/streaming 下 token 資料不穩定。

測試不只是確認「程式會跑」，而是在保護近期設計決策不要被無意改回去。

## 30. 自動存檔功能設計

**題目：** 如果要加入「把每場 session 自動存成檔案」功能，你會把責任放在哪些模組？可以重用 `format_transcript()` 到什麼程度，哪些資料、錯誤或隱私情境仍需要額外設計？

**參考答案：** 自動存檔應該避免塞進 `provider`，因為 provider 只處理模型呼叫；也不應讓 CLI 手寫太多格式細節。比較好的做法是新增 persistence/repository 類模組，接收 `DebateSession` 序列化成 JSON 或 Markdown，再由 CLI 在 session 結束或每回合後呼叫，或讓 engine 透過 callback 通知。`format_transcript()` 可以重用來產生人類可讀的 Markdown transcript，但若要做可機器讀取、可恢復 session 或後續分析，仍應保存結構化的 `DebateSession` / `DebateTurn`。額外要設計的是儲存位置、檔名、API key 不外洩、是否包含人類補充、模型失敗時是否仍寫 partial session，以及寫檔失敗時不能中斷整場討論。

一個比較完整的設計回答可以包含：

- 模組位置：新增 `storage.py`、`persistence.py` 或 `sessions.py`，不要放在 `provider.py`；provider 不應知道檔案系統，也不應知道 Markdown/JSON 格式。
- 儲存格式：Markdown 適合人讀，可以用 `format_transcript()`；JSON 適合機器讀和未來恢復 session，應保存 dataclass 欄位而不只是格式化文字。
- 觸發時機：可以在每回合後自動 flush，降低 crash 後資料遺失；也可以在 session 結束時寫一次，簡化 I/O。若要最穩，應支援 partial session 寫入。
- 隱私與安全：不能寫 API key；要考慮使用者 persona、topic、human input 可能含敏感資訊；可能需要讓使用者設定輸出資料夾或關閉自動存檔。
- 錯誤處理：寫檔失敗不應讓討論中斷；CLI 可以警告，但 engine 不應因此丟掉 session。
- 檔名與索引：可以用 `session_id` 和 timestamp 命名，避免 topic 裡特殊字元造成路徑問題。

這題是設計題，重點不是背現有程式，而是能沿著現有邊界提出不破壞架構的擴充方式。
