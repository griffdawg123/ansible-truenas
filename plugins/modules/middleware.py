#!/usr/bin/python

# Call an arbitrary middleware method. An escape hatch for things that
# don't have a dedicated module yet.
#
# Equivalent to:
# midclt call <method> <args...>
# midclt call -j <method> <args...>

DOCUMENTATION = """
---
module: middleware
short_description: Call a TrueNAS middleware method directly
description:
  - Call any middleware API method, optionally as a job, and return its
    result.
  - Intended as an escape hatch for functionality that doesn't have a
    dedicated module. Prefer a dedicated module when one exists, since
    those compare current and desired state.
options:
  method:
    description:
      - Name of the middleware method, e.g. C(system.general.config) or
        C(app.redeploy).
    type: str
    required: true
  args:
    description:
      - Positional arguments to pass to the method, in order.
    type: list
    elements: raw
    default: []
  job:
    description:
      - Run the method as a job and wait for it to finish. Required for
        methods that are jobs, such as C(app.create) or
        C(pool.dataset.lock).
    type: bool
    default: false
  read_only:
    description:
      - Declare that the method doesn't change anything (e.g. a
        C(.query) or C(.config) method).
      - Read-only calls report C(changed=false) and also run in check
        mode. Other calls report C(changed=true) and are skipped in
        check mode; use C(changed_when) to refine that.
    type: bool
    default: false
notes:
  - Supports C(check_mode) for calls marked C(read_only).
version_added: 4.0.0
"""

EXAMPLES = """
- name: Read the general system config
  griffdawg.truenas.middleware:
    method: system.general.config
    read_only: true
  register: general

- name: List running apps
  griffdawg.truenas.middleware:
    method: app.query
    args:
      - [["state", "=", "RUNNING"]]
      - select: [name, version]
    read_only: true

- name: Redeploy an app
  griffdawg.truenas.middleware:
    method: app.redeploy
    args: [jellyfin]
    job: true
"""

RETURN = """
result:
  description:
    - The method's return value (for a job, the job's result).
  returned: success, unless skipped in check mode
  type: raw
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            method=dict(type="str", required=True),
            args=dict(type="list", elements="raw", default=[]),
            job=dict(type="bool", default=False),
            read_only=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    method = module.params["method"]
    args = module.params["args"]
    read_only = module.params["read_only"]

    result = dict(changed=not read_only)

    if module.check_mode and not read_only:
        result["msg"] = f"Would have called {method}"
        module.exit_json(**result)

    mw = MW.client()

    try:
        if module.params["job"]:
            result["result"] = mw.job(method, *args)
        else:
            result["result"] = mw.call(method, *args)
    except Exception as e:
        setup.fail(module, f"Error calling {method}: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
