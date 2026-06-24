import type { Caption } from "@remotion/captions";
import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type PromoFormat = "landscape" | "portrait";

export type JunyuQuantPromoProps = {
  format: PromoFormat;
};

const FPS = 30;
const DURATION = 60 * FPS;

const palette = {
  ink: "#020708",
  deep: "#061012",
  panel: "rgba(6, 16, 18, 0.72)",
  panelStrong: "rgba(5, 12, 14, 0.88)",
  glass: "rgba(255,255,255,0.075)",
  line: "rgba(143, 255, 229, 0.22)",
  lineHot: "rgba(143, 255, 229, 0.58)",
  text: "#F7FFFC",
  muted: "rgba(234, 249, 246, 0.72)",
  dim: "rgba(234, 249, 246, 0.48)",
  teal: "#8FFFE5",
  tealDeep: "#0B5B52",
  gold: "#E8C76B",
  red: "#FF5C68",
  green: "#43D296",
  blue: "#70B7FF",
  orange: "#FF9F4A",
};

const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
const easeInOut = Easing.bezier(0.76, 0, 0.24, 1);

const s = (seconds: number) => seconds * FPS;

const clamp = (frame: number, input: [number, number], output: [number, number]) =>
  interpolate(frame, input, output, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });

const linear = (frame: number, input: [number, number], output: [number, number]) =>
  interpolate(frame, input, output, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const sceneDefs = [
  { id: "hook", from: s(0), to: s(4.2) },
  { id: "problem", from: s(4.2), to: s(8.8) },
  { id: "lock", from: s(8.8), to: s(13.6) },
  { id: "quant", from: s(13.6), to: s(20.2) },
  { id: "evidence", from: s(20.2), to: s(26.4) },
  { id: "quality", from: s(26.4), to: s(31.2) },
  { id: "committee", from: s(31.2), to: s(39.2) },
  { id: "report", from: s(39.2), to: s(47.4) },
  { id: "trace", from: s(47.4), to: s(53.6) },
  { id: "finale", from: s(53.6), to: s(60) },
] as const;

type SceneId = (typeof sceneDefs)[number]["id"];

const captions: Caption[] = [
  {
    text: "你输入的不是一串数字，是一次完整投研的起点。",
    startMs: 0,
    endMs: 4200,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "系统先用量化算法读取趋势、动量、波动、量价和风险。",
    startMs: 4200,
    endMs: 8800,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "沪深港股标的被锁定，名称、市场和数字代码同步进入模型。",
    startMs: 8800,
    endMs: 13600,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "金融量化算法先生成底稿，把证据交给后续质询。",
    startMs: 13600,
    endMs: 20200,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "行情、财报、公告、新闻和行业线索，被整理成同一条证据链。",
    startMs: 20200,
    endMs: 26400,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "证据质量先确认：时间、缺口、异常和延迟风险都会被检查。",
    startMs: 26400,
    endMs: 31200,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "十位金融角色围绕同一份底稿协作，多头进攻，空头反证，风控压测。",
    startMs: 31200,
    endMs: 39200,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "最后生成的不是一段话，而是一份带图表、观点和边界的研究报告。",
    startMs: 39200,
    endMs: 47400,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "每一句判断，都能回到数据、算法和会议纪要。",
    startMs: 47400,
    endMs: 53600,
    timestampMs: null,
    confidence: null,
  },
  {
    text: "君宇·投研智能体：输入一只股票，得到一份专业研究报告。",
    startMs: 53600,
    endMs: 60000,
    timestampMs: null,
    confidence: null,
  },
];

const quantFactors = [
  { label: "趋势", value: 84, color: palette.green },
  { label: "动量", value: 78, color: palette.teal },
  { label: "波动", value: 61, color: palette.gold },
  { label: "量价", value: 72, color: palette.teal },
  { label: "风险", value: 38, color: palette.red },
  { label: "信息完整", value: 91, color: palette.teal },
];

const evidenceNodes = [
  ["实时行情", "行情", palette.teal],
  ["财报因子", "财报", palette.gold],
  ["公告事件", "公告", palette.blue],
  ["新闻情绪", "舆情", palette.orange],
  ["行业强弱", "行业", palette.teal],
  ["数据时点", "时点", palette.green],
] as const;

const roles = [
  ["首席策略官", "定边界", palette.gold],
  ["量化研究员", "建底稿", palette.teal],
  ["数据助理", "验链路", palette.blue],
  ["多头研究员", "上行逻辑", palette.red],
  ["空头研究员", "风险反证", palette.green],
  ["基本面分析师", "财务承接", palette.gold],
  ["技术分析师", "量价结构", palette.teal],
  ["风控负责人", "压测边界", palette.green],
  ["组合经理", "收敛口径", palette.blue],
  ["报告编辑", "沉淀报告", palette.orange],
] as const;

const useLayout = (format: PromoFormat) => {
  const portrait = format === "portrait";
  const { width, height } = useVideoConfig();

  return {
    portrait,
    width,
    height,
    pad: portrait ? 62 : 106,
    top: portrait ? 54 : 48,
    title: portrait ? 78 : 108,
    titleSmall: portrait ? 58 : 78,
    h2: portrait ? 44 : 56,
    body: portrait ? 28 : 28,
    captionBottom: portrait ? 56 : 44,
    safeBottom: portrait ? 44 : 36,
  };
};

const sceneOpacity = (frame: number, from: number, to: number) => {
  const enter = clamp(frame - from, [0, 18], [0, 1]);
  const exit = clamp(frame, [to - 18, to], [1, 0]);
  return Math.min(enter, exit);
};

const currentCaption = (frame: number) => {
  const ms = (frame / FPS) * 1000;
  return captions.find((caption) => ms >= caption.startMs && ms <= caption.endMs);
};

const Soundtrack = () => (
  <Audio
    src={staticFile("audio/institutional-ambient.wav")}
    volume={(frame) => {
      const fadeIn = linear(frame, [0, s(2.2)], [0, 0.46]);
      const fadeOut = linear(frame, [DURATION - s(3), DURATION], [0.46, 0]);
      const pulse = 0.94 + Math.sin(frame / 34) * 0.06;
      return Math.min(fadeIn, fadeOut) * pulse;
    }}
  />
);

const Backdrop = ({ format }: { format: PromoFormat }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const { portrait } = useLayout(format);
  const drift = linear(frame, [0, DURATION], [0, portrait ? width * 0.18 : width * 0.075]);
  const zoom = 1.1 + Math.sin(frame / 180) * 0.018;

  return (
    <AbsoluteFill style={{ background: palette.ink, overflow: "hidden" }}>
      <Img
        src={staticFile("images/decision-room-hero.png")}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${portrait ? zoom + 0.22 : zoom}) translateX(${-drift}px)`,
          filter: "saturate(1.16) contrast(1.12) brightness(0.72)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: portrait
            ? "linear-gradient(180deg, rgba(0,0,0,0.92), rgba(1,7,9,0.78) 38%, rgba(1,7,9,0.92))"
            : "linear-gradient(90deg, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.78) 42%, rgba(0,0,0,0.48) 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 22% 18%, rgba(143,255,229,0.19), transparent 31%), radial-gradient(circle at 75% 8%, rgba(232,199,107,0.16), transparent 26%), radial-gradient(circle at 56% 78%, rgba(255,92,104,0.10), transparent 32%)",
          opacity: 0.75 + Math.sin(frame / 20) * 0.12,
        }}
      />
      <KineticGrid />
      <DataRain format={format} />
      <EnergyVeins format={format} />
      <ScanBeams />
      <Vignette />
    </AbsoluteFill>
  );
};

const KineticGrid = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const offset = frame % 96;

  return (
    <>
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.19,
          backgroundImage:
            "linear-gradient(rgba(143,255,229,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(143,255,229,0.10) 1px, transparent 1px)",
          backgroundSize: `${Math.max(76, width / 22)}px ${Math.max(76, height / 18)}px`,
          backgroundPosition: `${-offset}px ${offset * 0.45}px`,
          maskImage: "radial-gradient(circle at 50% 46%, black, transparent 78%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.15,
          background:
            "repeating-linear-gradient(180deg, transparent 0 7px, rgba(255,255,255,0.13) 8px, transparent 9px)",
          mixBlendMode: "screen",
        }}
      />
    </>
  );
};

const DataRain = ({ format }: { format: PromoFormat }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const { portrait } = useLayout(format);
  const labels = ["趋势", "动量", "波动", "估值", "风险", "财务", "舆情", "行业", "公告", "现金"];
  const count = portrait ? 38 : 72;

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {Array.from({ length: count }).map((_, index) => {
        const x = (((index * 149) % 1000) / 1000) * width;
        const speed = 0.42 + (index % 9) * 0.08;
        const y = ((((index * 257) % 1000) / 1000) * height + frame * speed) % (height + 120);
        const hot = index % 5 === 0;
        const label = labels[index % labels.length];
        return (
          <div
            key={index}
            style={{
              position: "absolute",
              left: x,
              top: y - 80,
              color: hot ? "rgba(232,199,107,0.58)" : "rgba(143,255,229,0.34)",
              fontSize: portrait ? 18 : 15,
              fontWeight: 900,
              letterSpacing: 1.5,
              opacity: hot ? 0.48 : 0.28,
              textShadow: hot ? "0 0 18px rgba(232,199,107,0.3)" : "0 0 16px rgba(143,255,229,0.22)",
              transform: `translateX(${Math.sin((frame + index * 7) / 14) * 9}px)`,
            }}
          >
            {label}：{String((frame + index * 41) % 100).padStart(2, "0")}
          </div>
        );
      })}
    </div>
  );
};

const EnergyVeins = ({ format }: { format: PromoFormat }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const { portrait } = useLayout(format);
  const count = portrait ? 9 : 14;

  return (
    <svg width={width} height={height} style={{ position: "absolute", inset: 0, opacity: 0.64, mixBlendMode: "screen" }}>
      {Array.from({ length: count }).map((_, index) => {
        const y = (height * (0.18 + (index / count) * 0.68) + Math.sin((frame + index * 21) / 32) * 38) % height;
        const progress = (frame * (1.4 + (index % 3) * 0.4) + index * 83) % (width + 400);
        const start = progress - 360;
        const end = progress;
        const color = index % 3 === 0 ? palette.gold : index % 3 === 1 ? palette.teal : palette.red;
        return (
          <path
            key={index}
            d={`M ${start} ${y} C ${start + 120} ${y - 70}, ${end - 120} ${y + 70}, ${end} ${y}`}
            fill="none"
            stroke={color}
            strokeWidth={index % 4 === 0 ? 5 : 3}
            strokeLinecap="round"
            opacity={0.22 + (index % 4) * 0.05}
            filter="drop-shadow(0 0 12px currentColor)"
          />
        );
      })}
    </svg>
  );
};

const ScanBeams = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const x = linear(frame % 150, [0, 150], [-width * 0.14, width * 1.08]);
  const y = linear((frame + 50) % 180, [0, 180], [-height * 0.18, height * 1.05]);

  return (
    <>
      <div
        style={{
          position: "absolute",
          left: x,
          top: 0,
          width: width * 0.08,
          height,
          background: "linear-gradient(90deg, transparent, rgba(143,255,229,0.22), transparent)",
          filter: "blur(16px)",
          transform: "skewX(-12deg)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: y,
          height: height * 0.08,
          background: "linear-gradient(180deg, transparent, rgba(232,199,107,0.16), transparent)",
          filter: "blur(14px)",
        }}
      />
    </>
  );
};

const Vignette = () => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      background:
        "radial-gradient(circle at 50% 45%, transparent 0%, transparent 48%, rgba(0,0,0,0.72) 100%)",
      pointerEvents: "none",
    }}
  />
);

const GlobalHeader = ({ format }: { format: PromoFormat }) => {
  const { portrait, pad, top } = useLayout(format);
  const frame = useCurrentFrame();
  const opacity = clamp(frame, [0, 30], [0, 1]);

  return (
    <div
      style={{
        position: "absolute",
        top,
        left: pad,
        right: pad,
        zIndex: 60,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        opacity,
      }}
    >
      <div>
        <div style={{ color: palette.text, fontSize: portrait ? 28 : 28, fontWeight: 980, letterSpacing: 0 }}>
          君宇·投研智能体
        </div>
        <div style={{ color: palette.muted, fontSize: portrait ? 19 : 18, marginTop: 7, fontWeight: 720 }}>
          人工智能金融量化分析系统
        </div>
      </div>
      {!portrait ? (
        <div style={{ display: "flex", gap: 14 }}>
          <Pill>沪深港股全域数据</Pill>
          <Pill>金融量化算法与深度推理</Pill>
          <Pill>十位金融专家提供专业建议</Pill>
        </div>
      ) : null}
    </div>
  );
};

const Pill = ({ children, tone = "teal" }: { children: React.ReactNode; tone?: "teal" | "gold" | "red" }) => {
  const color = tone === "gold" ? palette.gold : tone === "red" ? palette.red : palette.teal;
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 9,
        width: "fit-content",
        border: `1px solid ${color}88`,
        background: `linear-gradient(90deg, ${color}30, rgba(255,255,255,0.05))`,
        boxShadow: `0 0 32px ${color}26, inset 0 1px 0 rgba(255,255,255,0.12)`,
        color: palette.text,
        borderRadius: 999,
        padding: "10px 16px",
        fontSize: 18,
        fontWeight: 920,
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ width: 8, height: 8, borderRadius: 999, background: color, boxShadow: `0 0 18px ${color}` }} />
      {children}
    </div>
  );
};

const SceneLayer = ({
  id,
  children,
}: {
  id: SceneId;
  children: (local: number, opacity: number) => React.ReactNode;
}) => {
  const frame = useCurrentFrame();
  const scene = sceneDefs.find((entry) => entry.id === id);
  if (!scene) {
    return null;
  }
  const opacity = sceneOpacity(frame, scene.from, scene.to);
  if (frame < scene.from - 16 || frame > scene.to + 16 || opacity <= 0.001) {
    return null;
  }
  const local = frame - scene.from;
  const zoom = 0.985 + opacity * 0.015;

  return (
    <AbsoluteFill
      style={{
        opacity,
        transform: `scale(${zoom})`,
        zIndex: 10,
      }}
    >
      {children(local, opacity)}
    </AbsoluteFill>
  );
};

const Kicker = ({ children, tone = "teal" }: { children: React.ReactNode; tone?: "teal" | "gold" | "red" }) => {
  const color = tone === "gold" ? palette.gold : tone === "red" ? palette.red : palette.teal;
  return (
    <div
      style={{
        display: "inline-flex",
        width: "fit-content",
        alignItems: "center",
        gap: 12,
        border: `1px solid ${color}55`,
        background: `linear-gradient(90deg, ${color}24, rgba(0,0,0,0.28))`,
        color,
        borderRadius: 999,
        padding: "11px 18px",
        fontSize: 20,
        fontWeight: 920,
      }}
    >
      <span style={{ width: 22, height: 22, borderRadius: 999, border: `4px double ${color}` }} />
      {children}
    </div>
  );
};

const Title = ({
  children,
  format,
  small = false,
  maxWidth,
}: {
  children: React.ReactNode;
  format: PromoFormat;
  small?: boolean;
  maxWidth?: number;
}) => {
  const { portrait, title, titleSmall } = useLayout(format);
  return (
    <h1
      style={{
        margin: 0,
        color: palette.text,
        fontSize: small ? titleSmall : title,
        lineHeight: portrait ? 1.08 : 1,
        letterSpacing: 0,
        fontWeight: 990,
        maxWidth,
        textWrap: "balance",
        wordBreak: "keep-all",
        overflowWrap: "normal",
        textShadow: "0 20px 80px rgba(0,0,0,0.72)",
      }}
    >
      {children}
    </h1>
  );
};

const Body = ({ children, format, maxWidth }: { children: React.ReactNode; format: PromoFormat; maxWidth?: number }) => {
  const { body } = useLayout(format);
  return (
    <p
      style={{
        margin: 0,
        color: palette.muted,
        fontSize: body,
        lineHeight: 1.58,
        fontWeight: 760,
        maxWidth,
        textWrap: "pretty",
        wordBreak: "keep-all",
        overflowWrap: "normal",
      }}
    >
      {children}
    </p>
  );
};

const HookScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad, width } = useLayout(format);
  const punch = clamp(local, [0, 22], [0, 1]);
  const titleY = clamp(local, [0, 28], [54, 0]);
  const panel = clamp(local, [32, 62], [0, 1]);

  return (
    <>
      <div
        style={{
          position: "absolute",
          left: pad,
          top: portrait ? 220 : 220,
          width: portrait ? width - pad * 2 : 875,
          display: "flex",
          flexDirection: "column",
          gap: portrait ? 28 : 30,
          transform: `translateY(${titleY}px)`,
          opacity: punch,
        }}
      >
        <Kicker>人工智能金融量化分析系统</Kicker>
        <Title format={format} maxWidth={portrait ? undefined : 870}>
          输入一只股票
          <br />
          得到一份
          <br />
          专业研究报告
        </Title>
        <Body format={format} maxWidth={portrait ? undefined : 830}>
          从量化底稿到证据链，再到金融专家推演，把研究判断变成可复核、可跟踪的专业报告。
        </Body>
      </div>
      <div
        style={{
          position: "absolute",
          right: portrait ? pad : 108,
          left: portrait ? pad : undefined,
          bottom: portrait ? 250 : 175,
          width: portrait ? undefined : 620,
          opacity: panel,
          transform: `translateY(${(1 - panel) * 46}px)`,
        }}
      >
        <LiveKernel compact={portrait} />
      </div>
      <FlashWord local={local} format={format} words={["市场", "算法", "投委会"]} />
    </>
  );
};

const LiveKernel = ({ compact = false }: { compact?: boolean }) => {
  const frame = useCurrentFrame();
  const pulse = 0.72 + Math.sin(frame / 10) * 0.12;
  const items = [
    ["1", "先判断是否值得研究"],
    ["2", "把依据整理成证据链"],
    ["3", "给出可跟踪的研究结论"],
  ];

  return (
    <div
      style={{
        border: `1px solid ${palette.line}`,
        background: "linear-gradient(145deg, rgba(2,8,10,0.88), rgba(255,255,255,0.08))",
        boxShadow: `0 28px 120px rgba(0,0,0,0.56), 0 0 ${60 * pulse}px rgba(143,255,229,0.12)`,
        borderRadius: compact ? 26 : 24,
        padding: compact ? 26 : 32,
        backdropFilter: "blur(18px)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: compact ? 22 : 28 }}>
        <div>
          <div style={{ color: palette.dim, fontSize: compact ? 21 : 20, fontWeight: 800 }}>核心优势</div>
          <div style={{ color: palette.text, fontSize: compact ? 33 : 34, fontWeight: 980, marginTop: 6 }}>
            人工智能量化系统能帮你什么
          </div>
        </div>
        <PulseSvg size={compact ? 72 : 86} />
      </div>
      <div style={{ display: "grid", gap: compact ? 16 : 17 }}>
        {items.map(([index, text], itemIndex) => {
          const x = clamp(frame - itemIndex * 8, [0, 32], [42, 0]);
          const glow = itemIndex === Math.floor((frame / 34) % items.length);
          return (
            <div
              key={text}
              style={{
                display: "grid",
                gridTemplateColumns: compact ? "70px 1fr" : "78px 1fr",
                gap: compact ? 18 : 20,
                alignItems: "center",
                padding: compact ? "20px 22px" : "22px 24px",
                border: `1px solid ${glow ? palette.lineHot : "rgba(255,255,255,0.15)"}`,
                background: glow ? "rgba(143,255,229,0.10)" : "rgba(255,255,255,0.055)",
                borderRadius: 17,
                transform: `translateX(${x}px)`,
              }}
            >
              <div
                style={{
                  width: compact ? 60 : 64,
                  height: compact ? 60 : 64,
                  borderRadius: 999,
                  display: "grid",
                  placeItems: "center",
                  color: palette.text,
                  background: "linear-gradient(135deg, rgba(143,255,229,0.4), rgba(11,91,82,0.6))",
                  fontSize: compact ? 27 : 26,
                  fontWeight: 950,
                  boxShadow: glow ? "0 0 26px rgba(143,255,229,0.36)" : "none",
                }}
              >
                {index}
              </div>
              <div style={{ color: palette.text, fontSize: compact ? 27 : 26, fontWeight: 920, lineHeight: 1.22 }}>{text}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const FlashWord = ({ local, format, words }: { local: number; format: PromoFormat; words: string[] }) => {
  const { width, height, portrait } = useLayout(format);
  const index = Math.floor(local / 30) % words.length;
  const inWord = local % 30;
  const opacity = Math.min(clamp(inWord, [0, 7], [0, 0.32]), clamp(inWord, [22, 30], [0.32, 0]));

  return (
    <div
      style={{
        position: "absolute",
        left: width * (portrait ? 0.08 : 0.38),
        top: height * (portrait ? 0.11 : 0.11),
        color: "transparent",
        WebkitTextStroke: `2px rgba(143,255,229,${opacity})`,
        fontSize: portrait ? 128 : 168,
        fontWeight: 1000,
        letterSpacing: 8,
        opacity,
        transform: `scale(${1 + inWord * 0.012}) skewX(-8deg)`,
      }}
    >
      {words[index]}
    </div>
  );
};

const ProblemScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad } = useLayout(format);
  const cards = [
    ["过去", "一堆指标", "一条结论", palette.dim],
    ["现在", "证据链", "投委会推演", palette.teal],
    ["结果", "图表报告", "清晰边界", palette.gold],
  ];

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        padding: portrait ? `220px ${pad}px 0` : `190px ${pad}px 0`,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "0.9fr 1.1fr",
        gap: portrait ? 36 : 78,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: portrait ? 24 : 28 }}>
        <Kicker tone="gold">用户真正想知道</Kicker>
        <Title format={format} small>
          这只股票
          <br />
          为什么值得看？
          <br />
          风险在哪里？
        </Title>
        <Body format={format}>
          君宇不只给一句判断，而是把模型、数据和专业团队的质询过程一起呈现。
        </Body>
      </div>
      <div style={{ display: "grid", gap: portrait ? 16 : 22 }}>
        {cards.map(([tag, a, b, color], index) => {
          const reveal = clamp(local - index * 12, [0, 26], [0, 1]);
          return (
            <div
              key={tag}
              style={{
                opacity: reveal,
                transform: `translateX(${(1 - reveal) * (portrait ? 28 : 60)}px)`,
                border: `1px solid ${color}66`,
                background: "linear-gradient(135deg, rgba(255,255,255,0.09), rgba(255,255,255,0.03))",
                borderRadius: 22,
                padding: portrait ? "24px 26px" : "30px 34px",
                display: "grid",
                gridTemplateColumns: "120px 1fr",
                alignItems: "center",
                gap: 20,
                boxShadow: `0 0 42px ${color}18`,
              }}
            >
              <div style={{ color, fontSize: portrait ? 25 : 27, fontWeight: 980 }}>{tag}</div>
              <div style={{ color: palette.text, fontSize: portrait ? 34 : 38, fontWeight: 980 }}>
                {a} <span style={{ color: palette.dim, fontWeight: 800 }}>→</span> {b}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const LockScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad, width } = useLayout(format);
  const targetLabel = "五一视界 / 06651";
  const inputProgress = Math.floor(clamp(local - 18, [0, 54], [0, targetLabel.length]));
  const typed = targetLabel.slice(0, inputProgress);
  const lock = clamp(local - 76, [0, 22], [0, 1]);

  return (
    <div
      style={{
        position: "absolute",
        left: pad,
        right: pad,
        top: portrait ? 230 : 205,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "0.92fr 1.08fr",
        gap: portrait ? 46 : 76,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 24 }}>
        <Kicker>沪深港股标的锁定</Kicker>
        <Title format={format} small>
          锁定标的
          <br />
          启动研究
        </Title>
        <Body format={format}>锁定标的后，系统立即生成量化底稿、核验数据，并交给金融专家研判。</Body>
      </div>
      <div
        style={{
          border: `1px solid ${palette.lineHot}`,
          background: "linear-gradient(145deg, rgba(2,8,10,0.84), rgba(143,255,229,0.08))",
          borderRadius: 28,
          padding: portrait ? 30 : 36,
          boxShadow: "0 34px 120px rgba(0,0,0,0.45), 0 0 60px rgba(143,255,229,0.16)",
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 26 }}>
          <MarketTab label="沪深股" muted />
          <MarketTab label="港股" />
        </div>
        <div
          style={{
            height: portrait ? 86 : 76,
            borderRadius: 18,
            border: `2px solid ${palette.teal}`,
            background: "rgba(255,255,255,0.08)",
            display: "flex",
            alignItems: "center",
            padding: "0 26px",
            color: palette.text,
            fontSize: portrait ? 29 : 28,
            fontWeight: 920,
            boxShadow: "0 0 32px rgba(143,255,229,0.22)",
          }}
        >
          <span style={{ color: palette.teal, marginRight: 18 }}>⌕</span>
          {typed}
          <span style={{ color: palette.teal, marginLeft: 5 }}>▌</span>
        </div>
        <div
          style={{
            marginTop: 24,
            opacity: lock,
            transform: `translateY(${(1 - lock) * 24}px)`,
            borderRadius: 22,
            border: `1px solid ${palette.teal}77`,
            background: "rgba(143,255,229,0.12)",
            padding: portrait ? "26px 28px" : "24px 28px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ color: palette.teal, fontSize: portrait ? 21 : 20, fontWeight: 900 }}>标的已锁定</div>
            <div style={{ color: palette.text, fontSize: portrait ? 35 : 34, fontWeight: 990, marginTop: 8 }}>五一视界</div>
            <div style={{ color: palette.muted, fontSize: portrait ? 24 : 22, fontWeight: 760, marginTop: 5 }}>港股代码 06651</div>
          </div>
          {!portrait ? <PulseSvg size={width > 1600 ? 90 : 76} /> : <Pill>进入模型</Pill>}
        </div>
      </div>
    </div>
  );
};

const MarketTab = ({ label, muted = false }: { label: string; muted?: boolean }) => (
  <div
    style={{
      height: 70,
      borderRadius: 18,
      display: "grid",
      placeItems: "center",
      background: muted ? "rgba(255,255,255,0.08)" : "rgba(143,255,229,0.16)",
      border: muted ? "1px solid rgba(255,255,255,0.08)" : `1px solid ${palette.teal}77`,
      color: muted ? palette.muted : palette.teal,
      fontSize: 25,
      fontWeight: 950,
    }}
  >
    {label}
  </div>
);

const QuantScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad } = useLayout(format);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        padding: portrait ? `210px ${pad}px 0` : `175px ${pad}px 0`,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "0.72fr 1.28fr",
        gap: portrait ? 34 : 70,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 22 }}>
        <Kicker tone="gold">量化研究底稿</Kicker>
        <Title format={format} small>
          算法先出底稿
          <br />
          讨论才有证据
        </Title>
        <Body format={format}>趋势、动量、波动、量价、风险和相对强弱会先被量化，结论必须接受后续质询。</Body>
      </div>
      <QuantEngine local={local} portrait={portrait} />
    </div>
  );
};

const QuantEngine = ({ local, portrait }: { local: number; portrait: boolean }) => {
  return (
    <div
      style={{
        border: `1px solid ${palette.line}`,
        borderRadius: 30,
        background: "linear-gradient(145deg, rgba(4,11,13,0.84), rgba(255,255,255,0.08))",
        boxShadow: "0 42px 140px rgba(0,0,0,0.48), inset 0 1px 0 rgba(255,255,255,0.1)",
        padding: portrait ? 30 : 38,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "1.05fr 0.95fr",
        gap: portrait ? 26 : 32,
      }}
    >
      <div>
        <div style={{ color: palette.text, fontSize: portrait ? 32 : 34, fontWeight: 980, marginBottom: 22 }}>
          金融量化算法正在生成底稿
        </div>
        <FactorMatrix local={local} portrait={portrait} />
      </div>
      <div
        style={{
          borderRadius: 24,
          background: "rgba(143,255,229,0.08)",
          border: "1px solid rgba(143,255,229,0.16)",
          padding: portrait ? 24 : 28,
          overflow: "hidden",
        }}
      >
        <WaveChart local={local} portrait={portrait} />
      </div>
    </div>
  );
};

const FactorMatrix = ({ local, portrait }: { local: number; portrait: boolean }) => (
  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: portrait ? 14 : 18 }}>
    {quantFactors.map((factor, index) => {
      const reveal = clamp(local - index * 5, [0, 28], [0, 1]);
      const width = clamp(local - index * 5, [10, 48], [0, factor.value]);
      return (
        <div
          key={factor.label}
          style={{
            opacity: reveal,
            transform: `translateY(${(1 - reveal) * 24}px)`,
            borderRadius: 18,
            background: "rgba(255,255,255,0.09)",
            border: "1px solid rgba(255,255,255,0.10)",
            padding: portrait ? "18px 18px" : "20px 22px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", color: palette.muted, fontSize: portrait ? 20 : 21, fontWeight: 850 }}>
            <span>{factor.label}</span>
            <span style={{ color: factor.color }}>{Math.round(width)}</span>
          </div>
          <div style={{ marginTop: 12, height: portrait ? 10 : 12, borderRadius: 999, background: "rgba(255,255,255,0.14)" }}>
            <div
              style={{
                width: `${width}%`,
                height: "100%",
                borderRadius: 999,
                background: factor.color,
                boxShadow: `0 0 22px ${factor.color}66`,
              }}
            />
          </div>
        </div>
      );
    })}
  </div>
);

const WaveChart = ({ local, portrait }: { local: number; portrait: boolean }) => {
  const count = portrait ? 38 : 56;
  const height = portrait ? 260 : 370;
  const progress = clamp(local, [0, 120], [0, 1]);

  return (
    <div>
      <div style={{ color: palette.teal, fontSize: portrait ? 22 : 23, fontWeight: 940, marginBottom: 18 }}>
        市场波形｜相对强弱｜风险读数
      </div>
      <svg width="100%" height={height} viewBox={`0 0 ${count * 16} ${height}`}>
        {Array.from({ length: count }).map((_, index) => {
          const h = 42 + Math.sin((index + local / 10) * 0.62) * 28 + (index % 7) * 10;
          const color = index % 9 === 0 ? palette.red : index % 5 === 0 ? palette.gold : palette.teal;
          return (
            <rect
              key={index}
              x={index * 16 + 3}
              y={height - 54 - h * progress}
              width={8}
              height={h * progress}
              rx={5}
              fill={color}
              opacity={0.38 + (index % 4) * 0.09}
            />
          );
        })}
        <path
          d={Array.from({ length: count })
            .map((_, index) => {
              const x = index * 16 + 8;
              const y = height - 120 - Math.sin((index + local / 12) * 0.32) * 48 - index * 1.3;
              return `${index === 0 ? "M" : "L"} ${x} ${y}`;
            })
            .join(" ")}
          fill="none"
          stroke={palette.teal}
          strokeWidth={5}
          strokeLinecap="round"
          opacity={0.92}
        />
      </svg>
    </div>
  );
};

const EvidenceScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad } = useLayout(format);
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        padding: portrait ? `210px ${pad}px 0` : `170px ${pad}px 0`,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "0.85fr 1.15fr",
        gap: portrait ? 46 : 70,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 22 }}>
        <Kicker>沪深港股全域数据</Kicker>
        <Title format={format} small>
          信息先成链
          <br />
          结论才站得住
        </Title>
        <Body format={format}>行情、财报、公告、新闻和行业线索进入同一条研究链路，后续所有质询都围绕这条链展开。</Body>
      </div>
      <EvidenceConstellation local={local} portrait={portrait} />
    </div>
  );
};

const EvidenceConstellation = ({ local, portrait }: { local: number; portrait: boolean }) => {
  const size = portrait ? 720 : 760;
  const center = size / 2;
  const orbit = portrait ? 250 : 280;

  return (
    <div
      style={{
        position: "relative",
        width: portrait ? "100%" : size,
        height: portrait ? 720 : size,
        borderRadius: 36,
        border: `1px solid ${palette.line}`,
        background: "radial-gradient(circle at center, rgba(143,255,229,0.18), rgba(255,255,255,0.05), rgba(0,0,0,0.25))",
        overflow: "hidden",
      }}
    >
      <svg width="100%" height="100%" viewBox={`0 0 ${size} ${size}`}>
        <circle cx={center} cy={center} r={orbit} fill="none" stroke="rgba(143,255,229,0.22)" strokeWidth="2" />
        <circle cx={center} cy={center} r={orbit * 0.62} fill="none" stroke="rgba(232,199,107,0.18)" strokeWidth="2" />
        {evidenceNodes.map((node, index) => {
          const angle = (index / evidenceNodes.length) * Math.PI * 2 + local / 92;
          const x = center + Math.cos(angle) * orbit;
          const y = center + Math.sin(angle) * orbit;
          const reveal = clamp(local - index * 6, [0, 26], [0, 1]);
          return (
            <g key={node[0]} opacity={reveal}>
              <line x1={center} y1={center} x2={x} y2={y} stroke={node[2]} strokeWidth="2" opacity="0.35" />
              <circle cx={x} cy={y} r={portrait ? 48 : 52} fill={`${node[2]}22`} stroke={node[2]} strokeWidth="3" />
              <text x={x} y={y - 6} textAnchor="middle" fill={palette.text} fontSize="24" fontWeight="950">
                {node[1]}
              </text>
              <text x={x} y={y + 25} textAnchor="middle" fill={palette.muted} fontSize="18" fontWeight="760">
                {node[0]}
              </text>
            </g>
          );
        })}
        <circle cx={center} cy={center} r="94" fill="rgba(2,8,10,0.82)" stroke={palette.teal} strokeWidth="4" />
        <text x={center} y={center - 8} textAnchor="middle" fill={palette.text} fontSize="28" fontWeight="980">
          证据
        </text>
        <text x={center} y={center + 25} textAnchor="middle" fill={palette.teal} fontSize="22" fontWeight="900">
          链路
        </text>
      </svg>
    </div>
  );
};

const QualityScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad } = useLayout(format);
  const gates = [
    ["时间戳校验", "发布时点 / 可用时间", palette.green],
    ["缺口识别", "行情与财报字段检查", palette.green],
    ["延迟模拟", "防止信息提前进入", palette.green],
    ["未来函数防护", "历史信号不可被未来改写", palette.green],
  ] as const;

  return (
    <div
      style={{
        position: "absolute",
        left: pad,
        right: pad,
        top: portrait ? 230 : 210,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "0.82fr 1.18fr",
        gap: portrait ? 42 : 72,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 22 }}>
        <Kicker>证据质量校验</Kicker>
        <Title format={format} small>
          证据先确认
          <br />
          再进入推演
        </Title>
        <Body format={format}>时间、缺口、延迟和未来函数风险先被系统核验，避免讨论建立在错误底稿上。</Body>
      </div>
      <div style={{ display: "grid", gap: portrait ? 18 : 20 }}>
        {gates.map(([title, desc, color], index) => {
          const reveal = clamp(local - index * 9, [0, 26], [0, 1]);
          return (
            <div
              key={title}
              style={{
                opacity: reveal,
                transform: `translateX(${(1 - reveal) * 48}px)`,
                border: `1px solid ${color}66`,
                background: `linear-gradient(90deg, ${color}22, rgba(255,255,255,0.06))`,
                borderRadius: 22,
                padding: portrait ? "24px 26px" : "26px 32px",
                display: "grid",
                gridTemplateColumns: portrait ? "58px 1fr" : "68px 1fr 120px",
                gap: 20,
                alignItems: "center",
              }}
            >
              <div
                style={{
                  width: portrait ? 54 : 60,
                  height: portrait ? 54 : 60,
                  borderRadius: 999,
                  background: color,
                  color: palette.ink,
                  display: "grid",
                  placeItems: "center",
                  fontSize: 26,
                  fontWeight: 1000,
                }}
              >
                ✓
              </div>
              <div>
                <div style={{ color: palette.text, fontSize: portrait ? 28 : 30, fontWeight: 980 }}>{title}</div>
                <div style={{ color: palette.muted, fontSize: portrait ? 22 : 22, fontWeight: 750, marginTop: 6 }}>{desc}</div>
              </div>
              {!portrait ? <Pill>通过</Pill> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const CommitteeScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad } = useLayout(format);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        padding: portrait ? `198px ${pad}px 0` : `160px ${pad}px 0`,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "0.78fr 1.22fr",
        gap: portrait ? 34 : 62,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 22 }}>
        <Kicker tone="gold">十位金融专家推演</Kicker>
        <Title format={format} small>
          不是普通对话
          <br />
          是结构化投委会
        </Title>
        <Body format={format}>多头提出上行逻辑，空头拆反证，风控压边界，组合经理最后收敛研究口径。</Body>
      </div>
      <RoleArena local={local} portrait={portrait} />
    </div>
  );
};

const RoleArena = ({ local, portrait }: { local: number; portrait: boolean }) => {
  const active = Math.floor(local / 20) % roles.length;
  return (
    <div
      style={{
        position: "relative",
        minHeight: portrait ? 820 : 700,
        borderRadius: 34,
        border: `1px solid ${palette.line}`,
        background: "linear-gradient(145deg, rgba(2,8,10,0.84), rgba(255,255,255,0.075))",
        boxShadow: "0 34px 120px rgba(0,0,0,0.45)",
        overflow: "hidden",
        padding: portrait ? 28 : 34,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: portrait ? 34 : 56,
          borderRadius: "50%",
          border: "1px dashed rgba(143,255,229,0.24)",
          transform: `rotate(${local * 0.12}deg)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          transform: "translate(-50%, -50%)",
          width: portrait ? 250 : 310,
          height: portrait ? 250 : 310,
          borderRadius: 999,
          display: "grid",
          placeItems: "center",
          background: "radial-gradient(circle, rgba(143,255,229,0.28), rgba(2,8,10,0.9))",
          border: `2px solid ${palette.teal}`,
          color: palette.text,
          textAlign: "center",
          fontSize: portrait ? 30 : 34,
          lineHeight: 1.18,
          fontWeight: 1000,
          boxShadow: "0 0 70px rgba(143,255,229,0.24)",
        }}
      >
        投委会
        <br />
        推演中
      </div>
      {roles.map(([name, job, color], index) => {
        const angle = (index / roles.length) * Math.PI * 2 - Math.PI / 2;
        const radiusX = portrait ? 355 : 470;
        const radiusY = portrait ? 330 : 275;
        const x = 50 + Math.cos(angle + local / 260) * 43;
        const y = 50 + Math.sin(angle + local / 260) * 36;
        const reveal = clamp(local - index * 4, [0, 30], [0, 1]);
        const isActive = index === active;

        return (
          <div
            key={name}
            style={{
              position: "absolute",
              left: `calc(${x}% - ${portrait ? 110 : 130}px)`,
              top: `calc(${y}% - ${portrait ? 43 : 46}px)`,
              width: portrait ? 220 : 260,
              opacity: reveal,
              transform: `scale(${isActive ? 1.08 : 1})`,
              border: `1px solid ${isActive ? color : "rgba(255,255,255,0.12)"}`,
              background: isActive ? `${color}1F` : "rgba(255,255,255,0.07)",
              borderRadius: 18,
              padding: portrait ? "15px 16px" : "16px 18px",
              boxShadow: isActive ? `0 0 42px ${color}38` : "none",
            }}
          >
            <div style={{ color: palette.text, fontSize: portrait ? 20 : 22, fontWeight: 970 }}>{name}</div>
            <div style={{ color, fontSize: portrait ? 16 : 17, fontWeight: 840, marginTop: 4 }}>{job}</div>
          </div>
        );
      })}
      <DebateBursts local={local} portrait={portrait} />
    </div>
  );
};

const DebateBursts = ({ local, portrait }: { local: number; portrait: boolean }) => {
  const messages = [
    ["多头", "趋势延续需要量价确认", palette.red],
    ["空头", "风险不能被涨幅掩盖", palette.green],
    ["风控", "结论强度下调一档", palette.gold],
    ["组合", "收敛为研究建议", palette.teal],
  ] as const;

  return (
    <div
      style={{
        position: "absolute",
        left: portrait ? 34 : 42,
        right: portrait ? 34 : 42,
        bottom: portrait ? 34 : 38,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "repeat(4, 1fr)",
        gap: 12,
      }}
    >
      {messages.map(([speaker, text, color], index) => {
        const reveal = clamp((local % 90) - index * 12, [0, 18], [0, 1]);
        return (
          <div
            key={speaker}
            style={{
              opacity: 0.42 + reveal * 0.58,
              border: `1px solid ${color}55`,
              background: `${color}18`,
              borderRadius: 14,
              padding: portrait ? "13px 15px" : "14px 16px",
            }}
          >
            <div style={{ color, fontSize: portrait ? 17 : 17, fontWeight: 950 }}>{speaker}</div>
            <div style={{ color: palette.text, fontSize: portrait ? 18 : 18, fontWeight: 820, marginTop: 4 }}>{text}</div>
          </div>
        );
      })}
    </div>
  );
};

const ReportScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad } = useLayout(format);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        padding: portrait ? `190px ${pad}px 0` : `155px ${pad}px 0`,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "0.82fr 1.18fr",
        gap: portrait ? 38 : 70,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 22 }}>
        <Kicker>机构式研究报告</Kicker>
        <Title format={format} small>
          不是一句结论
          <br />
          而是一份报告
        </Title>
        <Body format={format}>核心观点、量化图表、投资研究建议、风险边界与跟踪条件，会被沉淀到同一份报告里。</Body>
      </div>
      <ReportStack local={local} portrait={portrait} />
    </div>
  );
};

const ReportStack = ({ local, portrait }: { local: number; portrait: boolean }) => {
  const checklist = ["核心观点", "图表指标", "投资研究建议", "跟踪条件", "风险提示"];
  const rise = clamp(local, [0, 46], [72, 0]);

  return (
    <div style={{ position: "relative", height: portrait ? 780 : 720 }}>
      {[0, 1, 2].map((index) => {
        const reveal = clamp(local - index * 16, [0, 30], [0, 1]);
        return (
          <div
            key={index}
            style={{
              position: "absolute",
              left: portrait ? index * 14 : index * 28,
              right: portrait ? index * 14 : index * 28,
              top: index * (portrait ? 34 : 30) + rise * (1 - reveal),
              height: portrait ? 650 : 560,
              borderRadius: 24,
              background: index === 0 ? "rgba(246,255,252,0.96)" : "rgba(246,255,252,0.36)",
              border: "1px solid rgba(143,255,229,0.22)",
              opacity: index === 0 ? 1 : 0.5,
              transform: `scale(${1 - index * 0.035})`,
              boxShadow: index === 0 ? "0 34px 100px rgba(0,0,0,0.38)" : "none",
              padding: portrait ? 34 : 40,
              color: palette.deep,
            }}
          >
            {index === 0 ? (
              <>
                <div style={{ color: palette.tealDeep, fontSize: portrait ? 22 : 22, fontWeight: 900 }}>机构式研究报告</div>
                <div style={{ fontSize: portrait ? 45 : 54, fontWeight: 1000, lineHeight: 1.05, marginTop: 14 }}>
                  五一视界
                  <br />
                  研究结论
                </div>
                <div style={{ marginTop: 28, display: "grid", gridTemplateColumns: portrait ? "1fr" : "1fr 1fr", gap: 22 }}>
                  <MiniChart local={local} />
                  <div style={{ display: "grid", gap: 12 }}>
                    {checklist.map((item, itemIndex) => {
                      const done = clamp(local - 45 - itemIndex * 7, [0, 16], [0, 1]);
                      return (
                        <div
                          key={item}
                          style={{
                            height: portrait ? 54 : 56,
                            borderRadius: 14,
                            border: "1px solid rgba(10,91,82,0.15)",
                            background: "rgba(10,91,82,0.06)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "0 18px",
                            fontSize: portrait ? 21 : 22,
                            fontWeight: 900,
                          }}
                        >
                          <span>{item}</span>
                          <span style={{ color: palette.tealDeep, opacity: done }}>✓</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        );
      })}
    </div>
  );
};

const MiniChart = ({ local }: { local: number }) => {
  const bars = [74, 68, 61, 46, 82];
  return (
    <div
      style={{
        borderRadius: 20,
        background: "rgba(10,91,82,0.09)",
        padding: 22,
        display: "grid",
        gap: 18,
      }}
    >
      <div style={{ color: palette.tealDeep, fontSize: 20, fontWeight: 950 }}>量化图表摘要</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, alignItems: "end", height: 210 }}>
        {bars.map((bar, index) => {
          const height = clamp(local - index * 8, [0, 36], [0, bar]);
          const colors = [palette.green, palette.teal, palette.gold, palette.red, palette.teal];
          const color = colors[index] ?? palette.teal;
          return (
            <div key={index} style={{ display: "grid", alignItems: "end", height: "100%", background: "rgba(255,255,255,0.74)", borderRadius: 12, padding: 9 }}>
              <div style={{ height: `${height}%`, borderRadius: 10, background: color }} />
            </div>
          );
        })}
      </div>
    </div>
  );
};

const TraceScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad } = useLayout(format);
  const rows = [
    ["数据", "行情 / 财报 / 公告 / 新闻"],
    ["算法", "趋势 / 动量 / 波动 / 相对强弱"],
    ["会议", "质询 / 反证 / 风控 / 收敛"],
    ["报告", "观点 / 建议 / 边界 / 跟踪"],
  ];

  return (
    <div
      style={{
        position: "absolute",
        left: pad,
        right: pad,
        top: portrait ? 230 : 205,
        display: "grid",
        gridTemplateColumns: portrait ? "1fr" : "0.82fr 1.18fr",
        gap: portrait ? 40 : 70,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 22 }}>
        <Kicker tone="gold">全链路可追溯</Kicker>
        <Title format={format} small>
          每一句判断
          <br />
          都能找到来路
        </Title>
        <Body format={format}>用户不需要看所有底层细节，但系统内部必须知道每个结论来自哪里。</Body>
      </div>
      <div style={{ display: "grid", gap: portrait ? 16 : 18 }}>
        {rows.map(([title, desc], index) => {
          const reveal = clamp(local - index * 10, [0, 24], [0, 1]);
          return (
            <div
              key={title}
              style={{
                opacity: reveal,
                transform: `translateY(${(1 - reveal) * 24}px)`,
                borderRadius: 22,
                border: "1px solid rgba(143,255,229,0.24)",
                background: "linear-gradient(90deg, rgba(143,255,229,0.14), rgba(255,255,255,0.05))",
                padding: portrait ? "24px 26px" : "28px 32px",
                display: "grid",
                gridTemplateColumns: portrait ? "90px 1fr" : "120px 1fr 90px",
                gap: 20,
                alignItems: "center",
              }}
            >
              <div style={{ color: palette.teal, fontSize: portrait ? 26 : 29, fontWeight: 980 }}>{title}</div>
              <div style={{ color: palette.text, fontSize: portrait ? 25 : 27, fontWeight: 880 }}>{desc}</div>
              {!portrait ? <div style={{ color: palette.gold, fontSize: 24, fontWeight: 1000 }}>可追溯</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const FinaleScene = ({ format, local }: { format: PromoFormat; local: number }) => {
  const { portrait, pad, height } = useLayout(format);
  const scale = clamp(local, [0, 38], [0.94, 1]);
  const glow = 0.3 + Math.sin(local / 12) * 0.12;

  return (
    <div
      style={{
        position: "absolute",
        left: pad,
        right: pad,
        top: portrait ? 250 : 205,
        bottom: portrait ? 220 : 140,
        display: "grid",
        placeItems: "center",
        textAlign: "center",
        transform: `scale(${scale})`,
      }}
    >
      <div>
        <div
          style={{
            color: palette.teal,
            fontSize: portrait ? 28 : 28,
            fontWeight: 940,
            marginBottom: portrait ? 26 : 28,
            textShadow: `0 0 ${60 * glow}px rgba(143,255,229,0.6)`,
          }}
        >
          君宇·投研智能体
        </div>
        <Title format={format} maxWidth={portrait ? undefined : 1050}>
          输入一只股票
          <br />
          得到一份
          <br />
          专业研究报告
        </Title>
        <div
          style={{
            margin: portrait ? "42px auto 0" : "46px auto 0",
            display: "inline-flex",
            alignItems: "center",
            gap: 16,
            borderRadius: 999,
            padding: portrait ? "22px 30px" : "22px 34px",
            background: "linear-gradient(90deg, rgba(143,255,229,0.22), rgba(232,199,107,0.16))",
            border: `1px solid ${palette.lineHot}`,
            color: palette.text,
            fontSize: portrait ? 26 : 28,
            fontWeight: 970,
            boxShadow: "0 0 70px rgba(143,255,229,0.25)",
          }}
        >
          量化底稿 <span style={{ color: palette.dim }}>｜</span> 可信证据链 <span style={{ color: palette.dim }}>｜</span> 专业研究报告
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: portrait ? -80 : -30,
          height: Math.max(2, height * 0.006),
          background: `linear-gradient(90deg, transparent, ${palette.teal}, ${palette.gold}, transparent)`,
          boxShadow: "0 0 36px rgba(143,255,229,0.55)",
        }}
      />
    </div>
  );
};

const PulseSvg = ({ size = 82 }: { size?: number }) => {
  const frame = useCurrentFrame();
  const progress = clamp(frame % 60, [0, 60], [0, 1]);
  const points = [
    [0, 32],
    [18, 32],
    [28, 12],
    [40, 52],
    [55, 22],
    [70, 32],
    [92, 32],
  ];
  const visible = points
    .slice(0, Math.max(2, Math.round(progress * points.length)))
    .map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`)
    .join(" ");
  return (
    <svg width={size} height={size * 0.62} viewBox="0 0 92 64">
      <path d={visible} fill="none" stroke={palette.teal} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

const Subtitle = ({ format }: { format: PromoFormat }) => {
  const frame = useCurrentFrame();
  const { portrait, pad, captionBottom } = useLayout(format);
  const active = currentCaption(frame);

  if (!active) {
    return null;
  }

  const start = Math.floor((active.startMs / 1000) * FPS);
  const end = Math.floor((active.endMs / 1000) * FPS);
  const opacity = Math.min(clamp(frame - start, [0, 12], [0, 1]), clamp(frame, [end - 12, end], [1, 0]));
  const progress = linear(frame - start, [0, Math.max(1, end - start)], [0, 1]);

  return (
    <div
      style={{
        position: "absolute",
        left: pad,
        right: pad,
        bottom: captionBottom,
        zIndex: 90,
        opacity,
        transform: `translateY(${(1 - opacity) * 20}px)`,
        borderRadius: portrait ? 24 : 20,
        border: `1px solid ${palette.line}`,
        background: "linear-gradient(90deg, rgba(2,8,10,0.9), rgba(8,18,20,0.68))",
        boxShadow: "0 22px 80px rgba(0,0,0,0.46), 0 0 42px rgba(143,255,229,0.14)",
        padding: portrait ? "23px 25px" : "18px 28px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          height: 4,
          width: `${progress * 100}%`,
          background: `linear-gradient(90deg, ${palette.teal}, ${palette.gold})`,
        }}
      />
      <div
        style={{
          color: palette.text,
          fontSize: portrait ? 31 : 26,
          lineHeight: 1.36,
          fontWeight: 920,
          letterSpacing: 0,
          textAlign: portrait ? "left" : "center",
        }}
      >
        {active.text}
      </div>
    </div>
  );
};

const TransitionHits = () => {
  const frame = useCurrentFrame();
  return (
    <>
      {sceneDefs.slice(1).map((scene) => {
        const local = frame - scene.from;
        const opacity = Math.max(0, 1 - Math.abs(local) / 8);
        if (opacity <= 0) {
          return null;
        }
        return (
          <div
            key={scene.id}
            style={{
              position: "absolute",
              inset: 0,
              zIndex: 80,
              opacity: opacity * 0.55,
              background: "linear-gradient(105deg, transparent, rgba(143,255,229,0.70), rgba(255,255,255,0.55), transparent)",
              transform: `translateX(${(local - 4) * 18}%) skewX(-16deg)`,
              mixBlendMode: "screen",
            }}
          />
        );
      })}
    </>
  );
};

const SceneDeck = ({ format }: { format: PromoFormat }) => {
  const frame = useCurrentFrame();
  const activeIndex = sceneDefs.findIndex((scene) => frame >= scene.from && frame < scene.to);

  return (
    <>
      <SceneLayer id="hook">{(local) => <HookScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="problem">{(local) => <ProblemScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="lock">{(local) => <LockScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="quant">{(local) => <QuantScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="evidence">{(local) => <EvidenceScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="quality">{(local) => <QualityScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="committee">{(local) => <CommitteeScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="report">{(local) => <ReportScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="trace">{(local) => <TraceScene format={format} local={local} />}</SceneLayer>
      <SceneLayer id="finale">{(local) => <FinaleScene format={format} local={local} />}</SceneLayer>
      <ProgressRail activeIndex={Math.max(0, activeIndex)} format={format} />
    </>
  );
};

const ProgressRail = ({ activeIndex, format }: { activeIndex: number; format: PromoFormat }) => {
  const { portrait, pad } = useLayout(format);
  if (portrait) {
    return null;
  }
  return (
    <div
      style={{
        position: "absolute",
        left: pad,
        right: pad,
        bottom: 112,
        height: 3,
        zIndex: 55,
        display: "grid",
        gridTemplateColumns: `repeat(${sceneDefs.length}, 1fr)`,
        gap: 8,
      }}
    >
      {sceneDefs.map((scene, index) => (
        <div
          key={scene.id}
          style={{
            height: 3,
            borderRadius: 99,
            background: index <= activeIndex ? palette.teal : "rgba(255,255,255,0.15)",
            boxShadow: index === activeIndex ? "0 0 20px rgba(143,255,229,0.7)" : "none",
          }}
        />
      ))}
    </div>
  );
};

export const JunyuQuantPromo = ({ format }: JunyuQuantPromoProps) => {
  return (
    <AbsoluteFill
      style={{
        fontFamily:
          "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        background: palette.ink,
        overflow: "hidden",
      }}
    >
      <Soundtrack />
      <Backdrop format={format} />
      <GlobalHeader format={format} />
      <SceneDeck format={format} />
      <TransitionHits />
      <Subtitle format={format} />
      <Sequence from={0} durationInFrames={DURATION}>
        <NoiseTexture />
      </Sequence>
    </AbsoluteFill>
  );
};

const NoiseTexture = () => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 100,
        pointerEvents: "none",
        opacity: 0.055,
        backgroundImage:
          "radial-gradient(circle at 12% 22%, white 0 1px, transparent 1px), radial-gradient(circle at 72% 62%, white 0 1px, transparent 1px)",
        backgroundSize: `${32 + (frame % 3)}px ${28 + (frame % 5)}px`,
        mixBlendMode: "screen",
      }}
    />
  );
};
