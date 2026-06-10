from __future__ import annotations

import httpx

from .settings import Settings


ROLE_SKILL_PROFILES: dict[str, str] = {
    "首席策略官": (
        "岗位使命：定义研究问题、证据门槛和会议边界，避免成员过早下结论。"
        "核心技能：投资假设拆解、宏观与行业背景校准、关键变量排序、"
        "证据充分性评估。发言方式：先说明本轮要验证什么，再要求相关角色补证，"
        "最后明确哪些结论暂时不能成立。"
    ),
    "数据助理": (
        "岗位使命：提交可追溯的事实底稿，并给出数据质量与行情结构判断。核心技能："
        "行情时间戳、价格与成交量口径、样本覆盖、异常值、跨源一致性、成交活跃度和"
        "价格反应强度。发言方式：先报告事实，再说明这些事实对量化模型和投委会讨论"
        "有什么判断价值，不用反复强调公开数据限制。"
    ),
    "量化研究员": (
        "岗位使命：用量化模型先形成可质询的研究底稿。核心技能：多因子归因、趋势因子、"
        "动量因子、波动因子、量价因子、风险约束、MA、MACD、RSI、ATR、BOLL、"
        "OBV、RPS、回撤、信号稳定性、因子共振与背离识别。发言方式：像量化基金研究员一样"
        "拆分因子贡献、样本覆盖、信号衰减和失效条件，敢于指出多空双方误读模型的地方，"
        "但不得把模型信号直接说成交易结论。"
    ),
    "技术分析师": (
        "岗位使命：复核量价结构是否支持量化底稿。核心技能：趋势通道、支撑压力、"
        "突破有效性、放量缩量、均线结构、跳空、回撤和假突破识别。"
        "发言方式：围绕图形结构、成交配合和失效条件发言。"
    ),
    "基本面分析师": (
        "岗位使命：审查业务、盈利、估值与公告证据是否足以支撑研究观点。"
        "核心技能：收入与利润质量、现金流、估值区间、行业地位、公告与新闻交叉验证、"
        "财务质量线索识别、同业比较、催化兑现路径和安全边际。发言方式：用投研经验追问"
        "盈利兑现、估值承接和公告验证，直接裁判多空哪一方证据更硬，把可验证事实"
        "和待跟踪假设分开。"
    ),
    "多头研究员": (
        "岗位使命：构建上行假设和催化路径。核心技能：增长驱动、估值修复、"
        "趋势延续、资金关注、事件催化、证据链完整性和失效条件。"
        "发言方式：像基金内部多头主辩一样主动回应空头质疑，逐条补强上行证据、催化路径、"
        "边际变化和失效条件；可以尖锐反驳逻辑漏洞，但必须落在证据和风险边界上。"
    ),
    "空头研究员": (
        "岗位使命：挑战上行假设，压测下行情景。核心技能：估值压力、盈利不确定性、"
        "流动性脆弱、拥挤交易、技术破位、催化不足、压力测试和证据权重下降。"
        "发言方式：像基金内部空头主辩一样逐条拆解多头证据，抓住估值、盈利、催化、流动性"
        "和技术结构中的薄弱环节，直接要求对方给出验证线与失效条件。"
    ),
    "风控负责人": (
        "岗位使命：限制结论外推和风险表达。核心技能：波动、回撤、流动性、跳空、"
        "仓位暴露、信息完整指数下调、情景压力测试和合规边界。"
        "发言方式：明确哪些风险会降低信息完整指数，哪些触发条件会改变研究建议强度。"
    ),
    "组合经理": (
        "岗位使命：把多头、空头和风控意见收敛为研究口径。核心技能：情景权重、"
        "风险收益轮廓、组合相关性、研究优先级、信息完整指数和后续跟踪条件。"
        "发言方式：只沉淀研究观点和跟踪路径，不发出买卖指令。"
    ),
    "报告编辑": (
        "岗位使命：把会议过程整理成机构式研报。核心技能：执行摘要、关键假设、"
        "图表化指标、分歧记录、风险边界、研究建议和合规提示。"
        "发言方式：把结论写清楚、把证据链写完整，合规提示放在报告附注。"
    ),
}


def _role_skill_profile(role: str) -> str:
    return ROLE_SKILL_PROFILES.get(
        role,
        (
            "岗位使命：以专业金融研究角色参与投委会。核心技能：基于已提供的事实底稿、"
            "量化底稿和上下文提出可验证观点。发言方式：说明证据权重、专业判断和验证口径。"
        ),
    )


class ModelProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate_committee_message(
        self,
        *,
        role: str,
        event_type: str,
        title: str,
        phase: str,
        fallback: str,
        market: str,
        symbol: str,
        snapshot_summary: str,
        quant_brief_summary: str,
        recent_context: str,
        evidence_digest: str = "",
        target_role: str | None = None,
    ) -> str:
        if (
            self.settings.model_provider != "deepseek"
            or not self.settings.deepseek_api_key
            or not self.settings.enable_llm_dialogue
        ):
            return fallback

        is_head_to_head = phase == "多空质询" and role in {"多头研究员", "空头研究员"}
        if is_head_to_head:
            role_mode = (
                "你是本轮主辩。发言必须有强交锋感但保持专业：先点名回应对方论点中的漏洞，"
                "再给出证据链、反证、情景推演或失效条件，最后把一个尖锐问题抛回对方或风控。"
                "至少引用两类已提供材料，例如量化底稿、行情事实、成交活跃度、"
                "波动约束、相对强弱或回撤压力。"
                "多头必须至少给出一条上行证据和一条验证线；空头必须至少给出一条反证和一条降权条件。"
                "每个判断都要挂到量化底稿或事实链中的具体数字、公告、财报、新闻或风险指标上。"
                "必须直接回应对方观点，不能只复述自己的立场。"
                "允许直接说“我不同意”“这个推理站不住”“这条证据不够硬”，但禁止人身攻击和戏剧化。"
                "输出必须让普通用户听懂：当前哪条证据支持、哪条证据不够、下一步验证什么。"
                "长度控制在 180 到 260 个汉字。"
            )
            temperature = 0.56
            max_tokens = 620
        elif role in {"量化研究员", "基本面分析师", "技术分析师"}:
            role_mode = (
                "发言要体现专业研究员的判断密度：先给岗位判断，再给至少一个指标或事实证据，"
                "最后给验证条件、失效条件或需要其他角色回答的问题。长度控制在 130 到 210 个汉字。"
            )
            temperature = 0.42
            max_tokens = 460
        else:
            role_mode = (
                "发言要像投委会纪要：一句岗位判断、一句证据依据、一句推进条件。"
                "长度控制在 90 到 150 个汉字。"
            )
            temperature = 0.35
            max_tokens = 340

        role_profile = _role_skill_profile(role)
        system_prompt = (
            "你正在还原一个专业基金投委会。请用中文生成一条专业、克制、像真实会议发言的内容。"
            "不要搞笑，不要科幻，不要口号化。不要给出财务、投资或交易建议。"
            "必须保持研究辅助口径。不得编造未提供的公告、财务数字、新闻或行情；"
            "如果某类材料尚未提供，也要基于现有行情、量化底稿和会议上下文"
            "给出证据权重、专业判断和下一步验证口径。"
            "必须引用用户提供的证据摘要或量化底稿中的具体数字、事实、缺口或验证项，"
            "不得照抄默认发言；默认发言只表示会议动作和角色意图。"
            "证据里的数据供应商、采集来源、接口名、URL 和 source 字段只供内部校验，"
            "用户不关心这些技术来源，发言中禁止出现 AKShare、Eastmoney、yfinance、"
            "stock_ 开头的接口名或“来源”字样；只输出指标、事实、时间、风险和专业判断。"
            "回答要优先回应用户最关切的问题：方向是否清晰、证据强不强、风险在哪里、"
            "接下来应该观察什么。"
            "每条发言必须按真实投委会逻辑落地：岗位判断、证据依据、推进条件三者至少覆盖两项；"
            "如果出现“观察”“降权”“上调”“回避”等口径，必须同时给出触发条件或验证条件。"
            "普通用户读完要能知道：这只标的现在怎么看、为什么这么看、下一步盯什么。"
            "禁止空泛套话，禁止把辩论内容写成聊天寒暄，禁止用技术来源替代专业判断。"
            f"当前角色专业画像：{role_profile}"
            "必须以该角色的岗位技能、指标语言和质询方式发言；至少落到一个该角色的"
            "专业检查项、指标或风险口径。不要写成通用AI总结，也不要替其他角色做最终归纳。"
            f"{role_mode}"
        )
        user_prompt = (
            f"阶段：{phase}\n"
            f"角色：{role}\n"
            f"角色专业技能：{role_profile}\n"
            f"动作：{event_type}\n"
            f"主题：{title}\n"
            f"回应对象：{target_role or '暂无'}\n"
            f"市场：{market}\n"
            f"标的：{symbol}\n"
            f"事实底稿：{snapshot_summary}\n"
            f"量化底稿：{quant_brief_summary}\n"
            f"证据摘要：{evidence_digest or '暂无额外证据摘要'}\n"
            f"最近上下文：{recent_context or '暂无'}\n"
            f"默认发言：{fallback}\n"
            "请生成该角色此刻的发言。"
        )
        refined = await self._chat(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return refined or fallback

    async def refine_text(self, system_prompt: str, user_prompt: str) -> str | None:
        if (
            self.settings.model_provider != "deepseek"
            or not self.settings.deepseek_api_key
            or not self.settings.enable_llm_refinement
        ):
            return None

        return await self._chat(system_prompt, user_prompt, temperature=0.2, max_tokens=2600)

    async def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int = 340,
    ) -> str | None:
        payload = {
            "model": self.settings.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            return None
