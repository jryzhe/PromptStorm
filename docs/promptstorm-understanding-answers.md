# PromptStorm 專案理解檢核題參考答案

這份答案對應 `docs/promptstorm-understanding-questions.md` 的 30 題。它不是唯一標準答案，但好的回答應該能覆蓋這裡的核心概念、資料流和設計取捨。

1. 使用者執行 `promptstorm debate` 時，安裝後的 console script 會進入 `promptstorm.cli:main()`。`main()` 透過 `build_parser()` 解析子指令，確認 `debate` 是合法 session mode 後呼叫 `run_session(Path.cwd(), "debate")`。`run_session()` 讀設定、詢問 persona 與 topic，建立 `VercelGatewayProvider` 和 `DebateEngine`，再呼叫 `engine.run()`。`DebateEngine.run()` 建立 `DebateSession`，進入 `_run_rounds()`，由 `_build_messages()` 組 prompt，再由 `_complete_with_retries()` 呼叫 provider。provider 透過 OpenAI SDK 指向 Vercel AI Gateway，第一個 streaming chunk 回來時，callback 會一路回到 CLI 的 `on_response()`，印到 terminal。

2. `main.py` 是 clone repo 後本地開發的便利入口，會把 `src` 加到 `sys.path`，所以可以直接跑 `python3 main.py debate`。`src/promptstorm/__main__.py` 支援套件形式的 `python3 -m promptstorm`。`pyproject.toml` 的 `[project.scripts]` 則讓安裝後的 shell 指令 `promptstorm` 指到 `promptstorm.cli:main`。三者最後都進同一個 CLI main，但服務的是開發、module 執行和正式安裝三種入口。

3. `cli.py` 負責使用者互動、輸入、顏色輸出和控制選單；`DebateEngine` 負責 session 狀態、回合流程、prompt 組裝和重試；`VercelGatewayProvider` 負責外部模型 API。這樣 CLI 不需要知道 SDK 細節，engine 也不需要知道 terminal 顯示方式。測試時也可以用假的 provider 驗證 engine，而不用真的呼叫模型。

4. 空白 persona 會透過 `_display_persona()` 轉成該 mode 的預設 persona，例如 debate 的 `Point of View A` 或 dialogue 的 `Character A`。這避免 session、prompt identity、turn heading、transcript 和 conclusion 裡出現空名稱，也讓 `_build_messages()` 可以判斷這是預設 persona，改用「不是在扮演名人」的 identity 說法。

5. `DebateTurn` 記錄 `session_id`、`round`、`speaker`、`persona`、`model`、`response_text`、`timestamp`、`status` 和 `error`。如果只留文字，系統就無法知道哪一輪、哪個 speaker、哪個 model 出錯，也無法在 fallback transcript 中標示模型失敗，更難除錯 rate limit 或 provider 問題。

6. `continue_debate()` 由 engine 用 `_next_round_number(session)` 計算下一輪，避免 CLI 自己保存一份容易過期的回合狀態。這尤其重要，因為 session 裡可能混有 `USER` turn，也可能在模型錯誤後提前停止。engine 直接看目前 transcript，可以避免重複回合或跳號。

7. 使用者補充被存成 `speaker="USER"` 的 `DebateTurn`，所以它會成為正式 transcript 的一部分。這讓後續 prompt 能看到人類補充，`detect_output_language()` 能依 topic 和人類輸入判斷語言，fallback conclusion 也能清楚標示「Human input after Round N」，而不是把補充混在某個模型回覆裡。

8. `ModeProfile` 控制 mode 名稱、help text、標題、角色稱呼、預設 persona、system/opening/continuation prompt、human support context、控制選單文字、輸出標籤、final state 標籤和 conclusion prompt。新增第四種模式最少要新增一個 `ModeProfile`，放進 `MODES`，必要時調整 CLI 的特殊回合數或 speaker order 規則。

9. `dialogue` 是角色對話，每回合 A/B 各一句會推進場景；初始 1 回合就足以讓使用者開始主持方向。`debate` 和 `discussion` 需要多一點來回才能形成初始論點、反駁或分析脈絡，所以預設 3 回合。這反映 dialogue 偏「逐句互動」，debate/discussion 偏「先產生一段可評估的思考」。

10. 在 dialogue 中，如果使用者選 B，意思是讓 B 更主動，所以 `_speaker_order_for_control_choice()` 讓 B 先說，A 再回應。debate 的選 A/B 不是「誰先講」，而是「目前支持哪個方向」，兩方仍應照 A/B 順序辯。如果 debate 也改 speaker order，使用者支持 B 會被誤解成讓 B 搶先發言，而不只是加強 B 的論點。

11. engine 內部只需要 `A`、`B`、`TIE` 三種 human support 狀態，但每個 mode 用 `support_contexts` 把它轉成不同語意。debate 裡 A/B 是支持哪方，discussion 裡是某角度較有幫助，dialogue 裡是某角色更主動。內部狀態共用可以簡化流程，對外文字則由 mode profile 保持語境正確。

12. `detect_output_language()` 看 topic 和使用者補充，是因為使用者才是語言意圖來源。若把模型 transcript 也納入，某個模型一時用了英文或中文，後續整場可能被錯誤帶偏。只看人類輸入能避免模型互相放大語言漂移。

13. `format_language_instruction()` 是輸出語言控制，不是 persona 控制。放在 system prompt 中，權重較高，也和角色指令一起成為模型的穩定行為約束。若只放在 user prompt，後續 transcript、角色語氣或模型習慣更可能蓋過語言要求。

14. transcript 為空時，user prompt 只包含 topic、round、對手和 opening instruction，要求開場提出清楚立場或角色台詞。transcript 不為空時，prompt 會加入 support context、完整 transcript 和 continuation instruction，要求直接接續前文。這避免第一輪被迫回應不存在的內容，也讓後續回合能針對前面發言互動。

15. `<think>` 清理是防止 reasoning model 把思考區塊吐到終端；回合前綴清理是防止模型自作聰明輸出 `Round 1 [A: ...]`，造成 transcript 重複；禮貌開場清理則移除「好的，我明白」這類低資訊量句子，讓 debate/discussion 更直接。

16. dialogue 要求每次只輸出該角色的一句 spoken reply。模型很容易輸出角色名、舞台指示、括號動作、多段敘事，甚至替對方續寫。`_clean_dialogue_reply()` 會移除 speaker label、開頭舞台指示，優先取中文引號內台詞，並壓成第一段或第一行，讓 terminal 對話更像一來一往。

17. `complete()` 雖然看起來是非 streaming 介面，但目前實作只是呼叫 `stream_complete()` 並等全部 chunk 組完。也就是 provider 對外保留「拿完整 `ModelResponse`」的抽象，內部實際仍使用 streaming API。engine 可以依有沒有 `on_delta` 決定是否讓使用者即時看到 chunk。

18. `parts` 用來累積完整文字，最後回傳 `ModelResponse(text=...)` 給 engine 存進 `DebateTurn`。`on_delta` 則讓 CLI 在模型生成時即時印出，不必等整段完成。前者服務資料完整性與 transcript，後者服務互動體驗。

19. `_complete_with_retries()` 只在錯誤像 rate limit、尚未超過重試次數、而且還沒有 emit 任何 delta 時重試。若已經 emit delta，代表使用者 terminal 已看見部分內容；此時重試可能造成畫面上有兩份同一回合的開頭。非 rate limit 錯誤或重試用盡也會直接拋出。

20. streaming 已輸出部分文字後中斷時，terminal 狀態已經不可回滾。如果自動重試，同一回合可能先顯示半段失敗文字，再顯示重試的新文字，但 transcript 只會存其中一份，造成使用者看到的內容和 session 紀錄不一致。因此目前設計寧可記錄失敗，讓使用者用 partial transcript 繼續或收尾。

21. 某位 speaker 失敗後 `_run_rounds()` 記錄 error turn 並停止，是因為下一位 speaker 需要以前一位的有效發言作為上下文。若跳過失敗方繼續，後續模型會基於缺口對話，容易產生不連貫或假裝對方已回答。停止可以保住 transcript 的真實性，並把控制權交回使用者。

22. 這是「可恢復失敗」的體驗設計。模型錯誤不等於整場討論沒有價值；使用者可能已經得到有用 transcript，可以補充一句、換方向，或直接輸出目前內容。相比直接退出，這保留主持權，也避免因單次 API 問題丟失整場 session。

23. 結論模型是最後一步，失敗時如果例外往上拋，使用者會失去已經產生的 transcript。`write_conclusion_safely()` 把模型總結失敗轉成 fallback conclusion，讓流程仍能以可讀內容結束。這符合 PromptStorm 的核心保護：外部模型失敗時不丟資料。

24. fallback conclusion 至少保證有標題、session ID、topic、Player A/B、human verdict 或 direction、失敗原因，以及完整 transcript。它不假裝有智能分析，但保留所有原始討論內容，讓使用者可以自己閱讀或再交給其他工具整理。

25. 這顯示外部或早期 CLI 語意可能曾用 `C` 表示平手或無明確方向，而內部現在統一成 `TIE`。`normalize_verdict()` 接受 `C/TIE/DRAW` 是為了相容多種輸入，但錯誤訊息還停留在 A/B/C 的使用者語彙。它提醒維護者 CLI 顯示語意與內部模型語意需要同步。

26. `load_config_from_paths()` 依序讀傳入的 `.env` 檔，後讀到的非空值會覆蓋先前值。`run_session()` 傳入的順序是全域 config，再讀當前資料夾 `.env`，所以本地專案設定可以覆蓋全域設定。最後 `_config_from_values()` 會讓 shell 環境變數覆蓋所有檔案設定，因此優先序是環境變數最高，本地 `.env` 次之，全域 `.env` 最低。

27. `save_api_key()` 若沒有收到 model 參數，會用 `setdefault()` 只在缺少該 key 時補預設模型。這保護使用者先前在 `.env` 裡設定過的 `PLAYER_A_MODEL`、`PLAYER_B_MODEL` 或 `REPORT_MODEL`，避免只是更新 API key 時把自訂模型靜默改回預設值。

28. OpenAI Python SDK 已經處理 chat completion 請求格式、streaming iterator 和錯誤型別；把 `base_url` 指到 Vercel AI Gateway 後，同一套 SDK 介面就能呼叫 Gateway 後方的多家模型。程式不必為 Gemini、Qwen、OpenAI 等模型各寫一套 provider，同時仍可透過 model id 選擇不同上游模型。

29. streaming 測試防止回歸成「等完整回答結束才印出」，也確認 transcript 存的是完整、清理後的文字，不是 chunk 列表。no token accounting 測試防止資料模型重新引入 `tokens_used` 這類欄位，維持近期設計：PromptStorm 不再追蹤或保存 token 用量。

30. 自動存檔應該避免塞進 `provider`，因為 provider 只處理模型呼叫；也不應讓 CLI 手寫太多格式細節。比較好的做法是新增 persistence/repository 類模組，接收 `DebateSession` 序列化成 JSON 或 Markdown，再由 CLI 在 session 結束或每回合後呼叫，或讓 engine 透過 callback 通知。現有 `DebateSession` 和 `DebateTurn` 已足夠保存主題、persona、回合、模型、時間和錯誤；額外要設計的是儲存位置、檔名、API key 不外洩、是否包含人類補充、模型失敗時是否仍寫 partial session，以及寫檔失敗時不能中斷整場討論。
