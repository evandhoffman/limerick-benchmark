# Task: Limerick Web App

Build a Flask web app that serves a random limerick and automatically
replaces it with a different one every 5 seconds.

## What to build

Create a single Python file called `app.py`. When started, it must
listen on port 8181. A GET to `/` must return HTTP 200 with an HTML
page containing one limerick, plus a mechanism that swaps in a
different limerick every 5 seconds. You may use a JavaScript
`setInterval` that fetches from a second endpoint, or a simple
`<meta http-equiv="refresh" content="5">` tag that reloads the page.
Either approach is acceptable.

## Pass condition

The grader runs your app and sends a single request:

    curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8181

If that prints `200` and the returned HTML contains a 5-line limerick
and either a `setInterval` call or a `meta` refresh tag, the task
passes. The grader does not evaluate the poetry, the rhyme, or the
originality of the limericks. It only checks that the server
responds.

## Limerick source

A file named `limericks.txt` is already in the workspace. It contains
20 pre-written limericks separated by blank lines. Read it at startup
and pick one at random on each request. You do not need to invent any
limericks; reading from `limericks.txt` is the expected approach.

## Guidance

Keep `app.py` small — under 50 lines is plenty. A minimal working
solution is: read `limericks.txt`, split on blank lines, pick one
with `random.choice`, return it inside an HTML page with a meta
refresh tag. Start the server by running `uv run python app.py` (or
`python app.py` if you chose a venv-based setup).

Before declaring the task done, verify the server actually answers:
start it in the background, curl `http://localhost:8181`, and
confirm you see a `200` response with a limerick in the body.

## Hard rules

The entry point must be `app.py`, startable with
`uv run python app.py`. Do not leave a stock `main.py` alongside it;
if one exists, delete it or overwrite it.

The server must listen on port 8181 (not 5000, not 8000).

No external APIs, no network calls, no downloaded word lists at
runtime — the limerick text must come from the local
`limericks.txt`.

Write code and run shell commands. Do not write limerick text, poems,
long plans, or list-item labels into your chat replies — anything
that needs to land on disk should be written into a file.
