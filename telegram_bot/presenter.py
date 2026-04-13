"""Presentation helpers for Telegram menus and long report delivery."""

from __future__ import annotations

from typing import Any, Iterable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


MAX_MESSAGE_CHARS = 3900


def build_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("새 분석", callback_data="menu:new_analysis")],
            [InlineKeyboardButton("실행 목록", callback_data="menu:executions")],
            [InlineKeyboardButton("시스템 현황", callback_data="menu:stats")],
            [InlineKeyboardButton("엔진 정보", callback_data="menu:engine")],
            [InlineKeyboardButton("도움말", callback_data="menu:help")],
        ]
    )


def build_analyst_menu(selected: set[str]) -> InlineKeyboardMarkup:
    options = [
        ("market", "시장"),
        ("social", "소셜"),
        ("news", "뉴스"),
        ("fundamentals", "펀더멘털"),
    ]
    rows = []
    for key, label in options:
        prefix = "✅" if key in selected else "⬜"
        rows.append(
            [InlineKeyboardButton(f"{prefix} {label}", callback_data=f"analyst:{key}")]
        )
    rows.append([InlineKeyboardButton("선택 완료", callback_data="analyst:done")])
    return InlineKeyboardMarkup(rows)


def build_date_menu(default_date: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"오늘 사용 ({default_date})", callback_data=f"date:{default_date}"
                )
            ],
            [InlineKeyboardButton("메인 메뉴", callback_data="menu:root")],
        ]
    )


def build_execution_menu(items: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{item['ticker']} · {item['status']} · {round(item['progress'])}%",
                callback_data=f"execution:{item['id']}",
            )
        ]
        for item in items[:8]
    ]
    rows.append([InlineKeyboardButton("메인 메뉴", callback_data="menu:root")])
    return InlineKeyboardMarkup(rows)


def build_execution_detail_menu(execution_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "요약", callback_data=f"execution_section:{execution_id}:summary"
                ),
                InlineKeyboardButton(
                    "분석가 리포트",
                    callback_data=f"execution_section:{execution_id}:reports",
                ),
            ],
            [
                InlineKeyboardButton(
                    "리서치/트레이딩",
                    callback_data=f"execution_section:{execution_id}:research",
                ),
                InlineKeyboardButton(
                    "리스크", callback_data=f"execution_section:{execution_id}:risk"
                ),
            ],
            [InlineKeyboardButton("목록으로", callback_data="menu:executions")],
        ]
    )


def split_long_message(text: str, limit: int = MAX_MESSAGE_CHARS) -> list[str]:
    normalized = text.strip()
    if len(normalized) <= limit:
        return [normalized]

    parts: list[str] = []
    remaining = normalized
    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def format_engine_info(engine: dict[str, Any]) -> str:
    return (
        "🤖 엔진 요약\n\n"
        f"- Provider: {engine['provider']}\n"
        f"- Deep Model: {engine['deep_model']}\n"
        f"- Quick Model: {engine['quick_model']}\n"
        f"- 언어: {engine['language']}\n"
        f"- 분석가: {engine['selected_analyst_count']}명\n"
        f"- 고정 에이전트: {engine['fixed_agent_count']}명\n"
        f"- 총 에이전트: {engine['total_agent_count']}명\n"
        f"- CLI 동일 수: {'예' if engine['agent_count_matches_cli'] else '아니오'}\n\n"
        f"{engine['engine_explanation']}"
    )


def format_system_stats(stats: dict[str, Any]) -> str:
    return (
        "📊 시스템 현황\n\n"
        f"- 동시 실행: {stats['concurrent_runs']}\n"
        f"- 실행 중: {stats['running_executions']}\n"
        f"- 재개 가능: {stats['resumable_executions']}\n"
        f"- 실패: {stats['failed_executions']}\n"
        f"- 완료: {stats['completed_executions']}\n"
        f"- 전체 실행: {stats['total_executions']}\n"
        f"- 활성 lease: {stats['active_leases']}"
    )


def format_progress_message(progress: dict[str, Any], ticker: str, date: str) -> str:
    elapsed = format_duration(progress.get("elapsed_seconds", 0))
    return (
        f"📈 {ticker} 분석 중\n"
        f"- 분석일: {date}\n"
        f"- 단계: {progress.get('current_stage') or '대기 중'}\n"
        f"- 진행률: {round(progress.get('progress', 0))}%\n"
        f"- 마일스톤: {progress.get('completed_milestones', 0)}/{progress.get('total_milestones', 0)}\n"
        f"- 경과 시간: {elapsed}"
    )


def format_execution_detail(detail: dict[str, Any]) -> str:
    lines = [
        f"📄 {detail['ticker']} 실행 상세",
        f"- 상태: {detail['status']}",
        f"- 진행률: {round(detail['progress'])}%",
        f"- 현재 단계: {detail.get('current_stage') or '대기 중'}",
        f"- 분석일: {detail['analysis_date']}",
        f"- 시작 시각: {detail['started_at']}",
        f"- 최신 시각: {detail.get('updated_at') or '-'}",
        f"- 총 소요 시간: {format_duration(detail.get('elapsed_seconds', 0))}",
        f"- 분석가: {', '.join(detail.get('analysts', []))}",
    ]
    return "\n".join(lines)


def format_section_messages(detail: dict[str, Any], section: str) -> list[str]:
    if section == "summary":
        text = (
            detail.get("summary_report")
            or detail.get("decision")
            or "요약이 아직 없습니다."
        )
        return split_long_message(f"🧾 최종 요약\n\n{text}")

    if section == "reports":
        reports = detail.get("reports") or {}
        text = (
            "\n\n".join(
                f"[{label}]\n{content}"
                for label, content in [
                    ("시장", reports.get("market", "")),
                    ("소셜", reports.get("sentiment", "")),
                    ("뉴스", reports.get("news", "")),
                    ("펀더멘털", reports.get("fundamentals", "")),
                ]
                if content
            )
            or "분석가 리포트가 없습니다."
        )
        return split_long_message(f"📚 분석가 리포트\n\n{text}")

    if section == "research":
        research = detail.get("research") or {}
        text = (
            "\n\n".join(
                [
                    f"[리서치 매니저]\n{research.get('investment_plan', '')}",
                    f"[트레이더]\n{research.get('trader_plan', '')}",
                ]
            ).strip()
            or "리서치/트레이딩 정보가 없습니다."
        )
        return split_long_message(f"🧠 리서치 / 트레이딩\n\n{text}")

    if section == "risk":
        risk = detail.get("risk") or {}
        text = (
            "\n\n".join(
                f"[{label}]\n{content}"
                for label, content in [
                    ("공격형", risk.get("aggressive", "")),
                    ("보수형", risk.get("conservative", "")),
                    ("중립형", risk.get("neutral", "")),
                    ("최종 리스크 판단", risk.get("final_decision", "")),
                ]
                if content
            )
            or "리스크 정보가 없습니다."
        )
        return split_long_message(f"🛡️ 리스크 상세\n\n{text}")

    return ["알 수 없는 섹션입니다."]


def format_duration(seconds: float) -> str:
    rounded = max(int(seconds), 0)
    minutes, remain = divmod(rounded, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}시간 {minutes}분 {remain}초"
    if minutes:
        return f"{minutes}분 {remain}초"
    return f"{remain}초"


def format_help_text() -> str:
    return (
        "사용 방법\n\n"
        "1. 새 분석: 종목코드 → 날짜 → 분석가 선택 후 실행\n"
        "2. 실행 목록: 진행 중/완료된 분석 상태와 상세 확인\n"
        "3. 시스템 현황: 현재 동시 실행 수와 누적 상태 확인\n"
        "4. 긴 리포트는 섹션별 버튼으로 나눠 전송됩니다."
    )


def format_startup_guide() -> str:
    return (
        "✅ TradingAgents Telegram Bot이 기동되었습니다.\n\n"
        "사용 방법\n"
        "- /start 를 보내거나 아래 메뉴 버튼을 눌러 시작하세요.\n"
        "- 새 분석: 종목코드 입력 → 분석가 선택 → 날짜 선택/입력\n"
        "- 실행 목록: 진행 중/완료된 분석 상태와 상세 확인\n"
        "- 시스템 현황: 현재 동시 실행 수와 누적 상태 확인\n"
        "- 긴 리포트는 요약/리포트/리서치/리스크 섹션으로 나눠 전달됩니다.\n\n"
        "최종 한글 요약이 먼저 오고, 상세 내용은 버튼으로 이어서 볼 수 있습니다."
    )
