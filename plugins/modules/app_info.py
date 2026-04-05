#!/usr/bin/python
# -*- coding: utf-8 -*-
__metaclass__ = type

# Query TrueNAS app information.
#
# midclt call app.query
# midclt call app.available
# midclt call app.config "plex"

DOCUMENTATION = '''
---
module: app_info
short_description: Gather information about apps
description:
  - Query installed apps and available catalog apps on TrueNAS.
  - This is a read-only info module.
options:
  name:
    description:
      - Name of a specific installed app to query.
      - Returns detailed info including current configuration.
      - Mutually exclusive with C(available).
    type: str
  available:
    description:
      - If true, list available apps from the catalog instead of
        installed apps.
      - Mutually exclusive with C(name).
    type: bool
    default: false
notes:
  - Supports C(check_mode).
seealso:
  - module: arensb.truenas.app
  - module: arensb.truenas.app_service
version_added: 1.15.0
'''

EXAMPLES = '''
- name: List all installed apps
  arensb.truenas.app_info:
  register: installed

- name: Show installed app names and states
  debug:
    msg: "{{ item.name }} - {{ item.state }}"
  loop: "{{ installed.apps }}"

- name: Get details for a specific app
  arensb.truenas.app_info:
    name: plex
  register: plex_info

- name: List available catalog apps
  arensb.truenas.app_info:
    available: true
  register: catalog
'''

RETURN = '''
apps:
  description:
    - List of app objects (installed or available).
  type: list
  elements: dict
  returned: when querying installed apps or available apps
config:
  description:
    - Configuration values for a specific installed app.
  type: dict
  returned: when C(name) is specified
'''

from ansible.module_utils.basic import AnsibleModule
from ..module_utils.middleware import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str'),
            available=dict(type='bool', default=False),
        ),
        mutually_exclusive=[
            ['name', 'available'],
        ],
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
    )

    mw = MW.client()

    name = module.params['name']
    available = module.params['available']

    try:
        if available:
            result['apps'] = mw.call("app.available")
        elif name is not None:
            apps = mw.call("app.query",
                           [["name", "=", name]])
            if len(apps) == 0:
                module.fail_json(msg=f"App '{name}' not found")
            result['apps'] = apps
            # Also fetch the app's config values
            try:
                result['config'] = mw.call("app.config", name)
            except Exception:
                pass
        else:
            result['apps'] = mw.call("app.query")
    except Exception as e:
        module.fail_json(msg=f"Error querying apps: {e}")

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
