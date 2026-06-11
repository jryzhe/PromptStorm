# PromptStorm 專案理解檢核題

以下 30 題用來區分「真正理解 PromptStorm」與「只背過 README 或講義」的人。好的回答應該能說清楚資料流、模組邊界、錯誤情境、設計取捨，以及修改專案時會牽動哪些地方。

1. 如果使用者執行 `promptstorm debate`，從 CLI 解析指令到第一位模型開始輸出，中間會經過哪些主要函式與物件？請按實際資料流說明。

2. `main.py`、`src/promptstorm/__main__.py` 和 `pyproject.toml` 裡的 `promptstorm = "promptstorm.cli:main"` 分別解決什麼啟動情境？為什麼三者不是重複的同一件事？

3. `cli.py` 為什麼不直接組 prompt 或呼叫 OpenAI SDK，而是把流程交給 `DebateEngine`、把 API 呼叫交給 `VercelGatewayProvider`？

4. `DebateEngine.run()` 建立 `DebateSession` 時，為什麼要先把空白 persona 轉成 mode 的預設 persona？這會影響哪些後續 prompt 或輸出？

5. 一個模型回合完成後，`DebateTurn` 會記錄哪些資訊？如果只記錄文字內容，後面的結論、fallback 或除錯會失去哪些能力？

6. `continue_debate()` 使用 `_next_round_number(session)` 而不是由 CLI 傳入目前回合數，這個設計避免了什麼狀態不同步問題？

7. `add_human_input()` 把使用者補充記成 speaker `USER`，而不是直接拼進下一個 prompt。這對 transcript、語言偵測和 fallback summary 有什麼好處？

8. 在 `debate`、`discussion`、`dialogue` 三種模式中，哪些東西由 `ModeProfile` 控制？如果要新增第四種模式，最少要改哪些地方？

9. `dialogue` 的初始回合數為什麼是 1，而 `debate` 和 `discussion` 預設是 3？這反映了三種模式在使用體驗上的什麼差異？

10. `_speaker_order_for_control_choice()` 為什麼只有在 `dialogue` 且使用者選 B 時會改成 `("B", "A")`？如果 debate 也這樣改，語義會變成什麼？

11. `human_support` 在不同 mode 裡如何被轉成不同的 prompt context？為什麼 `A/B/TIE` 可以共用為內部狀態，但對使用者顯示成不同語意？

12. `detect_output_language()` 只看 topic 和使用者補充，而不是把全部模型 transcript 都拿來判斷。這個選擇避免了什麼語言漂移問題？

13. `format_language_instruction()` 放在 system prompt 中的目的，是語言格式控制還是 persona 控制？如果它放到 user prompt，可能會有什麼差異？

14. `_build_messages()` 在 transcript 為空與不為空時組出的 user prompt 有什麼不同？這對第一輪發言和後續互動的品質有什麼影響？

15. `clean_response()` 會移除 `<think>` 區塊、回合前綴與禮貌開場。這些清理分別對哪些模型輸出行為做防護？

16. `dialogue` 模式還會用 `_clean_dialogue_reply()` 額外清理回答。為什麼角色對話比 debate 更需要移除 speaker label、舞台指示或多段文字？

17. `VercelGatewayProvider.complete()` 其實呼叫 `stream_complete()`。這代表「非 streaming API」在目前實作中是什麼樣的抽象？

18. 在 `stream_complete()` 裡，為什麼要同時累積 `parts` 並透過 `on_delta` 即時送出 chunk？這分別服務 engine 的哪兩個需求？

19. `DebateEngine._complete_with_retries()` 何時會重試 rate limit，何時即使是錯誤也不重試？請特別說明 `emitted_delta` 的作用。

20. 如果模型在 A 已經 streaming 出部分文字後中斷，為什麼目前設計不安全地重試同一回合？這對 terminal 顯示與 transcript 一致性有什麼意義？

21. `_run_rounds()` 在某個 speaker 發生例外時會新增一個 `status="error"` 的 turn 並立刻 `return`。為什麼不是跳過失敗方繼續下一位？

22. `cli.py` 偵測 `session_has_model_error(session)` 後，仍然允許使用者補充或輸出目前 transcript。這和「整場 session 失敗就退出」相比，產品體驗差在哪裡？

23. `write_conclusion_safely()` 為什麼包住 `ConclusionWriter.generate_conclusion()`，而不是讓例外一路往上拋出？

24. `ConclusionWriter.build_fallback_conclusion()` 不能產生真正的智能總結，但仍然有價值。它保證了哪些最低限度的輸出？

25. `normalize_verdict()` 接受 `C/TIE/DRAW` 都轉成 `TIE`，但錯誤訊息寫 `A, B, or C`。這透露了 CLI 顯示語意和內部語意之間的什麼歷史或相容性問題？

26. `config.py` 讀設定時會先讀多個 `.env` 檔，再讓環境變數覆蓋。請說明全域設定、本地專案設定與 shell 環境變數的優先順序。

27. `save_api_key()` 在沒有傳入 model 參數時使用 `setdefault()`，而不是每次都覆蓋成預設模型。這保護了使用者的哪一類既有設定？

28. `provider.py` 只依賴 `openai` 套件，但 `base_url` 指向 Vercel AI Gateway。請說明這個設計如何同時降低 SDK 複雜度並保留多模型能力。

29. 現有測試特別確認 streaming chunk 會先被 emit、最後 transcript 存 cleaned 完整文字，還確認資料模型不存 token count。這兩個測試分別在防止什麼回歸？

30. 如果要加入「把每場 session 自動存成檔案」功能，你會把責任放在哪些模組？哪些資料已經足夠，哪些錯誤或隱私情境需要額外設計？
