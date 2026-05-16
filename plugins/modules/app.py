#!/usr/bin/python

# Manage TrueNAS apps (install, configure, remove).
#
# midclt call app.query
# midclt call app.create '{"app_name": "plex", "catalog_app": "plex", "train": "stable"}'
# midclt call app.config "plex"
# midclt call app.update "plex" '{"values": {...}}'
# midclt call app.delete "plex"

DOCUMENTATION = '''
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
      - On update, these are merged with the existing configuration.
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
  - Supports C(check_mode).
  - App creation and deletion are jobs and may take some time.
seealso:
  - module: jdevera.truenas.app_service
  - module: jdevera.truenas.app_info
version_added: 1.15.0
'''

EXAMPLES = '''
- name: Install Plex from catalog
  jdevera.truenas.app:
    name: plex
    catalog_app: plex
    values:
      network:
        host_network: true

- name: Update Plex configuration
  jdevera.truenas.app:
    name: plex
    values:
      network:
        host_network: false

- name: Deploy a custom Docker Compose app
  jdevera.truenas.app:
    name: my-nginx
    custom_app: true
    custom_compose_config_string: |
      services:
        web:
          image: nginx:latest
          ports:
            - "8080:80"

- name: Remove an app and its data
  jdevera.truenas.app:
    name: plex
    state: absent
    remove_images: true
    remove_ix_volumes: true
'''

RETURN = '''
app:
  description:
    - The app data after creation or update.
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def main():
    setup.require_scale_min_version()

    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            state=dict(type='str', default='present',
                       choices=['present', 'absent']),
            catalog_app=dict(type='str'),
            train=dict(type='str', default='stable'),
            version=dict(type='str'),
            values=dict(type='dict'),
            custom_app=dict(type='bool', default=False),
            custom_compose_config=dict(type='dict'),
            custom_compose_config_string=dict(type='str'),
            remove_images=dict(type='bool', default=False),
            remove_ix_volumes=dict(type='bool', default=False),
            force_remove_ix_volumes=dict(type='bool', default=False),
        ),
        mutually_exclusive=[
            ['custom_compose_config', 'custom_compose_config_string'],
        ],
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    name = module.params['name']
    state = module.params['state']

    # Look up the app
    try:
        apps = mw.call("app.query",
                       [["name", "=", name]])
        if len(apps) == 0:
            app_info = None
        else:
            app_info = apps[0]
    except Exception as e:
        module.fail_json(msg=f"Error looking up app '{name}': {e}")

    if state == 'absent':
        if app_info is None:
            result['changed'] = False
        else:
            if module.check_mode:
                result['msg'] = f"Would have deleted app {name}"
            else:
                try:
                    options = {
                        "remove_images": module.params['remove_images'],
                        "remove_ix_volumes": module.params['remove_ix_volumes'],
                        "force_remove_ix_volumes":
                            module.params['force_remove_ix_volumes'],
                    }
                    mw.job("app.delete", name, options)
                except Exception as e:
                    module.fail_json(msg=f"Error deleting app '{name}': {e}")
            result['changed'] = True

    elif state == 'present':
        if app_info is None:
            # App doesn't exist — create it
            custom_app = module.params['custom_app']
            catalog_app = module.params['catalog_app']

            if not custom_app and catalog_app is None:
                module.fail_json(
                    msg="'catalog_app' is required when creating a "
                        "non-custom app")

            arg = {
                "app_name": name,
                "custom_app": custom_app,
            }

            if custom_app:
                compose_config = module.params['custom_compose_config']
                compose_string = module.params['custom_compose_config_string']
                if compose_config is not None:
                    arg['custom_compose_config'] = compose_config
                elif compose_string is not None:
                    arg['custom_compose_config_string'] = compose_string
            else:
                arg['catalog_app'] = catalog_app
                arg['train'] = module.params['train']
                if module.params['version'] is not None:
                    arg['version'] = module.params['version']

            if module.params['values'] is not None:
                arg['values'] = module.params['values']

            if module.check_mode:
                result['msg'] = f"Would have created app {name} with {arg}"
            else:
                try:
                    err = mw.job("app.create", arg)
                    result['app'] = err
                except Exception as e:
                    module.fail_json(
                        msg=f"Error creating app '{name}': {e}")
            result['changed'] = True

        else:
            # App exists — update if values are provided
            values = module.params['values']
            compose_config = module.params['custom_compose_config']
            compose_string = module.params['custom_compose_config_string']

            if values is None and compose_config is None \
               and compose_string is None:
                # Nothing to update
                result['changed'] = False
            else:
                # Check if values actually differ
                needs_update = False
                if values is not None:
                    try:
                        current_config = mw.call("app.config", name)
                    except Exception as e:
                        module.fail_json(
                            msg=f"Error getting config for '{name}': {e}")
                    # Check if any requested values differ from current
                    for key, val in values.items():
                        if current_config.get(key) != val:
                            needs_update = True
                            break
                else:
                    # Compose config changes — always update since we
                    # can't easily diff compose configs
                    needs_update = True

                if not needs_update:
                    result['changed'] = False
                else:
                    arg = {}
                    if values is not None:
                        arg['values'] = values
                    if compose_config is not None:
                        arg['custom_compose_config'] = compose_config
                    if compose_string is not None:
                        arg['custom_compose_config_string'] = compose_string

                    if module.check_mode:
                        result['msg'] = \
                            f"Would have updated app {name} with {arg}"
                    else:
                        try:
                            err = mw.job("app.update", name, arg)
                            result['app'] = err
                        except Exception as e:
                            module.fail_json(
                                msg=f"Error updating app '{name}': {e}")
                    result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
