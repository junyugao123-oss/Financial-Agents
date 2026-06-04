type AvatarStyle = {
  accessory?: "headset" | "tablet";
  accent: string;
  bg: string;
  expression: "calm" | "firm" | "warm";
  eyewear: "none" | "rect" | "round";
  face: "long" | "oval" | "round" | "square";
  gender: "female" | "male";
  hair: string;
  hairStyle:
    | "bob"
    | "crop"
    | "curly"
    | "long"
    | "sidePart"
    | "slick"
    | "swept"
    | "tied";
  neckwear: "neckScarf" | "open" | "slimTie" | "stripedTie" | "tie" | "turtleneck" | "wideTie";
  outfit: "blazer" | "classicSuit" | "executiveSuit" | "knit" | "structuredJacket";
  skin: string;
  shirt: string;
  suit: string;
};

export type Participant = {
  avatar: AvatarStyle;
  duty: string;
  role: string;
  short: string;
};

const defaultAvatar: AvatarStyle = {
  accent: "#0f766e",
  bg: "#e2e8f0",
  expression: "calm",
  eyewear: "none",
  face: "oval",
  gender: "male",
  hair: "#172033",
  hairStyle: "sidePart",
  neckwear: "tie",
  outfit: "classicSuit",
  skin: "#f0bd93",
  shirt: "#f8fafc",
  suit: "#1e293b",
};

export const participants: Participant[] = [
  {
    role: "多头研究员",
    duty: "构建上行证据链",
    short: "多",
    avatar: {
      accessory: "tablet",
      accent: "#2563eb",
      bg: "#dbeafe",
      expression: "warm",
      eyewear: "rect",
      face: "oval",
      gender: "female",
      hair: "#111827",
      hairStyle: "long",
      neckwear: "open",
      outfit: "classicSuit",
      skin: "#f0c6a3",
      shirt: "#f8fafc",
      suit: "#1e2f55",
    },
  },
  {
    role: "数据助理",
    duty: "校验行情与数据口径",
    short: "数",
    avatar: {
      accent: "#334155",
      bg: "#dff2df",
      expression: "firm",
      eyewear: "none",
      face: "square",
      gender: "male",
      hair: "#172033",
      hairStyle: "swept",
      neckwear: "stripedTie",
      outfit: "classicSuit",
      skin: "#e7b58c",
      shirt: "#f8fafc",
      suit: "#1f2937",
    },
  },
  {
    role: "量化研究员",
    duty: "拆解多因子信号",
    short: "量",
    avatar: {
      accent: "#64748b",
      bg: "#f8d8df",
      expression: "warm",
      eyewear: "none",
      face: "round",
      gender: "female",
      hair: "#2f1d1d",
      hairStyle: "curly",
      neckwear: "open",
      outfit: "blazer",
      skin: "#d99b77",
      shirt: "#f8fafc",
      suit: "#94a3b8",
    },
  },
  {
    role: "技术分析师",
    duty: "复核量价与趋势结构",
    short: "技",
    avatar: {
      accent: "#7f1d1d",
      bg: "#f7e8ad",
      expression: "calm",
      eyewear: "none",
      face: "long",
      gender: "male",
      hair: "#2b211b",
      hairStyle: "slick",
      neckwear: "wideTie",
      outfit: "structuredJacket",
      skin: "#e9b58a",
      shirt: "#fff7ed",
      suit: "#b0895b",
    },
  },
  {
    role: "基本面分析师",
    duty: "审查盈利、估值与公告",
    short: "基",
    avatar: {
      accent: "#ca8a04",
      bg: "#d5eee9",
      expression: "warm",
      eyewear: "none",
      face: "oval",
      gender: "female",
      hair: "#1f1b2d",
      hairStyle: "long",
      neckwear: "open",
      outfit: "blazer",
      skin: "#f0c6a3",
      shirt: "#f8fafc",
      suit: "#166534",
    },
  },
  {
    role: "首席策略官",
    duty: "设定研究假设与边界",
    short: "策",
    avatar: {
      accent: "#111827",
      bg: "#f6c37c",
      expression: "firm",
      eyewear: "none",
      face: "long",
      gender: "male",
      hair: "#cbd5e1",
      hairStyle: "swept",
      neckwear: "tie",
      outfit: "executiveSuit",
      skin: "#e1aa83",
      shirt: "#f8fafc",
      suit: "#374151",
    },
  },
  {
    role: "空头研究员",
    duty: "压测下行情景",
    short: "空",
    avatar: {
      accent: "#be123c",
      bg: "#f7bfd4",
      expression: "firm",
      eyewear: "none",
      face: "oval",
      gender: "female",
      hair: "#b7412e",
      hairStyle: "bob",
      neckwear: "open",
      outfit: "structuredJacket",
      skin: "#efbd9b",
      shirt: "#fff1f2",
      suit: "#7e2553",
    },
  },
  {
    role: "风控负责人",
    duty: "约束流动性与回撤风险",
    short: "控",
    avatar: {
      accent: "#0f766e",
      bg: "#cfead0",
      expression: "calm",
      eyewear: "none",
      face: "round",
      gender: "male",
      hair: "#111827",
      hairStyle: "sidePart",
      neckwear: "slimTie",
      outfit: "classicSuit",
      skin: "#f0c6a3",
      shirt: "#f8fafc",
      suit: "#111827",
    },
  },
  {
    role: "组合经理",
    duty: "收敛信息完整指数与研究口径",
    short: "组",
    avatar: {
      accent: "#92400e",
      bg: "#f7d889",
      expression: "warm",
      eyewear: "none",
      face: "oval",
      gender: "female",
      hair: "#24130f",
      hairStyle: "tied",
      neckwear: "neckScarf",
      outfit: "blazer",
      skin: "#9f654b",
      shirt: "#fff7ed",
      suit: "#f8fafc",
    },
  },
  {
    role: "报告编辑",
    duty: "沉淀图表化研报",
    short: "报",
    avatar: {
      accessory: "headset",
      accent: "#111827",
      bg: "#f7b66e",
      expression: "calm",
      eyewear: "none",
      face: "oval",
      gender: "male",
      hair: "#111827",
      hairStyle: "crop",
      neckwear: "turtleneck",
      outfit: "knit",
      skin: "#e7b58c",
      shirt: "#111827",
      suit: "#1f2937",
    },
  },
];

const rosterOrder = [
  "首席策略官",
  "组合经理",
  "风控负责人",
  "基本面分析师",
  "量化研究员",
  "技术分析师",
  "多头研究员",
  "空头研究员",
  "数据助理",
  "报告编辑",
];

const participantByRole = new Map(participants.map((participant) => [participant.role, participant]));

export const participantRoster = rosterOrder.flatMap((role) => {
  const participant = participantByRole.get(role);
  return participant ? [participant] : [];
});

export function roleProfile(role: string): Participant {
  return participantByRole.get(role) ?? {
    role,
    duty: "记录会议过程",
    short: role.slice(0, 1),
    avatar: defaultAvatar,
  };
}

export function RolePortrait({
  active = false,
  role,
  size = "normal",
}: {
  active?: boolean;
  role: string;
  size?: "micro" | "normal" | "large";
}) {
  const profile = roleProfile(role);
  const avatar = profile.avatar;
  const face = faceMetrics(avatar.face);
  const sizeClass =
    size === "large" ? "h-16 w-16" : size === "micro" ? "h-9 w-9" : "h-12 w-12";

  return (
    <div
      aria-label={profile.role}
      className={`relative shrink-0 overflow-hidden rounded-full bg-white ${sizeClass} ${
        active
          ? "ring-2 ring-[var(--teal)] ring-offset-2 ring-offset-white"
          : "ring-1 ring-[var(--line)]"
      }`}
      data-avatar-style={`${avatar.gender}-${avatar.face}-${avatar.hairStyle}-${avatar.outfit}-${avatar.neckwear}-${avatar.eyewear}-${avatar.accessory ?? "none"}`}
    >
      <svg aria-hidden="true" className="h-full w-full" viewBox="0 0 64 64">
        <rect fill={avatar.bg} height="64" rx="32" width="64" />
        <path d="M26 37h12l2 9-8 5-8-5Z" fill={avatar.skin} />
        {renderOutfit(avatar)}
        {renderNeckwear(avatar)}
        <path d="M15 58c8 4 24 5 47 1" fill="none" opacity="0.16" stroke="#fff" strokeWidth="3" />
        {renderHairBack(avatar)}
        <ellipse cx="18.8" cy="30" fill={avatar.skin} rx="3" ry="4.2" />
        <ellipse cx="45.2" cy="30" fill={avatar.skin} rx="3" ry="4.2" />
        {avatar.face === "square" ? (
          <rect fill={avatar.skin} height="31" rx="9" width="26" x="19" y="13.8" />
        ) : (
          <ellipse cx="32" cy={face.cy} fill={avatar.skin} rx={face.rx} ry={face.ry} />
        )}
        {renderHairFront(avatar)}
        {renderBrows(avatar.expression)}
        <circle cx="27" cy="31" fill="#111827" r="1.4" />
        <circle cx="37" cy="31" fill="#111827" r="1.4" />
        {renderEyewear(avatar)}
        <path d="M32 31c-.5 3-1.4 5-2.7 6 1.3.8 3 .8 4.4 0" fill="none" stroke="#c77855" strokeLinecap="round" strokeWidth="1.8" />
        {renderMouth(avatar.expression)}
        {renderAccessory(avatar)}
        <path d="M16 15c6-8 21-11 33 0" fill="none" opacity="0.25" stroke="#fff" strokeLinecap="round" strokeWidth="3" />
        <path d="M11 62l17-17 4 19Z" fill="#000" opacity="0.08" />
        <path d="M63 63 37 45l-5 19Z" fill="#000" opacity="0.08" />
        <rect fill={avatar.shirt} height="2" opacity="0.9" rx="1" width="8" x="45" y="53" />
        <rect
          fill="none"
          height="58"
          opacity="0.42"
          rx="29"
          stroke="#fff"
          strokeWidth="1.5"
          width="58"
          x="3"
          y="3"
        />
      </svg>
      {active ? (
        <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border border-white bg-[var(--green)]" />
      ) : null}
    </div>
  );
}

function faceMetrics(face: AvatarStyle["face"]) {
  if (face === "round") return { cy: 28, rx: 13.8, ry: 14 };
  if (face === "long") return { cy: 27.2, rx: 12.2, ry: 16.2 };
  return { cy: 27.5, rx: 13.4, ry: 15.2 };
}

function renderOutfit(avatar: AvatarStyle) {
  switch (avatar.outfit) {
    case "executiveSuit":
      return (
        <>
          <path d="M7 64c3-16 14-24 33-23 12 1 20 9 23 23Z" fill={avatar.suit} />
          <path d="M23 42h19l-4 22H27Z" fill={avatar.shirt} />
          <path d="M15 64l14-21 4 21Z" fill="#000" opacity="0.2" />
          <path d="M61 64 38 43l-5 21Z" fill="#000" opacity="0.18" />
          <path d="M18 56h10M45 55h9" stroke="#fff" strokeLinecap="round" strokeWidth="1.6" opacity="0.38" />
        </>
      );
    case "structuredJacket":
      return (
        <>
          <path d="M8 64c3-16 14-24 33-23 11 1 19 9 23 23Z" fill={avatar.suit} />
          <path d="M22 42h20v22H22Z" fill={avatar.shirt} />
          <path d="M15 64l8-21 9 21Z" fill={avatar.suit} opacity="0.96" />
          <path d="M57 64 42 43l-10 21Z" fill={avatar.suit} opacity="0.96" />
          <path d="M17 50h10M42 50h10" stroke="#fff" strokeLinecap="round" strokeWidth="1.5" opacity="0.4" />
        </>
      );
    case "blazer":
      return (
        <>
          <path d="M8 64c3-15 13-23 31-23 11 1 19 9 23 23Z" fill={avatar.suit} />
          <path d="M24 42h17l-3 22H27Z" fill={avatar.shirt} />
          <path d="M16 64l11-20 5 20Z" fill="#fff" opacity="0.12" />
          <path d="M60 64 38 44l-4 20Z" fill="#fff" opacity="0.12" />
        </>
      );
    case "knit":
      return (
        <>
          <path d="M9 64c4-15 14-24 32-23 11 1 19 9 24 23Z" fill={avatar.suit} />
          <path d="M24 42h16v14H24Z" fill={avatar.shirt} />
          <path d="M18 52h28M16 58h34" stroke="#fff" strokeLinecap="round" strokeWidth="1.5" opacity="0.22" />
        </>
      );
    default:
      return (
        <>
          <path d="M8 64c3-15 13-23 32-23 11 1 19 9 23 23Z" fill={avatar.suit} />
          <path d="M22 42h20l-5 22H27Z" fill={avatar.shirt} />
          <path d="M13 64l17-20 3 20Z" fill="#000" opacity="0.16" />
          <path d="M62 64 36 44l-4 20Z" fill="#000" opacity="0.16" />
        </>
      );
  }
}

function renderHairBack(avatar: AvatarStyle) {
  switch (avatar.hairStyle) {
    case "bob":
      return <path d="M15 31c0-14 8-23 20-23 11 0 18 8 18 22 0 9-3 17-8 22-3-6-8-8-14-8-6 0-11 3-15 8-4-6-1-16-1-21Z" fill={avatar.hair} />;
    case "long":
      return <path d="M14 29c0-13 8-22 19-22 12 0 19 8 19 22 0 12-4 22-10 30-4-6-15-6-20 0-6-8-8-18-8-30Z" fill={avatar.hair} />;
    case "tied":
      return (
        <>
          <circle cx="50" cy="27" fill={avatar.hair} r="7" />
          <circle cx="17" cy="29" fill={avatar.hair} r="4.5" />
          <path d="M17 28c0-12 8-20 19-20 10 0 16 7 16 18-5-4-10-6-17-6-8 0-14 3-18 8Z" fill={avatar.hair} />
        </>
      );
    case "curly":
      return (
        <>
          <path d="M16 25c1-9 7-16 18-17 11-1 18 5 19 15-5-2-10-3-15-3-7-1-14 1-22 5Z" fill={avatar.hair} />
          <circle cx="21" cy="21" fill={avatar.hair} r="5" />
          <circle cx="29" cy="16.5" fill={avatar.hair} r="5" />
          <circle cx="38" cy="17" fill={avatar.hair} r="5" />
          <circle cx="46" cy="21" fill={avatar.hair} r="4.5" />
        </>
      );
    case "crop":
      return <path d="M18 24c2-9 9-14 20-12 6 1 10 5 11 11-8-3-18-3-31 1Z" fill={avatar.hair} />;
    case "swept":
      return <path d="M17 25c2-10 8-16 18-16 9 0 15 4 18 12-7-5-18-6-36 4Z" fill={avatar.hair} />;
    case "slick":
      return <path d="M17 24c3-10 10-15 20-14 8 1 13 6 15 14-8-5-20-6-35 0Z" fill={avatar.hair} />;
    default:
      return <path d="M18 24c2-9 9-14 20-12 6 1 10 5 11 11-8-3-18-3-31 1Z" fill={avatar.hair} />;
  }
}

function renderHairFront(avatar: AvatarStyle) {
  switch (avatar.hairStyle) {
    case "bob":
      return <path d="M18 24c5-9 14-12 28-6-6 3-15 4-26 4-1 2-2 3-2 4Z" fill={avatar.hair} />;
    case "long":
      return <path d="M17 25c6-11 15-14 29-6-6 3-15 4-25 3-2 1-3 3-4 5Z" fill={avatar.hair} />;
    case "tied":
      return <path d="M18 24c5-8 13-11 25-6 2 1 4 2 6 4-11-2-20-1-31 3Z" fill={avatar.hair} />;
    case "curly":
      return <path d="M17 24c5-8 14-10 28-4-6 2-14 3-23 6-2 0-4 0-5-2Z" fill={avatar.hair} />;
    case "crop":
      return <path d="M19 23c4-5 14-7 26-3-9 1-17 2-26 3Z" fill={avatar.hair} />;
    case "swept":
      return <path d="M17 24c7-10 16-13 29-7 0 0-7 6-21 5-3 1-5 3-8 2Z" fill={avatar.hair} />;
    case "slick":
      return <path d="M18 23c8-5 18-6 29-2-8 1-16 2-27 5-1-1-2-2-2-3Z" fill={avatar.hair} />;
    default:
      return <path d="M18 24c5-9 14-12 28-6-6 3-15 4-26 4-1 2-2 3-2 4Z" fill={avatar.hair} />;
  }
}

function renderNeckwear(avatar: AvatarStyle) {
  switch (avatar.neckwear) {
    case "neckScarf":
      return (
        <>
          <path d="M23 43c5 5 13 5 18 0l-4 8-5-3-5 3Z" fill={avatar.accent} opacity="0.95" />
          <path d="M34 48l8 16h-7l-5-14Z" fill={avatar.accent} opacity="0.72" />
        </>
      );
    case "open":
      return <path d="M27 44l5 6 5-6" fill="none" stroke={avatar.accent} strokeLinecap="round" strokeWidth="2" />;
    case "slimTie":
      return <path d="M31 45h3l2 19h-8Z" fill={avatar.accent} opacity="0.95" />;
    case "stripedTie":
      return (
        <>
          <path d="M30 45h4l3 19h-10Z" fill={avatar.accent} opacity="0.95" />
          <path d="M29 52h7M28.5 58h8" opacity="0.45" stroke="#fff" strokeLinecap="round" strokeWidth="1.4" />
        </>
      );
    case "turtleneck":
      return (
        <>
          <path d="M25 42h14v16H25Z" fill={avatar.shirt} />
          <path d="M25 44h14" opacity="0.45" stroke={avatar.accent} strokeLinecap="round" strokeWidth="2" />
        </>
      );
    case "wideTie":
      return <path d="M29 45h6l5 19H24Z" fill={avatar.accent} opacity="0.95" />;
    default:
      return <path d="M30 45h4l3 19h-10Z" fill={avatar.accent} opacity="0.95" />;
  }
}

function renderBrows(expression: AvatarStyle["expression"]) {
  if (expression === "firm") {
    return (
      <>
        <path d="M24 27c2.4-1.6 4.5-1.3 6.4.2" fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.7" />
        <path d="M34 27.2c2-1.4 4.2-1.8 6.5-.2" fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.7" />
      </>
    );
  }
  return (
    <>
      <path d="M24 28c2-1.2 4-1.2 6 0" fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.7" />
      <path d="M34 28c2-1.2 4-1.2 6 0" fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.7" />
    </>
  );
}

function renderEyewear(avatar: AvatarStyle) {
  if (avatar.eyewear === "rect") {
    return (
      <g fill="none" stroke="#334155" strokeWidth="1.25">
        <rect height="5.2" rx="1.8" width="8.4" x="22.2" y="28.8" />
        <rect height="5.2" rx="1.8" width="8.4" x="33.4" y="28.8" />
        <path d="M30.6 31.3h2.8" strokeLinecap="round" />
      </g>
    );
  }
  return null;
}

function renderAccessory(avatar: AvatarStyle) {
  if (avatar.accessory === "tablet") {
    return (
      <g transform="rotate(-8 18 50)">
        <rect fill="#f8fafc" height="19" rx="2.3" stroke="#334155" strokeWidth="1.2" width="14" x="11" y="40" />
        <rect fill={avatar.accent} height="2" opacity="0.7" rx="1" width="8" x="14" y="44" />
        <rect fill="#cbd5e1" height="1.6" rx="0.8" width="7" x="14" y="49" />
        <circle cx="18" cy="55" fill="#94a3b8" r="0.9" />
      </g>
    );
  }
  if (avatar.accessory === "headset") {
    return (
      <g fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.8">
        <path d="M18 31c0-11 6-18 14-18s14 7 14 18" opacity="0.9" />
        <rect fill={avatar.bg} height="8" rx="2" stroke="#111827" width="4.5" x="14.5" y="29" />
        <rect fill={avatar.bg} height="8" rx="2" stroke="#111827" width="4.5" x="45" y="29" />
        <path d="M47 38c2.8 0 4.5 1.2 5 3.4" />
        <path d="M49.6 41.5h4.5" />
      </g>
    );
  }
  return null;
}

function renderMouth(expression: AvatarStyle["expression"]) {
  if (expression === "firm") {
    return <path d="M27 40c3 1.2 7 1.2 10 0" fill="none" stroke="#b86b52" strokeLinecap="round" strokeWidth="1.8" />;
  }
  if (expression === "warm") {
    return <path d="M26 39.5c4 3 8 3 12 0" fill="none" stroke="#b86b52" strokeLinecap="round" strokeWidth="1.8" />;
  }
  return <path d="M26.5 40c3.8 2.2 7.8 2.2 11.5 0" fill="none" stroke="#b86b52" strokeLinecap="round" strokeWidth="1.8" />;
}
