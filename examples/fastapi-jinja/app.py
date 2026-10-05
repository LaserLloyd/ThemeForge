"""A minimal FastAPI + Jinja app themed with ThemeForge.

    pip install -r requirements.txt
    uvicorn app:app --reload        (from this folder), then open http://127.0.0.1:8000

In your own app, install the folder into static/ui-theme with update.py (see the
README) and mount static/ once. This example serves the repository's own
ui-theme/ folder so it always shows the current version.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

HERE = Path(__file__).resolve().parent
BUNDLE = HERE / "static" / "ui-theme"
if not BUNDLE.is_dir():  # running inside the theme repository: use its copy
    BUNDLE = HERE.parent.parent / "ui-theme"


class NoCacheStatic(StaticFiles):
    """Static files that the browser revalidates on every load, so a new copy
    of ui-theme/ shows up without a hard refresh."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI()
app.mount("/static/ui-theme", NoCacheStatic(directory=BUNDLE), name="ui-theme")
app.mount("/static", NoCacheStatic(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

TASKS = [
    {"title": "Write the release notes", "done": True},
    {"title": "Review the dashboard layout", "done": False},
    {"title": "Book the venue", "done": False},
]


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"tasks": TASKS})


@app.post("/tasks")
def add_task(title: str = Form(...)):
    if title.strip():
        TASKS.append({"title": title.strip(), "done": False})
    return RedirectResponse("/", status_code=303)


@app.post("/tasks/{index}/toggle")
def toggle_task(index: int):
    if 0 <= index < len(TASKS):
        TASKS[index]["done"] = not TASKS[index]["done"]
    return RedirectResponse("/", status_code=303)
