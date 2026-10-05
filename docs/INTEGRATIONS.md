# Integrations

The theme is one folder of static files. Every integration is the same three steps: put
`ui-theme/` where the app serves static files, add the tags to the page head in the right
order, and serve the folder so a new copy is picked up. The head block, with the order rules,
is in [`AGENTS.md`](../AGENTS.md) section 3; here it is per stack.

The order, always:

1. `ui-theme.js`: classic, blocking, first in `<head>`, with its `data-*` settings
   (and, for NiceGUI, `adapters/quasar.js` right after it);
2. `ui-theme-base.css`, then `ui-components.css`;
3. the app's own stylesheets;
4. `ui-theme.css` (and, for NiceGUI, `adapters/quasar.css` right after it);
5. optional: `ui-components.js` with `defer`.

## Plain HTML

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="ui-theme/ui-theme.js" data-themes="purple,midnight-gold,glacier,forest,paper,daylight"
          data-default="auto" data-storage-key="mysite.theme"></script>
  <link rel="stylesheet" href="ui-theme/ui-theme-base.css">
  <link rel="stylesheet" href="ui-theme/ui-components.css">
  <link rel="stylesheet" href="site.css">
  <link rel="stylesheet" href="ui-theme/ui-theme.css">
</head>
```

See [`examples/static-html/`](../examples/static-html/). Opening the file straight from disk
works; a local server (`python3 -m http.server`) is closer to production.

## FastAPI, Flask, Starlette (Jinja templates)

Put the folder in the app's `static/` directory and the block in the base template. Serve it
with revalidation so an update shows up on the next load:

```python
# FastAPI / Starlette
from fastapi.staticfiles import StaticFiles

class NoCacheStatic(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response

app.mount("/static", NoCacheStatic(directory="static"), name="static")
```

```python
# Flask
app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0   # revalidate static files
```

FastAPI / Starlette templates take `path=`:

```jinja
<script src="{{ url_for('static', path='ui-theme/ui-theme.js') }}"
        data-themes="purple,midnight-gold,glacier,forest,paper,daylight"
        data-default="auto" data-storage-key="myapp.theme"></script>
<link rel="stylesheet" href="{{ url_for('static', path='ui-theme/ui-theme-base.css') }}">
```

Flask templates take `filename=`:

```jinja
<script src="{{ url_for('static', filename='ui-theme/ui-theme.js') }}"
        data-themes="purple,midnight-gold,glacier,forest,paper,daylight"
        data-default="auto" data-storage-key="myapp.theme"></script>
<link rel="stylesheet" href="{{ url_for('static', filename='ui-theme/ui-theme-base.css') }}">
```

(and the same for the other files, in the order above). A complete FastAPI app is in
[`examples/fastapi-jinja/`](../examples/fastapi-jinja/).

## Django

`static/ui-theme/` in an app or `STATICFILES_DIRS`, then in `base.html`:

```django
{% load static %}
<script src="{% static 'ui-theme/ui-theme.js' %}" data-themes="purple,midnight-gold,glacier,forest,paper,daylight"
        data-default="auto" data-storage-key="myapp.theme"></script>
<link rel="stylesheet" href="{% static 'ui-theme/ui-theme-base.css' %}">
<link rel="stylesheet" href="{% static 'ui-theme/ui-components.css' %}">
<link rel="stylesheet" href="{% static 'css/app.css' %}">
<link rel="stylesheet" href="{% static 'ui-theme/ui-theme.css' %}">
```

With `ManifestStaticFilesStorage` the URLs carry content hashes, so caching takes care of
itself. `collectstatic` also copies `update.py`; it is inert text there.

## Vite, Vue, Svelte, SvelteKit, Astro

Put the folder in `public/` (served from `/`), and the block in the HTML shell: `index.html`
(Vite, Vue), `src/app.html` (SvelteKit), or the base layout's `<head>` (Astro), with the
`/ui-theme/...` prefix. Do not import the CSS from a component or `main.js`: the bundler would
reorder it, and the runtime must run before the app mounts.

React components read the theme with the API:

```js
import { useEffect, useState } from 'react';

export function useTheme() {
  const [slug, setSlug] = useState(() => window.UITheme.current());
  useEffect(() => window.UITheme.onChange((d) => setSlug(d.slug)), []);
  return [slug, (s) => window.UITheme.set(s)];
}

// The runtime finds a picker rendered later and fills it; keep it
// uncontrolled (React must not own its value or options).
export function ThemePicker() {
  return <select data-ui-theme-picker className="ui-select" aria-label="Theme" />;
}
```

The same `<select data-ui-theme-picker>` works in Vue and Svelte templates. To call
`UITheme.mountPicker(el)` yourself instead (a select without the attribute), do it after the
element is in the DOM: `useEffect`, `onMounted`, `onMount`.

**TypeScript:** add `public/ui-theme/ui-theme.d.ts` to `tsconfig.json`'s `include` (or
`/// <reference path="../public/ui-theme/ui-theme.d.ts" />` in one file). It declares
`window.UITheme`, `window.UIComponents` and the `ui-theme-change` event.

## Next.js (app router)

`public/ui-theme/`, then in `app/layout.tsx`:

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* eslint-disable-next-line @next/next/no-sync-scripts -- must run before first paint */}
        <script src="/ui-theme/ui-theme.js"
                data-themes="purple,midnight-gold,glacier,forest,paper,daylight"
                data-default="auto" data-storage-key="myapp.theme" />
        <link rel="stylesheet" href="/ui-theme/ui-theme-base.css" />
        <link rel="stylesheet" href="/ui-theme/ui-components.css" />
        <link rel="stylesheet" href="/ui-theme/ui-theme.css" />
      </head>
      <body>{children}</body>
    </html>
  );
}
```

The plain `<script>` is server-rendered into the page's HTML, so the browser runs it while
parsing `<head>`, before first paint. `next/script` with any strategy loads later and flashes.
`suppressHydrationWarning` is needed because the runtime sets `data-palette` and `data-theme`
on `<html>` before React hydrates. Global CSS imported in the layout is bundled by Next and
its position relative to these links is not guaranteed; keep it free of token declarations
(which the rules forbid anyway) and nothing depends on the order. Check `UITheme.config` in
the console to confirm the settings arrived.

## NiceGUI (Quasar)

Installed into `static/ui-theme` next to `main.py`:

```python
from nicegui import app, ui

app.add_static_files('/static', 'static')
ui.add_head_html('''
<script src="/static/ui-theme/ui-theme.js" data-themes="purple,midnight-gold,glacier,forest,paper,daylight"
        data-default="auto" data-storage-key="myapp.theme"></script>
<script src="/static/ui-theme/adapters/quasar.js"></script>
<link rel="stylesheet" href="/static/ui-theme/ui-theme-base.css">
<link rel="stylesheet" href="/static/ui-theme/ui-theme.css">
<link rel="stylesheet" href="/static/ui-theme/adapters/quasar.css">
''', shared=True)
```

The adapter maps the tokens onto Quasar's components (cards, fields, tabs, toggles, checkboxes,
radios, tables, notifications, the `--q-*` brand colours) and keeps Quasar's dark mode in step
with the theme's ground, so remove any `ui.dark_mode()` from the app. Leave out
`ui-components.css` unless you use its classes in raw HTML. Prefer the `.ui-text-*` classes to
opacity utilities for quieter labels.

## Tailwind CSS

v4, in the entry CSS:

```css
@import "tailwindcss";
@import "./static/ui-theme/adapters/tailwind.css";
```

Then `bg-surface-2`, `text-fg`, `text-fg-muted`, `text-fg-subtle`, `text-link`,
`bg-accent text-on-accent`, `bg-selected text-on-selected`, `border-line`,
`border-line-strong`, `bg-danger-subtle text-danger-text`, `bg-cat-3`, and so on. Load the
ui-theme files in the page as usual; they carry the values. Text colours are `fg-*` because
`text-*` is Tailwind's font-size namespace. Tailwind's `rounded-*`, `font-sans`, `font-mono`,
`ease-in` and `ease-out` take the theme's values, because the theme defines those variables
outside any cascade layer.

v3, in `tailwind.config.js`:

```js
module.exports = {
  presets: [require('./static/ui-theme/adapters/tailwind-v3.preset.js')],
  content: ['./templates/**/*.html', './src/**/*.{js,jsx,ts,tsx,vue,svelte}'],
};
```

In an ES module config, load it with `createRequire(import.meta.url)`.

## Electron, Tauri, pywebview

Same as plain HTML: the folder sits next to the app's `index.html` and loads with relative
paths. localStorage persists per app. If the window chrome should follow the theme, read
`UITheme.theme().themeColor` and `UITheme.theme().colorScheme` in `UITheme.onChange` and pass
them to the shell.

## Fonts

The stacks name web fonts first and fall back to system fonts, so nothing has to be loaded.
To load them, add the families your themes use (`fonts` in `themes.json`) before the theme
block, from Google Fonts:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
```

(the opt-in themes also name Space Grotesk and Archivo), or self-host: put one CSS file per
family in a folder, named after the family in lower case with hyphens (`inter.css`,
`jetbrains-mono.css`), and set `data-fonts-href="/static/fonts/"` on the script tag. The
runtime then loads only the families the active theme names.

## Charts

Series take `--cat-1` ... `--cat-12`; heatmaps and scales take the ramps `--seq-1` ...
`--seq-5` (low to high) and `--div-1` ... `--div-5` (bad, neutral, good). Canvas and chart
libraries cannot read `var()`, and some tokens are `color-mix()` values, so resolve them with
`UITheme.colors()` (plain `rgb()` strings) and redraw when the theme changes (the static
example draws one this way):

```js
const colours = () => UITheme.colors(['--cat-1', '--cat-2', '--cat-3', '--chart-grid', '--chart-axis', '--text-secondary']);
const chart = new Chart(ctx, { /* ... use colours() ... */ });
UITheme.onChange(() => { /* copy colours() into the chart's options */ chart.update(); });
```

## Content Security Policy

The theme needs no inline scripts or styles: `ui-theme.js` and `ui-components.js` are files
and set styles through the DOM. `script-src 'self'` and `style-src 'self'` are enough when
the folder is served from the app's origin.
