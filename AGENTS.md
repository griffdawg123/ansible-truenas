# Agent notes — `jdevera.truenas`

Personal fork of `arensb.truenas` targeting **TrueNAS SCALE 25.10 and newer only**.

## Module structure

Every module's `main()` follows this order:

```python
def main():
    module = AnsibleModule(argument_spec=..., supports_check_mode=True)
    setup.require_scale_min_version(module)
    # ... module logic
```

- `AnsibleModule(...)` is constructed **before** the version check so the check can use `module.fail_json` to report a clean Ansible failure instead of `sys.exit()`.
- The floor version is `setup.MIN_SCALE_VERSION`

## Reporting failures

Use `setup.fail(module, msg, **kwargs)` instead of `module.fail_json(msg=..., **kwargs)`. `setup.fail` is annotated `NoReturn`; plain `fail_json` isn't.

## Versions and dependencies

- Floor: SCALE **25.10**. Modules `fail_json` with a clear message on anything older. Any code that exists only to support older versions can and should be deleted.
- Prefer keeping third-party deps to a minimum. If you need one, add it to a `requirements.txt` and audit the sanity venv impact first.

## License and author

- License is **Apache-2.0**
- Author and (GPL) license fields are intentionally left out. Both ignores are per-file in `tests/sanity/ignore-2.21.txt`. If you add a new module, append the same two lines for it.

## Conventions

- `DOCUMENTATION`, `EXAMPLES`, `RETURN` strings come **before** Python imports. ruff's E402 is ignored to allow this.
- For dicts whose internal shape we don't want to fully spec, use `type: dict` rather than `type: complex` — `complex` requires a `contains:` schema we typically don't want to maintain.

## Checks

One command: `pre-commit run --all-files`. It runs ruff, ruff-format, mypy, ansible-doc, and ansible-test sanity, with each hook bringing its own dependencies (`additional_dependencies: [ansible-core]`). Run `pre-commit install` once per checkout to also trigger it on `git commit`. To call any tool directly, use uv: `uv run --with ruff ruff check plugins/` etc.

## Upstream

`.upstream-reviewed` at the repo root contains the SHA of the last `arensb/ansible-truenas` commit reviewed for porting. To see what's new since:

```
git fetch upstream
git log "$(cat .upstream-reviewed)..upstream/main" --oneline
```

After porting, update the file to the new upstream tip and commit:

```
git rev-parse upstream/main > .upstream-reviewed
git commit .upstream-reviewed -m 'Note upstream review checkpoint.'
```

## Docs

`.github/workflows/docs.yml` builds the Sphinx site (antsibull-docs + antsibull-changelog + sphinx_ansible_theme) on every push to main and deploys it to GitHub Pages. Local preview: `scripts/prepare-collection-layout.sh && uv run --with 'ansible-core>=2.13.0' --with antsibull-docs --with antsibull-changelog --with sphinx --with sphinx_ansible_theme bash docs/build.sh && open docs/build/html/index.html`.

## Repo layout idiosyncrasies

- `plugins/module_utils/setup.py` holds shared helpers (`fail`, `require_scale_min_version`, `_parse_version`, `get_tn_version`, `MIN_SCALE_VERSION`).
- `plugins/module_utils/middleware.py` is a thin wrapper over `client.py`, which talks to middlewared natively via the `truenas_api_client` library. Treat `MiddleWare.client().call(...)` returns as `Any`.
- `.local/` is gitignored — personal scratch space, agent dropbox. Anything that needs to ship goes into a real path.

