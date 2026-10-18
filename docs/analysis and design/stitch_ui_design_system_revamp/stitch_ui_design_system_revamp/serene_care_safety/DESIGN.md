---
name: Serene Care & Safety
colors:
  surface: '#fffae0'
  surface-dim: '#e3dc97'
  surface-bright: '#fffae0'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#fdf6ae'
  surface-container: '#f7f0a9'
  surface-container-high: '#f1eba4'
  surface-container-highest: '#ece59f'
  on-surface: '#1e1c00'
  on-surface-variant: '#3f4947'
  inverse-surface: '#353200'
  inverse-on-surface: '#faf3ac'
  outline: '#6f7977'
  outline-variant: '#bec9c7'
  surface-tint: '#0e6a64'
  primary: '#00615b'
  on-primary: '#ffffff'
  primary-container: '#287a74'
  on-primary-container: '#bbfff8'
  inverse-primary: '#87d4cd'
  secondary: '#006a63'
  on-secondary: '#ffffff'
  secondary-container: '#9ef2e7'
  on-secondary-container: '#097169'
  tertiary: '#20604b'
  on-tertiary: '#ffffff'
  tertiary-container: '#3c7963'
  on-tertiary-container: '#c0ffe4'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#a3f1e9'
  primary-fixed-dim: '#87d4cd'
  on-primary-fixed: '#00201e'
  on-primary-fixed-variant: '#00504b'
  secondary-fixed: '#9ef2e7'
  secondary-fixed-dim: '#82d5cb'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#00504a'
  tertiary-fixed: '#b0f0d5'
  tertiary-fixed-dim: '#94d3b9'
  on-tertiary-fixed: '#002116'
  on-tertiary-fixed-variant: '#0b513d'
  background: '#fffae0'
  on-background: '#1e1c00'
  surface-variant: '#ece59f'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 52px
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
  title-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 19px
    fontWeight: '600'
    lineHeight: 26px
  title-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 17px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-md: 1.5rem
  gutter-lg: 2rem
  margin: 1rem
  margin-md: 2rem
  margin-lg: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system establishes an empathetic, reassuring, and uncompromisingly clear digital environment for a Medication Safety Assistant targeting older adults, caregivers, and clinical support teams. The emotional core balances clinical precision with tender domestic warmth, eliminating the dread and cognitive fatigue often caused by complex medical management tools.

The visual style blends **Modern Humanist Healthcare** with **Tactile Softness**:
- **Clarity and Legibility First:** Interfaces prioritize immediate scannability, generous touch targets, and high typographic contrast to prevent dosing confusion.
- **Organic Warmth:** Strict medical sterility is replaced by soft sage-mints, calming teals, and luminous buttery creams that mimic sunlit care environments.
- **Protective Feedback:** Critical states (dosage schedules, drug interaction warnings, ingestion confirmation) leverage calm, distinct signals rather than jarring alert fatigue.

## Colors

The palette is derived directly from restorative botanical tones, creating natural comfort while sustaining accessibility standards:

- **Primary Deep Teal (`#287a74`):** Anchors high-priority actions, primary typography, headers, and essential navigational states. Delivers WCAG AAA compliance against cream and white grounds.
- **Secondary Sage / Mint (`#55a9a0`):** Drives secondary actions, active tabs, auxiliary icons, progress gauges, and secondary button outlines.
- **Tertiary Soft Mint (`#aeeed3`):** Serves as a soothing tint for success states, confirmed doses, pill badge containers, and gentle surface highlights.
- **Warm Cream / Butter Yellow (`#fff8b0`):** Acts as an ambient canvas wash, reminder banner background, and gentle highlight container, replacing stark white voids with gentle tactile warmth.
- **Text & Surface Semantics:** Pure `#133834` (near-black teal) handles high-legibility body copy. Background canvases alternate between pure `#FAFCFB` and warm tint `#FFFDF0`. Alert and caution signals use a dedicated warm amber (`#D97706`) paired against the butter cream.

## Typography

**Plus Jakarta Sans** is employed universally across headlines, body copy, and UI badges. Its open counters, distinct ascenders, and geometric clarity provide exceptional readability for aging eyes and individuals experiencing visual or cognitive fatigue.

Key Typographic Rules:
- Never drop below `14px` (`body-sm`) for critical instructional copy or medication dosages.
- Body sizes default to `18px` (`body-lg`) in primary medication verification workflows to maximize effortless recognition.
- Numbers in dosage counts and time reminders must use tabular figures (`tnum`) for instant scanning across lists.
- Avoid low-weight (300 or lower) fonts; maintain regular (400) for prose and semi-bold (600) to bold (700) for anchors and interactive labels.

## Layout & Spacing

The layout utilizes an adaptable 4-to-12 column fluid responsive grid anchored by a base 8-point increment:

- **Mobile (<600px):** 4 fluid columns, `margin` of `1rem`, `gutter` of `1rem`. Generous vertical space between interactive cards minimizes mis-taps.
- **Tablet (600px - 1024px):** 8 fluid columns, `margin-md` of `2rem`, `gutter-md` of `1.5rem`. Enables dual-pane layouts (medication routine alongside schedule view).
- **Desktop (>1024px):** 12 columns, max container width of `1200px`, centered with `margin-lg` of `3rem`, `gutter-lg` of `2rem`.

Layout Model:
- **Strict Touch Target Padding:** Every primary interaction area (confirm dose, snooze, view precautions) enforces a minimal tap footprint of 48×48px, padded with `space-md` internally.
- **Section Rhythm:** Group related medical cards with `space-sm` or `space-md`, while separating distinct daily time-blocks (Morning, Afternoon, Evening) with `space-xl`.

## Elevation & Depth

Visual hierarchy emphasizes comforting physical surfaces through subtle layering, eliminating harsh drop shadows that create visual clutter:

- **Surface Tiers:**
  - *Base Canvas:* Warm off-white (`#FAFCFB`) or butter tint (`#FFFDF0`).
  - *Container Level 1 (Resting Cards):* Crisp white (`#FFFFFF`) with a 1px soft border in `#E1ECE8`.
  - *Container Level 2 (Active Alerts / Pending Dose):* Light Butter Yellow (`#fff8b0`) or Soft Mint (`#aeeed3`) at 40% opacity.
- **Shadow Profile:** Shadows are ultra-diffuse and tinted with the primary teal tone (`rgba(40, 122, 116, 0.08)` to `rgba(40, 122, 116, 0.14)`), with a blur radius of 16px to 24px and minimal vertical displacement (4px to 6px). This creates an ambient "cushioned" presence rather than floating planes.
- **Modal Overlays:** Backdrops apply a smooth 8px blur combined with a tinted deep teal wash at 25% opacity (`rgba(40, 122, 116, 0.25)`), sustaining context while focusing attention.

## Shapes

The design uses **Rounded (Level 2)** geometry:
- Standard elements (input fields, action chips, cards) feature `0.5rem` (8px) base radius.
- Larger interactive cards, medication summary panels, and bottom sheets adopt `rounded-lg` (`1rem` / 16px) or `rounded-xl` (`1.5rem` / 24px).
- Pill status indicators, medication intake markers, and primary circular confirmations adopt full pill curvature to mirror actual pharmaceutical capsule forms.
- This balance yields an approachable, friendly touchpoint without looking juvenile or compromising clinical authority.

## Components

### Buttons
- **Primary Action (e.g., "Confirm Dose Taken"):** Solid Deep Teal (`#287a74`) background with clean white typography (`#FFFFFF`). Min height 52px, radius `0.75rem`. Hover shifts to `#1f645f`.
- **Secondary Action (e.g., "Remind in 15 mins"):** Tinted Butter Yellow (`#fff8b0`) or Sage tint with Deep Teal text. Soft 1px border using `#55a9a0`.
- **Tertiary / Ghost:** Transparent surface with Deep Teal text and bold underline or icon pairing.

### Medication Cards
- Pure white container with `1rem` radius, bordered in `1px solid rgba(85, 169, 160, 0.2)`.
- Left-side accent bar: Deep Teal for prescription meds, Mint (`#55a9a0`) for daily supplements, Warm Butter (`#fff8b0`) for time indicators.
- Includes dosage name in `title-lg`, instruction line in `body-md`, and large pill-shaped status badge.

### Chips & Badges
- Pill-shaped (`9999px` radius).
- **Scheduled Time:** `#fff8b0` background with `#433b00` text.
- **Taken / Safe:** `#aeeed3` background with Deep Teal (`#133834`) text.
- **Requires Attention / Interaction Risk:** Soft warm amber background with `#78350f` text.

### Inputs & Dosage Pickers
- Generous 52px input height with `0.5rem` radius.
- Background in white or tinted `#F5FAF8`, transitioning to a 2px Deep Teal (`#287a74`) stroke with soft teal outer glow on focus.
- Placeholder text in subdued sage-gray (`#698985`) meeting 4.5:1 contrast minimums.

### Checkboxes & Radios
- Oversized target boxes (24×24px visual marker within a 48×48px tap container).
- Checked state fills with Deep Teal (`#287a74`) and displays a crisp white checkmark.
- Radio circles feature an inner concentric mint pill ring when selected.

### Critical Safety Banners & Modals
- Caution banners adopt warm cream (`#fff8b0`) borders with Deep Teal text and amber accent icons.
- Emergency or drug-conflict alerts feature high-contrast Deep Teal headers with direct action pathways ("Call Doctor", "Review Conflict").