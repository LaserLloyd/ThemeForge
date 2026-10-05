# Tokens

Generated from `src/css/theme-base.css` by `tools/sync_theme.py build` (ThemeForge 1.0.0).
Every theme resolves every token below: a theme sets the colours, and the rest are
shared or derived. The values shown are Purple's (the `:root` base).
`tokens/<theme>.json` holds each theme's resolved values in the W3C design tokens format.

Use a token with `var(--name)`. Never redeclare one in app CSS; give app variables an
app prefix (`--myapp-sidebar-w`) or alias a token (`--myapp-brand: var(--accent)`).
Core groups are what most apps use; extension groups exist for apps that need them.

Contrast floors every theme meets (`tools/check_contrast.py`; the night profile, used
by Night Red, lowers the text floors as noted in [THEMES.md](THEMES.md)):

| Pair | Floor |
|---|---|
| `--text-primary` on `--surface-0` and `--surface-2` | 7:1 |
| `--text-secondary` on `--surface-2` | 6:1 |
| `--text-primary`, `--text-secondary`, `--text-tertiary` on every surface | 4.5:1 |
| `--text-disabled` on every surface | 3:1 |
| `--on-accent` on `--accent` (and hover, pressed); every `--on-<status>` on its fill | 4.5:1 |
| every `--<status>-text` on `--surface-2`, `--surface-3` and its own `-subtle` fill | 4.5:1 |
| `--on-selected` on `--selected` | 4.5:1 |
| `--selected`, `--unselected-border`, `--unselected-fg` on the surfaces | 3:1 |
| `--border-strong`, `--control-track`, `--focus-ring` on the surfaces | 3:1 |
| syntax colours on `--syn-bg` (comments 3.5:1) | 4.5:1 |
| `--cat-1` ... `--cat-12` on `--surface-0` | 3:1 |

## Surfaces

*core.* Grounds, from the page (`--surface-0`) up through nav (1), cards (2), hover (3) and active (4); `--surface-sunken` for inset wells, `--surface-overlay` for menus and popovers, `--glass-*` for translucent panes, `--code-bg` for code.

| Token | Purple value |
|---|---|
| `--surface-void` | `#08080f` |
| `--surface-0` | `#0e0e1b` |
| `--surface-1` | `#14142a` |
| `--surface-2` | `#1d1d39` |
| `--surface-3` | `#232342` |
| `--surface-4` | `#262648` |
| `--surface-sunken` | `#0a0a14` |
| `--surface-overlay` | `#1d1d39` |
| `--glass-1` | `rgba(29,29,57,.72)` |
| `--glass-2` | `rgba(29,29,57,.84)` |
| `--glass-3` | `rgba(14,14,27,.92)` |
| `--glass-highlight` | `rgba(255,255,255,.055)` |
| `--code-bg` | `#0b0b16` |

## Text

*core.* Text tiers (primary, secondary, tertiary, disabled), links, and the label colour for each kind of fill (`--on-accent`, `--on-danger`, ...). Quieter text is a lower tier, never opacity.

| Token | Purple value |
|---|---|
| `--text-primary` | `#e8e8f0` |
| `--text-secondary` | `#a0a0bd` |
| `--text-tertiary` | `#8d8db0` |
| `--text-disabled` | `#717195` |
| `--text-inverse` | `#0e0e1b` |
| `--text-link` | `#a78bfa` |
| `--text-link-hover` | `#c4b5fd` |
| `--on-accent` | `#ffffff` |
| `--on-danger` | `#2a0808` |
| `--on-success` | `#052215` |
| `--on-warning` | `#251a00` |
| `--on-media` | `#ffffff` |
| `--on-media-muted` | `#d9d9e6` |

## Accent

*core.* The brand accent: fills for primary actions, with `--on-accent` for labels on them. Accent-coloured text uses `--text-link` instead.

| Token | Purple value |
|---|---|
| `--accent` | `#7c3aed` |
| `--accent-hover` | `#8250f0` |
| `--accent-pressed` | `#6d28d9` |
| `--accent-subtle` | `rgba(124,58,237,.16)` |
| `--accent-muted` | `rgba(124,58,237,.26)` |
| `--accent-glow` | `rgba(124,58,237,.35)` |
| `--accent-rgb` | `124,58,237` |
| `--accent-2` | `#5eead4` |
| `--accent-2-subtle` | `rgba(94,234,212,.12)` |

## Call to action

*core.* A stronger action plate for marketing-style calls to action, and the highlight colour for tips and marks.

| Token | Purple value |
|---|---|
| `--cta` | `#7c3aed` |
| `--cta-hover` | `#8250f0` |
| `--cta-pressed` | `#6d28d9` |
| `--on-cta` | `#ffffff` |
| `--cta-shadow` | `0 6px 20px rgba(124,58,237,.28)` |
| `--cta-shadow-hover` | `0 10px 28px rgba(124,58,237,.38)` |
| `--highlight` | `#fcd34d` |
| `--highlight-subtle` | `rgba(252,211,77,.12)` |
| `--on-highlight` | `#251a00` |

## Lines

*core.* Borders, dividers, the focus ring, glass strokes. `--border-strong` is the edge of a form control (3:1).

| Token | Purple value |
|---|---|
| `--border-subtle` | `#21213b` |
| `--border` | `#292945` |
| `--border-strong` | `#6f6f9c` |
| `--divider` | `#21213b` |
| `--focus-ring` | `#a78bfa` |
| `--focus-ring-width` | `2px` |
| `--focus-ring-offset` | `2px` |
| `--glass-stroke` | `rgba(255,255,255,.08)` |
| `--glass-stroke-strong` | `rgba(255,255,255,.16)` |

## Control states

*core.* On, checked, pressed and current (`--selected`, with `--on-selected` on it), and the off outline (`--unselected-border`, `--unselected-fg`). Measured at 3:1 or better on every surface in every theme.

| Token | Purple value |
|---|---|
| `--selected` | `var(--text-link)` |
| `--on-selected` | `var(--text-inverse)` |
| `--unselected-border` | `var(--border-strong)` |
| `--unselected-fg` | `var(--text-tertiary)` |

## Status

*core: success, warning, danger, info. extension: live, idle, offline, heartbeat.* Each status has a fill, a hover, a `-subtle` tint, a `-text` colour and a `-border`, plus an `--on-<status>` label colour for the solid fill. live, idle, offline and heartbeat (scheduled or ambient activity) are presence states for apps that show them.

| Token | Purple value |
|---|---|
| `--success` | `#34d399` |
| `--success-hover` | `#5fe0b0` |
| `--success-subtle` | `rgba(52,211,153,.12)` |
| `--success-text` | `#34d399` |
| `--success-border` | `rgba(52,211,153,.38)` |
| `--warning` | `#fbbf24` |
| `--warning-hover` | `#fcd34d` |
| `--warning-subtle` | `rgba(251,191,36,.12)` |
| `--warning-text` | `#fbbf24` |
| `--warning-border` | `rgba(251,191,36,.38)` |
| `--danger` | `#f87171` |
| `--danger-hover` | `#fca5a5` |
| `--danger-subtle` | `rgba(248,113,113,.12)` |
| `--danger-text` | `#f87171` |
| `--danger-border` | `rgba(248,113,113,.38)` |
| `--info` | `#60a5fa` |
| `--info-hover` | `#93c5fd` |
| `--info-subtle` | `rgba(96,165,250,.12)` |
| `--info-text` | `#60a5fa` |
| `--info-border` | `rgba(96,165,250,.38)` |
| `--live` | `#4ade80` |
| `--live-hover` | `#86efac` |
| `--live-subtle` | `rgba(74,222,128,.14)` |
| `--live-text` | `#4ade80` |
| `--live-border` | `rgba(74,222,128,.40)` |
| `--idle` | `#fbbf24` |
| `--idle-hover` | `#fcd34d` |
| `--idle-subtle` | `rgba(251,191,36,.12)` |
| `--idle-text` | `#fbbf24` |
| `--idle-border` | `rgba(251,191,36,.34)` |
| `--offline` | `#6b6b8a` |
| `--offline-hover` | `#8585a6` |
| `--offline-subtle` | `rgba(107,107,138,0.17)` |
| `--offline-text` | `#9a9ab8` |
| `--offline-border` | `rgba(107,107,138,.40)` |
| `--heartbeat` | `#f472b6` |
| `--heartbeat-hover` | `#f9a8d4` |
| `--heartbeat-subtle` | `rgba(244,114,182,.12)` |
| `--heartbeat-text` | `#f472b6` |
| `--heartbeat-border` | `rgba(244,114,182,.38)` |
| `--on-info` | `#041022` |
| `--on-live` | `#052210` |
| `--on-idle` | `#251a00` |
| `--on-offline` | `#ffffff` |
| `--on-heartbeat` | `#2a0c1c` |

## Overlays

*core.* Scrims behind dialogs and over media, the backdrop blur, and `--media-filter` for images marked `.ui-media`.

| Token | Purple value |
|---|---|
| `--scrim` | `rgba(6,6,14,.66)` |
| `--scrim-strong` | `rgba(4,4,10,.88)` |
| `--scrim-light` | `rgba(6,6,14,.44)` |
| `--scrim-media` | `linear-gradient(to top, rgba(8,8,15,.88), rgba(8,8,15,0))` |
| `--backdrop-blur` | `14px` |
| `--media-filter` | `none` |

## Chat and content

*extension.* Chat bubbles, the quote bar, `<mark>`, the markdown emphasis colours (`--md-*`), narrative text roles (`--rp-*`: speech, action, thought, whisper, out-of-character, shout, critical) for chat, fiction and transcript views, and diff colours.

| Token | Purple value |
|---|---|
| `--bubble-user-bg` | `#3b2b6e` |
| `--bubble-user-text` | `#e8e8f0` |
| `--bubble-user-border` | `#46337f` |
| `--bubble-assistant-bg` | `#1d1d39` |
| `--bubble-assistant-text` | `#e8e8f0` |
| `--quote-bar` | `#5eead4` |
| `--mark-bg` | `rgba(251,191,36,.30)` |
| `--md-bold` | `#ffffff` |
| `--md-italic` | `#fcd34d` |
| `--md-bolditalic` | `#fde68a` |
| `--md-bolditalic-glow` | `rgba(253,230,138,.40)` |
| `--rp-speech` | `#e8e8f0` |
| `--rp-action` | `#a0a0bd` |
| `--rp-thought` | `#a5f3ea` |
| `--rp-whisper` | `#8d8db0` |
| `--rp-ooc` | `var(--text-tertiary)` |
| `--rp-shout` | `#ff9a6c` |
| `--rp-shout-glow` | `rgba(255,154,108,.45)` |
| `--rp-critical` | `#ff7a90` |
| `--rp-critical-glow` | `rgba(255,122,144,.45)` |
| `--diff-add-bg` | `rgba(52,211,153,.14)` |
| `--diff-add-text` | `#7ee7bc` |
| `--diff-remove-bg` | `rgba(248,113,113,.14)` |
| `--diff-remove-text` | `#ffa0a0` |

## Syntax

*extension.* Code colours on `--syn-bg`, which is dark in every theme; the names follow highlight.js, which the base layer maps.

| Token | Purple value |
|---|---|
| `--syn-fg` | `#e2e2ef` |
| `--syn-bg` | `#0b0b16` |
| `--syn-comment` | `#7b7b9c` |
| `--syn-keyword` | `#c4a3ff` |
| `--syn-string` | `#86e8c8` |
| `--syn-number` | `#ffc46b` |
| `--syn-function` | `#8ec2ff` |
| `--syn-title` | `#8ec2ff` |
| `--syn-type` | `#6fe3d4` |
| `--syn-variable` | `#f0a8c8` |
| `--syn-attr` | `#ffd38a` |
| `--syn-tag` | `#c4a3ff` |
| `--syn-builtin` | `#6fe3d4` |
| `--syn-literal` | `#ffc46b` |
| `--syn-meta` | `#9a9ab8` |
| `--syn-operator` | `#d0c2f5` |
| `--syn-punctuation` | `#b6b6cf` |
| `--syn-deletion` | `#ffa0a0` |
| `--syn-addition` | `#7ee7bc` |

## Code block chrome

*extension.* The bar above a code block and its strokes, mixed from the syntax pair so they stay dark with the slab.

| Token | Purple value |
|---|---|
| `--code-header-bg` | `color-mix(in srgb, var(--syn-fg) 7%, var(--syn-bg))` |
| `--code-stroke` | `color-mix(in srgb, var(--syn-fg) 16%, var(--syn-bg))` |

## Categorical data

*extension.* Twelve series colours for charts and tags, at 3:1 on the page; chart grid and axis; and two ramps mixed from the theme: `--seq-1` ... `--seq-5` (low to high, for heatmaps) and `--div-1` ... `--div-5` (bad, neutral, good).

| Token | Purple value |
|---|---|
| `--cat-1` | `#a78bfa` |
| `--cat-2` | `#5eead4` |
| `--cat-3` | `#fcd34d` |
| `--cat-4` | `#f472b6` |
| `--cat-5` | `#60a5fa` |
| `--cat-6` | `#fb923c` |
| `--cat-7` | `#4ade80` |
| `--cat-8` | `#c4b5fd` |
| `--cat-9` | `#67e8f9` |
| `--cat-10` | `#facc15` |
| `--cat-11` | `#f0abfc` |
| `--cat-12` | `#93c5fd` |
| `--seq-1` | `color-mix(in srgb, var(--selected) 20%, var(--surface-2))` |
| `--seq-2` | `color-mix(in srgb, var(--selected) 40%, var(--surface-2))` |
| `--seq-3` | `color-mix(in srgb, var(--selected) 60%, var(--surface-2))` |
| `--seq-4` | `color-mix(in srgb, var(--selected) 80%, var(--surface-2))` |
| `--seq-5` | `var(--selected)` |
| `--div-1` | `var(--danger-text)` |
| `--div-2` | `color-mix(in srgb, var(--danger-text) 50%, var(--surface-3))` |
| `--div-3` | `var(--surface-3)` |
| `--div-4` | `color-mix(in srgb, var(--success-text) 50%, var(--surface-3))` |
| `--div-5` | `var(--success-text)` |
| `--chart-grid` | `rgba(255,255,255,.07)` |
| `--chart-axis` | `#66668a` |

## Canvas

*extension.* Overlays drawn on images in editors: mask, handles, guides, outlines.

| Token | Purple value |
|---|---|
| `--canvas-mask` | `rgba(6,6,14,.72)` |
| `--canvas-handle` | `#a78bfa` |
| `--canvas-guide` | `rgba(167,139,250,.55)` |
| `--canvas-outline` | `#e8e8f0` |

## Type families

*core.* Font stacks. They name Inter, JetBrains Mono and a few display faces, and fall back to system fonts.

| Token | Purple value |
|---|---|
| `--font-sans` | `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` |
| `--font-serif` | `var(--font-sans)` |
| `--font-mono` | `'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace` |
| `--font-display` | `var(--font-sans)` |

## Elevation

*core.* Shadows from 1 (subtle) to 4 (dialogs), a glow and an inset highlight.

| Token | Purple value |
|---|---|
| `--shadow-1` | `0 1px 2px rgba(0,0,0,.30)` |
| `--shadow-2` | `0 6px 20px rgba(0,0,0,.40)` |
| `--shadow-3` | `0 18px 50px rgba(0,0,0,.55)` |
| `--shadow-4` | `0 32px 80px rgba(0,0,0,.66)` |
| `--shadow-glow` | `0 0 0 1px rgba(124,58,237,.30), 0 8px 30px rgba(124,58,237,.28)` |
| `--shadow-inset` | `inset 0 1px 0 rgba(255,255,255,.05)` |

## Browser

*core.* Text selection and scrollbars.

| Token | Purple value |
|---|---|
| `--selection-bg` | `rgba(124,58,237,.40)` |
| `--selection-text` | `#ffffff` |
| `--scrollbar-track` | `transparent` |
| `--scrollbar-thumb` | `#33335a` |
| `--scrollbar-hover` | `#45457a` |

## Control boundary fill

*core.* `--control-track`: the empty part of a slider (3:1 on the surfaces).

| Token | Purple value |
|---|---|
| `--control-track` | `#696981` |

## Geometry

*core, invariant.* Radii, the 4px spacing scale, strokes, control heights, touch target and shell metrics. Themes may change radii.

| Token | Purple value |
|---|---|
| `--radius-xs` | `4px` |
| `--radius-sm` | `6px` |
| `--radius-md` | `12px` |
| `--radius-lg` | `16px` |
| `--radius-xl` | `20px` |
| `--radius-pill` | `999px` |
| `--space-1` | `4px` |
| `--space-2` | `8px` |
| `--space-3` | `12px` |
| `--space-4` | `16px` |
| `--space-5` | `24px` |
| `--space-6` | `32px` |
| `--space-7` | `48px` |
| `--space-8` | `64px` |
| `--stroke-hairline` | `1px` |
| `--stroke-default` | `1px` |
| `--control-h-sm` | `28px` |
| `--control-h-md` | `36px` |
| `--control-h-lg` | `44px` |
| `--touch-target` | `44px` |
| `--sidebar-w` | `320px` |
| `--header-h` | `56px` |
| `--rail-w` | `72px` |
| `--bar-h` | `60px` |
| `--content-max` | `1200px` |

## Component tokens

*core, invariant.* Slider, toggle and chip sizes and colours.

| Token | Purple value |
|---|---|
| `--slider-track-h` | `4px` |
| `--slider-thumb-d` | `16px` |
| `--slider-color` | `var(--accent)` |
| `--toggle-w` | `40px` |
| `--toggle-h` | `22px` |
| `--chip-color` | `var(--accent)` |

## Type scale

*core, invariant.* Font sizes, weights, line heights and letter spacing.

| Token | Purple value |
|---|---|
| `--fs-micro` | `11px` |
| `--fs-xs` | `12px` |
| `--fs-sm` | `13px` |
| `--fs-base` | `15px` |
| `--fs-md` | `17px` |
| `--fs-lg` | `20px` |
| `--fs-xl` | `24px` |
| `--fs-2xl` | `30px` |
| `--fs-3xl` | `38px` |
| `--fs-display` | `52px` |
| `--fw-regular` | `400` |
| `--fw-medium` | `500` |
| `--fw-semibold` | `600` |
| `--fw-bold` | `700` |
| `--lh-tight` | `1.15` |
| `--lh-snug` | `1.3` |
| `--lh-base` | `1.55` |
| `--lh-relaxed` | `1.75` |
| `--ls-tight` | `-0.02em` |
| `--ls-snug` | `-0.01em` |
| `--ls-base` | `0` |
| `--ls-label` | `0.18em` |
| `--ls-mono` | `0.01em` |

## Motion

*core, invariant.* Easings and durations. The base layer shortens every animation under reduced motion.

| Token | Purple value |
|---|---|
| `--ease-standard` | `cubic-bezier(.4,0,.2,1)` |
| `--ease-out` | `cubic-bezier(.22,1,.36,1)` |
| `--ease-in` | `cubic-bezier(.4,0,1,1)` |
| `--ease-spring` | `cubic-bezier(.34,1.56,.64,1)` |
| `--dur-instant` | `80ms` |
| `--dur-fast` | `120ms` |
| `--dur-base` | `200ms` |
| `--dur-slow` | `320ms` |
| `--dur-deliberate` | `520ms` |

## Layers

*core, fixed.* z-index layers. Fixed: themes and apps never change them.

| Token | Purple value |
|---|---|
| `--z-base` | `1` |
| `--z-sticky` | `40` |
| `--z-banner` | `50` |
| `--z-header` | `100` |
| `--z-nav` | `200` |
| `--z-tooltip` | `200` |
| `--z-drawer` | `500` |
| `--z-modal` | `1000` |
| `--z-lightbox` | `2000` |
| `--z-popover` | `9000` |
| `--z-toast` | `9999` |
| `--z-menu` | `100002` |
