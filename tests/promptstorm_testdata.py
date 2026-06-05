from __future__ import annotations

from promptstorm.models import DebateSession, DebateTurn, PromptStormConfig


SAMPLE_ENV_TEXT = """
# Local development settings
AI_GATEWAY_API_KEY='sample-secret'
PLAYER_A_MODEL=google/gemini-test-a
PLAYER_B_MODEL="anthropic/claude-test-b"
REPORT_MODEL=openai/report-test
IGNORED_WITHOUT_VALUE
""".lstrip()


def sample_config() -> PromptStormConfig:
    return PromptStormConfig(
        api_key="sample-secret",
        player_a_model="model-a",
        player_b_model="model-b",
        report_model="model-report",
    )


def sample_session_with_human_and_error() -> DebateSession:
    return DebateSession(
        session_id="sample-session-001",
        timestamp="2026-06-05T09:30:00+08:00",
        player_a="產品經理 A",
        player_b="工程師 B",
        topic="是否要在這週上線含有逗號, 換行與中文的功能？",
        winner="TIE",
        tokens_used=42,
        turns=[
            DebateTurn(
                session_id="sample-session-001",
                round=1,
                speaker="A",
                persona="產品經理 A",
                model="model-a",
                response_text="先上線小流量，觀察真實需求。",
                tokens_used=12,
                timestamp="2026-06-05T09:30:01+08:00",
            ),
            DebateTurn(
                session_id="sample-session-001",
                round=1,
                speaker="B",
                persona="工程師 B",
                model="model-b",
                response_text="風險包含資料遷移、回滾流程，以及客服負擔。",
                tokens_used=15,
                timestamp="2026-06-05T09:30:02+08:00",
            ),
            DebateTurn(
                session_id="sample-session-001",
                round=1,
                speaker="USER",
                persona="Human",
                model="human",
                response_text="請把企業客戶的 SLA 也納入考量。",
                tokens_used=0,
                timestamp="2026-06-05T09:30:03+08:00",
            ),
            DebateTurn(
                session_id="sample-session-001",
                round=2,
                speaker="A",
                persona="產品經理 A",
                model="model-a",
                response_text="The model did not produce a response.",
                tokens_used=0,
                timestamp="2026-06-05T09:30:04+08:00",
                status="error",
                error="RuntimeError: RateLimitError: 429",
            ),
        ],
    )
