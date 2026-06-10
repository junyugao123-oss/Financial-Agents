#!/usr/bin/env python3
"""Static mobile UX contract audit.

This is intentionally lightweight: it catches the regressions that have hurt
the MVP most often without introducing a browser dependency into CI.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Mobile layout audit failed: {message}")


def require_all(haystack: str, needles: list[str], context: str) -> None:
    missing = [needle for needle in needles if needle not in haystack]
    require(not missing, f"{context} missing {', '.join(missing)}")


def main() -> None:
    css = read("apps/web/app/globals.css")
    home = read("apps/web/components/home-experience.tsx")
    session = read("apps/web/components/session-experience.tsx")

    require(
        'homeSnapBreakpoint = "(min-width: 901px)"' in home,
        "desktop wheel snapping must stay PC-only",
    )
    require(
        '"committee-preview"' in home,
        "homepage must keep the committee preview section",
    )

    require_all(
        css,
        [
            "@media (max-width: 640px)",
            "100svh",
            "overflow-x: clip",
            "env(safe-area-inset-bottom)",
            ".mobile-session-dock",
            ".committee-chat-scroll",
            ".briefing-grid",
            ".quant-score-grid",
            ".mobile-committee-preview",
        ],
        "mobile CSS contract",
    )

    require_all(
        home,
        [
            "switchMarketSearchScope(item)",
            "lockMarketHintStock(market)",
            "摩尔线程-U",
            "688795",
            "五一视界",
            "HK6651",
            "深度研究（待后续开放）",
            "disabled",
        ],
        "research-task mobile/search contract",
    )

    require_all(
        session,
        [
            "MobileSessionDock",
            "PendingSpeakerNotice",
            "nextPendingSpeaker",
            "hasReportDraftingStarted",
            "data-report-export-root",
            "briefing-metric-grid",
            "quant-score-grid",
        ],
        "session mobile/report contract",
    )

    banned_public_terms = [
        "顶级",
        "最强",
        "DeepSeek Flash",
        "deepseek flash",
        "争执强度",
        "已归档",
        "16 条",
        "16条",
    ]
    public_surface = "\n".join([home, session])
    leaked = [term for term in banned_public_terms if term in public_surface]
    require(not leaked, f"banned public copy found: {', '.join(leaked)}")

    print("Mobile layout audit passed.")


if __name__ == "__main__":
    main()
