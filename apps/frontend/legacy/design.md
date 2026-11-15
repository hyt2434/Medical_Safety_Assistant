# Design — Tiểu Bạch

Locked design system for the PA2 frontend. Read this before changing any workspace.
Based on Hallmark's `references/design-md.md` and multi-page redesign contract, with the project's existing teal identity. This is a newly documented system, not a previously existing project specification.

## System
- Genre: modern-minimal, calm and readable for patients and healthcare staff.
- App macrostructure: Workbench. A top navigation menu, a restrained header, one primary task and a contextual secondary column.
- Login: split introduction and sign-in form, no decorative illustration or marketing claims.
- Theme: custom Tiểu Bạch teal; near-white neutral surfaces. Solid accent belongs to the primary action, brand mark and selected controls, not large backgrounds.
- PA1 is a historical reference at `/pa1.html`; these rules govern the current `src/pa2/` application.

## Typography
- Display: Bricolage Grotesque, weight 600–650, upright, tracking −0.035em.
- Body: IBM Plex Sans, weights 400–600. Vietnamese glyphs must be included.
- Code: local monospace fallback, only for diagnostic payloads.
- Fonts are bundled locally; no runtime Google Fonts dependency. System fonts are fallback only.
- Body 16px; secondary 14px; labels 12px; headings 28–40px. No tiny clinical explanations.

## Layout and spacing
- `tokens.css` at this directory is canonical; `src/pa2/tokens.css` imports it.
- Named spacing: 4, 8, 12, 16, 24, 32, 48, 64px. A 2px token is reserved for optical adjustment.
- No sidebar at any width; content up to 1440px. Task/context columns use `minmax(0, …)`.
- At tablet widths, forms stack. At every width navigation opens below the header using an explicit Menu control with `aria-expanded`.
- Buttons and navigation labels stay on one line. Long explanatory text belongs outside buttons.
- Cards delimit independent tasks; messages and medication rows use dividers, not nested cards.
- No decorative colored side stripes. Semantic warnings use a restrained tinted surface and a thin full border.

## CTA and interaction
- Primary: teal fill, white label, 8px corner, 44px minimum target. Action verbs and short labels.
- Secondary: neutral surface and border, same shape and target size.
- Distinct hover, pressed, instant focus ring, disabled, busy, error and saved feedback.
- No entrance animation, hover zoom, gradients or glass effects. Reduced motion disables spatial transitions.
- Success feedback is brief and factual. Existing consent and safety confirmation dialogs remain because they are part of the use-case specification.

## Shared contract
- All five roles share typography, tokens, navigation pattern and control shapes.
- One SVG stroke-icon vocabulary (`chrome.ts`). No emoji navigation. The patient chatbot shortcut reuses the PA1 mascot as a functional link.
- Existing route guards and UC-01–UC-18 state transitions remain intact.
- Fictional data stays labeled. A frontend role switch is not real authorization.
- Verify 320 / 375 / 414 / 768 / 1440px, visible labels, keyboard focus, menu toggle and form states before exporting screenshots.

## Exports
The following exports mirror `tokens.css`. Change the canonical file first, then regenerate these blocks. Tailwind and shadcn blocks are portability references, not dependencies of this Vite application.

### tokens.css
```css
/* Hallmark · genre: modern-minimal · macrostructure: Workbench · tone: calm clinical · anchor hue: teal */
:root {
  --color-paper: #f6f8f9;
  --color-surface: #ffffff;
  --color-paper-2: #edf5f3;
  --color-ink: #163631;
  --color-muted: #526b66;
  --color-accent: #26766b;
  --color-accent-strong: #18594f;
  --color-accent-ink: #ffffff;
  --color-rule: #d6e1de;
  --color-rule-strong: #9bb5ae;
  --color-warning: #785011;
  --color-warning-soft: #fff7e6;
  --color-danger: #9c3736;
  --color-danger-soft: #fff1ee;
  --color-success: #27604c;
  --color-focus: #006b77;
  --color-overlay: #10282066;
  --color-shadow: #183e3610;
  --color-shadow-raised: #10282020;
  --font-display: "Bricolage Grotesque Variable", "Segoe UI", sans-serif;
  --font-body: "IBM Plex Sans Variable", "Segoe UI", sans-serif;
  --font-mono: ui-monospace, Consolas, monospace;
  --space-3xs: .125rem;
  --space-2xs: .25rem;
  --space-xs: .5rem;
  --space-sm: .75rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;
  --space-2xl: 3rem;
  --space-3xl: 4rem;
  --space-4xl: 5rem;
  --text-xs: .75rem;
  --text-sm: .875rem;
  --text-base: 1rem;
  --text-md: 1.125rem;
  --text-lg: 1.25rem;
  --text-xl: 1.5rem;
  --text-2xl: 2rem;
  --text-display: clamp(1.75rem, 2.4vw, 2.5rem);
  --text-login: clamp(2rem, 3.5vw, 3.75rem);
  --tracking-display: -.035em;
  --tracking-label: .08em;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-pill: 999px;
  --rule-thin: 1px;
  --rule-strong: 2px;
  --rule-focus: 3px;
  --sidebar-width: 248px;
  --content-width: 1440px;
  --control-height: 44px;
  --icon-size: 20px;
  --avatar-size: 40px;
  --ease-out: cubic-bezier(.16,1,.3,1);
  --ease-in: cubic-bezier(.7,0,.84,0);
  --ease-in-out: cubic-bezier(.65,0,.35,1);
  --dur-micro: 120ms;
  --dur-short: 180ms;
  --dur-long: 320ms;
  --shadow-card: 0 1px 2px var(--color-shadow);
  --shadow-raised: 0 8px 32px var(--color-shadow-raised);
}

```

### Tailwind v4 @theme
```css
@theme {
  --color-paper: #f6f8f9;
  --color-surface: #ffffff;
  --color-paper-2: #edf5f3;
  --color-ink: #163631;
  --color-muted: #526b66;
  --color-accent: #26766b;
  --color-accent-strong: #18594f;
  --color-accent-ink: #ffffff;
  --color-rule: #d6e1de;
  --color-rule-strong: #9bb5ae;
  --color-warning: #785011;
  --color-warning-soft: #fff7e6;
  --color-danger: #9c3736;
  --color-danger-soft: #fff1ee;
  --color-success: #27604c;
  --color-focus: #006b77;
  --color-overlay: #10282066;
  --color-shadow: #183e3610;
  --color-shadow-raised: #10282020;
  --font-display: "Bricolage Grotesque Variable", "Segoe UI", sans-serif;
  --font-body: "IBM Plex Sans Variable", "Segoe UI", sans-serif;
  --font-mono: ui-monospace, Consolas, monospace;
  --spacing-3xs: .125rem;
  --spacing-2xs: .25rem;
  --spacing-xs: .5rem;
  --spacing-sm: .75rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --spacing-xl: 2rem;
  --spacing-2xl: 3rem;
  --spacing-3xl: 4rem;
  --spacing-4xl: 5rem;
  --text-xs: .75rem;
  --text-sm: .875rem;
  --text-base: 1rem;
  --text-md: 1.125rem;
  --text-lg: 1.25rem;
  --text-xl: 1.5rem;
  --text-2xl: 2rem;
  --text-display: clamp(1.75rem, 2.4vw, 2.5rem);
  --text-login: clamp(2rem, 3.5vw, 3.75rem);
  --ease-out: cubic-bezier(.16,1,.3,1);
  --ease-in: cubic-bezier(.7,0,.84,0);
  --ease-in-out: cubic-bezier(.65,0,.35,1);
}
```

### DTCG tokens.json
```json
{
  "color-paper": {
    "$type": "color",
    "$value": "#f6f8f9"
  },
  "color-surface": {
    "$type": "color",
    "$value": "#ffffff"
  },
  "color-paper-2": {
    "$type": "color",
    "$value": "#edf5f3"
  },
  "color-ink": {
    "$type": "color",
    "$value": "#163631"
  },
  "color-muted": {
    "$type": "color",
    "$value": "#526b66"
  },
  "color-accent": {
    "$type": "color",
    "$value": "#26766b"
  },
  "color-accent-strong": {
    "$type": "color",
    "$value": "#18594f"
  },
  "color-accent-ink": {
    "$type": "color",
    "$value": "#ffffff"
  },
  "color-rule": {
    "$type": "color",
    "$value": "#d6e1de"
  },
  "color-rule-strong": {
    "$type": "color",
    "$value": "#9bb5ae"
  },
  "color-warning": {
    "$type": "color",
    "$value": "#785011"
  },
  "color-warning-soft": {
    "$type": "color",
    "$value": "#fff7e6"
  },
  "color-danger": {
    "$type": "color",
    "$value": "#9c3736"
  },
  "color-danger-soft": {
    "$type": "color",
    "$value": "#fff1ee"
  },
  "color-success": {
    "$type": "color",
    "$value": "#27604c"
  },
  "color-focus": {
    "$type": "color",
    "$value": "#006b77"
  },
  "color-overlay": {
    "$type": "color",
    "$value": "#10282066"
  },
  "color-shadow": {
    "$type": "color",
    "$value": "#183e3610"
  },
  "color-shadow-raised": {
    "$type": "color",
    "$value": "#10282020"
  },
  "font-display": {
    "$type": "fontFamily",
    "$value": "\"Bricolage Grotesque Variable\", \"Segoe UI\", sans-serif"
  },
  "font-body": {
    "$type": "fontFamily",
    "$value": "\"IBM Plex Sans Variable\", \"Segoe UI\", sans-serif"
  },
  "font-mono": {
    "$type": "fontFamily",
    "$value": "ui-monospace, Consolas, monospace"
  },
  "space-3xs": {
    "$type": "dimension",
    "$value": ".125rem"
  },
  "space-2xs": {
    "$type": "dimension",
    "$value": ".25rem"
  },
  "space-xs": {
    "$type": "dimension",
    "$value": ".5rem"
  },
  "space-sm": {
    "$type": "dimension",
    "$value": ".75rem"
  },
  "space-md": {
    "$type": "dimension",
    "$value": "1rem"
  },
  "space-lg": {
    "$type": "dimension",
    "$value": "1.5rem"
  },
  "space-xl": {
    "$type": "dimension",
    "$value": "2rem"
  },
  "space-2xl": {
    "$type": "dimension",
    "$value": "3rem"
  },
  "space-3xl": {
    "$type": "dimension",
    "$value": "4rem"
  },
  "space-4xl": {
    "$type": "dimension",
    "$value": "5rem"
  },
  "text-xs": {
    "$type": "dimension",
    "$value": ".75rem"
  },
  "text-sm": {
    "$type": "dimension",
    "$value": ".875rem"
  },
  "text-base": {
    "$type": "dimension",
    "$value": "1rem"
  },
  "text-md": {
    "$type": "dimension",
    "$value": "1.125rem"
  },
  "text-lg": {
    "$type": "dimension",
    "$value": "1.25rem"
  },
  "text-xl": {
    "$type": "dimension",
    "$value": "1.5rem"
  },
  "text-2xl": {
    "$type": "dimension",
    "$value": "2rem"
  },
  "text-display": {
    "$type": "dimension",
    "$value": "clamp(1.75rem, 2.4vw, 2.5rem)"
  },
  "text-login": {
    "$type": "dimension",
    "$value": "clamp(2rem, 3.5vw, 3.75rem)"
  },
  "radius-sm": {
    "$type": "dimension",
    "$value": "8px"
  },
  "radius-md": {
    "$type": "dimension",
    "$value": "12px"
  },
  "radius-pill": {
    "$type": "dimension",
    "$value": "999px"
  }
}
```

### shadcn/ui CSS variables
```css
:root {
  --background: var(--color-paper);
  --foreground: var(--color-ink);
  --card: var(--color-surface);
  --card-foreground: var(--color-ink);
  --primary: var(--color-accent);
  --primary-foreground: var(--color-accent-ink);
  --secondary: var(--color-paper-2);
  --secondary-foreground: var(--color-ink);
  --muted: var(--color-paper-2);
  --muted-foreground: var(--color-muted);
  --border: var(--color-rule);
  --input: var(--color-rule);
  --ring: var(--color-focus);
  --radius: var(--radius-sm);
}
```
