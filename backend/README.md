# Backend

FastAPI web API for CanixPy. Optional — the desktop app does not depend on this.

## Running

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Server runs at http://127.0.0.1:8000 — docs at http://127.0.0.1:8000/docs, health check at http://127.0.0.1:8000/health.

## Data Model

Single-user cloud sync scope: every record is owned by exactly one `User`, no cross-user sharing yet.

```
User ──┬──▶ Project ──▶ Design ──▶ Page ──▶ items[] (rect/ellipse/text/image/group)
        │                  ▲                        │
        │                  │ (project_id nullable —  │ image elements
        │                  │  a Design can be         │ reference an
        │                  │  ungrouped)               ▼
        └──────────────────┴───────────────────▶ Asset
```

```mermaid
erDiagram
    USER ||--o{ PROJECT : owns
    USER ||--o{ DESIGN : owns
    USER ||--o{ ASSET : owns
    PROJECT ||--o{ DESIGN : groups
    DESIGN ||--o{ PAGE : contains
    PAGE }o..o{ ASSET : "references (via items JSON)"

    USER {
        string id PK
        string email
        string hashed_password
        datetime created_at
    }
    PROJECT {
        string id PK
        string user_id FK
        string name
        datetime created_at
    }
    DESIGN {
        string id PK
        string user_id FK
        string project_id FK "nullable"
        string name
        int canvas_width
        int canvas_height
        int format_version
        datetime created_at
        datetime modified_at
    }
    PAGE {
        string id PK
        string design_id FK
        int order
        string name "nullable"
        json items "list of element dicts"
    }
    ASSET {
        string id PK
        string user_id FK
        string filename
        string content_type
        int size
        string storage_path
        datetime created_at
    }
```

**Design notes**

- `Page.items` holds the same element shape `desktop_app`'s `serialize_page()` already produces (`{kind, x, y, z, rotation, ...}` per rect/ellipse/polygon/text/image/group) — one JSON blob per page rather than a normalized element table, so desktop ⇄ backend sync is a straight JSON translation.
- `Asset` exists because `desktop_app` embeds images as base64 (`png_base64`) inline in the JSON — the backend instead stores image bytes via `Asset` and elements reference it by `asset_id`, so that reference is a lookup key inside the `items` JSON, not a real foreign key the database enforces.
- Each domain owns its model at `backend/app/<domain>/models.py` (`users/`, `projects/`, `designs/`, `pages/`, `assets/`) — see the [root README](../README.md) for how this fits into the whole repo.
