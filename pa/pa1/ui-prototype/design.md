# Design — Medication Safety Assistant

A locked design system for the multi-page prototype. Patient, HCP and Admin pages share the same visual language while exposing only the navigation appropriate to each role.

## Genre

Playful–clinical: reassuring and friendly for older adults, precise and information-dense for healthcare professionals. The interface is never childish and never presents simulated content as medical advice.

## Macrostructure family

- Marketing pages: **Feature Stack**, adapted to a non-sticky mobile-first narrative.
- App pages: **Workbench**, with a persistent horizontal N1b menu and task-focused content below it.
- Content and policy pages: **Long Document**, limited to 60–65 characters per line.

## Navigation

- Public, Patient and HCP areas use an **N1b always-solid top menu**.
- No sidebar is used.
- Patient and HCP menus have separate route sets and clear role labels.
- Below the content breakpoint the links collapse behind one menu button; link labels never wrap.
- Frontend role navigation is prototype-only and is not authorization.

## Theme

- `--color-paper`: `oklch(98% 0.012 172)`
- `--color-paper-2`: `oklch(95% 0.025 169)`
- `--color-paper-3`: `oklch(91% 0.065 162)`
- `--color-ink`: `oklch(22% 0.025 174)`
- `--color-ink-2`: `oklch(32% 0.035 176)`
- `--color-rule`: `oklch(80% 0.035 172)`
- `--color-accent`: `oklch(51% 0.085 183)`
- `--color-focus`: `oklch(48% 0.16 185)`
- Cream is a supportive accent. Red, amber, green and blue are reserved for medical or system status.

## Typography

- Display: Bricolage Grotesque, weight 700, roman.
- Body: IBM Plex Sans, weight 400; labels use 600–700.
- Display tracking: `-0.035em`.
- Patient body text starts at 18 px and can be increased from the interface.
- Vietnamese copy uses explicit labels, short verbs and no diagnostic claims.

## Spacing

The 4-point named scale in `tokens.css` is mandatory. Pages use tokens instead of raw spacing values.

## Components

- Buttons: primary, secondary, quiet and destructive variants; minimum 44 px target.
- Inputs: visible label, stable helper slot, one-pixel border in every state and immediate focus outline.
- Status: icon/text plus colour; never colour alone.
- Cards: one containment layer, 12 px radius, one restrained shadow.
- Tables: full table on large screens and labelled records on narrow screens.
- Workflow: one shared three-step stepper for prescription processing.
- Feedback: inline status for visible results; no celebratory success toast.

## Motion

- Easings: `--ease-out`, `--ease-in`, `--ease-in-out` from `tokens.css`.
- Primitives: button press, menu reveal and direct status update.
- No page-wide scroll reveals or decorative motion.
- Reduced motion removes spatial animation and keeps state changes at 150 ms or less.

## CTA voice

- Primary: dark teal fill, direct verb such as “Tải đơn thuốc” or “Bắt đầu review”.
- Secondary: paper fill with teal outline.
- Dangerous actions: red is used only with explicit destructive wording.

## Per-page allowances

- Landing may use one hand-built product illustration; the patient dashboard uses one generated medication illustration to fill the primary action card.
- App pages use functional content rather than decorative enrichment.
- Tiểu Bạch is a functional assistant entry point, not an ambient decoration.

## What pages MUST share

- Tiểu Bạch wordmark, teal/mint palette and paired fonts.
- Top-menu geometry, mobile disclosure and active-page treatment.
- Page-header rhythm, buttons, fields, status chips, stepper and safety notices.
- Mock-data labels where no backend is connected.

## What pages MAY differ on

- Patient pages use larger copy and simpler actions.
- HCP pages may use denser tables, filters and case metadata.
- Admin retains a darker operational header but uses the same tokens and components.

## Exports

### tokens.css

`tokens.css` beside this file is the source of truth.

### Tailwind v4 `@theme`

```css
@theme {
  --color-paper: oklch(98% 0.012 172);
  --color-paper-2: oklch(95% 0.025 169);
  --color-paper-3: oklch(91% 0.065 162);
  --color-ink: oklch(22% 0.025 174);
  --color-ink-2: oklch(32% 0.035 176);
  --color-accent: oklch(51% 0.085 183);
  --color-focus: oklch(48% 0.16 185);
  --font-display: "Bricolage Grotesque", sans-serif;
  --font-body: "IBM Plex Sans", sans-serif;
  --spacing-sm: 0.75rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --radius-card: 0.75rem;
  --radius-pill: 99rem;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

### DTCG `tokens.json`

```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "color": {
    "paper": { "$value": "oklch(98% 0.012 172)", "$type": "color" },
    "ink": { "$value": "oklch(22% 0.025 174)", "$type": "color" },
    "accent": { "$value": "oklch(51% 0.085 183)", "$type": "color" },
    "focus": { "$value": "oklch(48% 0.16 185)", "$type": "color" }
  },
  "font": {
    "display": { "$value": "Bricolage Grotesque, sans-serif", "$type": "fontFamily" },
    "body": { "$value": "IBM Plex Sans, sans-serif", "$type": "fontFamily" }
  },
  "space": {
    "sm": { "$value": "0.75rem", "$type": "dimension" },
    "md": { "$value": "1rem", "$type": "dimension" },
    "lg": { "$value": "1.5rem", "$type": "dimension" }
  }
}
```

### shadcn/ui CSS variables

```css
:root {
  --background: 98% 0.012 172;
  --foreground: 22% 0.025 174;
  --card: 95% 0.025 169;
  --card-foreground: 22% 0.025 174;
  --primary: 43% 0.083 183;
  --primary-foreground: 98% 0.012 172;
  --secondary: 91% 0.065 162;
  --secondary-foreground: 22% 0.025 174;
  --muted: 87% 0.026 172;
  --muted-foreground: 42% 0.025 176;
  --destructive: 46% 0.17 28;
  --destructive-foreground: 98% 0.012 172;
  --border: 80% 0.035 172;
  --input: 80% 0.035 172;
  --ring: 48% 0.16 185;
  --radius: 0.75rem;
}
```
