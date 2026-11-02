---
name: Clinical Clarity
colors:
  surface: '#e7fef9'
  surface-dim: '#c8dfda'
  surface-bright: '#e7fef9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#e1f8f3'
  surface-container: '#dcf3ee'
  surface-container-high: '#d6ede8'
  surface-container-highest: '#d0e7e2'
  on-surface: '#0a1f1c'
  on-surface-variant: '#3f4947'
  inverse-surface: '#203431'
  inverse-on-surface: '#dff6f1'
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
  background: '#e7fef9'
  on-background: '#0a1f1c'
  surface-variant: '#d0e7e2'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system is engineered for dual audiences: healthcare professionals (HCPs) requiring rapid, error-free clinical decision support, and patients seeking calm, unambiguous reassurance regarding medication safety. 

The aesthetic is **Clinical Precision with Human Warmth**—combining the exacting structure of high-reliability medical instrumentation with welcoming, non-intimidating healthcare interfaces. The visual language conveys uncompromising competence, pharmaceutical safety, and quiet reassurance.

Key visual attributes:
- **Crisp & Sterile-Clean:** Pure white primary surfaces set against soft off-white canvases evoke hospital-grade hygiene without cold sterility.
- **Cognitive Ease:** High contrast text hierarchy and dedicated color coding for clinical alerts (safe green-mints, cautionary soft ambers/creams) ensure rapid scanning during high-stress workflows.
- **Architectural Balance:** Restrained lines, deliberate spacing, and controlled card elevations create a systematic environment where critical drug interactions and dosage calculations take precedence.

## Colors

The palette establishes an authoritative medical baseline utilizing deep clinical teal, mint accents, and warm cream indicators over high-clarity white surfaces.

### Primary Role & Tones
- **Primary Deep Teal (`#287a74`):** Anchors core actions, critical confirmation flows, primary navigation headers, and authoritative clinical states.
- **Secondary Mid Teal (`#55a9a0`):** Interactive highlights, secondary button fills, input focus rings, and active data visualization segments.
- **Tertiary Soft Mint (`#aeeed3`):** Low-strain background fills for "Safe" drug interaction tags, verified dosage badges, and subtle positive status panels. Contrast against `#1a2e2b` text.

### Surface & Canvas Architecture
- **Canvas Base (`#f8fafc`):** Pristine slate off-white serving as the foundational background layer, isolating work cards without causing glare.
- **Surface Elevation (`#ffffff`):** Pure stark white reserved for active content cards, clinical patient charts, modals, and prescription summary panels.
- **Border & Hairline Grids (`#e2e8f0` and `#e6f0ed`):** Subdued, razor-sharp 1px delimiters keeping medical tables and inputs clearly partitioned.

### Alerts & Contextual Neutrals
- **Warm Caution / Notice Cream (`#fff8b0`):** Used strictly for safety warning callouts, dose change flags, and contraindication notices when paired with `#334e4a` typography.
- **Primary Ink (`#1a2e2b`):** Deep botanical-slate charcoal for maximum legibility on headings, drug names, and numerical values.
- **Secondary Ink (`#334e4a`):** Subdued slate-teal for descriptive metadata, lab references, and form field labels.
- **Tertiary Ink (`#64748b`):** Timestamps, deactivated states, and helper instructions.

## Typography

The typographic engine relies on **Plus Jakarta Sans** across all roles to achieve a balance between medical authority and approachable clarity. Its tall x-height, clear aperture openings, and modern geometric terminals ensure drug nomenclatures (e.g., *Amoxicillin/Clavulanic acid*), dosages (e.g., *125 mg/5 mL*), and complex clinical instructions remain unmistakable under screen glare and quick glance conditions.

### Rules of Implementation
- **Numerical Regularity:** For titration charts, lab metrics, and medication timings, tabular numbers (`tnum`) must be enforced via OpenType features to preserve strict vertical alignment.
- **Weight Restraint:** Limit weights strictly to Semi-Bold (600), Bold (700), and Regular (400). Never use thin or light weights; they degrade clinical readability.
- **Uppercase Application:** Restrict uppercase text to `label-sm` for critical tag anchors (e.g., `RX ONLY`, `INTERACTION DETECTED`) with explicit `0.04em` tracking to prevent letter clumping.

## Layout & Spacing

The structural layout utilizes a fluid 12-column grid system bounded by maximum ergonomic line lengths for medical records.

### Grid Architecture
- **Desktop (>= 1280px):** 12-column grid with `2rem` outer margins and `1.5rem` gutters. Content containers are capped at 1440px width to prevent chart stretching.
- **Tablet (768px - 1279px):** 8-column grid with `1.5rem` outer margins and `1.25rem` gutters. Left-hand clinician navigation sidebars collapse into a persistent drawer.
- **Mobile (<= 767px):** 4-column grid with `1rem` margins and `1rem` gutters. Multicolumn patient records stack linearly into single-column card flows.

### Spacing Principles
- Clinical data elements (medication name, concentration, schedule) are grouped tightly using `space-xs` (4px) and `space-sm` (8px).
- Structural module separation within clinical review cards requires `space-md` (16px) or `space-lg` (24px) to preserve breathing room and prevent misreading adjacent records.
- Major anatomical or timeline sections use `space-xl` (40px) vertical margins.

## Elevation & Depth

To avoid visual pollution and maintain a sterile, clinical appearance, this design system relies on **Tonal Separation paired with Ultra-Soft Ambient Shadowing**. 

Heavy skeuomorphic drops and dark drop shadows are forbidden; depth must evoke paper-thin clinical slips and elevated surgical trays.

### Elevation Hierarchy
- **Level 0 (Base Floor):** Pure `#f8fafc`. Houses the outer backdrop and inactive paneling.
- **Level 1 (Clinical Cards & Tables):** Pure `#ffffff` surface, framed by a crisp 1px border of `#e2e8f0` and an ambient shadow: `0 1px 3px 0 rgba(26, 46, 43, 0.04), 0 1px 2px -1px rgba(26, 46, 43, 0.02)`.
- **Level 2 (Interactive Modules & Hover States):** Raised white containers, bordered with `#e6f0ed`, elevated by `0 4px 6px -1px rgba(40, 122, 116, 0.06), 0 2px 4px -2px rgba(26, 46, 43, 0.04)`.
- **Level 3 (Safety Alerts, Dropdowns & Modals):** Dedicated dialogs floating above a softened `#1a2e2b` (opacity 30%) veil: `0 10px 15px -3px rgba(26, 46, 43, 0.08), 0 4px 6px -4px rgba(26, 46, 43, 0.03)`.

## Shapes

The design system incorporates a disciplined **0.5rem (8px) to 0.75rem (12px)** border radius standard. This creates an architecture that is reassuring and ergonomic without losing its formal medical authority.

### Application Specs
- **Default Elements (8px / `rounded-md`):** Buttons, text fields, notification alerts, interaction pills, and internal sub-panels.
- **Containers & Cards (12px / `rounded-lg`):** Patient overview panels, dosage calculators, drug interaction cards, and modal dialogs.
- **Badges & Status Indicators (Pill / Full):** Drug scheduling tags, verification status checks, and numeric quantity indicators strictly utilize 9999px fully rounded caps for instant visual isolation from rectangular inputs.

## Components

### Buttons
- **Primary:** Background `#287a74`, text `#ffffff`, height 44px, padding 0 20px, radius 8px. Hover state changes background to `#216560`. Focus produces a 2px offset ring in `#55a9a0`.
- **Secondary:** Background `#ffffff`, border 1.5px solid `#55a9a0`, text `#287a74`. Hover state shifts background to `#f0f9f8`.
- **Tertiary / Ghost:** Text `#287a74`, no border or shadow. Hover introduces `#e6f0ed` tint.

### Chips & Badges
- **Safe / Normal Tag:** Background `#aeeed3`, text `#1a2e2b`, font weight 600, radius 9999px, padding 4px 10px.
- **Warning / Notice Tag:** Background `#fff8b0`, text `#334e4a`, border 1px solid rgba(51, 78, 74, 0.12), radius 9999px, padding 4px 10px.
- **Neutral Info Tag:** Background `#f1f5f9`, text `#64748b`, radius 9999px, padding 4px 10px.

### Form Inputs
- **Text & Select Fields:** Surface `#ffffff`, border 1px solid `#e2e8f0`, radius 8px, padding 12px 14px, text `#1a2e2b`. Placeholder `#64748b`. Active focus shifts border to `#55a9a0` with a 3px soft focus halo (`rgba(85, 169, 160, 0.15)`).
- **Error State:** Border shifts to `#e11d48` with helper text rendered in high-contrast red.

### Checkboxes & Radio Controls
- **Size & Style:** 18px width/height, 4px radius for checkboxes, 50% radius for radio controls. Unchecked border is 1.5px solid `#cbd5e1`. Checked state transitions fill directly to `#287a74` with an internal white checkmark or radio dot.

### Clinical Data Cards
- Pure `#ffffff` surface, 1px solid `#e6f0ed` border, 12px border radius, `space-lg` (24px) internal padding. 
- Headers feature a bottom divider of 1px solid `#f1f5f9`, partitioning the patient metadata from active drug titration and clinical notes.

### Safety Alert Banner
- Dedicated banner spanning card widths: 1px border in `#e6f0ed`, filled with pale warm cream tint (`#fffde6`), flanked by a solid 4px accent left border in `#287a74` (for informational protocol) or an amber tint for allergy warnings.