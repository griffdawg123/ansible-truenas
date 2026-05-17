# Agent notes — `jdevera.truenas`

Personal fork of `arensb.truenas` targeting **TrueNAS SCALE 25.10 and newer only**. Read this before touching code; the conventions below aren't all obvious from the source.

## Module structure

Every module's `main()` follows this order:

```python
def main():
    module = AnsibleModule(argument_spec=..., supports_check_mode=True)
    setup.require_scale_min_version(module)
    # ... module logic
```

- `AnsibleModule(...)` is constructed **before** the version check so the check can use `module.fail_json` to report a clean Ansible failure instead of `sys.exit()`.
- `setup.require_scale_min_version(module)` lives in `plugins/module_utils/setup.py`. The floor version is `setup.MIN_SCALE_VERSION` — a tuple of ints (currently `(25, 10)`).

## Reporting failures

Use `setup.fail(module, msg, **kwargs)` instead of `module.fail_json(msg=..., **kwargs)` when you want static analysis to prune control flow after the call. `setup.fail` is annotated `NoReturn`; plain `fail_json` isn't.

When you call `setup.fail`, **do not** add a trailing `return` — that's the whole point. The previous "fake return after fail_json" pattern is gone.

## Versions and dependencies

- Floor: SCALE **25.10**. Modules `fail_json` with a clear message on anything older. Don't write pre-25.10 compat branches.
- **Do not import `packaging`** anywhere. The `ansible-test sanity` venv is minimal and doesn't ship it. For version comparison, use `setup._parse_version(s)` which returns a tuple of ints.
- No other runtime third-party deps. If you need one, add it to a `requirements.txt` and audit the sanity venv impact first.

## License and author

- License is **Apache-2.0** (not GPLv3, despite ansible-test's preference). Don't add GPLv3 headers. The `missing-gplv3-license` warning is silenced in `tests/sanity/ignore-2.20.txt`.
- Author fields in inherited `DOCUMENTATION` blocks are deliberately not added. `invalid-documentation` (which fires for missing author) is silenced too.
- Both ignores are per-file in `tests/sanity/ignore-2.20.txt`. If you add a new module, append the same two lines for it.

## Linting and validation

| Command | What it checks | Authoritative? |
|---|---|---|
| `make lint` | ruff (E/W/F/I/B/UP) | yes |
| `make typecheck` | mypy via pyproject.toml | yes |
| `make check-docs` | every module parses through `ansible-doc` | yes |
| `make validate` | `ansible-test sanity` full suite | mostly; pre-existing doc nits remain |
| Pyright | editor-time | best-effort; many rules silenced because ansible-core is untyped |

**All four should be green before a commit.** Tool config is consolidated in `pyproject.toml` — `[tool.ruff]`, `[tool.mypy]`, `[tool.pyright]`. No `.mypy.ini`, no `pyrightconfig.json`.

Run tools through `uv` so they pick up the right environment: `uv run --with ruff ruff check plugins/`, `uv run --with mypy --with ansible-core mypy ...`. The `make` targets do this already.

`make typecheck` and `make validate` require the `ansible_collections/jdevera/truenas/` compatibility-link to exist; `make compatibility-link` sets it up.

## Avoid the word "sanity"

In commit messages, comments, docs, and target names, use "validate", "checks", "verify" etc. instead of "sanity". The Makefile target was renamed `sanity → validate` for this reason. The underlying `ansible-test sanity` subcommand name is hardcoded by ansible-core and can't be avoided in shell invocations, but everything we author should.

## Ansible YAML conventions to remember

- `DOCUMENTATION`, `EXAMPLES`, `RETURN` strings come **before** Python imports. ruff's E402 is ignored to allow this.
- Every `RETURN` top-level key needs `returned:` and `type:`. Missing either makes `validate-modules` fail with `return-syntax-error`.
- For dicts whose internal shape we don't want to fully spec, use `type: dict` rather than `type: complex` — `complex` requires a `contains:` schema we typically don't want to maintain.

## Repo layout idiosyncrasies

- `plugins/module_utils/setup.py` holds shared helpers (`fail`, `require_scale_min_version`, `_parse_version`, `get_tn_version`, `MIN_SCALE_VERSION`).
- `plugins/module_utils/middleware.py` wraps either `client.py` (faster, newer) or `midclt.py` (subprocess-based, fallback). The choice is via `middleware_method` env var. Treat `MiddleWare.client().call(...)` returns as `Any`.
- Deleted modules: `jail`, `jails`, `jail_fstab`, `plugin`. SCALE removed their APIs — don't resurrect them.
- `.local/` is gitignored — personal scratch space, agent dropbox. Anything that needs to ship goes into a real path.
- `.local/doc-backlog.md` (untracked) catalogs the open `validate-modules` findings. If you're doing doc cleanup, start there.

## Things to keep clean

This is a personal collection used by an agent-driven workflow. The working assumption is: a clean baseline makes new noise stand out. So:

- New files start clean (ruff, mypy, pyright, validate-modules).
- New code uses `setup.fail` for fail paths; no manual `return` after `fail_json`.
- Don't add ignore entries to `tests/sanity/ignore-2.20.txt` without recording the reason in the commit message.
- Don't import `packaging`, `requests`, or other heavy deps without checking that `make validate` still runs in the minimal sanity venv.
