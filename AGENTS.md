# AGENTS.md

MCP server (Python) that exposes Oracle 11g databases to MCP clients over stdio via FastMCP, using `python-oracledb` in **thick mode** (11g does not support thin mode).

## Commands (Windows)

- Bootstrap: `.\setup.ps1` — creates `.venv`, runs `pip install -e .`, copies `.env.example` to `.env` if missing.
- Run server: `.\\.venv\\Scripts\\oracle-mcp` or `.\\.venv\\Scripts\\python -m oracle_mcp.server`.
- Healthy startup logs `Pools Oracle listos: N` then `Conexiones Oracle disponibles: N`.
- **No tests, no linter/typecheck, no CI exist.** Verify changes by launching the server; this requires live network access to the configured Oracle DBs (there is no offline test path).
- Set individual connection credentials as Windows User-scope env vars (avoids plaintext in `.env`) with `.\set-secrets.ps1 -Name <connection>` (or `-Unset`).

## Codebase

- All logic lives in `src/oracle_mcp/`: `config.py` (env → `OracleConfig`), `db.py` (thick init, connection pools, SQL-validation), `server.py` (FastMCP tools; entry point `oracle-mcp = oracle_mcp.server:main`).
- `src/oracle_mcp/installer/` contains only stale `__pycache__` — there is no source; ignore it.
- **Language convention: READMEs, code comments, and docstrings are Spanish. Write new/edited prose in Spanish.**

## Env & connections

- Config comes exclusively from env vars. `.env` is loaded from the **repo root**, independent of cwd (anchored to `Path(__file__)` in `config.py`) — so `.env` picks up even when the client starts the server from elsewhere.
- Precedence: already-set process env (incl. `opencode.json` `environment` block) > Windows User-scope vars > `.env`. python-dotenv never overrides existing vars.
- Multi-connection mode: names in `ORACLE_CONNECTIONS` (comma-separated) map directly to `ORACLE_CONN_<NAME_UPPER>_*` vars (e.g. `afp_pruebas` → `ORACLE_CONN_AFP_PRUEBAS_USER`). Legacy single-connection mode: bare `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_HOST`, etc.
- A connection with missing required vars is **skipped with a warning, not fatal** — the server only errors when *every* connection is invalid.
- Oracle 11g generally connects by **SID** (`oracledb.makedsn(host, port, sid=...)`), not service_name. Thick mode is initialized once, using the `CLIENT_LIB_DIR` of the *first* connection that defines it; if libs aren't on PATH and no dir is set, startup fails.

## Security model (do not break)

- Never read, print, or commit `.env` contents. `.env`, `.venv`, and `instant-client/` are gitignored.
- `run_query` accepts only a single SELECT/WITH statement (no `;`-separated multiples).
- `execute_statement` requires env `ORACLE_CONN_<NAME>_ALLOW_WRITE=true` **and** `confirm=true` in the tool call — both are mandatory.