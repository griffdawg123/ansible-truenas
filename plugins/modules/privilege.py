#!/usr/bin/python
# -*- coding: utf-8 -*-
__metaclass__ = type

# Manage privilege-to-group assignments on TrueNAS.
#
# Privileges like LOCAL_ADMINISTRATOR are built-in. This module assigns
# local groups to them via privilege.update with local_groups (list of GIDs).
#
# midclt call privilege.query
# midclt call privilege.update 1 '{"local_groups": [1000, 1001]}'

DOCUMENTATION = '''
---
module: privilege
short_description: Manage privilege group assignments
description:
  - Assign local groups to TrueNAS built-in privileges.
  - Privileges (e.g., LOCAL_ADMINISTRATOR, READONLY_ADMINISTRATOR,
    SHARING_ADMINISTRATOR) are built-in and cannot be created or deleted.
  - This module manages which local groups are assigned to a privilege.
options:
  name:
    description:
      - Name of the privilege.
      - Common values include C(LOCAL_ADMINISTRATOR),
        C(READONLY_ADMINISTRATOR), and C(SHARING_ADMINISTRATOR).
    type: str
    required: true
  groups:
    description:
      - List of local group names to assign to this privilege.
      - When I(append) is false (default), this replaces the full list of
        assigned groups.
      - When I(append) is true, groups are added to the existing assignments.
    type: list
    elements: str
    required: true
  append:
    description:
      - If true, add the listed groups to the privilege without removing
        existing group assignments.
      - If false (default), the listed groups replace all current assignments.
    type: bool
    default: false
seealso:
- module: arensb.truenas.group
author:
- Jacobo de Vera
notes:
- Supports C(check_mode)
version_added: 1.14.5
'''

EXAMPLES = '''
- name: Give the admins group full local admin privileges
  arensb.truenas.privilege:
    name: LOCAL_ADMINISTRATOR
    groups:
      - admins

- name: Add operators group to sharing admin without removing existing groups
  arensb.truenas.privilege:
    name: SHARING_ADMINISTRATOR
    groups:
      - operators
    append: true
'''

RETURN = '''
privilege:
  description:
    - The privilege data after the update.
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ..module_utils.middleware import MiddleWare as MW


def resolve_group_gids(mw, module, group_names):
    """Look up GIDs for a list of group names."""
    gids = []
    for name in group_names:
        try:
            result = mw.call("group.query",
                             [["group", "=", name]])
            if len(result) == 0:
                module.fail_json(msg=f"Group '{name}' not found")
            gids.append(result[0]['gid'])
        except Exception as e:
            module.fail_json(msg=f"Error looking up group '{name}': {e}")
    return gids


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            groups=dict(type='list', elements='str', required=True),
            append=dict(type='bool', default=False),
        ),
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    name = module.params['name']
    groups = module.params['groups']
    append = module.params['append']

    # Look up the privilege
    try:
        priv_info = mw.call("privilege.query",
                            [["name", "=", name]])
        if len(priv_info) == 0:
            module.fail_json(msg=f"Privilege '{name}' not found")
        priv_info = priv_info[0]
    except Exception as e:
        module.fail_json(msg=f"Error looking up privilege '{name}': {e}")

    # Resolve group names to GIDs
    wanted_gids = resolve_group_gids(mw, module, groups)

    # Determine the desired set of GIDs
    current_gids = set(priv_info.get('local_groups', []))
    if append:
        desired_gids = current_gids | set(wanted_gids)
    else:
        desired_gids = set(wanted_gids)

    if desired_gids == current_gids:
        result['changed'] = False
    else:
        if module.check_mode:
            result['msg'] = (f"Would have updated privilege {name}: "
                             f"local_groups {sorted(current_gids)} -> "
                             f"{sorted(desired_gids)}")
        else:
            try:
                err = mw.call("privilege.update",
                              priv_info['id'],
                              {"local_groups": sorted(desired_gids)})
                result['privilege'] = err
            except Exception as e:
                module.fail_json(
                    msg=f"Error updating privilege '{name}': {e}")
        result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
