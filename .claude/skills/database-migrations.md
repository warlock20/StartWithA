---
name: database-migrations
description: Use when adding or changing SQLAlchemy models, columns, tables or indexes, or writing an Alembic migration. Migrations are generated with `flask db migrate` (hash revision ids), never hand-written from scratch.
---

# Database Migrations

Migrations live in `migrations/versions/` and are managed by Flask-Migrate (Alembic).

## Rule: let Alembic generate the file

Always create a migration with:

```bash
flask db migrate -m "short description"
```

This gives the file Alembic's hash revision id (e.g. `155df2cb043d`) and the correct
`down_revision`. **Never hand-write a migration file or pick a descriptive revision id**
(`add_ai_check`, `research_reopenings`, …). A few older migrations use descriptive ids;
don't copy them. New migrations use hash ids.

## Steps

1. **Start from head.** Run `flask db upgrade`, then `flask db heads`. There must be exactly
   one head. If there are two, stop and ask; don't merge heads silently.
2. **Change the models**, then run `flask db migrate -m "…"`.
3. **Read the generated file before applying it.** Autogenerate compares every model with
   the database, so it can pick up changes that have nothing to do with your feature.
   - Delete operations that belong to unrelated drift (tables or columns you didn't touch).
     Mention what you removed in your report.
   - Autogenerate cannot detect some changes, so add these by hand *inside the generated
     file*:
     - **Data backfills**, e.g. copying an old column into a new one:
       `op.execute("UPDATE … SET … WHERE …")`
     - **Renames.** Autogenerate writes a rename as drop + add, which loses the data.
       Replace it with `op.alter_column(..., new_column_name=...)`.
     - **`server_default`** for new `NOT NULL` columns on tables that already have rows.
     - **Enum value changes** and **check constraints**.
   - Keep `upgrade()` and `downgrade()` symmetric. The downgrade reverses your hand-added
     steps too.
4. **Apply and verify.** Run `flask db upgrade`. `flask db current` must show the new
   revision as `(head)`.

## Tests

The pytest suite (`unittests/`) builds its own scratch database (`<dev_db>_companion_test`)
with `db.create_all()`, which creates missing **tables** but never adds new **columns** to
existing ones. After adding a column, tests fail with `UndefinedColumn` until the scratch
DB is dropped. It rebuilds itself on the next run:

```bash
psql "<dev database url>" -c 'DROP DATABASE "<dev_db>_companion_test";'
```

Never drop or edit the dev database itself.

## Production

`docker-entrypoint.sh` runs `flask db upgrade` on deploy (Railway web service), so every
migration must run unattended against real data: no interactive steps, and backfills
must be safe to run on tables of any size.
