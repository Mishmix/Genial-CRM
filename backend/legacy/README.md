# Legacy migration & maintenance scripts

These one-shot scripts were used during initial SQLite → Postgres migration
and local development. They are **not** referenced by the running app and are
preserved here for historical reference. Do not invoke unless you know what
you're doing.

If you ever need to run one, copy it back to `backend/` first — the app's
import path expects to be at the backend root.
