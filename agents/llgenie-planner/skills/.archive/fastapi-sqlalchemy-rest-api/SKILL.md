---
name: fastapi-sqlalchemy-rest-api
category: development
description: Use when building REST APIs with FastAPI + SQLAlchemy.
---

# FastAPI + SQLAlchemy REST API development

Building a typed REST API with FastAPI, SQLAlchemy 2.0 ORM, Alembic migrations, and PostgreSQL.

## Workflow

1. **Scaffold** the layered structure up front — `main.py` (app factory, router registration), `config.py` (pydantic-settings, `.env`), `database.py` (engine + `SessionLocal` + `Base`), `models.py` (ORM), `schemas.py` (Pydantic I/O), `crud.py` (DB access), `deps.py` (dependencies), `routers/*.py`. Adding a resource later = new router + model + schema + migration, no core surgery.
2. **Install:** `pip install "fastapi[standard]" sqlalchemy psycopg[binary] alembic pydantic-settings pytest httpx`. Run with `uvicorn app.main:app --reload`; production via `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w N` behind a TLS reverse proxy.
3. **Models are the schema source of truth** — Alembic autogenerate diffs models against the live DB. Write them carefully; a sloppy ORM class yields bad migrations.
4. **Input vs output schemas must be separate.** `ItemCreate`, `ItemUpdate`, `ItemOut` — never reuse a request schema as a response. Output schemas need `ConfigDict(from_attributes=True)` to serialize ORM rows. Always set `response_model=`; never return raw ORM objects.
5. **Migrations:** `alembic init alembic`, point `env.py` at `target_metadata = Base.metadata` (import the models so they register), then `alembic revision --autogenerate -m "..."` → **review** → `alembic upgrade head`. Run `upgrade head` once at deploy (record in CI/ansible) so environments don't drift.

## Data-modeling rules (autogenerate correctness + prod safety)

- **Money is never Float** — map currency columns to `Numeric(12, 2)` and type them `Mapped[Decimal]` (`from decimal import Decimal`), NOT `Mapped[float]`. `Numeric` returns `Decimal`; typing it float is a latent bug. This is the most commonly missed mapping.
- **IDs: `BigInteger`**, not Integer — overflow earlier pain than a later column-type migration.
- **Timestamps always timezone-aware**: `DateTime(timezone=True)` (TIMESTAMPTZ). Naive timestamps are a bug factory. Stamp with `server_default=func.now()` so the DB, not the app, sets `created_at`; `onupdate=func.now()` for `updated_at`.
- **Every FK gets an explicit `ondelete=`** (`RESTRICT`/`CASCADE`/`SET NULL`) and `index=True`. Declare `nullable` explicitly on every column.
- Many-to-many uses an association `Table` (join table), not a model class. 1-to-many uses `relationship(back_populates=...)`.

## Schema-versioning (Alembic) pitfalls

- **`--autogenerate` is a draft, not truth.** It cannot detect renames (sees drop+add) or many constraint changes. Review every generated migration; hand-write renames with `op.alter_column`.
- **Never edit an applied migration.** History is append-only — write a new migration on top of any committed release.
- **Adding a NOT NULL column to a populated table breaks prod**: add nullable, backfill with `op.execute(...)`, then `op.alter_column(... nullable=False)`.
- `revision` + `down_revision` form a linear chain; `upgrade head` must be reproducible from an empty DB.

## REST/contract rules

- Nouns not verbs in URLs, plural (`/items/{id}`); HTTP methods carry the verb.
- Correct status codes: 201 created, 204 delete, 404 not found via `HTTPException(status_code=..., detail=...)`, FastAPI auto-422s validation errors.
- FastAPI derives the OpenAPI contract from type hints + Pydantic models — one source of truth feeding `/docs`, `/openapi.json`, and client codegen. Configure `title/version/description/openapi_tags` on the app factory.
- `Annotated[type, Query(min_length=...)]` / `Annotated[int, Path(gt=0)]` for constraint-bearing params; path `/x/{param}` must come after fixed paths like `/x/me`.
- DB session via generator dependency `Depends(get_db)` (yield + finally close); auth/token via `OAuth2PasswordBearer`.
- Engine: use `pool_pre_ping=True`. Add `index=True` on every column used in `WHERE`. Paginate list endpoints (skip/limit) — never unbounded rows.
- Never commit secrets: `.env` + `.env.example`, `.env` gitignored; URL from pydantic-settings.

## Pitfalls (general)

- **`Mapped[float]` + `Numeric` is a type lie** — see money rule; check generated migrations and ORM types when reviewing a guide or codebase, not just SQL.
- FastAPI `--reload` is dev-only; don't carry it into production commands in docs/examples.
- Write guides as runnable reference: full file blocks (main/database/models/schemas/crud/router) that a user can reassemble, plus exact shell commands. See `references/data-modeling.md` for the canonical table example and column-type map.
