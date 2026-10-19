# Icons

Generated from `src/icons/icons.json` by `tools/sync_theme.py build` (ThemeForge 1.4.0).

105 outline icons for app chrome, one sprite (`ui-theme/icons.svg`). They draw in
`currentColor` with the theme's `--icon-stroke`, so every theme colours them and the
high-contrast pair draws them heavier. They are not decoration: use them where an app
would otherwise put an emoji in a button, tab, menu or status line. The set is what the
LaserLloyd apps draw, not a library; each icon lists the emoji and the Material Icons names
it replaces, so moving an app over is a lookup.

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

NiceGUI and Quasar: Quasar draws a sprite icon from `svguse:<url>#<name>`, so any `icon=` takes
one. `forgeui.quasar_icon()` writes that string, from an icon name or the Material name the app
uses today:

```python
import forgeui
forgeui.mount(app)                                          # the bundle at /theme
ui.button(icon=forgeui.quasar_icon('trash'))                # 'svguse:/theme/icons.svg#trash'
ui.icon(forgeui.quasar_icon('delete_forever'))              # a Material name maps to trash too
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

| Icon | Label | Use for | Emoji and symbols it replaces | Material Icons names |
|---|---|---|---|---|
| `plus` | Add | add, new, create | ➕ ＋ ✚ | `add`, `add_circle` |
| `x` | Close | close, remove, dismiss | ✕ ✖ ✗ ✘ ❎ | `close`, `clear` |
| `check` | Done | done, confirm, selected | ✓ ✔ ☑ | `check`, `done` |
| `pencil` | Edit | edit, rename, write | ✏ 📝 ✒ 🖊 🖋 | `edit`, `edit_note`, `mode_edit` |
| `trash` | Delete | delete, discard | 🗑 | `delete`, `delete_forever`, `delete_outline`, `delete_sweep` |
| `copy` | Copy | copy, duplicate | ⧉ | `content_copy` |
| `save` | Save | save, store to disk | 💾 💿 📀 | `save` |
| `download` | Download | download, export | ⤓ | `download`, `cloud_download`, `system_update_alt`, `download_for_offline`, `file_download` |
| `upload` | Upload | upload, attach from disk, publish | 📤 ⤒ | `upload`, `cloud_upload`, `file_upload` |
| `refresh-cw` | Refresh | refresh, retry, sync, regenerate, restart | 🔄 🔃 🔁 ↻ ⟳ ↺ ⟲ | `refresh`, `sync`, `autorenew`, `restart_alt`, `replay` |
| `undo-2` | Undo | undo, restore | ⎌ ↶ | `undo`, `restore` |
| `reply` | Reply | reply, quote in a reply | ↩ | `reply` |
| `search` | Search | search, find, filter | 🔍 🔎 | `search`, `search_off`, `troubleshoot` |
| `link` | Link | link, URL, connect two things | 🔗 | `link` |
| `unlink` | Unlink | remove a link, disconnect |  | `link_off` |
| `external-link` | Open in new tab | opens elsewhere, pop out | ↗ ⬈ | `open_in_new`, `launch` |
| `pin` | Pin | pin, keep on top, sticky | 📌 📍 | `push_pin` |
| `archive` | Archive | archive, put away; zip files | 🗃 📦 | `archive`, `inventory_2` |
| `tag` | Label | label, tag, category | 🏷 🔖 | `label`, `sell` |
| `flag` | Flag | flag, report, mark | 🚩 🏁 🏳 🏴 | `flag`, `outlined_flag` |
| `eraser` | Clear | clear, clean up, start over | 🧹 🧽 | `cleaning_services`, `layers_clear`, `clear_all` |
| `eye` | Show | show, preview, visible | 👁 👀 | `visibility` |
| `eye-off` | Hide | hide, private, not visible | 🙈 | `visibility_off` |
| `sliders-horizontal` | Adjust | tune, adjust, controls | 🎛 🎚 | `tune`, `settings_input_component` |
| `user-plus` | Add person | invite, add a user |  | `person_add` |
| `list-checks` | Checklist | checklist, steps, tasks |  | `checklist`, `fact_check` |
| `menu` | Menu | open the navigation | ☰ ≡ | `menu` |
| `ellipsis` | More | more actions | … ⋯ | `more_horiz` |
| `ellipsis-vertical` | More | more actions (kebab) | ⋮ | `more_vert` |
| `chevron-down` | Expand | expand, open a list, sorted descending | ▾ ▼ ⌄ 🔽 | `expand_more`, `keyboard_arrow_down`, `arrow_drop_down` |
| `chevron-up` | Collapse | collapse, sorted ascending | ▴ ▲ ⌃ 🔼 | `expand_less`, `keyboard_arrow_up`, `arrow_drop_up` |
| `chevron-right` | Next | next, go into, collapsed row | ▸ ▹ › ❯ | `chevron_right`, `keyboard_arrow_right`, `navigate_next` |
| `chevron-left` | Previous | previous, back one step | ◂ ◀ ◃ ‹ ❮ | `chevron_left`, `keyboard_arrow_left`, `navigate_before` |
| `arrow-left` | Back | back | ← ⬅ 🔙 | `arrow_back` |
| `arrow-right` | Forward | forward, continue | → ➡ ⟶ | `arrow_forward` |
| `arrow-up` | Up | up, scroll to top, sort ascending | ↑ ⬆ | `arrow_upward` |
| `arrow-down` | Down | down, scroll to latest, sort descending | ↓ ⬇ | `arrow_downward` |
| `arrow-up-down` | Sort | sortable column, reorder | ⇅ ↕ | `swap_vert`, `unfold_more`, `sort` |
| `grip-vertical` | Drag | drag handle | ⠿ ⋮⋮ ⣿ | `drag_indicator`, `drag_handle` |
| `list` | List | list view |  | `list`, `view_list` |
| `maximize-2` | Expand view | open in full, full screen | ⛶ ⤢ | `open_in_full`, `fullscreen` |
| `info` | Information | info, note, tip | ℹ ⓘ 💡 | `info`, `lightbulb` |
| `triangle-alert` | Warning | warning, needs attention | ⚠ ❗ ❕ ‼ 🚨 | `warning`, `report_problem`, `priority_high`, `report` |
| `circle-check` | Success | success, passed, healthy | ✅ 🟢 | `check_circle`, `task_alt` |
| `circle-x` | Error | error, failed | ❌ 🛑 🔴 | `cancel`, `error`, `highlight_off` |
| `ban` | Blocked | blocked, not allowed | 🚫 ⛔ | `block`, `do_not_disturb` |
| `circle-question-mark` | Help | help, unknown, maybe | ❓ ❔ ⁉ 🤔 | `help`, `help_outline`, `contact_support` |
| `bell` | Notifications | notifications, announcements | 🔔 📣 📢 | `notifications`, `campaign` |
| `clock` | Time | time, schedule, pending | ⏰ ⏱ ⏲ ⌚ ⌛ ⏳ 🕐 🕑 🕒 🕓 🕔 🕕 🕖 🕗 🕘 🕙 🕚 🕛 | `schedule`, `pending_actions`, `access_time`, `timer` |
| `history` | History | history, earlier sessions | 🕰 | `history` |
| `activity` | Health | health, activity, pulse | 🩺 💓 | `monitor_heart`, `health_and_safety`, `show_chart` |
| `cloud-off` | Offline | offline, not connected |  | `cloud_off`, `wifi_off` |
| `settings` | Settings | settings, preferences | ⚙ 🔩 | `settings` |
| `wrench` | Tools | tools, configure, fix | 🔧 🛠 🔨 🧰 | `build`, `construction`, `handyman` |
| `palette` | Theme | theme, appearance, colours | 🎨 🖌 | `palette`, `brush` |
| `sun` | Light | light theme, daytime | ☀ 🌞 🔆 🔅 | `light_mode`, `wb_sunny` |
| `moon` | Dark | dark theme, night | 🌙 🌛 🌜 ☾ ☽ | `dark_mode`, `nightlight` |
| `folder` | Folder | folder, files, browse | 📁 📂 🗂 | `folder`, `folder_open` |
| `file-text` | Document | document, page, notes | 📄 📃 📑 📜 📰 📕 | `description`, `article`, `sticky_note_2`, `note` |
| `book-open` | Knowledge | docs, manual, library | 📖 📚 📘 📗 📙 📓 📔 📒 | `menu_book`, `library_books`, `auto_stories` |
| `clipboard-list` | Jobs | jobs, tasks, board | 📋 💼 🗒 | `assignment`, `work` |
| `paperclip` | Attach | attachment, attach a file | 📎 🖇 | `attach_file`, `attachment` |
| `image` | Image | image, photo, gallery | 🖼 🎞 | `image`, `photo`, `collections` |
| `image-off` | No images | images hidden |  | `hide_image` |
| `camera` | Camera | take or change a picture | 📷 📸 | `photo_camera`, `add_a_photo` |
| `message-circle` | Chat | chat, comment, conversation | 💬 🗨 💭 🗯 | `chat`, `chat_bubble`, `comment` |
| `messages-square` | Chats | conversations, thread list |  | `forum`, `question_answer` |
| `mail` | Mail | email, message | ✉ 📧 📨 📩 📮 | `mail`, `email`, `mark_email_unread` |
| `mail-open` | Read mail | read, opened, drafts |  | `mark_email_read`, `drafts` |
| `inbox` | Inbox | inbox, incoming | 📥 📬 📭 📫 📪 | `inbox`, `all_inbox`, `move_to_inbox` |
| `send` | Send | send a message, outbox |  | `send`, `outbox` |
| `chart-column` | Statistics | stats, reports, dashboard | 📊 📈 📉 | `bar_chart`, `query_stats`, `insights`, `leaderboard` |
| `puzzle` | Extensions | plugins, extensions, apps | 🧩 | `extension` |
| `code` | Code | code, source, markup |  | `code` |
| `music` | Audio | audio, music, sound file | 🎵 🎶 🎼 | `music_note`, `audiotrack`, `library_music` |
| `target` | Goal | goal, focus, aim | 🎯 | `gps_fixed`, `track_changes` |
| `user` | Account | account, profile, person | 👤 🧑 👨 👩 🙋 | `person`, `account_circle` |
| `users` | People | people, team, members | 👥 👪 | `group`, `people`, `groups` |
| `bot` | Assistant | AI assistant, bot, agent | 🤖 👾 | `smart_toy` |
| `brain` | Thinking | thinking, reasoning, memory | 🧠 | `psychology` |
| `sparkles` | AI | AI action, generate, new | ✨ 🌟 💫 ⭐ | `auto_awesome` |
| `life-buoy` | Support | help, support, recovery | 🛟 🆘 | `support`, `support_agent` |
| `lock` | Security | security, private, locked | 🔒 🔐 🔏 | `lock` |
| `lock-open` | Unlocked | unlocked, sign in | 🔓 | `lock_open`, `no_encryption` |
| `key` | Key | password, key, token | 🔑 🗝 | `key`, `vpn_key`, `password` |
| `shield` | Protection | protection, safety | 🛡 | `shield`, `security` |
| `shield-check` | Verified | verified, trusted, safe |  | `verified`, `verified_user`, `gpp_good` |
| `shield-alert` | Suspicious | suspicious, spam, phishing |  | `gpp_maybe`, `gpp_bad` |
| `monitor` | Device | computer, screen, host | 🖥 💻 📺 | `computer`, `desktop_windows`, `monitor` |
| `smartphone` | Phone | phone, this device | 📱 📲 | `smartphone`, `phone_iphone`, `phone_android` |
| `terminal` | Console | console, logs, command line | ⌨ | `terminal` |
| `cpu` | Model | AI model, processor, memory |  | `memory`, `developer_board` |
| `database` | Database | database, storage | 🗄 🛢 | `storage`, `dns` |
| `gauge` | Speed | speed, benchmark, load |  | `speed` |
| `power` | Power | start, stop, power | ⏻ ⏼ ⭘ | `power_settings_new` |
| `plug` | Connect | connection, integration | 🔌 🔋 | `electrical_services`, `cable` |
| `globe` | Web | web, language, public | 🌐 🌍 🌎 🌏 🗺 | `public`, `language`, `travel_explore` |
| `flask-conical` | Test | tests, experiments, evals | 🧪 ⚗ 🔬 | `science`, `biotech` |
| `zap` | Quick action | quick action, automation, fast | ⚡ 🔥 🚀 | `bolt`, `flash_on`, `local_fire_department`, `rocket_launch` |
| `play` | Play | play, run, start | ▶ ⏯ ► | `play_arrow`, `play_circle` |
| `pause` | Pause | pause, hold | ⏸ | `pause`, `pause_circle` |
| `square` | Stop | stop, end a run | ⏹ ■ ◼ ⬛ | `stop`, `stop_circle` |
| `mic` | Voice | voice, record, dictate | 🎤 🎙 | `mic`, `keyboard_voice` |
| `thumbs-up` | Like | like, approve, good answer | 👍 👌 | `thumb_up` |
| `thumbs-down` | Dislike | dislike, reject, bad answer | 👎 | `thumb_down` |

## Adding an icon

The set holds what the apps draw, and the build refuses more than 120: add an icon when an app
needs one and nothing here means the same thing (a Material name or an emoji can usually join an
existing icon instead). To add one, copy the icon's file from the
`lucide-static` 1.50.0 package (`icons/<name>.svg`, unchanged) into `src/icons/lucide/`, add
an entry to `src/icons/icons.json`, and run `python tools/sync_theme.py build`. Icon names are public
API, like token names: never rename or remove one in a minor release.

## License

The icons are [Lucide](https://lucide.dev) 1.50.0, ISC license (some derived from
Feather, MIT). The notice ships beside the sprite as `ui-theme/icons-LICENSE.txt`; keep it with any copy.
