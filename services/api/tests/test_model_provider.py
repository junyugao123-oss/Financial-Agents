import pytest

from app.agent_engine import _strip_user_visible_source_noise
from app.model_provider import ModelProvider
from app.settings import Settings


class CapturingModelProvider(ModelProvider):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.calls: list[dict[str, object]] = []

    async def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int = 340,
    ) -> str | None:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return "已按角色专业能力生成发言"


def _settings() -> Settings:
    return Settings(
        model_provider="deepseek",
        model_name="deepseek-v4-pro",
        deepseek_api_key="test-key",
        enable_llm_dialogue=True,
        enable_llm_refinement=False,
    )


@pytest.mark.asyncio
async def test_committee_message_injects_quant_research_skill_profile():
    provider = CapturingModelProvider(_settings())

    result = await provider.generate_committee_message(
        role="量化研究员",
        event_type="量化初筛",
        title="运行量化交易模型初筛",
        phase="事实底稿",
        fallback="我先跑一遍量化模型。",
        market="港股",
        symbol="06651.HK",
        snapshot_summary="实时行情已刷新。",
        quant_brief_summary="趋势因子 72，动量因子 68，风险约束 45。",
        recent_context="暂无",
        evidence_digest="财报因子取得 5/7 项，事件摘要含回购公告。",
    )

    assert result == "已按角色专业能力生成发言"
    call = provider.calls[0]
    system_prompt = str(call["system_prompt"])
    user_prompt = str(call["user_prompt"])
    assert "当前角色专业画像" in system_prompt
    assert "不要写成通用AI总结" in system_prompt
    assert "MA、MACD、RSI、ATR、BOLL" in system_prompt
    assert "角色专业技能" in user_prompt
    assert "证据摘要" in user_prompt
    assert "不得照抄默认发言" in system_prompt
    assert "用户不关心这些技术来源" in system_prompt
    assert "岗位判断、证据依据、推进条件" in system_prompt
    assert "这只标的现在怎么看、为什么这么看、下一步盯什么" in system_prompt
    assert "禁止空泛套话" in system_prompt
    assert "AKShare" in system_prompt
    assert "stock_" in system_prompt
    assert "多因子信号" in system_prompt or "多因子" in user_prompt


@pytest.mark.asyncio
async def test_committee_message_keeps_head_to_head_debate_role_specific():
    provider = CapturingModelProvider(_settings())

    await provider.generate_committee_message(
        role="空头研究员",
        event_type="压力测试",
        title="挑战上行假设",
        phase="多空质询",
        fallback="我要压测多头假设。",
        market="A股",
        symbol="688234.SH",
        snapshot_summary="涨跌幅 3.2%，成交量放大。",
        quant_brief_summary="趋势 80，动量 74，波动 86。",
        recent_context="多头研究员认为趋势延续。",
        evidence_digest="风险约束 86/100，估值分位 78%。",
        target_role="多头研究员",
    )

    call = provider.calls[0]
    system_prompt = str(call["system_prompt"])
    user_prompt = str(call["user_prompt"])
    assert "你是本轮主辩" in system_prompt
    assert "必须直接回应对方观点" in system_prompt
    assert "量化底稿或事实链中的具体数字" in system_prompt
    assert "一条反证和一条降权条件" in system_prompt
    assert "普通用户听懂" in system_prompt
    assert "估值压力" in system_prompt
    assert "压力测试" in system_prompt
    assert "回应对象：多头研究员" in user_prompt
    assert call["temperature"] == 0.56


def test_committee_visible_text_strips_data_source_noise():
    raw = (
        "基本面裁判：营收规模=3.48亿(neutral; 营业收入未从公开接口取得，"
        "来源 AKShare stock_financial_hk_analysis_indicator_em); "
        "ROE=-37.55%(negative; 来源 Eastmoney quote hk06651); "
        "估值分位=46.63%(neutral; stock_financial_hk_analysis_indicator_em)。"
    )

    cleaned = _strip_user_visible_source_noise(raw)

    assert "AKShare" not in cleaned
    assert "Eastmoney" not in cleaned
    assert "stock_financial" not in cleaned
    assert "来源" not in cleaned
    assert "暂未进入本轮可用指标" in cleaned
