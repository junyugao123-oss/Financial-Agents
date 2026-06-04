from __future__ import annotations

import asyncio
import random
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
        "content": "各位先不要急着给结论。本次只做 A 股与港股公开信息研究，先把事实底稿立住，再允许多空团队争论。",
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
        "content": "我先提交行情底稿：同步实时价、涨跌幅、成交量和刷新时间。数据口径足以支撑第一轮模型判断，异常波动会交给量化和风控复核。",
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
        "content": "我先跑量化底稿：趋势、动量、波动、量价、RPS近似强弱、突破距离和回撤约束同步看。模型只给证据权重，不替投委会做结论。",
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
        "content": "从技术面看，价格变化能反映短期资金态度，但我不把它直接解释为趋势成立，还需要成交量和关键位置配合。",
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
        "content": "我先把基本面验证线立起来：价格动作只能说明预期变化，真正能抬高研究评级的是业务质量、盈利弹性、估值分位、行业景气和公告事实同向。",
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
        "content": "我把多头假设摊开：趋势延续、动量扩散、量价确认和催化预期必须形成闭环。空头要反驳，请直接指出哪一环已经断，不要只拿波动两个字否定全部证据。",
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
        "content": "我不同意多头把链条说得这么顺。价格强势可能是拥挤交易，成交放大也可能是高位分歧换手。盈利兑现、估值空间和催化强度没有同步抬升前，上行假设必须降级。",
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
        "content": "我接受空头对估值和催化剂的追问，但不接受把强势全部打成噪音。只要相对强弱、量价配合和回撤约束没有同时恶化，多头主线就不能被提前判死。",
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
        "content": "我先当裁判：多头必须证明强势不是一次性资金行为，空头必须证明风险不是短期噪音。双方都把公告、盈利质量、估值分位和行业比较纳入同一套验证线。",
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
        "content": "我继续压测：如果量能回落、相对强弱失速或价格跌回关键通道，多头证据链怎么处理？报告必须单列估值压力、流动性约束和回撤情景，不能只写漂亮路径。",
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
        "content": "我用模型做裁判：趋势、RPS近似强弱、突破距离、波动和成交若出现背离，多头与空头都要降权。量化信号只负责给出可质询、可复核的事实底稿。",
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
        "content": "这里必须插一句风控口径：涨跌幅、波动和流动性要放在同一个情景表里，不允许单一强信号被放大为结论。若回撤扩大或成交萎缩，信息完整指数必须下调。",
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
        "content": "我建议把结论强度和证据等级分开：量化强势可以提高跟踪优先级，但风险边界必须同步写入，避免把研究建议误读成交易指令。",
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
        "content": "我听到的共识是：多头给出跟踪理由，空头压测失效条件，风控限定风险边界。最终报告要沉淀专业研究结论、跟踪条件和风险触发线。",
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
        "content": "我确认最终口径：报告要给出清晰研究判断、关键假设、分歧来源和风险边界，同时保持研究辅助属性，避免被理解为直接交易指令。",
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
        "content": "我将按机构研报格式整理：执行摘要、量化底稿、多空分歧、关键判断、研究建议、跟踪条件和风险边界，合规提示作为附注处理。",
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
        "content": "我补一刀基本面问题：如果多头说估值能修复，就要解释利润率、收入可见度和行业景气谁来承接；如果空头说估值贵，也要给出同业比较和安全边际缺口。",
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
        "content": "多头的问题是把价格强势、资金关注和基本面改善混成一件事。没有公告、订单、利润率或行业β的交叉验证，所谓催化路径只是情绪外推。",
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
        "content": "空头把所有不确定性都当成否定项，这也不专业。研究不是等所有证据百分百齐全才行动，而是判断边际变化、赔率结构和失效条件是否足够清晰。",
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
        "content": "我把分歧拆成因子：趋势强不等于胜率高，波动高也不等于必须看空。关键是动量、成交确认、回撤约束和证据覆盖是否同向，不同向就降低信息完整指数。",
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
        "content": "我从图形结构补充：突破如果没有量能跟随和回撤承接，就是假突破风险；但如果回踩不破关键区间，空头也不能把正常换手解释成趋势反转。",
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
        "content": "我继续追问：催化如果只是市场想象，没有时间表、业绩传导和公告验证，就不能抬高结论等级。多头必须给出触发条件，否则报告只能写观察。",
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
        "content": "可以，我把触发线写清楚：相对强弱维持、量价不背离、回撤不破核心区间，并且公告或行业数据继续验证时，上行假设才升级；否则降回观察。",
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
        "content": "我把双方争点压到验证表：多头需要证明增长、利润率和估值承接能形成同向链条；空头需要证明风险不是短期波动。谁拿不出证据，谁的权重就下调。",
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
            f"{event.sequence}. {event.role}（{event.event_type}）：{event.content}"
            for event in self.repository.list_events(session.id)
        ]
        quant_summary = brief_summary(quant_brief)
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
                recent_context="\n".join(recent_context[-4:]),
                target_role=item["target_role"],
            )
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
        return (
            f"{content} 当前标的 {snapshot.name} 实时价约 {snapshot.latest_close}，"
            f"涨跌幅 {snapshot.pct_change}%，行情刷新时间 {snapshot.data_as_of}。"
        )
    if role == "量化研究员" and quant_brief:
        return (
            f"{content} 当前量化底稿：{quant_brief.signal_label}，"
            f"趋势 {quant_brief.trend_score}/100，动量 {quant_brief.momentum_score}/100，"
            f"量价 {quant_brief.volume_score}/100，风险约束 {quant_brief.risk_score}/100。"
            f"我只把它作为研究线索交给投委会质询。"
        )
    if role == "技术分析师" and quant_brief:
        return f"{content} 我会重点复核均线、MACD、RSI、ATR 和成交量变化，避免单一指标放大。"
    if role == "多头研究员" and quant_brief:
        return (
            f"{content} 多头引用的事实底稿是：{quant_brief.signal_label}，"
            f"趋势 {quant_brief.trend_score}/100，动量 {quant_brief.momentum_score}/100，"
            f"量价 {quant_brief.volume_score}/100；"
            f"客观事实包括：{'；'.join(quant_brief.facts[:2])}。"
            "我的上行假设只在这些事实继续成立时保留。"
        )
    if role == "空头研究员" and quant_brief:
        return (
            f"{content} 空头引用的反证底稿是：风险约束 {quant_brief.risk_score}/100，"
            f"波动 {quant_brief.volatility_score}/100，证据覆盖 {quant_brief.evidence_score}/100；"
            f"需要质疑的客观事实包括：{'；'.join(quant_brief.facts[2:5])}。"
            "任何结论都必须写明失效条件和待验证项。"
        )
    if role == "风控负责人" and quant_brief:
        return (
            f"{content} 量化底稿证据覆盖度 {quant_brief.evidence_score}/100，"
            "我会结合波动、回撤和成交活跃度重新校准信息完整指数与触发条件。"
        )
    if role == "组合经理" and quant_brief:
        return (
            f"{content} 我会把量化观察 {quant_brief.signal_label} 作为输入，"
            "再根据多空证据和风控约束收敛表述。"
        )
    return content


def _snapshot_summary(snapshot: MarketSnapshot) -> str:
    return (
        f"{snapshot.name} 实时价 {snapshot.latest_close}，涨跌幅 {snapshot.pct_change}%，"
        f"行情刷新时间 {snapshot.data_as_of}。"
    )
