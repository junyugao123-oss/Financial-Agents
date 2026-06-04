# Design

## Design System Name

Top Fund Decision Room

## Theme

The visual theme is a premium institutional investment committee experience. The interface should feel quiet, professional, and guided. It should not feel like a dense trader terminal, an AI chatbot, or a marketing landing page.

## Color Palette

Use OKLCH tokens in CSS.

- Background: near-white neutral with a slight cool tint.
- Ink: graphite and charcoal for primary reading.
- Surface: white and cool gray panels with crisp separators.
- Accent: restrained deep teal for current progress and primary actions.
- Secondary accent: steel blue for information states.
- Risk: red only for downside risk or warnings.
- Positive: green only for upside or completion states.

Accent color should be used for current selection, progress, focus, and primary actions. It should not become decorative.

## Typography

Use one modern sans-serif stack:

`Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif`

Product UI uses a tight fixed scale:

- Page title: 40px desktop, 32px mobile.
- Section title: 28px desktop, 24px mobile.
- Panel title: 18px.
- Body: 15px to 16px.
- Metadata: 12px to 13px.

No fluid viewport-based type scaling. No all-caps body copy.

## Layout

The MVP experience is vertical and step-based:

1. Homepage introduction with visual narrative and clear call to action.
2. Research task setup.
3. Fact-base preview.
4. Live investment committee process.
5. Institutional report output.

Avoid putting all state into a single dense screen. The session page can use sticky progress and a single main stage so users understand where they are in the process.

## Components

- Buttons: 8px radius, clear states, icons where useful.
- Panels: 8px radius max, crisp border or subtle shadow, not both as decoration.
- Progress: step rail with completion states.
- Live events: structured meeting records, not chat bubbles.
- Report: formal reading layout with section navigation, export actions, and persistent disclaimer.

## Motion

Motion is used to communicate state: section entrance, event arrival, progress completion, and report section readiness. Transitions should be 150-250ms and respect reduced-motion preferences.

## Copy

Copy should be specific and institutional. Avoid generic AI marketing language. The central message is:

还原专业金融机构投研团队的决策流程，让用户看见一份研究结论如何被提出、质疑、修正并写入研报。

## Compliance

The following statement must appear on the homepage, session workflow, and final report:

本程序输出仅用于信息整理与研究辅助，不构成任何财务、投资或交易建议。
