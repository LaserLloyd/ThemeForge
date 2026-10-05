# Text standard

One set of text rules for every app that uses the theme: which tier each kind of text takes,
how to make text quieter, and how rendered markdown looks. `src/css/text.css` implements it,
and it ships at the end of `ui-theme/ui-theme-base.css`, so every app that loads the base
layer has it.

The rules are theme-agnostic: every colour is a token, so the same markup is right in Purple,
in Paper and in Night Red.

## Text roles

| Role | Token | Class | Use it for | Smallest size |
|---|---|---|---|---|
| Primary | `--text-primary` | `.ui-text-primary` | body text, chat replies, values, input text, headings | 13px |
| Secondary | `--text-secondary` | `.ui-text-secondary` | labels, descriptions, table cells, captions | 12px |
| Tertiary | `--text-tertiary` | `.ui-text-tertiary` | hints, placeholders, timestamps, metadata, uppercase overlines | 11px |
| Disabled | `--text-disabled` | `.ui-text-disabled` | disabled controls only; never content | 11px |
| Link | `--text-link`, `--text-link-hover` | `.ui-text-link` | links and link-like actions | 12px |
| Status | `--<status>-text` | none | text that states a status (error, warning, live) | 11px |

`tools/check_contrast.py` measures every text token against every surface, and each theme
must pass the floors of its contrast profile ([TOKENS.md](TOKENS.md)). Under the standard
profile tertiary text keeps 4.5:1 everywhere; Night Red's night profile keeps it at 4:1.

In a dim theme the tiers sit close together (Night Red's steps are about 1.17:1, Midnight
Gold's 1.5 to 1.9:1), because widening them would push the lower tiers below legibility. Size,
weight and position carry the rest of the hierarchy: a label is smaller or bolder than the
value beside it, and metadata is smaller still.

## Rules

1. **A tier, never opacity.** Make text quieter by choosing a lower tier. Never lower its
   opacity, and never mix a text colour toward the background with `rgba()` or `color-mix()`.
   Opacity multiplies the theme's own colour: in the dark core themes that still leaves about
   6:1, which is why it looks harmless, but 60% of Night Red's body text `#ff5800` is 2.9:1.
   Opacity is fine for icons, images and whole disabled controls. The Quasar adapter turns a
   NiceGUI label dimmed with an opacity utility (`text-xs opacity-70`) into a tier.
2. **Content lives in primary or secondary.** Tertiary is for text a reader can skip: hints,
   timestamps, counts. Disabled text is never content.
3. **Respect the smallest sizes above.** Tertiary text below 11px is unreadable in the dim
   themes. Uppercase overlines use `--ls-label` and stay at 11px or more.
4. **Status text uses `--<status>-text`,** on a surface or on its own `--<status>-subtle`
   fill. The fill token (`--danger`, `--success`) is for dots, bars and solid plates, with
   `--on-<status>` for a label on the plate.
5. **Accent fills are never text.** Accent-coloured text uses `--text-link`. A label on an
   accent fill uses `--on-accent`.
6. **Paper:** keep secondary and status text off `--surface-3` and `--surface-4` where you
   can; they are the two darkest parchment steps (see the contrast report).

## Markdown

Put `.ui-markdown` on the element that holds rendered markdown. Every rule in it is exactly
one class plus one element (specificity 0-1-1; pseudo-classes sit inside `:where()`), and the
base layer loads before the app's CSS, so an app rule of the same shape (say,
`.chat-message strong`) still wins. That is how an app layers its own rules on top. The one
deliberate exception is the heading scale: `.ui-markdown h1` to `h3` use a chat-sized scale
(1.35, 1.2 and 1.08em: 20, 18 and 16px in a 15px bubble) that beats an app's bare page-heading
rule such as `h1 { font-size: 1.75rem }`, which would otherwise make a heading in a reply 28px.

| Element | Standard |
|---|---|
| container | line-height 1.7; its colour comes from the bubble or panel it sits in (normally `--text-primary`) |
| `h1` to `h4` | `--text-primary`, semibold, 1.35, 1.2, 1.08 and 1em |
| `strong` | `--md-bold`, bold |
| `em` | `--md-italic` |
| `strong em` | `--md-bolditalic` with `--md-bolditalic-glow` |
| `a` | `--text-link`, underline at 45%; hover `--text-link-hover` |
| inline `code` | mono at .86em, `--text-link` on `--surface-2`, `--glass-stroke` edge |
| `pre` | mono at `--fs-xs`, `--syn-fg` on `--syn-bg` (dark in every theme), `--glass-stroke` edge |
| `blockquote` | `--text-secondary` on `--surface-sunken`, 3px `--quote-bar` on the inline start |
| `table` | `--border` cells; header `--text-primary` on `--surface-3`; cells `--text-secondary` |
| `mark` | `--mark-bg` behind `--text-primary` |
| `del` | `--text-tertiary` with a strike line, never opacity |
| list markers | `--text-tertiary` |
| `hr` | `--divider` |

Narrative text roles for chat, fiction and transcript views (`--rp-speech`, `--rp-action`,
`--rp-thought`, `--rp-whisper`, `--rp-ooc`, `--rp-shout`, `--rp-critical`) are tokens an app
applies with its own classes on top of `.ui-markdown`, for example `em` as an action in a
story reply.

## Why the dim themes need this

Pure red text tops out at 5.25:1 on black and carries almost no luma, so Night Red cannot
afford any loss between the token and the screen. Two common habits lose it: putting labels
and small print in the dimmest tier, and dimming secondary text with opacity. The theme lifts
every tier ([THEMES.md](THEMES.md)), and this standard removes the opacity dimming.
