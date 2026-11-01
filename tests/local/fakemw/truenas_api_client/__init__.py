"""Fake truenas_api_client backed by a JSON state file, for local tests."""

import json
import os


class ClientException(Exception):
    errno = 0
    error = ""


def _load():
    with open(os.environ["FAKE_MW_STATE"]) as f:
        return json.load(f)


def _save(s):
    with open(os.environ["FAKE_MW_STATE"], "w") as f:
        json.dump(s, f, indent=1)


def _match(row, filters):
    return all(row.get(k) == v for k, op, v in filters)


class Client:
    def call(self, method, *args, job=False):
        s = _load()
        s.setdefault("_log", []).append([method, list(args), job])
        try:
            return self._dispatch(s, method, args)
        finally:
            _save(s)

    def _dispatch(self, s, method, args):
        if method == "system.product_type":
            return "COMMUNITY_EDITION"
        if method == "system.version":
            return "TrueNAS-SCALE-25.10.6"
        if method == "app.config":
            return s["app_config"][args[0]]
        if method == "app.update":
            name, data = args
            if "custom_compose_config" in data:
                s["app_config"][name] = data["custom_compose_config"]
            else:
                s["app_config"][name].update(data["values"])
            return {"name": name}
        ns, op = method.rsplit(".", 1)
        rows = s.setdefault(ns, [])
        if op == "query":
            return [r for r in rows if _match(r, args[0] if args else [])]
        if op == "create":
            row = dict(args[0], id=max([r["id"] for r in rows], default=0) + 1)
            row.pop("force", None)
            rows.append(row)
            return row
        if op == "update":
            row = next(r for r in rows if r["id"] == args[0])
            row.update(args[1])
            return row
        if op == "delete":
            s[ns] = [r for r in rows if r["id"] != args[0]]
            return True
        raise ClientException(f"unhandled {method}")
