from __future__ import annotations

from datetime import datetime

from .models import (
    DecisionEvent,
    MarketSnapshot,
    QuantBrief,
    ResearchReport,
    ReportSection,
    ResearchSession,
)


DISCLAIMER = "本程序输出仅用于信息整理与研究辅助，不构成任何财务、投资或交易建议。"


def render_report(
    session: ResearchSession,
    snapshot: MarketSnapshot,
    events: list[DecisionEvent],
    quant_brief: QuantBrief | None = None,
) -> ResearchReport:
    bull_points = [event.content for event in events if event.stance == "bull"][:3]
    bear_points = [event.content for event in events if event.stance == "bear"][:3]
    risk_points = [event.content for event in events if event.stance == "risk"][:3]
    decision_events = [event for event in events if event.stance == "decision"]
    manager_decisions = [
        event for event in decision_events if event.role in ("组合经理", "投资经理", "基金经理")
    ]

    rating = _rating_from_snapshot(snapshot, risk_points, quant_brief)
    confidence = _confidence_from_events(events, risk_points, quant_brief)
    action_label = _action_from_rating(rating, snapshot, quant_brief)

    sections = [
        ReportSection(
            key="summary",
            title="执行摘要",
            status="ready",
            content=(
                f"一句话结论：{snapshot.name} 当前研究结论为 {rating}，"
                f"投委会动作口径为 {action_label}，信息完整指数 {confidence}/100。"
                f"核心理由：{_summary_core_reason(snapshot, quant_brief)}"
                f"主要风险：{_summary_primary_risk(quant_brief)}"
                "下一步重点：继续跟踪成交活跃度、关键价格区间、公告与财务验证、风险读数变化。"
            ),
        ),
        ReportSection(
            key="action",
            title="最终买卖观察结论",
            status="ready",
            content=(
                f"用户可读口径：{_action_plain_explanation(action_label)}"
                "该口径代表当前研究跟踪动作，不构成任何买卖指令、财务建议、投资建议或交易建议。"
            ),
        ),
        ReportSection(
            key="quant_brief",
            title="量化模型底稿",
            status="ready",
            content=_render_quant_brief(quant_brief),
        ),
        ReportSection(
            key="bull_bear",
            title="多空分歧",
            status="ready",
            content=_render_bull_bear_summary(
                snapshot=snapshot,
                quant_brief=quant_brief,
                bull_points=bull_points,
                bear_points=bear_points,
            ),
        ),
        ReportSection(
            key="assumptions",
            title="关键假设",
            status="ready",
            content=(
                "结论依赖于三个前提：实时行情能有效反映当前市场预期，量化因子与成交结构"
                "能够解释主要价格变化，后续公告、财务和行业信息没有推翻当前证据链。"
            ),
        ),
        ReportSection(
            key="risk",
            title="风险边界",
            status="ready",
            content=_render_risk_boundary(
                quant_brief=quant_brief,
                rating=rating,
                risk_points=risk_points,
                snapshot=snapshot,
            ),
        ),
        ReportSection(
            key="judgement",
            title="关键判断",
            status="ready",
            content=_render_key_judgement(
                action_label=action_label,
                bear_points=bear_points,
                bull_points=bull_points,
                confidence=confidence,
                quant_brief=quant_brief,
                rating=rating,
                risk_points=risk_points,
                snapshot=snapshot,
            ),
        ),
        ReportSection(
            key="recommendation",
            title="研究建议与跟踪条件",
            status="ready",
            content=_render_research_recommendation(
                action_label=action_label,
                manager_content=(
                    manager_decisions[-1].content
                    if manager_decisions
                    else decision_events[-1].content
                    if decision_events
                    else ""
                ),
                quant_brief=quant_brief,
                rating=rating,
                snapshot=snapshot,
            ),
        ),
    ]

    markdown = _render_markdown(session, snapshot, sections, rating, confidence, action_label)
    return ResearchReport(
        session_id=session.id,
        title=f"{snapshot.name} 机构式研究报告",
        generated_at=datetime.now(),
        data_as_of=snapshot.data_as_of,
        rating=rating,
        confidence=confidence,
        sections=sections,
        disclaimer=DISCLAIMER,
        markdown=markdown,
    )


def _rating_from_snapshot(
    snapshot: MarketSnapshot,
    risk_points: list[str],
    quant_brief: QuantBrief | None,
) -> str:
    if quant_brief and quant_brief.evidence_score >= 58:
        if quant_brief.signal_label == "偏多观察" and snapshot.pct_change >= 0:
            return "积极观察"
        if quant_brief.signal_label == "偏空观察" or quant_brief.risk_score >= 82:
            return "风险观察"
    if len(risk_points) >= 2 and snapshot.pct_change < 0:
        return "审慎观察"
    if snapshot.pct_change > 1.5:
        return "积极观察"
    if snapshot.pct_change < -1.5:
        return "风险观察"
    return "中性观察"


def _confidence_from_events(
    events: list[DecisionEvent],
    risk_points: list[str],
    quant_brief: QuantBrief | None,
) -> int:
    base = 68 + min(len(events), 12)
    if quant_brief:
        base = round((base + quant_brief.evidence_score) / 2)
    penalty = len(risk_points) * 4
    return max(45, min(86, base - penalty))


def _action_from_rating(
    rating: str,
    snapshot: MarketSnapshot,
    quant_brief: QuantBrief | None,
) -> str:
    signal = quant_brief.signal_label if quant_brief else ""
    risk_score = quant_brief.risk_score if quant_brief else 50
    has_high_risk = (
        signal == "偏空观察"
        or (rating == "风险观察" and signal != "偏多观察")
        or (risk_score >= 88 and signal != "偏多观察")
    )
    has_positive_setup = (
        rating == "积极观察"
        and signal != "偏空观察"
        and risk_score < 78
        and snapshot.pct_change >= -1.5
    )
    if has_high_risk:
        return "风险回避"
    if has_positive_setup:
        return "买入观察"
    return "观望观察"


def _summary_core_reason(snapshot: MarketSnapshot, quant_brief: QuantBrief | None) -> str:
    if quant_brief is None:
        return (
            f"{snapshot.name} 已完成行情事实记录，但量化因子尚未形成完整底稿，"
            "结论以谨慎观察为主。"
        )
    return (
        f"量化模型给出 {quant_brief.signal_label}，趋势 {quant_brief.trend_score}/100，"
        f"动量 {quant_brief.momentum_score}/100，量价 {quant_brief.volume_score}/100，"
        f"风险约束 {quant_brief.risk_score}/100。"
    )


def _summary_primary_risk(quant_brief: QuantBrief | None) -> str:
    if quant_brief is None:
        return "当前主要风险在于量化因子、公告和财务事实尚未完成统一复核。"
    if quant_brief.risk_score >= 82:
        return "风险读数偏高，需优先观察波动、回撤和成交是否继续恶化。"
    if quant_brief.evidence_score < 65:
        return "信息完整指数不足，需等待公告、财务或行业证据进一步补强。"
    return "主要风险在于量价信号能否被基本面、公告和行业事实继续验证。"


def _action_plain_explanation(action_label: str) -> str:
    if action_label == "买入观察":
        return "纳入买入观察池，适合继续跟踪中期持有条件，重点等待回踩确认或放量突破。"
    if action_label == "风险回避":
        return "进入风险回避口径，已持有应优先降低风险暴露，未持有不急于介入。"
    return "维持观望观察，短期不新增持有，等待方向、成交和风险读数进一步确认。"


def _render_quant_brief(quant_brief: QuantBrief | None) -> str:
    if quant_brief is None:
        return "量化模型底稿暂未形成，报告仅保留行情事实与投委会讨论记录。"
    factor_summary = (
        f"算法版本：{quant_brief.algorithm_version}。\n"
        f"模型观察：{quant_brief.signal_label}；趋势 {quant_brief.trend_score}/100，"
        f"动量 {quant_brief.momentum_score}/100，波动 {quant_brief.volatility_score}/100，"
        f"量价 {quant_brief.volume_score}/100，风险约束 {quant_brief.risk_score}/100，"
        f"信息完整指数 {quant_brief.evidence_score}/100，"
        f"数据质量 {quant_brief.data_quality_score}/100（{quant_brief.data_quality_grade}）。"
    )
    facts = "\n".join(f"{index}. {fact}" for index, fact in enumerate(quant_brief.facts, start=1))
    quality_checks = "\n".join(
        f"{index}. {item.label}：{item.detail}"
        for index, item in enumerate(quant_brief.data_quality_checks, start=1)
    )
    fact_chain = "\n".join(
        f"{index}. {item.category} - {item.title}（{_fact_status_text(item.status)}）：{item.summary}"
        for index, item in enumerate(quant_brief.fact_chain[:8], start=1)
    )
    cross_section = ""
    if quant_brief.cross_section:
        cross_section = "\n".join(
            f"{index}. {item.label}：{item.value}{item.unit}。{item.detail}"
            for index, item in enumerate(quant_brief.cross_section.factors, start=1)
        )
    validation = "\n".join(
        f"{index}. {item.label}（{_validation_status_text(item.status)}）：{item.detail}"
        for index, item in enumerate(quant_brief.validation_checks, start=1)
    )
    limitations = "\n".join(
        f"{index}. {item}" for index, item in enumerate(quant_brief.limitations, start=1)
    )
    return (
        f"{factor_summary}\n\n"
        f"客观事实：\n{facts}\n\n"
        f"事实链：\n{fact_chain or '事实链暂未返回，报告不得编造财报、公告、新闻或行业事实。'}\n\n"
        f"横截面因子：\n{cross_section or '横截面因子暂未返回，RPS、行业相对强弱和资金拥挤度不参与强结论。'}\n\n"
        f"数据质量校验：\n{quality_checks}\n\n"
        f"量化安全校验：\n{validation or '安全校验暂未运行。'}\n\n"
        f"验证口径：\n{limitations}"
    )


def _fact_status_text(status: str) -> str:
    if status == "confirmed":
        return "已确认"
    if status == "partial":
        return "待复核"
    return "待补证"


def _validation_status_text(status: str) -> str:
    if status == "pass":
        return "通过"
    if status == "warn":
        return "警告"
    return "失败"


def _join_points(title: str, points: list[str]) -> str:
    if not points:
        return f"{title}：本轮暂无压倒性信号，维持证据权重观察。"
    lines = [f"{title}："]
    lines.extend(f"{index}. {point}" for index, point in enumerate(points, start=1))
    return "\n".join(lines)


def _render_risk_boundary(
    *,
    quant_brief: QuantBrief | None,
    rating: str,
    risk_points: list[str],
    snapshot: MarketSnapshot,
) -> str:
    if quant_brief:
        risk_level = (
            "高风险"
            if quant_brief.risk_score >= 82
            else "中等风险"
            if quant_brief.risk_score >= 58
            else "低风险"
        )
        return (
            f"风险等级：{risk_level}，风险约束 {quant_brief.risk_score}/100，"
            f"波动因子 {quant_brief.volatility_score}/100，信息完整指数 {quant_brief.evidence_score}/100，"
            f"数据质量 {quant_brief.data_quality_score}/100。\n"
            f"主要边界：{snapshot.name} 当前研究评级为 {rating}，需要同时观察价格波动、成交活跃度、"
            "回撤区间和公告事实是否同向验证。\n"
            "触发条件：若波动继续扩张、成交活跃度回落或价格跌破关键通道，研究口径应下调；"
            "若风险读数回落且量价结构继续改善，可维持或上调观察优先级。"
        )
    if risk_points:
        return (
            "风险等级：待复核。\n"
            "主要边界：本轮风控发言已识别到额外约束，报告需保留价格波动、成交活跃度和回撤区间复核。\n"
            "触发条件：后续补齐量化底稿后，再重新校准风险等级和跟踪优先级。"
        )
    return (
        "风险等级：待复核。\n"
        "主要边界：当前仅保留行情事实和会议讨论记录，后续需补充量化底稿、公告和财务事实。\n"
        "触发条件：完成数据补证后，再更新研究口径。"
    )


def _render_bull_bear_summary(
    *,
    snapshot: MarketSnapshot,
    quant_brief: QuantBrief | None,
    bull_points: list[str],
    bear_points: list[str],
) -> str:
    if quant_brief is None:
        return (
            "多方证据：行情事实已进入会议记录，但量化底稿尚未形成完整因子拆分。\n"
            "空方约束：当前缺少趋势、动量、波动、量价和风险约束的统一评分。\n"
            "分歧焦点：需等待量化底稿、公开公告和财务事实补齐后再归纳多空证据。"
        )

    bull_count = len(bull_points)
    bear_count = len(bear_points)
    return (
        "多方证据摘要：\n"
        f"1. 量化方向为 {quant_brief.signal_label}，趋势因子 {quant_brief.trend_score}/100，"
        f"动量因子 {quant_brief.momentum_score}/100，量价因子 {quant_brief.volume_score}/100。\n"
        f"2. 多方成立条件集中在相对强弱延续、成交活跃度不萎缩、关键通道不被跌破，"
        f"并需要后续公告、行业或财务事实继续验证。\n\n"
        "空方约束摘要：\n"
        f"1. 风险约束 {quant_brief.risk_score}/100，波动因子 {quant_brief.volatility_score}/100，"
        f"信息完整指数 {quant_brief.evidence_score}/100。\n"
        f"2. 空方关注的核心约束集中在波动扩张、估值承接、量能回落、回撤扩大和催化兑现不足。\n\n"
        "分歧焦点：\n"
        f"本轮记录到多方观点 {bull_count} 条、空方观点 {bear_count} 条。"
        f"{snapshot.name}的关键分歧不在单日涨跌，而在趋势强度、成交验证、风险边界"
        "和基本面证据是否能够同向确认。"
    )


def _render_key_judgement(
    *,
    action_label: str,
    bear_points: list[str],
    bull_points: list[str],
    confidence: int,
    quant_brief: QuantBrief | None,
    rating: str,
    risk_points: list[str],
    snapshot: MarketSnapshot,
) -> str:
    quant_line = (
        f"量化模型给出 {quant_brief.signal_label}，信息完整指数 {quant_brief.evidence_score}/100，"
        f"数据质量 {quant_brief.data_quality_score}/100，风险约束 {quant_brief.risk_score}/100。"
        if quant_brief
        else "量化底稿暂未形成，当前仅保留行情事实与会议讨论输入。"
    )
    bull_line = _support_summary(quant_brief)
    bear_line = _constraint_summary(quant_brief, bear_points)
    risk_line = _risk_summary(quant_brief, risk_points)
    return (
        f"核心判断：{snapshot.name} 当前研究评级为 {rating}，研究动作口径为 {action_label}，"
        f"信息完整指数 {confidence}/100。\n"
        f"量化证据：{quant_line}\n"
        f"支持因素：{bull_line}\n"
        f"约束因素：{bear_line}\n"
        f"风控结论：{risk_line}"
    )


def _render_research_recommendation(
    *,
    action_label: str,
    manager_content: str,
    quant_brief: QuantBrief | None,
    rating: str,
    snapshot: MarketSnapshot,
) -> str:
    if action_label == "买入观察":
        action_text = (
            "明确口径：买入观察。研究建议为中期持有型跟踪；已持有可继续持有，"
            "未持有等待回踩确认或放量突破后纳入观察。"
        )
        trigger = "趋势保持强势、成交活跃度不萎缩、公告和财务信息没有出现负面修正。"
    elif action_label == "风险回避":
        action_text = (
            "明确口径：风险回避。研究建议为暂不持有、偏卖出观察；已持有优先降低暴露，"
            "未持有不介入，等待风险明显回落后再看。"
        )
        trigger = "风险读数下降、趋势重新站稳、成交恢复并完成公告与财务信息复核。"
    else:
        action_text = (
            "明确口径：观望观察。研究建议为短期观望、不新增持有；已持有以轻仓跟踪为主，"
            "未持有等待方向确认，不急于介入。"
        )
        trigger = "若趋势突破并站稳、成交同步放大、风险读数下降，可上调为买入观察；若跌破关键支撑或风险继续升温，转为风险回避。"

    factor_line = (
        f"当前量化输入为 {quant_brief.signal_label}，趋势 {quant_brief.trend_score}/100，"
        f"动量 {quant_brief.momentum_score}/100，风险约束 {quant_brief.risk_score}/100。"
        if quant_brief
        else "当前可见行情尚不足以支持进攻口径，研究动作先按短期观望和不新增持有处理。"
    )
    manager_line = _manager_summary(manager_content)
    return (
        f"{action_text}\n"
        f"判断依据：{factor_line}\n"
        f"跟踪条件：{trigger}\n"
        f"组合经理口径：{manager_line}\n"
        f"合规边界：以上为研究辅助输出，不构成对 {snapshot.name} 的买卖指令、"
        "财务建议、投资建议或交易建议。"
    )


def _compact_point(points: list[str], fallback: str) -> str:
    if not points:
        return fallback
    return points[0].replace("\n", " ").strip()


def _support_summary(quant_brief: QuantBrief | None) -> str:
    if quant_brief is None:
        return "多方证据需等待量化底稿和公开事实补齐后再确认。"
    return (
        f"多方证据主要来自趋势、动量和量价结构，当前趋势 {quant_brief.trend_score}/100，"
        f"动量 {quant_brief.momentum_score}/100，量价 {quant_brief.volume_score}/100；"
        "若相对强弱延续且成交活跃度不回落，可维持积极观察。"
    )


def _constraint_summary(quant_brief: QuantBrief | None, bear_points: list[str]) -> str:
    if quant_brief is None:
        return "空方约束需等待波动、回撤和成交活跃度指标补齐后再确认。"
    if bear_points:
        return (
            f"空方约束集中在波动扩张、估值承接、成交持续性和回撤风险，"
            f"当前波动 {quant_brief.volatility_score}/100，风险约束 {quant_brief.risk_score}/100。"
        )
    return (
        f"当前风险约束 {quant_brief.risk_score}/100，仍需持续跟踪波动、回撤和成交活跃度变化。"
    )


def _risk_summary(quant_brief: QuantBrief | None, risk_points: list[str]) -> str:
    if quant_brief is None:
        return "风控结论待量化底稿补齐后确认。"
    risk_state = "偏高" if quant_brief.risk_score >= 82 else "可控"
    suffix = "风控已要求报告写明失效条件和跟踪触发线。" if risk_points else "仍需保留失效条件和跟踪触发线。"
    return (
        f"风控判断为风险约束{risk_state}，信息完整指数 {quant_brief.evidence_score}/100。"
        f"{suffix}"
    )


def _manager_summary(manager_content: str) -> str:
    if manager_content.strip():
        return (
            "组合经理将多空分歧、风控边界和量化底稿收敛为当前研究口径，"
            "后续按跟踪条件复核并更新报告结论。"
        )
    return "组合经理将研究动作收敛为当前口径，并要求按跟踪条件复核。"


def _render_markdown(
    session: ResearchSession,
    snapshot: MarketSnapshot,
    sections: list[ReportSection],
    rating: str,
    confidence: int,
    action_label: str,
) -> str:
    parts = [
        f"# {snapshot.name} 机构式研究报告",
        "",
        f"- 市场：{session.market}",
        f"- 标的：{session.symbol}",
        f"- 分析日期：{session.analysis_date.isoformat()}",
        f"- 行情刷新时间：{snapshot.data_as_of}",
        f"- 模型：{session.model_name}",
        f"- 研究结论：{rating}",
        f"- 买卖观察口径：{action_label}",
        f"- 信息完整指数：{confidence}/100",
        "",
    ]
    for section in sections:
        parts.extend([f"## {section.title}", "", section.content, ""])
    parts.extend(["## 免责声明", "", DISCLAIMER])
    return "\n".join(parts)
