# Examples

Both examples use this repository's own `ui-theme/` folder, so they always show the current
version. In your app the folder sits in the app (installed with `update.py`, see
[`AGENTS.md`](../AGENTS.md)).

## static-html

A notes page: app shell with a side nav that collapses on small screens, theme picker,
cards, badges, switches with On/Off labels (one disabled), a segmented control, and themed
`prompt()` / `confirm()` dialogs and toasts from `ui-components.js`. No server code.

```
python3 -m http.server 8000      # from the repository root
```

then open http://127.0.0.1:8000/examples/static-html/ (opening the file directly works too).

## fastapi-jinja

A task list in FastAPI with Jinja templates: the theme block in `templates/base.html`, static
files served with `Cache-Control: no-cache` so an updated theme shows on the next load, a
form, badges and a table.

```
cd examples/fastapi-jinja
pip install -r requirements.txt
uvicorn app:app --reload
```

then open http://127.0.0.1:8000. In your own app: install the theme with
`python3 -c "..."` from AGENTS.md section 2 into `static/ui-theme`, and keep one
`app.mount("/static", ...)`; the `url_for('ui-theme', ...)` calls become
`url_for('static', path='ui-theme/...')`.
