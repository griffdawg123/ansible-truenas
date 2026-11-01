#!/usr/bin/python

# Manage the system's NTP servers.
#
# midclt call system.ntpserver.query
# midclt call system.ntpserver.create '{"address": "0.pool.ntp.org", "prefer": true}'
# midclt call system.ntpserver.update <id> '{"prefer": false}'
# midclt call system.ntpserver.delete <id>

DOCUMENTATION = """
---
module: ntp
short_description: Manage TrueNAS NTP servers
description:
  - Make sure the given NTP servers are configured, and optionally remove
    any others.
  - Servers are identified by C(address).
options:
  servers:
    description:
      - NTP servers that should be configured.
      - For each server, options that are omitted are not managed; new
        servers get the middleware's defaults for them.
    type: list
    elements: dict
    required: true
    suboptions:
      address:
        description:
          - Hostname or IP address of the NTP server.
        type: str
        required: true
      burst:
        description:
          - Send a burst of packets when the server is reachable.
        type: bool
      iburst:
        description:
          - Send a burst of packets when the server is unreachable, to
            speed up initial synchronization.
        type: bool
      prefer:
        description:
          - Prefer this server over the others.
        type: bool
      minpoll:
        description:
          - Minimum polling interval, as a power of 2 seconds.
        type: int
      maxpoll:
        description:
          - Maximum polling interval, as a power of 2 seconds.
        type: int
  purge:
    description:
      - If true, delete configured NTP servers that aren't listed in
        C(servers).
    type: bool
    default: false
  force:
    description:
      - Add new servers even if middleware can't reach them.
    type: bool
    default: false
notes:
  - Supports C(check_mode).
version_added: 4.0.0
"""

EXAMPLES = """
- name: Use the Australian NTP pool, preferring the first server
  griffdawg.truenas.ntp:
    servers:
      - address: 0.au.pool.ntp.org
        prefer: true
      - address: 1.au.pool.ntp.org
      - address: 2.au.pool.ntp.org
    purge: true
"""

RETURN = """
servers:
  description:
    - The configured NTP servers after any changes.
  returned: success
  type: list
  elements: dict
created:
  description:
    - Addresses of servers that were (or would be) added.
  returned: always
  type: list
  elements: str
updated:
  description:
    - Addresses of servers whose settings were (or would be) changed.
  returned: always
  type: list
  elements: str
deleted:
  description:
    - Addresses of servers that were (or would be) removed.
  returned: always
  type: list
  elements: str
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW

SERVER_OPTIONS = ("burst", "iburst", "prefer", "minpoll", "maxpoll")


def main():
    module = AnsibleModule(
        argument_spec=dict(
            servers=dict(
                type="list",
                elements="dict",
                required=True,
                options=dict(
                    address=dict(type="str", required=True),
                    burst=dict(type="bool"),
                    iburst=dict(type="bool"),
                    prefer=dict(type="bool"),
                    minpoll=dict(type="int"),
                    maxpoll=dict(type="int"),
                ),
            ),
            purge=dict(type="bool", default=False),
            force=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, created=[], updated=[], deleted=[])

    mw = MW.client()

    try:
        existing = {s["address"]: s for s in mw.call("system.ntpserver.query")}
    except Exception as e:
        setup.fail(module, f"Error looking up NTP servers: {e}")

    wanted = set()
    for server in module.params["servers"]:
        address = server["address"]
        wanted.add(address)
        settings = {k: server[k] for k in SERVER_OPTIONS if server[k] is not None}

        current = existing.get(address)
        if current is None:
            result["created"].append(address)
            if not module.check_mode:
                arg = dict(settings, address=address, force=module.params["force"])
                try:
                    mw.call("system.ntpserver.create", arg)
                except Exception as e:
                    setup.fail(module, f"Error adding NTP server {address}: {e}", **result)
            continue

        arg = {k: v for k, v in settings.items() if current.get(k) != v}
        if arg:
            result["updated"].append(address)
            if not module.check_mode:
                try:
                    mw.call("system.ntpserver.update", current["id"], arg)
                except Exception as e:
                    setup.fail(module, f"Error updating NTP server {address}: {e}", **result)

    if module.params["purge"]:
        for address, current in existing.items():
            if address in wanted:
                continue
            result["deleted"].append(address)
            if not module.check_mode:
                try:
                    mw.call("system.ntpserver.delete", current["id"])
                except Exception as e:
                    setup.fail(module, f"Error deleting NTP server {address}: {e}", **result)

    result["changed"] = bool(result["created"] or result["updated"] or result["deleted"])

    if not module.check_mode:
        try:
            result["servers"] = mw.call("system.ntpserver.query")
        except Exception as e:
            setup.fail(module, f"Error looking up NTP servers: {e}", **result)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
