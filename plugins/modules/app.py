#!/usr/bin/python

# Manage TrueNAS apps (install, configure, remove).
#
# midclt call app.query
# midclt call app.create '{"app_name": "plex", "catalog_app": "plex", "train": "stable"}'
# midclt call app.config "plex"
# midclt call app.update "plex" '{"values": {...}}'
# midclt call app.delete "plex"

DOCUMENTATION = """
---
module: app
short_description: Manage TrueNAS apps
description:
  - Install, configure, and remove apps on TrueNAS.
  - Supports both catalog apps and custom apps (Docker Compose).
  - For starting/stopping/upgrading apps, use the C(app_service) module.
options:
  name:
    description:
      - Name of the app.
      - Must be lowercase alphanumeric with optional hyphens, starting
        with a letter.
    type: str
    required: true
  state:
    description:
      - Whether the app should be present or absent.
    type: str
    choices: [ present, absent ]
    default: present
  catalog_app:
    description:
      - Name of the catalog app to install (e.g., C(plex), C(pihole)).
      - Required when creating a new catalog app.
      - Ignored when C(custom_app) is true or when updating an existing app.
    type: str
  train:
    description:
      - Catalog train to install from.
    type: str
    default: stable
  version:
    description:
      - Specific version to install.
      - If not specified, the latest version is installed.
    type: str
  values:
    description:
      - Configuration values for the app.
      - These are app-specific and vary per catalog app.
      - On create, these are the initial configuration.
      - On update, the app is only updated if some key given here differs
        from the stored config (nested dicts are compared key by key;
        keys you don't give are ignored).
      - Middleware merges C(values) into the stored config at the top
        level only, so a nested dict given here replaces that whole
        section, and its omitted keys revert to the app's defaults.
      - Only valid for catalog apps.
    type: dict
  custom_app:
    description:
      - If true, create a custom app using Docker Compose instead of
        installing from the catalog.
    type: bool
    default: false
  custom_compose_config:
    description:
      - Docker Compose configuration as a dict for custom apps.
      - Mutually exclusive with C(custom_compose_config_string).
    type: dict
  custom_compose_config_string:
    description:
      - Docker Compose configuration as a YAML string for custom apps.
      - Mutually exclusive with C(custom_compose_config).
    type: str
  remove_images:
    description:
      - When removing an app, also remove its container images.
    type: bool
    default: false
  remove_ix_volumes:
    description:
      - When removing an app, also remove its ix-volumes data.
    type: bool
    default: false
  force_remove_ix_volumes:
    description:
      - Force removal of ix-volumes even if they are in use.
    type: bool
    default: false
notes:
  - Supports C(check_mode) and C(diff_mode).
  - Every C(app.update) recreates the app's containers, so the module
    compares before updating. For custom apps the requested compose is
    parsed and compared as data with the stored compose, so formatting
    and key order don't cause spurious updates.
  - App creation and deletion are jobs and may take some time.
seealso:
  - module: griffdawg.truenas.app_service
  - module: griffdawg.truenas.app_info
version_added: 1.15.0
"""

EXAMPLES = """
- name: Install Plex from catalog
  griffdawg.truenas.app:
    name: plex
    catalog_app: plex
    values:
      network:
        host_network: true

- name: Update Plex configuration
  griffdawg.truenas.app:
    name: plex
    values:
      network:
        host_network: false

- name: Deploy a custom Docker Compose app
  griffdawg.truenas.app:
    name: my-nginx
    custom_app: true
    custom_compose_config_string: |
      services:
        web:
          image: nginx:latest
          ports:
            - "8080:80"

- name: Remove an app and its data
  griffdawg.truenas.app:
    name: plex
    state: absent
    remove_images: true
    remove_ix_volumes: true
"""

RETURN = """
app:
  returned: always
  description:
    - The app data after creation or update.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.yaml import HAS_YAML, yaml_load

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def subset_matches(desired, current):
    """
    Return True if every key in 'desired' has the same value in
    'current', recursing into dicts. Catalog app configs are full of
    defaults the caller never set; those are ignored.
    """
    if isinstance(desired, dict):
        if not isinstance(current, dict):
            return False
        return all(k in current and subset_matches(v, current[k]) for k, v in desired.items())
    return desired == current


def desired_compose(module):
    """
    Return the requested compose config as a dict, or None if neither
    compose option was given. Middleware stores the parsed YAML, so
    comparing dicts ignores formatting and key order.
    """
    if module.params["custom_compose_config"] is not None:
        return module.params["custom_compose_config"]
    compose_string = module.params["custom_compose_config_string"]
    if compose_string is None:
        return None
    if not HAS_YAML:
        setup.fail(module, "PyYAML is required to parse custom_compose_config_string")
    try:
        compose = yaml_load(compose_string)
    except Exception as e:
        setup.fail(module, f"custom_compose_config_string is not valid YAML: {e}")
    if not isinstance(compose, dict):
        setup.fail(module, "custom_compose_config_string must be a YAML mapping")
    return compose


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            state=dict(type="str", default="present", choices=["present", "absent"]),
            catalog_app=dict(type="str"),
            train=dict(type="str", default="stable"),
            version=dict(type="str"),
            values=dict(type="dict"),
            custom_app=dict(type="bool", default=False),
            custom_compose_config=dict(type="dict"),
            custom_compose_config_string=dict(type="str"),
            remove_images=dict(type="bool", default=False),
            remove_ix_volumes=dict(type="bool", default=False),
            force_remove_ix_volumes=dict(type="bool", default=False),
        ),
        mutually_exclusive=[
            ["custom_compose_config", "custom_compose_config_string"],
        ],
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
            app_info = None
        else:
            app_info = apps[0]
    except Exception as e:
        setup.fail(module, f"Error looking up app '{name}': {e}")

    if state == "absent":
        if app_info is None:
            result["changed"] = False
        else:
            if module.check_mode:
                result["msg"] = f"Would have deleted app {name}"
            else:
                try:
                    options = {
                        "remove_images": module.params["remove_images"],
                        "remove_ix_volumes": module.params["remove_ix_volumes"],
                        "force_remove_ix_volumes": module.params["force_remove_ix_volumes"],
                    }
                    mw.job("app.delete", name, options)
                except Exception as e:
                    setup.fail(module, f"Error deleting app '{name}': {e}")
            result["changed"] = True

    elif state == "present":
        if app_info is None:
            # App doesn't exist — create it
            custom_app = module.params["custom_app"]
            catalog_app = module.params["catalog_app"]

            if not custom_app and catalog_app is None:
                setup.fail(module, "'catalog_app' is required when creating a non-custom app")

            arg = {
                "app_name": name,
                "custom_app": custom_app,
            }

            if custom_app:
                compose = desired_compose(module)
                if compose is None:
                    setup.fail(module, "A compose config is required when creating a custom app")
                arg["custom_compose_config"] = compose
            else:
                arg["catalog_app"] = catalog_app
                arg["train"] = module.params["train"]
                if module.params["version"] is not None:
                    arg["version"] = module.params["version"]

            if module.params["values"] is not None:
                arg["values"] = module.params["values"]

            if module.check_mode:
                result["msg"] = f"Would have created app {name} with {arg}"
            else:
                try:
                    err = mw.job("app.create", arg)
                    result["app"] = err
                except Exception as e:
                    setup.fail(module, f"Error creating app '{name}': {e}")
            result["changed"] = True

        else:
            # App exists. Compare what was asked for with the stored
            # config and only update if they differ: every app.update
            # re-runs 'compose up --force-recreate', restarting the app.
            values = module.params["values"]
            compose = desired_compose(module)

            if values is None and compose is None:
                result["changed"] = False
            else:
                if compose is not None and not app_info["custom_app"]:
                    setup.fail(module, f"App '{name}' is a catalog app; it has no compose config")
                if values is not None and app_info["custom_app"]:
                    setup.fail(module, f"App '{name}' is a custom app; use custom_compose_config")

                try:
                    current_config = mw.call("app.config", name)
                except Exception as e:
                    setup.fail(module, f"Error getting config for '{name}': {e}")

                if compose is not None:
                    needs_update = compose != current_config
                    arg = {"custom_compose_config": compose}
                    after = compose
                else:
                    needs_update = not subset_matches(values, current_config)
                    arg = {"values": values}
                    after = {**current_config, **values}

                if module._diff:
                    result["diff"] = dict(before=current_config, after=after)

                if not needs_update:
                    result["changed"] = False
                else:
                    if module.check_mode:
                        result["msg"] = f"Would have updated app {name}"
                    else:
                        try:
                            result["app"] = mw.job("app.update", name, arg)
                        except Exception as e:
                            setup.fail(module, f"Error updating app '{name}': {e}")
                    result["changed"] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
