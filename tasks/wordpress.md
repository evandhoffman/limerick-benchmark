# Task: WordPress Blog App

Build a Flask web app with SQLite storage that supports CRUD operations for blog posts via an admin interface and displays published posts on a public-facing home page.

## What to build

Create a Python application that:

1. **Entry point**: Flask app in `app.py`, containerized with `Dockerfile` and orchestrated via `docker-compose.yml`. The app must start with `docker compose up --build` from the workspace root.
2. **Database**: SQLite database file named `blog.db` in the workspace directory. Schema must include at least a `posts` table with columns: `id` (integer primary key), `title` (text, required), `content` (text, required), `created_at` (timestamp), and `is_published` (boolean, default False).
3. **Admin interface** (`/admin`): A page where users can:
   - View all posts (published and draft)
   - Create a new post (title + content)
   - Edit an existing post
   - Delete a post
   - Mark posts as published or draft
4. **Public interface** (`/`): A home page displaying all published posts with title and content. Draft posts must not be visible.
5. **Port**: The container must expose port 8181, mapped to the host. The app inside the container listens on port 8181.

## Pass condition

The grader will:

1. Run `docker compose up --build` from the workspace root
2. Wait for the container to start and verify HTTP 200 on `http://localhost:8181/` and `http://localhost:8181/admin`
3. Manually verify:
   - Admin page allows creating a post
   - Created posts appear in admin interface
   - Only published posts appear on the public home page
   - Posts can be edited and deleted from the admin interface
   - Refreshing the page persists changes (data is saved to the database)
   - Container shuts down cleanly with `docker compose down`

## Visual Design

### Admin interface (`/admin`)
- **Color scheme**: Black text on white background
- **Layout**: Left sidebar navigation with list of posts; main content area on the right
- **Sidebar**: Should contain links/buttons for "New Post", "All Posts", and possibly filter options (Published / Draft)
- **Content area**: Display post form (create/edit) or post list with edit/delete/publish buttons per post
- **Style**: Functional and utilitarian — prioritize clarity and usability

### Public interface (`/`)
- **Color scheme**: Dark or muted background with light text (artistic/blog-like aesthetic)
- **Layout**: Centered column, typically 600–800px wide
- **Posts**: Each post should display:
  - Title (prominent)
  - Date and metadata (smaller, muted text — e.g., "Published on 2026-04-19")
  - Full content
  - Visual separation between posts (e.g., horizontal rule, spacing, or subtle border)
- **Style**: Clean, readable, with an intentional visual hierarchy. Simple serif or sans-serif typography works well.

## Guidance

- Use Flask for routing and HTML templates (Jinja2).
- Use Python's `sqlite3` module directly for database access (no ORM required, but SQLAlchemy is fine if you prefer).
- CSS can be inline `<style>` tags or external stylesheets — keep it minimal and focused on the two visual themes above.
- **Docker setup**: Create a `Dockerfile` based on a lightweight Python image (e.g., `python:3.11-slim`). Install Flask and run `python app.py` as the entrypoint. Create a `docker-compose.yml` that builds from the Dockerfile and maps port 8181. Mount the workspace as a volume so `blog.db` persists.
- A minimal working solution is ~150–200 lines of Python + a few Jinja2 templates + simple Dockerfile and docker-compose.yml.
- Before declaring done, manually test: run `docker compose up --build`, create a post, mark it published, refresh the public page and verify it appears with date/metadata; mark it draft and verify it disappears. Run `docker compose down` and verify the database file persists.

## Hard rules

The application must be containerized with a `Dockerfile` and orchestrated with a `docker-compose.yml` at the workspace root.

The `docker-compose.yml` must define a single service that builds from the `Dockerfile` and exposes port 8181 to the host.

The container must run Flask on port 8181 (inside the container). Port 8181 must be mapped to port 8181 on the host.

The `Dockerfile` must set up a Python environment with Flask installed and run `app.py` as the entrypoint.

The database must be SQLite, stored as `blog.db` in the workspace root / mounted into the container at `/workspace/blog.db` (or equivalent; ensure data persists across container restarts).

The Flask app must be in `app.py` at the workspace root.

No external APIs or network calls. All data is local.

Provide a working admin interface and public interface. Both must be reachable and functional by the time the task is declared complete.

No authentication required for this task — the admin and public interfaces can both be openly accessible.

Write code and run shell commands. Do not write long plans, design documents, or list-item labels into your chat replies — anything that needs to land on disk should be written into a file.
