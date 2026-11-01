#!/usr/bin/python

# Manage TrueNAS app runtime state (start, stop, upgrade).
#
# midclt call app.start "plex"
# midclt call app.stop "plex"
# midclt call app.upgrade "plex"

DOCUMENTATION = """
---
module: app_service
short_description: Manage app runtime state
description:
  - Start, stop, and upgrade TrueNAS apps.
  - For installing/configuring/removing apps, use the C(app) module.
options:
  name:
    description:
      - Name of the app.
    type: str
    required: true
  state:
    description:
      - Desired runtime state of the app.
      - C(started) ensures the app is running.
      - C(stopped) ensures the app is stopped.
      - C(redeployed) unconditionally redeploys the app.
      - C(upgraded) upgrades the app to the latest (or specified) version.
    type: str
    required: true
    choices: [ started, stopped, redeployed, upgraded ]
  app_version:
    description:
      - Target version when upgrading.
      - If not specified, upgrades to the latest available version.
      - Only used when C(state) is C(upgraded).
    type: str
  upgrade_values:
    description:
      - Configuration values to apply during the upgrade.
      - Only used when C(state) is C(upgraded).
    type: dict
  snapshot_hostpaths:
    description:
      - If true, snapshot host paths before upgrading.
      - Only used when C(state) is C(upgraded).
    type: bool
notes:
  - Supports C(check_mode).
  - All operations are jobs and may take some time.
seealso:
  - module: griffdawg.truenas.app
  - module: griffdawg.truenas.app_info
version_added: 1.15.0
"""

EXAMPLES = """
- name: Start an app
  griffdawg.truenas.app_service:
    name: plex
    state: started

- name: Stop an app
  griffdawg.truenas.app_service:
    name: plex
    state: stopped

- name: Upgrade to latest version
  griffdawg.truenas.app_service:
    name: plex
    state: upgraded

- name: Upgrade to a specific version
  griffdawg.truenas.app_service:
    name: plex
    state: upgraded
    app_version: "1.32.0"

- name: Redeploy an app
  griffdawg.truenas.app_service:
    name: plex
    state: redeployed
"""

RETURN = """
app:
  returned: always
  description:
    - The app data after the operation.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            state=dict(
                type="str", required=True, choices=["started", "stopped", "redeployed", "upgraded"]
            ),
            app_version=dict(type="str"),
            upgrade_values=dict(type="dict"),
            snapshot_hostpaths=dict(type="bool"),
        ),
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, msg="")

    mw = MW.client()

    name = module.params["name"]
    state = module.params["state"]

    # Look up the app
    try:
        apps = mw.call("app.query", [["name", "=", name]])
        if len(apps) == 0:
            module.fail_json(msg=f"App '{name}' not found")
        app_info = apps[0]
    except Exception as e:
        module.fail_json(msg=f"Error looking up app '{name}': {e}")

    if state == "started":
        if app_info["state"] == "RUNNING":
            result["changed"] = False
        else:
            if module.check_mode:
                result["msg"] = f"Would have started app {name}"
            else:
                try:
                    mw.job("app.start", name)
                except Exception as e:
                    module.fail_json(msg=f"Error starting app '{name}': {e}")
            result["changed"] = True

    elif state == "stopped":
        if app_info["state"] == "STOPPED":
            result["changed"] = False
        else:
            if module.check_mode:
                result["msg"] = f"Would have stopped app {name}"
            else:
                try:
                    mw.job("app.stop", name)
                except Exception as e:
                    module.fail_json(msg=f"Error stopping app '{name}': {e}")
            result["changed"] = True

    elif state == "redeployed":
        if module.check_mode:
            result["msg"] = f"Would have redeployed app {name}"
        else:
            try:
                mw.job("app.redeploy", name)
            except Exception as e:
                module.fail_json(msg=f"Error redeploying app '{name}': {e}")
        result["changed"] = True

    elif state == "upgraded":
        if not app_info.get("upgrade_available", False) and module.params["app_version"] is None:
            result["changed"] = False
        else:
            if module.check_mode:
                result["msg"] = f"Would have upgraded app {name}"
            else:
                try:
                    options = {}
                    if module.params["app_version"] is not None:
                        options["app_version"] = module.params["app_version"]
                    if module.params["upgrade_values"] is not None:
                        options["values"] = module.params["upgrade_values"]
                    if module.params["snapshot_hostpaths"] is not None:
                        options["snapshot_hostpaths"] = module.params["snapshot_hostpaths"]

                    err = mw.job("app.upgrade", name, options)
                    result["app"] = err
                except Exception as e:
                    module.fail_json(msg=f"Error upgrading app '{name}': {e}")
            result["changed"] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
