# Components

`ui-theme/ui-components.css` styles the controls most apps need, using tokens only, so every
class follows the active theme. Load it after `ui-theme-base.css` and before the app's CSS.
The [specimen](../specimen/index.html) shows every one of them in every theme.

Conventions:

- Names: `.ui-<block>`, `.ui-<block>--<variant>`, `.ui-<block>__<part>`.
- State comes from native attributes, never from extra classes: `disabled`, `checked`,
  `aria-pressed`, `aria-selected`, `aria-current`, `aria-invalid`, `aria-busy`, `[open]`.
- Most selectors are one class, so an app rule of the same specificity (loaded later) wins.
- Logical properties throughout: everything works right-to-left.
- **States in every theme:** on, checked, pressed and current are filled or marked with
  `--selected`; off is an outline; disabled is dashed, unfilled and in the disabled tier, even
  when on.

## Layout

```html
<div class="ui-stack">…</div>                 <!-- column, gap --space-3 -->
<div class="ui-row">…</div>                   <!-- wrapping row, centred, gap --space-2 -->
<div class="ui-grid" style="--ui-grid-min: 200px">…</div>   <!-- auto-fill columns -->
<div class="ui-container">…</div>             <!-- centred, max width --content-max -->
<span class="ui-spacer"></span>               <!-- pushes the rest of a row to the end -->
```

Set `--ui-gap` on any of them to change the gap.

## App shell and navigation

```html
<div class="ui-app">
  <header class="ui-app__header">
    <a class="ui-brand" href="/">Notes</a>
    <span class="ui-spacer"></span>
    <select class="ui-select" data-ui-theme-picker aria-label="Theme" style="width: auto"></select>
  </header>
  <nav class="ui-app__nav ui-nav" aria-label="Main">
    <span class="ui-nav__label">Library</span>
    <a class="ui-nav__item" href="/" aria-current="page">Inbox</a>
    <a class="ui-nav__item" href="/archive">Archive</a>
  </nav>
  <main class="ui-app__main">…</main>
</div>
```

Leave out the nav for a single column. Below 760px the nav hides; set `data-nav-open` on
`.ui-app` (from a menu button) to show it above the content. `--ui-nav-w` sets its width.

## Type

`.ui-title` (page title), `.ui-heading` (section), `.ui-subheading`, `.ui-lead` (intro
paragraph), `.ui-kicker` (uppercase overline), `.ui-small`, `.ui-mono`, `.ui-num` (tabular
figures), `.ui-kbd` (a key), `.ui-code` (inline code), `.ui-divider` (`<hr>`). Text tiers:
`.ui-text-primary`, `-secondary`, `-tertiary`, `-disabled`, `-link`. Markdown: `.ui-markdown`
([TEXT.md](TEXT.md)).

## Buttons

```html
<button class="ui-btn ui-btn--primary">Save</button>
<button class="ui-btn">Cancel</button>                    <!-- secondary is the default -->
<button class="ui-btn ui-btn--ghost">More</button>
<button class="ui-btn ui-btn--outline">Export</button>
<button class="ui-btn ui-btn--danger">Delete</button>
<button class="ui-btn ui-btn--cta ui-btn--lg">Get started</button>
<button class="ui-btn ui-btn--icon" aria-label="Settings" data-ui-tooltip="Settings">⚙</button>
<button class="ui-btn" aria-pressed="true">Bold</button> <!-- a toggle button that is on -->
<button class="ui-btn ui-btn--primary" aria-busy="true">Saving</button>
<button class="ui-btn ui-btn--primary" disabled>Save</button>
<div class="ui-btn-group"><button class="ui-btn">Day</button><button class="ui-btn">Week</button></div>
```

Sizes `--sm`, `--lg`; `--block` for full width. Works on `<a>` too.

## Form fields

```html
<label class="ui-field">
  <span class="ui-label">Email</span>
  <input class="ui-input" type="email" name="email" aria-describedby="email-help">
  <span class="ui-help" id="email-help">We never share it.</span>
</label>

<label class="ui-field">
  <span class="ui-label">Passes</span>
  <input class="ui-input" value="0" aria-invalid="true" aria-describedby="passes-err">
  <span class="ui-error" id="passes-err">Must be at least 1.</span>
</label>

<select class="ui-select">…</select>
<textarea class="ui-textarea"></textarea>
<div class="ui-input-group"><input class="ui-input"><button class="ui-btn">Go</button></div>
```

`.ui-input--sm` for a compact field. Disabled fields are dashed.

## Checkbox, radio, switch

```html
<label class="ui-check"><input type="checkbox" class="ui-checkbox"> Remember me</label>
<label class="ui-check"><input type="radio" name="size" class="ui-radio" checked> Small</label>
<label class="ui-check">
  <input type="checkbox" role="switch" class="ui-switch" checked> Notifications
  <span class="ui-switch-state" aria-hidden="true"></span>
</label>
```

The tick and dot are drawn from tokens, never the browser's white. A switch shows its state
four ways: fill (hollow when off, `--selected` when on), knob size and colour, knob position,
and a mark (a ring when off, a bar when on). `.ui-switch-state` prints "On" or "Off"; set
`data-on` / `data-off` on it for other words (it is `aria-hidden`: the switch announces its
own state). An indeterminate checkbox (`el.indeterminate = true`) shows a dash. Under
Windows high contrast the native controls come back.

`.ui-range` is a native range input coloured with `--slider-color`.

## Segmented control and tabs

```html
<div class="ui-segmented" role="group" aria-label="Range">
  <button aria-pressed="true">Day</button>
  <button aria-pressed="false">Week</button>
</div>

<div class="ui-tabs" role="tablist">
  <button class="ui-tab" role="tab" aria-selected="true">Overview</button>
  <button class="ui-tab" role="tab" aria-selected="false">Jobs <span class="ui-count">3</span></button>
</div>
```

Link tabs use `<a class="ui-tab" aria-current="page">`. Keyboard handling (arrow keys between
tabs) is the app's job.

## Cards, wells and stats

```html
<section class="ui-card">
  <header class="ui-card__header"><h2 class="ui-card__title">Storage</h2></header>
  <div class="ui-well">Logs, previews, secondary content</div>
  <div class="ui-stat"><span class="ui-stat__label">Used</span><span class="ui-stat__value">42 GB</span></div>
  <footer class="ui-card__footer"><button class="ui-btn">Manage</button></footer>
</section>
```

`--raised` adds a shadow, `--interactive` a hover; `aria-selected="true"` or `aria-current`
outlines a selected card in `--selected`.

## Badges, counts, dots

```html
<span class="ui-badge">neutral</span>
<span class="ui-badge ui-badge--success"><span class="ui-dot ui-dot--success"></span>done</span>
<span class="ui-badge ui-badge--live"><span class="ui-dot ui-dot--live"></span>live</span>
<span class="ui-count">3</span>
```

Badge variants: `--accent`, `--success`, `--warning`, `--danger`, `--info`, `--live`, `--idle`,
`--offline`. Counts are neutral; `.ui-count--accent` for new items, `.ui-count--danger` for
something that needs attention. Dots: `--success`, `--warning`, `--danger`, `--info`, `--idle`,
`--live` (pulses); plain is offline grey. Dots use the status text colours, which stay visible
on every surface.

## Callouts

```html
<div class="ui-callout ui-callout--warning" role="status">
  <strong class="ui-callout__title">Heads up</strong> The disk is 90% full.
</div>
```

Variants `--info`, `--success`, `--warning`, `--danger` (use `role="alert"` for errors).

## Tables and lists

```html
<div class="ui-table-wrap">
  <table class="ui-table ui-table--hover">
    <thead><tr><th>Job</th><th class="num">Minutes</th></tr></thead>
    <tbody><tr aria-selected="true"><td>render</td><td class="num">12.4</td></tr></tbody>
  </table>
</div>
<ul class="ui-list"><li>…</li></ul>
```

`--compact` tightens rows. `aria-selected="true"` marks a selected row.

## Dialog

```html
<dialog class="ui-dialog" id="confirm-delete" aria-labelledby="cd-title">
  <form method="dialog">
    <h2 class="ui-dialog__title" id="cd-title">Delete job?</h2>
    <div class="ui-dialog__body">This cannot be undone.</div>
    <div class="ui-dialog__actions">
      <button class="ui-btn" value="cancel">Cancel</button>
      <button class="ui-btn ui-btn--danger" value="ok">Delete</button>
    </div>
  </form>
</dialog>
<script>
  const d = document.getElementById('confirm-delete');
  d.showModal();
  d.addEventListener('close', () => { if (d.returnValue === 'ok') { /* delete */ } });
</script>
```

`.ui-dialog--wide` for forms. (Browsers before Chrome 122, Safari 17.4 and Firefox 120 do not
pass tokens to `::backdrop`, so the scrim behind the dialog is transparent there.) Or use
`ui-components.js` and skip the markup:

```js
await UIComponents.confirm({ title: 'Delete job?', message: 'This cannot be undone.',
                             confirmLabel: 'Delete', danger: true });   // true or false
await UIComponents.alert('Saved.');
await UIComponents.prompt({ title: 'Rename', value: 'draft', placeholder: 'Name' });  // string or null
UIComponents.toast('Settings saved', { kind: 'success', timeout: 4000 });  // 0 keeps it
```

All text is set as text, never HTML, so user input is safe to show.

## Menu, tooltip, toast

```html
<button class="ui-btn" popovertarget="row-menu">Actions</button>
<div class="ui-menu" id="row-menu" popover>
  <button class="ui-menu__item">Rename</button>
  <button class="ui-menu__item" role="menuitemcheckbox" aria-checked="true">Pinned</button>
  <hr class="ui-menu__separator">
  <button class="ui-menu__item ui-menu__item--danger">Delete</button>
</div>

<button class="ui-btn ui-btn--icon" aria-label="Copy link" data-ui-tooltip="Copy link">⧉</button>
<button class="ui-btn ui-btn--icon" aria-label="Help" data-ui-tooltip="Help" data-ui-tooltip-side="bottom">?</button>

<div class="ui-toasts" role="status" aria-live="polite">
  <div class="ui-toast ui-toast--success">Saved</div>
</div>
```

The menu uses the browser's popover API for opening, closing and focus; position it with CSS
anchor positioning or a few lines of script. Tooltips show on hover and keyboard focus; the
accessible name comes from `aria-label`.

## Progress, spinner, skeleton

```html
<progress class="ui-progress" value="42" max="100" aria-label="Upload"></progress>
<span class="ui-spinner" role="status" aria-label="Loading"></span>
<span class="ui-skeleton" style="width: 60%"></span>
```

Animations stop under reduced motion.

## Code block

```html
<figure class="ui-codeblock">
  <figcaption class="ui-codeblock__bar">
    <span>python</span><button class="ui-codeblock__button" type="button">Copy</button>
  </figcaption>
  <pre><code class="hljs">…</code></pre>
</figure>
```

The slab is dark in every theme, light themes too. The base layer maps highlight.js classes to
the syntax tokens; load highlight.js without its own theme stylesheet.

## Chat, empty state, media

```html
<div class="ui-stack">
  <div class="ui-bubble ui-bubble--user">Hi</div>
  <div class="ui-bubble ui-markdown"><p>Hello! <strong>How can I help?</strong></p></div>
  <span class="ui-typing" aria-label="Typing"><span></span><span></span><span></span></span>
</div>

<div class="ui-empty"><h3 class="ui-empty__title">No jobs yet</h3><p>Start one to see it here.</p></div>

<img class="ui-media" src="photo.jpg" alt="…">   <!-- follows the theme's media filter -->
```

## Breadcrumbs and pagination

```html
<nav aria-label="Breadcrumb"><ol class="ui-breadcrumbs">
  <li><a href="/">Home</a></li><li><a href="/jobs">Jobs</a></li>
  <li><span aria-current="page">render-12</span></li>
</ol></nav>

<nav class="ui-pagination" aria-label="Pages">
  <a class="ui-btn ui-btn--sm" href="?p=1">Previous</a>
  <a class="ui-btn ui-btn--sm" href="?p=1">1</a>
  <a class="ui-btn ui-btn--sm" href="?p=2" aria-current="page">2</a>
  <a class="ui-btn ui-btn--sm" href="?p=3">Next</a>
</nav>
```

The current page is filled with `--selected`.

## Avatar and chips

```html
<span class="ui-avatar" aria-hidden="true">JL</span>          <!-- --sm, --lg; or an <img class="ui-avatar"> -->
<span class="ui-chip">python <button class="ui-chip__remove" aria-label="Remove python">×</button></span>
<button class="ui-chip" aria-pressed="true">Pinned</button>  <!-- a selectable chip -->
```

## Disclosure (accordion) and drawer

```html
<details class="ui-details" name="settings" open>
  <summary>General</summary>
  <div class="ui-details__body">…</div>
</details>
<details class="ui-details" name="settings"><summary>Advanced</summary><div class="ui-details__body">…</div></details>

<dialog class="ui-drawer" id="filters" aria-labelledby="filters-title">  <!-- --start: at the inline start -->
  <form method="dialog"><h2 id="filters-title">Filters</h2>… <button class="ui-btn">Done</button></form>
</dialog>
<script>document.getElementById('filters').showModal();</script>
```

Details elements with the same `name` open one at a time.

## Fieldset, file input, long tables

```html
<fieldset class="ui-fieldset"><legend>Upload</legend>
  <input class="ui-input" type="file">
</fieldset>

<div class="ui-table-wrap ui-table-wrap--scroll" style="--ui-table-max-h: 320px">
  <table class="ui-table ui-table--sticky">…</table>     <!-- the header row stays put -->
</div>
```

## Printing and high contrast

The runtime prints a dark theme in a light one (`data-print-theme` on the script tag changes
it), and the component layer hides the side nav, toasts, menus, drawers and tooltips in print
and keeps cards, tables and callouts in one piece. Under `prefers-contrast: more` lines take the
control-edge strength and tertiary text the secondary tier, in every theme.

## Unprefixed helpers in the base layer

`ui-theme-base.css` also keeps a few unprefixed helpers that older apps rely on: `.num` and
`.tnum` (tabular figures), `.stat-value`, `.slider-value`, `.kicker`, `.divider`,
`.divider--dashed`, and the reduced-motion hooks `.ambient` and `.skeleton`. New code uses the
`ui-` names (`.ui-num`, `.ui-kicker`, `.ui-divider`, `.ui-skeleton`). If the app already has a
class with one of these names, its own rule wins when it is at least as specific and loads
later.

