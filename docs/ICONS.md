# Icons

Generated from `src/icons/icons.json` by `tools/sync_theme.py build` (ThemeForge 1.3.0).

48 outline icons for app chrome, one sprite (`ui-theme/icons.svg`). They draw in
`currentColor` with the theme's `--icon-stroke`, so every theme colours them and the
high-contrast pair draws them heavier. They are not decoration: use them where an app
would otherwise put an emoji in a button, tab, menu or status line.

![The icon set](images/icons.svg)

## Use

Markup (any page; the path is wherever the app serves `ui-theme/`):

```html
<svg class="ui-icon" aria-hidden="true"><use href="/static/ui-theme/icons.svg#settings"/></svg>
<button class="ui-btn"><svg class="ui-icon" aria-hidden="true"><use href="/static/ui-theme/icons.svg#trash"/></svg>Delete</button>
<button class="ui-btn ui-btn--icon" aria-label="Close"><svg class="ui-icon" aria-hidden="true"><use href="/static/ui-theme/icons.svg#x"/></svg></button>
```

Script (with `ui-components.js` loaded, which finds `icons.svg` next to itself, and inlines it
when it is on another origin such as the CDN, where `<use>` cannot reach):

```js
button.append(UIComponents.icon('trash'));                 // decorative
UIComponents.icon('bell', { label: 'Notifications', size: 'sm' });  // an image with a name
UIComponents.iconFor('🗑️');                               // 'trash'; null when no icon means it
UIComponents.icons();                                      // every name
```

Size: `1.25em` (it follows the text), or `.ui-icon--sm` (16px), `--md` (20px), `--lg` (24px), or
`--ui-icon-size` on the element. Colour: the text colour, or `.ui-icon--muted`, `--accent`,
`--success`, `--warning`, `--danger`, `--info`. Weight: `--icon-stroke` (2; 2.5 in the
high-contrast themes and when the system asks for more contrast).

## Emoji, three ways

| Style | Class | For |
|---|---|---|
| icon | `.ui-icon` | An emoji in app chrome (⚙ 🗑 📁 ✕). It becomes the outline icon the table below names. |
| text | `.ui-emoji` | An emoji someone typed (chat, notes), drawn in the text colour. |
| colour | `.ui-emoji--color` | An emoji whose colours are the point (reactions), toned by the theme's `--media-filter` (Night Red keeps it red). |

`UIComponents.emojify(element, 'icon' | 'text' | 'color')` applies one to an element's text, and
`data-ui-emoji="icon"` (or `text`, `color`) on an element does it on load. In `icon` style an
emoji with no icon falls back to `text`; a text node that is nothing but one mapped symbol
(a button reading `⚙` or `✕`) becomes its icon; arrows and symbols inside sentences are left
alone. The emoji stays in the page, visually hidden, so copy, find and screen readers keep it.

System fonts draw faces (😀) only in colour. For monochrome faces in `text` style, load the
Noto Emoji web font, which `--font-emoji` names first, e.g.
`data-fonts-href="https://fonts.googleapis.com/css2?family=Noto+Emoji&display=swap"` on the
`ui-theme.js` tag.

## The set

| Icon | Label | Use for | Emoji and symbols it replaces |
|---|---|---|---|
| `plus` | Add | add, new, create | ➕ ＋ ✚ |
| `x` | Close | close, remove, dismiss | ✕ ✖ ✗ ✘ ❎ |
| `check` | Done | done, confirm, selected | ✓ ✔ ☑ |
| `pencil` | Edit | edit, rename, write | ✏ 📝 ✒ 🖊 🖋 |
| `trash` | Delete | delete, discard | 🗑 |
| `copy` | Copy | copy, duplicate | ⧉ |
| `download` | Download | download, export, import into | 📥 ⬇ ⤓ |
| `upload` | Upload | upload, attach from disk, publish | 📤 ⬆ ⤒ |
| `refresh-cw` | Refresh | refresh, retry, sync, regenerate | 🔄 🔃 🔁 ↻ ⟳ ↺ ⟲ |
| `search` | Search | search, find, filter | 🔍 🔎 |
| `link` | Link | link, URL, connect two things | 🔗 |
| `external-link` | Open in new tab | opens elsewhere | ↗ ⬈ |
| `menu` | Menu | open the navigation | ☰ ≡ |
| `ellipsis` | More | more actions | … ⋯ ⋮ |
| `chevron-down` | Expand | expand, open a list | ▾ ▼ ⌄ 🔽 |
| `chevron-right` | Next | next, go into, collapsed row | ▸ ▹ › ❯ |
| `arrow-left` | Back | back, previous | ← ⬅ 🔙 ◂ ◀ ‹ ❮ |
| `info` | Information | info, note, tip | ℹ ⓘ 💡 |
| `triangle-alert` | Warning | warning, needs attention | ⚠ ❗ ❕ ‼ 🚨 |
| `circle-check` | Success | success, passed, healthy | ✅ 🟢 |
| `circle-x` | Error | error, failed, blocked | ❌ 🛑 ⛔ 🚫 🔴 |
| `bell` | Notifications | notifications, announcements | 🔔 📣 📢 |
| `settings` | Settings | settings, preferences | ⚙ 🔩 |
| `wrench` | Tools | tools, configure, fix | 🔧 🛠 🔨 🧰 🎛 🎚 |
| `palette` | Theme | theme, appearance, colours | 🎨 🖌 |
| `folder` | Folder | folder, files, browse | 📁 📂 🗂 🗃 🗄 |
| `file-text` | Document | document, page, docs, notes | 📄 📃 📑 📜 📋 📰 📖 📕 📚 |
| `paperclip` | Attach | attachment, attach a file | 📎 🖇 |
| `image` | Image | image, photo, gallery | 🖼 📷 📸 🎞 |
| `message-circle` | Chat | chat, comment, conversation | 💬 🗨 💭 🗯 |
| `send` | Send | send a message, mail | ✉ 📧 📨 📩 📬 📮 |
| `chart-column` | Statistics | stats, reports, dashboard | 📊 📈 📉 |
| `puzzle` | Extensions | plugins, extensions, apps | 🧩 📦 |
| `user` | Account | account, profile, person | 👤 🧑 👨 👩 🙋 |
| `users` | People | people, team, members | 👥 👪 |
| `bot` | Assistant | AI assistant, bot, agent | 🤖 👾 |
| `sparkles` | AI | AI action, generate, new | ✨ 🌟 💫 ⭐ |
| `lock` | Security | security, private, locked | 🔒 🔐 🔏 🔑 🗝 🛡 |
| `monitor` | Device | device, screen, host | 🖥 💻 📺 |
| `terminal` | Console | console, logs, command line | ⌨ |
| `plug` | Connect | connection, integration, power | 🔌 🔋 |
| `globe` | Web | web, language, public | 🌐 🌍 🌎 🌏 🗺 |
| `zap` | Quick action | quick action, automation, fast | ⚡ 🔥 🚀 |
| `play` | Play | play, run, start | ▶ ⏯ ► |
| `square` | Stop | stop, end a run | ⏹ ■ ◼ ⬛ |
| `mic` | Voice | voice, record, dictate | 🎤 🎙 |
| `thumbs-up` | Like | like, approve, good answer | 👍 👌 |
| `thumbs-down` | Dislike | dislike, reject, bad answer | 👎 |

## Adding an icon

The set stays under 50: it covers chrome, not illustration. To add one, copy the icon's file from the
`lucide-static` 1.50.0 package (`icons/<name>.svg`, unchanged) into `src/icons/lucide/`, add
an entry to `src/icons/icons.json`, and run `python tools/sync_theme.py build`. Icon names are public
API, like token names: never rename or remove one in a minor release.

## License

The icons are [Lucide](https://lucide.dev) 1.50.0, ISC license (some derived from
Feather, MIT). The notice ships beside the sprite as `ui-theme/icons-LICENSE.txt`; keep it with any copy.
