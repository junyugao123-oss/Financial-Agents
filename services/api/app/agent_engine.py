from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import AsyncIterator

from .db import Repository
from .model_provider import ModelProvider
from .models import DecisionEvent, MarketSnapshot, QuantBrief, ResearchReport, ResearchSession
from .quant_engine import brief_summary
from .report_renderer import render_report
from .settings import Settings


MIN_COMMITTEE_TURNS = 10
MAX_COMMITTEE_TURNS = 23


SCRIPT = [
    {
        "phase": "事实底稿",
        "role": "首席策略官",
        "event_type": "开场",
        "title": "确认会议边界",
        "content": "本轮先确认研究边界：该标的进入沪深港股量化研究流程，量化底稿作为第一层输入，所有结论必须经过多空质询、基本面复核和风控约束后再写入报告。",
        "stance": "neutral",
        "reply_to": None,
        "target_role": None,
        "tension": 1,
    },
    {
        "phase": "事实底稿",
        "role": "数据助理",
        "event_type": "提交底稿",
        "title": "同步实时行情数据",
        "content": "已提交行情底稿：实时价、涨跌幅、成交量、刷新时间和样本覆盖进入会议记录。后续若出现价格与历史序列偏离，将在报告中单列数据质量提示。",
        "stance": "neutral",
        "reply_to": 1,
        "target_role": "首席策略官",
        "tension": 1,
    },
    {
        "phase": "事实底稿",
        "role": "量化研究员",
        "event_type": "量化初筛",
        "title": "运行量化交易模型初筛",
        "content": "量化底稿先拆为趋势、动量、波动、量价、相对强弱、突破距离和回撤约束。模型只判断证据强弱，不直接替代投委会结论。",
        "stance": "neutral",
        "reply_to": 2,
        "target_role": "数据助理",
        "tension": 2,
    },
    {
        "phase": "分析师初评",
        "role": "技术分析师",
        "event_type": "初评",
        "title": "观察量价结构",
        "content": "技术面只回答结构是否成立：突破需要成交跟随，回撤需要关键区间承接。否则价格强势只能按短期波动处理，不能直接写成趋势结论。",
        "stance": "bull",
        "reply_to": 3,
        "target_role": "量化研究员",
        "tension": 2,
    },
    {
        "phase": "分析师初评",
        "role": "基本面分析师",
        "event_type": "保留意见",
        "title": "要求补充基本面证据",
        "content": "基本面验证线包括营收、利润、现金流、ROE、负债率、估值分位和公告事实。价格信号若不能被这些证据承接，结论强度必须下调。",
        "stance": "neutral",
        "reply_to": 4,
        "target_role": "技术分析师",
        "tension": 3,
    },
    {
        "phase": "多空质询",
        "role": "多头研究员",
        "event_type": "主辩建模",
        "title": "建立上行证据链",
        "content": "多头假设建立在趋势延续、成交确认、相对强弱改善和催化验证四个条件上。空头若反驳，请指出哪一环已经断裂，不能只用波动否定全部证据。",
        "stance": "bull",
        "reply_to": 5,
        "target_role": "基本面分析师",
        "tension": 5,
    },
    {
        "phase": "多空质询",
        "role": "空头研究员",
        "event_type": "正面反证",
        "title": "拆解多头证据链",
        "content": "空头反证集中在三点：价格强势是否只是拥挤交易，成交放大是否是高位换手，估值与盈利是否能承接。任一项不成立，多头结论都要降级。",
        "stance": "bear",
        "reply_to": 6,
        "target_role": "多头研究员",
        "tension": 5,
    },
    {
        "phase": "多空质询",
        "role": "多头研究员",
        "event_type": "逐条反驳",
        "title": "回应空头反证",
        "content": "多头回应空头质疑：估值和催化需要验证，但强势信号不能被简单归为噪音。只要相对强弱、量价配合和回撤约束没有同步恶化，上行假设仍可保留。",
        "stance": "bull",
        "reply_to": 7,
        "target_role": "空头研究员",
        "tension": 5,
    },
    {
        "phase": "多空质询",
        "role": "基本面分析师",
        "event_type": "证据裁判",
        "title": "列出胜负手与验证线",
        "content": "基本面裁判线明确：多头必须证明强势不是一次性资金行为，空头必须证明风险不是短期噪音。公告、盈利质量、估值分位和行业比较统一进入验证表。",
        "stance": "neutral",
        "reply_to": 8,
        "target_role": "多头研究员 / 空头研究员",
        "tension": 4,
    },
    {
        "phase": "多空质询",
        "role": "空头研究员",
        "event_type": "压力测试",
        "title": "压测下行情景",
        "content": "空头压力测试要求回答：若量能回落、相对强弱失速或价格跌回关键通道，多头证据链如何处理。报告必须单列估值压力、流动性约束和回撤情景。",
        "stance": "bear",
        "reply_to": 9,
        "target_role": "多头研究员",
        "tension": 4,
    },
    {
        "phase": "多空质询",
        "role": "量化研究员",
        "event_type": "量化裁判",
        "title": "复核强弱与突破信号",
        "content": "量化裁判口径：趋势、相对强弱、突破距离、波动和成交若出现背离，多头与空头都要审慎处理。量化信号只提供可质询、可复核的事实底稿。",
        "stance": "neutral",
        "reply_to": 10,
        "target_role": "多头研究员 / 空头研究员",
        "tension": 3,
    },
    {
        "phase": "风控审查",
        "role": "风控负责人",
        "event_type": "插话",
        "title": "压实风险情景",
        "content": "风控口径必须压实：涨跌幅、波动和流动性要放在同一个情景表里，不允许单一强信号被放大为结论。若回撤扩大或成交萎缩，信息完整指数必须下调。",
        "stance": "risk",
        "reply_to": 11,
        "target_role": "量化研究员",
        "tension": 5,
    },
    {
        "phase": "风控审查",
        "role": "风控负责人",
        "event_type": "风控修正",
        "title": "下调结论强度",
        "content": "结论强度和证据等级需要分开：量化强势可以提高跟踪优先级，但风险边界必须同步写入，避免把研究建议误读成交易指令。",
        "stance": "risk",
        "reply_to": 10,
        "target_role": "空头研究员",
        "tension": 4,
    },
    {
        "phase": "投委会收敛",
        "role": "组合经理",
        "event_type": "收敛",
        "title": "压缩分歧",
        "content": "组合经理收敛口径：多头给出跟踪理由，空头压测失效条件，风控限定风险边界。最终报告要沉淀专业研究结论、跟踪条件和风险触发线。",
        "stance": "decision",
        "reply_to": 13,
        "target_role": "风控负责人",
        "tension": 2,
    },
    {
        "phase": "投委会收敛",
        "role": "首席策略官",
        "event_type": "确认口径",
        "title": "确认投委会表述边界",
        "content": "最终表述边界确认：报告要给出清晰研究判断、关键假设、分歧焦点和风险边界，同时保持研究辅助属性，避免被理解为直接交易指令。",
        "stance": "decision",
        "reply_to": 14,
        "target_role": "组合经理",
        "tension": 1,
    },
    {
        "phase": "研报定稿",
        "role": "报告编辑",
        "event_type": "定稿",
        "title": "生成机构式研究报告",
        "content": "报告按机构研报格式整理：执行摘要、量化底稿、多空分歧、关键判断、研究建议、跟踪条件和风险边界，合规提示作为附注处理。",
        "stance": "decision",
        "reply_to": 15,
        "target_role": "首席策略官",
        "tension": 1,
    },
]

ADDITIONAL_DEBATE_SCRIPT = [
    {
        "phase": "多空质询",
        "role": "基本面分析师",
        "event_type": "估值质询",
        "title": "追问盈利与估值承接",
        "content": "基本面补充质询：若多头认为估值可修复，需要解释利润率、收入可见度和行业景气由谁承接；若空头认为估值偏贵，也要给出同业比较和安全边际边界。",
        "stance": "neutral",
        "reply_to": None,
        "target_role": "多头研究员 / 空头研究员",
        "tension": 5,
    },
    {
        "phase": "多空质询",
        "role": "空头研究员",
        "event_type": "反击多头",
        "title": "否定单一强势叙事",
        "content": "空头反击重点：价格强势、资金关注和基本面改善不能混为一谈。没有公告、订单、利润率或行业景气的交叉验证，催化路径只能按待验证假设处理。",
        "stance": "bear",
        "reply_to": None,
        "target_role": "多头研究员",
        "tension": 5,
    },
    {
        "phase": "多空质询",
        "role": "多头研究员",
        "event_type": "正面回击",
        "title": "拆解空头过度保守",
        "content": "多头回击口径：空头不能把所有不确定性都当成否定项。研究重点不是等待证据百分百齐全，而是判断边际变化、赔率结构和失效条件是否足够清晰。",
        "stance": "bull",
        "reply_to": None,
        "target_role": "空头研究员",
        "tension": 5,
    },
    {
        "phase": "多空质询",
        "role": "量化研究员",
        "event_type": "因子复核",
        "title": "拆分趋势与噪音",
        "content": "量化复核把分歧拆成因子：趋势强不等于胜率高，波动高也不等于必须看空。关键看动量、成交确认、回撤约束和证据覆盖是否同向。",
        "stance": "neutral",
        "reply_to": None,
        "target_role": "多头研究员 / 空头研究员",
        "tension": 4,
    },
    {
        "phase": "多空质询",
        "role": "技术分析师",
        "event_type": "结构复核",
        "title": "识别假突破风险",
        "content": "技术结构补充：突破如果没有量能跟随和回撤承接，就是假突破风险；但若回踩不破关键区间，空头也不能把正常换手解释成趋势反转。",
        "stance": "neutral",
        "reply_to": None,
        "target_role": "多头研究员 / 空头研究员",
        "tension": 4,
    },
    {
        "phase": "多空质询",
        "role": "空头研究员",
        "event_type": "压力加码",
        "title": "质疑催化兑现",
        "content": "空头继续追问：催化若只是市场想象，没有时间表、业绩传导和公告验证，就不能抬高结论等级。多头必须给出触发条件，否则报告只能写观察。",
        "stance": "bear",
        "reply_to": None,
        "target_role": "多头研究员",
        "tension": 5,
    },
    {
        "phase": "多空质询",
        "role": "多头研究员",
        "event_type": "补强假设",
        "title": "明确上行触发线",
        "content": "多头补强触发线：相对强弱维持、量价不背离、回撤不破核心区间，并且公告或行业数据继续验证时，上行假设才升级；否则降回观察。",
        "stance": "bull",
        "reply_to": None,
        "target_role": "空头研究员",
        "tension": 5,
    },
    {
        "phase": "多空质询",
        "role": "基本面分析师",
        "event_type": "二次裁判",
        "title": "压实基本面验证表",
        "content": "基本面二次裁判：多头需要证明增长、利润率和估值承接能形成同向链条；空头需要证明风险不是短期波动。谁拿不出证据，谁的权重就下调。",
        "stance": "neutral",
        "reply_to": None,
        "target_role": "多头研究员 / 空头研究员",
        "tension": 4,
    },
]


class DecisionRoomEngine:
    def __init__(self, repository: Repository, model_provider: ModelProvider, settings: Settings):
        self.repository = repository
        self.model_provider = model_provider
        self.settings = settings

    async def run(
        self,
        session: ResearchSession,
        snapshot: MarketSnapshot,
        quant_brief: QuantBrief | None = None,
        start_sequence: int = 1,
    ) -> AsyncIterator[DecisionEvent | ResearchReport]:
        self.repository.update_session_status(session.id, "running")

        recent_context = [
            f"{event.sequence}. {event.role}（{event.event_type}）：{_strip_user_visible_source_noise(event.content)}"
            for event in self.repository.list_events(session.id)
        ]
        quant_summary = brief_summary(quant_brief)
        base_evidence_digest = _committee_evidence_digest(quant_brief)
        meeting_script = _script_for_session(session.id)
        for sequence, item in enumerate(meeting_script, start=1):
            if sequence < start_sequence:
                continue
            phase = item["phase"]
            role = item["role"]
            event_type = item["event_type"]
            title = item["title"]
            stance = item["stance"]
            reply_to = _resolve_reply_to(meeting_script, sequence - 1, item["target_role"])
            fallback = _enrich_content(item["content"], snapshot, quant_brief, phase, role)
            content = await self.model_provider.generate_committee_message(
                role=role,
                event_type=event_type,
                title=title,
                phase=phase,
                fallback=fallback,
                market=session.market,
                symbol=session.symbol,
                snapshot_summary=_snapshot_summary(snapshot),
                quant_brief_summary=quant_summary,
                evidence_digest=_role_evidence_digest(quant_brief, role, base_evidence_digest),
                recent_context="\n".join(recent_context[-4:]),
                target_role=item["target_role"],
            )
            content = _strip_user_visible_source_noise(content)
            event = DecisionEvent(
                session_id=session.id,
                sequence=sequence,
                phase=phase,
                role=role,
                event_type=event_type,
                title=title,
                content=content,
                stance=stance,
                metadata={
                    "market": session.market,
                    "symbol": session.symbol,
                    "source": snapshot.source,
                    "model": session.model_name,
                    "quant_signal": quant_brief.signal_label if quant_brief else None,
                    "quant_evidence": quant_brief.evidence_score if quant_brief else None,
                    "reply_to": reply_to,
                    "target_role": item["target_role"],
                },
                created_at=datetime.now(),
            )
            saved = self.repository.save_event(event)
            recent_context.append(f"{sequence}. {role}（{event_type}）：{content}")
            yield saved
            await asyncio.sleep(max(1.2, self.settings.event_pacing_seconds))

        events = self.repository.list_events(session.id)
        report = render_report(session, snapshot, events, quant_brief)
        report = await self._maybe_refine_report(report)
        self.repository.save_report(report)
        self.repository.update_session_status(session.id, "completed")
        yield report

    async def _maybe_refine_report(self, report: ResearchReport) -> ResearchReport:
        refined = await self.model_provider.refine_text(
            system_prompt=(
                "你是机构投研报告编辑。保持合规，禁止给出财务、投资或交易建议。"
                "只润色报告文字，不改变结论字段。"
            ),
            user_prompt=report.markdown,
        )
        if not refined:
            return report
        report.markdown = refined
        return report


def committee_turn_count(session_id: str) -> int:
    return len(_script_for_session(session_id))


def _script_for_session(session_id: str) -> list[dict[str, object]]:
    rng = random.Random(session_id)
    core_slots = [
        (0, SCRIPT[0]),
        (1, SCRIPT[1]),
        (2, SCRIPT[2]),
        (4, SCRIPT[4]),
        (5, SCRIPT[5]),
        (6, SCRIPT[6]),
        (7, SCRIPT[7]),
        (20, SCRIPT[11]),
        (22, SCRIPT[13]),
        (23, SCRIPT[15]),
    ]
    optional_slots = [
        (3, SCRIPT[3]),
        (8, SCRIPT[8]),
        (9, SCRIPT[9]),
        (10, SCRIPT[10]),
        *[(11 + index, item) for index, item in enumerate(ADDITIONAL_DEBATE_SCRIPT)],
        (21, SCRIPT[12]),
    ]
    desired_turns = rng.randint(MIN_COMMITTEE_TURNS, MAX_COMMITTEE_TURNS)
    optional_needed = max(0, min(len(optional_slots), desired_turns - len(core_slots)))
    selected_optional_indexes = rng.sample(range(len(optional_slots)), optional_needed)
    selected_slots = [*core_slots, *[optional_slots[index] for index in selected_optional_indexes]]
    return [item for _, item in sorted(selected_slots, key=lambda slot: slot[0])]


def _strip_user_visible_source_noise(text: str) -> str:
    cleaned = text
    cleaned = re.sub(
        r"[，,]?\s*来源[:：]?\s*(?:AKShare|Eastmoney|Tencent|Sina|yfinance|PublicEvidenceCrawler|东方财富)[^)]*\)",
        ")",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"[，,]?\s*来源[:：]?\s*(?:AKShare|Eastmoney|Tencent|Sina|yfinance|PublicEvidenceCrawler|东方财富)[^；。,\n]*(?=[；。,\n]|$)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:AKShare|Eastmoney|Tencent|Sina|yfinance|PublicEvidenceCrawler)\s+[A-Za-z0-9_().,/\- ]+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bstock_[A-Za-z0-9_().,/\- ]+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.replace("未从公开接口取得", "进入后续跟踪")
    cleaned = cleaned.replace("公开接口暂未返回", "进入后续跟踪")
    cleaned = cleaned.replace("暂未进入本轮可用指标", "进入后续跟踪")
    cleaned = cleaned.replace("本轮暂未取得", "进入后续跟踪")
    cleaned = cleaned.replace("暂未返回", "进入后续跟踪")
    cleaned = cleaned.replace("未取得", "进入后续跟踪")
    cleaned = cleaned.replace("待补证", "跟踪中")
    cleaned = cleaned.replace("待复核", "观察")
    cleaned = cleaned.replace("数据缺口", "研究边界")
    cleaned = cleaned.replace("信息缺口", "证据边界")
    cleaned = cleaned.replace("质量缺口", "质量边界")
    cleaned = cleaned.replace("缺口", "跟踪项")
    cleaned = cleaned.replace("降权", "审慎处理")
    cleaned = cleaned.replace("失败", "需关注")
    cleaned = cleaned.replace("接口", "数据通道")
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _resolve_reply_to(
    script: list[dict[str, object]],
    current_index: int,
    target_role: object,
) -> int | None:
    if current_index <= 0 or not isinstance(target_role, str) or not target_role:
        return None
    targets = [
        target.strip()
        for target in target_role.replace("、", "/").split("/")
        if target.strip()
    ]
    for prior_index in range(current_index - 1, -1, -1):
        prior_role = str(script[prior_index]["role"])
        if any(target in prior_role or prior_role in target for target in targets):
            return prior_index + 1
    return current_index


def _enrich_content(
    content: str,
    snapshot: MarketSnapshot,
    quant_brief: QuantBrief | None,
    phase: str,
    role: str,
) -> str:
    if phase == "事实底稿" and role == "数据助理":
        quality = _quality_digest(quant_brief)
        return (
            f"{content} 当前标的 {snapshot.name} 实时价约 {snapshot.latest_close}，"
            f"涨跌幅 {snapshot.pct_change}%，行情刷新时间 {snapshot.data_as_of}。"
            f"{quality}"
        )
    if role == "量化研究员" and quant_brief:
        return (
            f"{content} 当前量化底稿：{quant_brief.signal_label}，"
            f"趋势 {quant_brief.trend_score}/100，动量 {quant_brief.momentum_score}/100，"
            f"波动 {quant_brief.volatility_score}/100，量价 {quant_brief.volume_score}/100，"
            f"风险约束 {quant_brief.risk_score}/100。"
            f"因子明细：{_indicator_digest(quant_brief, ('rps_proxy', 'breakout_60', 'macd', 'rsi', 'atr'))}"
            f"验证状态：{_validation_digest(quant_brief)}。"
        )
    if role == "技术分析师" and quant_brief:
        return (
            f"{content} 技术复核重点："
            f"{_indicator_digest(quant_brief, ('ma_gap', 'macd', 'rsi', 'boll', 'volume_ratio'))}"
            "突破有效性、成交配合和回撤区间需要放在同一张验证表里。"
        )
    if role == "基本面分析师" and quant_brief:
        return (
            f"{content} 基本面裁判线："
            f"{_indicator_digest(quant_brief, ('fund_revenue', 'fund_profit', 'fund_cashflow', 'fund_gross_margin', 'fund_roe', 'fund_debt_ratio', 'fund_valuation_percentile'))}"
            f"事件证据：{_fact_digest(quant_brief, limit=2)}。"
            "多头要证明盈利与估值能承接，空头要证明风险不是短期波动。"
        )
    if role == "多头研究员" and quant_brief:
        return (
            f"{content} 多头证据链先看三件事：趋势 {quant_brief.trend_score}/100、"
            f"动量 {quant_brief.momentum_score}/100、量价 {quant_brief.volume_score}/100。"
            f"支撑材料：{_indicator_digest(quant_brief, ('rps_proxy', 'volume_ratio', 'event_sentiment', 'fund_profit', 'fund_roe'))}"
            f"事实钩子：{_fact_digest(quant_brief, limit=2)}。"
            "空头如果要否定上行假设，请指出趋势、量能或催化链条哪一环已经断裂。"
        )
    if role == "空头研究员" and quant_brief:
        return (
            f"{content} 空头压测集中在风险约束 {quant_brief.risk_score}/100、"
            f"波动 {quant_brief.volatility_score}/100、信息完整指数 {quant_brief.evidence_score}/100。"
            f"反证材料：{_indicator_digest(quant_brief, ('atr', 'drawdown_60', 'gap', 'event_risk', 'fund_debt_ratio', 'fund_valuation_percentile'))}"
            f"质量边界：{_quality_digest(quant_brief)}。"
            "多头必须证明强势不是拥挤交易，也不是公告与盈利证据不足时的情绪外推。"
        )
    if role == "风控负责人" and quant_brief:
        return (
            f"{content} 风控口径：风险约束 {quant_brief.risk_score}/100，"
            f"波动 {quant_brief.volatility_score}/100，信息完整指数 {quant_brief.evidence_score}/100，"
            f"数据质量 {quant_brief.data_quality_score}/100。"
            f"风险指标：{_indicator_digest(quant_brief, ('atr', 'boll', 'drawdown_60', 'event_risk'))}"
            "报告必须把触发线、失效线和证据边界分开写。"
        )
    if role == "组合经理" and quant_brief:
        return (
            f"{content} 组合层面将量化观察 {quant_brief.signal_label} 作为输入，"
            f"结合信息完整指数 {quant_brief.evidence_score}/100、"
            f"数据质量 {quant_brief.data_quality_score}/100 和多空分歧，"
            "收敛为研究建议、跟踪条件和风险边界。"
        )
    return content


def _snapshot_summary(snapshot: MarketSnapshot) -> str:
    return (
        f"{snapshot.name} 实时价 {snapshot.latest_close}，涨跌幅 {snapshot.pct_change}%，"
        f"行情刷新时间 {snapshot.data_as_of}。"
    )


def _committee_evidence_digest(quant_brief: QuantBrief | None) -> str:
    if not quant_brief:
        return "量化底稿正在整理，角色先围绕已确认行情事实和研究边界发言。"
    parts = [
        (
            f"模型信号 {quant_brief.signal_label}; 趋势 {quant_brief.trend_score}/100; "
            f"动量 {quant_brief.momentum_score}/100; 波动 {quant_brief.volatility_score}/100; "
            f"量价 {quant_brief.volume_score}/100; 风险 {quant_brief.risk_score}/100; "
            f"信息完整指数 {quant_brief.evidence_score}/100; "
            f"数据质量 {quant_brief.data_quality_score}/100。"
        ),
        f"关键因子：{_indicator_digest(quant_brief, _core_indicator_keys())}",
        f"事实链：{_fact_digest(quant_brief, limit=5)}",
        f"证据账本：{_ledger_digest(quant_brief)}",
        f"数据质量：{_quality_digest(quant_brief)}",
        f"验证：{_validation_digest(quant_brief)}",
    ]
    return " ".join(part for part in parts if part).strip()[:1800]


def _role_evidence_digest(
    quant_brief: QuantBrief | None,
    role: str,
    base_digest: str,
) -> str:
    if not quant_brief:
        return base_digest
    role_keys = _role_indicator_keys(role)
    role_facts_limit = 4 if role in {"首席策略官", "报告编辑"} else 3
    parts = [
        f"角色证据包：{role}。",
        (
            f"共用底稿：{quant_brief.signal_label}；趋势 {quant_brief.trend_score}/100，"
            f"动量 {quant_brief.momentum_score}/100，量价 {quant_brief.volume_score}/100，"
            f"风险 {quant_brief.risk_score}/100，信息完整指数 {quant_brief.evidence_score}/100，"
            f"数据质量 {quant_brief.data_quality_score}/100。"
        ),
        f"本角色重点因子：{_indicator_digest(quant_brief, role_keys)}",
    ]
    if role in {"数据助理", "首席策略官", "风控负责人", "报告编辑"}:
        parts.append(f"数据与校验：{_quality_digest(quant_brief)}")
    if quant_brief.evidence_ledger:
        parts.append(f"证据账本重点：{_ledger_digest(quant_brief, _role_ledger_categories(role))}")
    if role in {"量化研究员", "风控负责人", "组合经理", "报告编辑"}:
        parts.append(f"量化安全校验：{_validation_digest(quant_brief)}")
    if role in {"基本面分析师", "多头研究员", "空头研究员", "组合经理", "报告编辑"}:
        parts.append(f"事实证据：{_fact_digest(quant_brief, limit=role_facts_limit)}")
    parts.append(_role_instruction(role))
    return " ".join(part for part in parts if part).strip()[:1800]


def _role_indicator_keys(role: str) -> tuple[str, ...]:
    mapping: dict[str, tuple[str, ...]] = {
        "首席策略官": (
            "trusted_data_weight",
            "information_integrity",
            "factor_validity",
            "relative_strength",
            "financial_quality",
            "event_quality",
            "rps_proxy",
            "event_sentiment",
            "event_risk",
            "fund_valuation_percentile",
            "atr",
        ),
        "数据助理": (
            "trusted_data_weight",
            "data_quality",
            "information_integrity",
            "factor_validity",
            "fund_revenue",
            "event_sentiment",
        ),
        "量化研究员": (
            "trusted_data_weight",
            "ma_gap",
            "macd",
            "rsi",
            "adx",
            "volume_ratio",
            "volume_price_confirmation",
            "relative_strength",
            "factor_validity",
            "rps_proxy",
            "rps_20",
            "rps_60",
            "crowding",
        ),
        "技术分析师": (
            "ma",
            "ma_gap",
            "macd",
            "rsi",
            "boll",
            "atr",
            "volume_ratio",
            "volume_price_confirmation",
            "relative_strength",
            "breakout_60",
            "turtle_channel",
        ),
        "基本面分析师": (
            "financial_quality",
            "event_quality",
            "announcement_risk",
            "fund_revenue",
            "fund_profit",
            "fund_cashflow",
            "fund_gross_margin",
            "fund_roe",
            "fund_debt_ratio",
            "fund_valuation_percentile",
            "event_forecast",
        ),
        "多头研究员": (
            "relative_strength",
            "volume_price_confirmation",
            "event_quality",
            "financial_quality",
            "ma_gap",
            "macd",
            "rsi",
            "volume_ratio",
            "rps_proxy",
            "rps_20",
            "event_sentiment",
            "fund_profit",
            "fund_roe",
        ),
        "空头研究员": (
            "announcement_risk",
            "factor_validity",
            "financial_quality",
            "atr",
            "boll",
            "drawdown_60",
            "gap",
            "event_risk",
            "fund_debt_ratio",
            "fund_valuation_percentile",
            "trusted_data_weight",
        ),
        "风控负责人": (
            "risk_reading",
            "trusted_data_weight",
            "information_integrity",
            "announcement_risk",
            "factor_validity",
            "atr",
            "boll",
            "drawdown_60",
            "gap",
            "event_risk",
        ),
        "组合经理": (
            "trusted_data_weight",
            "information_integrity",
            "relative_strength",
            "financial_quality",
            "event_quality",
            "factor_validity",
            "rps_proxy",
            "rps_20",
            "event_sentiment",
            "event_risk",
            "fund_valuation_percentile",
            "drawdown_60",
        ),
        "报告编辑": (
            "trusted_data_weight",
            "information_integrity",
            "data_quality",
            "financial_quality",
            "event_quality",
            "factor_validity",
            "fund_revenue",
            "event_sentiment",
            "event_risk",
            "atr",
        ),
    }
    return mapping.get(role, _core_indicator_keys())


def _role_instruction(role: str) -> str:
    instructions = {
        "首席策略官": "发言目标：定义研究边界，要求所有结论回到证据、风险和可追踪条件。",
        "数据助理": "发言目标：只陈述已校验事实和研究边界，不能替投委会下判断。",
        "量化研究员": "发言目标：拆解多因子信号，说明趋势、动量、量价和验证测试如何共同影响底稿。",
        "技术分析师": "发言目标：判断量价结构、突破有效性和关键失效区间。",
        "基本面分析师": "发言目标：用盈利质量、现金流、ROE、负债和估值分位裁判多空证据。",
        "多头研究员": "发言目标：提出上行证据链，同时说清楚升级条件和必须被验证的假设。",
        "空头研究员": "发言目标：用波动、回撤、估值和证据边界压测多头叙事，指出审慎条件。",
        "风控负责人": "发言目标：把风险读数、数据质量和延迟校验转化为明确风险边界。",
        "组合经理": "发言目标：收敛多空分歧，形成研究建议、跟踪优先级和失效条件。",
        "报告编辑": "发言目标：把会议纪要压缩成机构式报告语言，保留观点、证据和风险边界。",
    }
    return instructions.get(role, "发言目标：基于证据给出专业判断。")


def _core_indicator_keys() -> tuple[str, ...]:
    return (
        "trusted_data_weight",
        "factor_validity",
        "relative_strength",
        "financial_quality",
        "event_quality",
        "announcement_risk",
        "rps_proxy",
        "rps_20",
        "rps_60",
        "crowding",
        "fund_revenue",
        "fund_profit",
        "fund_roe",
        "fund_debt_ratio",
        "fund_valuation_percentile",
        "event_sentiment",
        "event_risk",
        "atr",
        "drawdown_60",
    )


def _indicator_digest(quant_brief: QuantBrief, keys: tuple[str, ...]) -> str:
    by_key = {indicator.key: indicator for indicator in quant_brief.indicators}
    pieces: list[str] = []
    for key in keys:
        indicator = by_key.get(key)
        if not indicator:
            continue
        value = f"{indicator.value}{indicator.unit}".strip()
        detail = indicator.detail.strip()
        if len(detail) > 56:
            detail = f"{detail[:56]}..."
        direction = _indicator_direction_text(indicator.direction)
        pieces.append(f"{indicator.label}={value}（{direction}，{detail}）")
    return "；".join(pieces[:7]) or "对应因子进入后续跟踪，需保持该维度表达审慎"


def _indicator_direction_text(direction: str) -> str:
    return {
        "positive": "正向",
        "negative": "负向",
        "neutral": "中性",
        "risk": "风险",
    }.get(direction, "中性")


def _fact_digest(quant_brief: QuantBrief, *, limit: int) -> str:
    facts = [fact for fact in quant_brief.facts if fact]
    if not facts and quant_brief.fact_chain:
        facts = [
            f"{fact.category}:{fact.title}，{fact.summary}"
            for fact in quant_brief.fact_chain
            if fact.status != "unavailable"
        ]
    return "；".join(facts[:limit]) if facts else "当前事实摘要以已确认信息为主，必须把研究边界写入判断"


def _quality_digest(quant_brief: QuantBrief | None) -> str:
    if not quant_brief:
        return "数据质量待量化底稿生成后确认。"
    checks = [
        check
        for check in quant_brief.data_quality_checks
        if check.status in {"warn", "fail"} or check.key in {"fact_chain_coverage", "evidence_factor_layer"}
    ]
    if not checks:
        return "主要数据质量检查通过。"
    pieces = [
        f"{check.label}{check.score}/100:{check.detail}"
        for check in checks[:3]
    ]
    return "；".join(pieces)


def _role_ledger_categories(role: str) -> set[str]:
    mapping: dict[str, set[str]] = {
        "首席策略官": {"可信数据层", "量化安全", "横截面因子", "财报数据", "公告数据"},
        "数据助理": {"实时行情", "历史行情", "财报数据", "公告数据", "新闻事件", "行业数据"},
        "量化研究员": {"历史行情", "横截面因子", "量化安全", "可信数据层"},
        "技术分析师": {"实时行情", "历史行情", "横截面因子"},
        "基本面分析师": {"财报数据", "公告数据", "新闻事件", "行业数据"},
        "多头研究员": {"横截面因子", "新闻事件", "公告数据", "财报数据"},
        "空头研究员": {"量化安全", "财报数据", "公告数据", "新闻事件", "可信数据层"},
        "风控负责人": {"量化安全", "可信数据层", "实时行情", "公告数据"},
        "组合经理": {"可信数据层", "横截面因子", "财报数据", "量化安全"},
        "报告编辑": {"可信数据层", "财报数据", "公告数据", "新闻事件", "量化安全"},
    }
    return mapping.get(role, set())


def _ledger_digest(
    quant_brief: QuantBrief,
    categories: set[str] | None = None,
) -> str:
    items = quant_brief.evidence_ledger or []
    if categories:
        items = [item for item in items if item.category in categories]
    if not items:
        return "证据账本进入后续跟踪，所有角色必须保持审慎表达"
    priority = sorted(
        items,
        key=lambda item: {
            "blocked": 0,
            "missing": 1,
            "partial": 2,
            "available": 3,
        }.get(item.status, 4),
    )
    pieces: list[str] = []
    for item in priority[:5]:
        pieces.append(f"{item.label}{item.score}/100（{_ledger_status_text(item.status)}）")
    return "；".join(pieces)


def _ledger_status_text(status: str) -> str:
    return {
        "available": "可用",
        "partial": "观察",
        "missing": "跟踪中",
        "blocked": "审慎",
    }.get(status, "观察")


def _validation_digest(quant_brief: QuantBrief | None) -> str:
    if not quant_brief or not quant_brief.validation_checks:
        return "验证套件进入后续跟踪"
    priority = sorted(
        quant_brief.validation_checks,
        key=lambda check: {"fail": 0, "warn": 1, "pass": 2}.get(check.status, 3),
    )
    return "；".join(
        f"{check.label}:{check.status}-{check.detail}" for check in priority[:4]
    )
