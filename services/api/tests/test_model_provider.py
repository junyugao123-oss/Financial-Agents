import pytest

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
    )

    assert result == "已按角色专业能力生成发言"
    call = provider.calls[0]
    system_prompt = str(call["system_prompt"])
    user_prompt = str(call["user_prompt"])
    assert "当前角色专业画像" in system_prompt
    assert "不要写成通用AI总结" in system_prompt
    assert "MA、MACD、RSI、ATR、BOLL" in system_prompt
    assert "角色专业技能" in user_prompt
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
        target_role="多头研究员",
    )

    call = provider.calls[0]
    system_prompt = str(call["system_prompt"])
    user_prompt = str(call["user_prompt"])
    assert "你是本轮主辩" in system_prompt
    assert "估值压力" in system_prompt
    assert "压力测试" in system_prompt
    assert "回应对象：多头研究员" in user_prompt
    assert call["temperature"] == 0.56
