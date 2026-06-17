import React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

export const palette = {
  ink: "#061012",
  panel: "rgba(8, 18, 20, 0.72)",
  panelSoft: "rgba(255, 255, 255, 0.08)",
  line: "rgba(211, 255, 245, 0.22)",
  text: "#F5FBF9",
  muted: "rgba(232, 245, 242, 0.68)",
  teal: "#86F5DF",
  tealDeep: "#0A5A50",
  gold: "#D8B86A",
  red: "#D44B4B",
  green: "#087143",
  white: "#FFFFFF",
};

export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);

export const clamp = (value: number, input: [number, number], output: [number, number]) =>
  interpolate(value, input, output, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });

export const sceneOpacity = (frame: number, duration: number) => {
  const enter = clamp(frame, [0, 24], [0, 1]);
  const exit = clamp(frame, [duration - 24, duration], [1, 0]);
  return Math.min(enter, exit);
};

export const Background = ({ dim = 0.78 }: { dim?: number }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const drift = interpolate(frame, [0, 1800], [0, width * 0.035], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <>
      <Img
        src={staticFile("images/decision-room-hero.png")}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(1.06) translateX(${-drift}px)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(90deg, rgba(0,0,0,${dim + 0.08}) 0%, rgba(0,0,0,${dim}) 42%, rgba(0,0,0,0.48) 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 24% 18%, rgba(134,245,223,0.12), transparent 32%), radial-gradient(circle at 78% 18%, rgba(216,184,106,0.10), transparent 30%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.16,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)",
          backgroundSize: `${Math.max(72, width / 20)}px ${Math.max(72, height / 16)}px`,
        }}
      />
      <TechOverlay intensity={0.58} />
    </>
  );
};

export const Badge = ({ children, tone = "teal" }: { children: React.ReactNode; tone?: "teal" | "gold" }) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      width: "fit-content",
      border: `1px solid ${tone === "teal" ? "rgba(134,245,223,0.45)" : "rgba(216,184,106,0.48)"}`,
      color: tone === "teal" ? palette.teal : palette.gold,
      background: tone === "teal" ? "rgba(10, 90, 80, 0.36)" : "rgba(90, 70, 20, 0.28)",
      borderRadius: 999,
      padding: "10px 18px",
      fontWeight: 800,
      letterSpacing: 0,
      boxShadow: tone === "teal" ? "0 0 28px rgba(134,245,223,0.16)" : "0 0 24px rgba(216,184,106,0.14)",
    }}
  >
    <span style={{ width: 9, height: 9, borderRadius: 99, background: "currentColor" }} />
    {children}
  </div>
);

export const GlassPanel = ({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) => (
  <div
    style={{
      border: `1px solid ${palette.line}`,
      background: "linear-gradient(145deg, rgba(7, 16, 18, 0.72), rgba(255,255,255,0.08))",
      boxShadow: "0 28px 100px rgba(0,0,0,0.42), inset 0 1px 0 rgba(255,255,255,0.08)",
      borderRadius: 18,
      backdropFilter: "blur(18px)",
      ...style,
    }}
  >
    {children}
  </div>
);

export const SectionLabel = ({ children }: { children: React.ReactNode }) => (
  <div style={{ color: palette.muted, fontSize: 24, fontWeight: 700, marginBottom: 14 }}>{children}</div>
);

export const BigTitle = ({
  children,
  size = 82,
  maxWidth,
}: {
  children: React.ReactNode;
  size?: number;
  maxWidth?: number;
}) => (
  <h1
    style={{
      color: palette.text,
      fontSize: size,
      lineHeight: 1.08,
      fontWeight: 900,
      letterSpacing: 0,
      margin: 0,
      maxWidth,
      textWrap: "balance",
    }}
  >
    {children}
  </h1>
);

export const BodyText = ({
  children,
  size = 32,
  maxWidth,
}: {
  children: React.ReactNode;
  size?: number;
  maxWidth?: number;
}) => (
  <p
    style={{
      color: palette.muted,
      fontSize: size,
      lineHeight: 1.64,
      fontWeight: 650,
      letterSpacing: 0,
      margin: 0,
      maxWidth,
      textWrap: "pretty",
    }}
  >
    {children}
  </p>
);

export const PulseLine = () => {
  const frame = useCurrentFrame();
  const progress = clamp(frame % 90, [0, 90], [0, 1]);
  const points = [
    [0, 28],
    [20, 28],
    [34, 8],
    [48, 48],
    [66, 20],
    [86, 28],
    [110, 28],
  ];
  const visible = points
    .slice(0, Math.max(2, Math.round(progress * points.length)))
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x} ${y}`)
    .join(" ");

  return (
    <svg width="120" height="56" viewBox="0 0 120 56">
      <path d={visible} fill="none" stroke={palette.teal} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

export const AnimatedBar = ({ value, color = palette.teal, delay = 0 }: { value: number; color?: string; delay?: number }) => {
  const frame = useCurrentFrame();
  const width = clamp(frame - delay, [0, 42], [0, value]);

  return (
    <div style={{ height: 12, borderRadius: 20, background: "rgba(255,255,255,0.12)", overflow: "hidden" }}>
      <div style={{ width: `${width}%`, height: "100%", borderRadius: 20, background: color }} />
    </div>
  );
};

export const TypeText = ({ text, charsPerFrame = 0.7 }: { text: string; charsPerFrame?: number }) => {
  const frame = useCurrentFrame();
  const visible = text.slice(0, Math.floor(frame * charsPerFrame));

  return (
    <span>
      {visible}
      <span style={{ color: palette.teal }}>▌</span>
    </span>
  );
};

export const TechOverlay = ({ intensity = 1 }: { intensity?: number }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const scanY = interpolate(frame % 180, [0, 180], [-height * 0.1, height * 1.05], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <>
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.12 * intensity,
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 7px)",
          mixBlendMode: "screen",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: scanY,
          height: Math.max(80, height * 0.08),
          opacity: 0.22 * intensity,
          background:
            "linear-gradient(180deg, transparent, rgba(134,245,223,0.28), transparent)",
          filter: "blur(10px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
        }}
      >
        {Array.from({ length: 22 }).map((_, index) => {
          const x = ((index * 97) % 1000) / 1000;
          const yBase = ((index * 173) % 1000) / 1000;
          const y = (yBase * height + frame * (0.18 + (index % 5) * 0.03)) % height;
          const label = ["RPS", "MACD", "ROE", "ATR", "IC", "IR", "BETA", "VOL"][index % 8];
          return (
            <div
              key={index}
              style={{
                position: "absolute",
                left: x * width,
                top: y,
                color: index % 3 === 0 ? "rgba(216,184,106,0.40)" : "rgba(134,245,223,0.34)",
                fontSize: 14 + (index % 3) * 2,
                fontWeight: 800,
                letterSpacing: 1,
                opacity: 0.36 * intensity,
                transform: `translateY(${Math.sin((frame + index * 14) / 24) * 8}px)`,
              }}
            >
              {label}.{String((index * 37 + frame) % 100).padStart(2, "0")}
            </div>
          );
        })}
      </div>
    </>
  );
};

export const HudCorners = ({ color = palette.teal }: { color?: string }) => (
  <div style={{ position: "absolute", inset: 52, pointerEvents: "none", opacity: 0.52 }}>
    {[
      { position: { left: 0, top: 0 }, lines: { borderLeftWidth: 2, borderTopWidth: 2 } },
      { position: { right: 0, top: 0 }, lines: { borderRightWidth: 2, borderTopWidth: 2 } },
      { position: { left: 0, bottom: 0 }, lines: { borderLeftWidth: 2, borderBottomWidth: 2 } },
      { position: { right: 0, bottom: 0 }, lines: { borderRightWidth: 2, borderBottomWidth: 2 } },
    ].map((corner, index) => {
      return (
        <div
          key={index}
          style={{
            position: "absolute",
            width: 86,
            height: 86,
            borderColor: color,
            borderStyle: "solid",
            borderWidth: 0,
            ...corner.position,
            ...corner.lines,
          }}
        />
      );
    })}
  </div>
);

export const SceneCaption = ({ children, tone = "dark" }: { children: React.ReactNode; tone?: "dark" | "light" }) => (
  <div
    style={{
      position: "absolute",
      left: 108,
      right: 108,
      bottom: 54,
      display: "flex",
      alignItems: "center",
      gap: 16,
      borderTop: tone === "dark" ? "1px solid rgba(255,255,255,0.16)" : "1px solid rgba(0,70,60,0.14)",
      paddingTop: 18,
      color: tone === "dark" ? "rgba(245,251,249,0.76)" : "rgba(6,16,18,0.62)",
      fontSize: 24,
      lineHeight: 1.45,
      fontWeight: 700,
    }}
  >
    <span
      style={{
        width: 12,
        height: 12,
        borderRadius: 999,
        background: tone === "dark" ? palette.teal : palette.tealDeep,
        boxShadow: `0 0 22px ${tone === "dark" ? "rgba(134,245,223,0.5)" : "rgba(10,90,80,0.24)"}`,
      }}
    />
    {children}
  </div>
);

export const MetricChip = ({ label, value }: { label: string; value: string }) => (
  <div
    style={{
      border: "1px solid rgba(134,245,223,0.22)",
      background: "rgba(255,255,255,0.07)",
      borderRadius: 14,
      padding: "14px 16px",
      minWidth: 150,
    }}
  >
    <div style={{ color: palette.muted, fontSize: 18, fontWeight: 700 }}>{label}</div>
    <div style={{ color: palette.text, fontSize: 30, fontWeight: 950, marginTop: 4 }}>{value}</div>
  </div>
);
