# Tiểu Bạch — Figma V2

Source: eKLIigmXybYf18oiLCPRf5, FULL V2 frames and V02 dashboard/chat frames. Archived v01 frames are excluded.

Review follow-up: mobile prioritizes the prescription action before its illustration, with two compact patient metrics and a 2×2 admin metric grid. Reviewer labels identify the review workspace independently of HCP. Tiểu Bạch uses a shared medical-companion vector with a white coat, teal medical mark and stethoscope; the shield brand logo stays unchanged.

Soft light theme, teal actions, mint/sky surfaces, restrained yellow warnings. Keep the established Bricolage Grotesque / IBM Plex Sans typography. Shared tokens live in tokens.css; Figma adjustments in src/figma.css. No dark mode. Existing high-contrast and larger-text preferences remain available.

Use existing Card, CardHeading, PageHeading, Field, Badge, Modal, Stepper. Cards: 17px radius, 24px padding, subtle shadow; controls: 10–12px radius, at least 44px touch area; body 14–16px, page heading 32/40, card heading 24/32. Top navigation and responsive menu, not a sidebar. Content max 1440 with 56px desktop padding. Mobile uses one column and 20px padding.

Figma specifies the layout and assets. Values are supplied by existing state/API, not copied as misleading static counts. Auth and role administration use real APIs. Clinical, reviewer and support workflows remain explicitly marked local demonstrations. Prototype controls must perform the stated local action or explain unavailable integration.
`nLanding approved: alternating C layout, teal color enabled, compact copy, duplicate final CTA removed, scroll reveal motion. Implemented in src/pages/Landing.tsx and landing.css. Local prescription preview does not upload files or run OCR; sample data is explicitly labeled.
