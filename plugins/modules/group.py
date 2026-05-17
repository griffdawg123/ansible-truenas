#!/usr/bin/python

# Create and manage groups.
#
# midclt call group.query '[["group","=","wheel"]]'
# midclt call group.query '[["gid","=",0]]'
# midclt call group.query '[["builtin","=",false]]'

DOCUMENTATION = '''
---
module: group
short_description: Manage groups
description:
  - Create, destroy, and manage groups on a TrueNAS host.
options:
  name:
    description:
      - Name of the group to manage.
    type: str
    required: true
  gid:
    description:
      - Optional I(GID) to set for the group
    type: int
  state:
    description:
      - Whether the group should be present or not.
    type: str
    choices: [ absent, present ]
    default: present
  sudo_commands:
    description:
      - List of commands this group can run with sudo.
      - Use C(ALL) to allow all commands.
    type: list
    elements: str
  sudo_commands_nopasswd:
    description:
      - List of commands this group can run with sudo without a password.
      - Use C(ALL) to allow all commands without a password.
    type: list
    elements: str
seealso:
- module: ansible.builtin.group
author:
- Andrew Arensburger (@arensb)
notes:
- Supports C(check_mode)
version_added: 0.1.0
'''

EXAMPLES = '''
- name: Make sure group "mygroup" exists
  jdevera.truenas.group:
    name: mygroup

- name: Make sure group "badgroup" is gone
  jdevera.truenas.group:
    name: badgroup
    state: absent

- name: Group with sudo access
  jdevera.truenas.group:
    name: admins
    sudo_commands:
      - ALL
    sudo_commands_nopasswd:
      - /usr/bin/apt
'''

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            gid=dict(type='int'),
            name=dict(type='str', required=True),

            sudo_commands=dict(type='list', elements='str'),
            sudo_commands_nopasswd=dict(type='list', elements='str', no_log=False),

            state=dict(type='str', default='present',
                       choices=['absent', 'present'])
        ),
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    # Assign variables from properties, for convenience
    gid = module.params['gid']
    group = module.params['name']
    state = module.params['state']
    sudo_commands = module.params['sudo_commands']
    sudo_commands_nopasswd = module.params['sudo_commands_nopasswd']

    # Look up the group.
    # group.query returns an array of objects like:
    # {
    #    "builtin": false,
    #    "gid": 1000,
    #    "group": "mygroup",
    #    "id": 123,
    #    "id_type_both": false,
    #    "local": true,
    #    "smb": true,
    #    "sudo": false,
    #    "sudo_commands": [],
    #    "sudo_nopasswd": false,
    #    "users": [
    #        456
    #    ]
    # },
    try:
        group_info = mw.call("group.query",
                             [["group", "=", group]])
        # group_info is an array. We specified a "group=<name>"
        # filter, so we'll get either 0 or 1 elements back.
        if len(group_info) == 0:
            # No such group
            group_info = None
        else:
            # Group exists
            group_info = group_info[0]
    except Exception as e:
        module.fail_json(msg=f"Error looking up group {group}: {e.stderr}")

    # XXX - Mostly for debugging:
    result['group_info'] = group_info

    if group_info is None:
        # The group doesn't exist
        if state == 'present':
            # The group is supposed to exist

            # Assemble arguments
            arg = {"name": group}

            if gid is not None:
                arg['gid'] = gid

            if sudo_commands is not None:
                arg['sudo_commands'] = sudo_commands

            if sudo_commands_nopasswd is not None:
                arg['sudo_commands_nopasswd'] = sudo_commands_nopasswd

            if module.check_mode:
                result['msg'] = f"Would have created group {group} with {arg}"
            else:
                try:
                    err = mw.call("group.create", arg)

                    # XXX - Maybe rerun "group.info" and get fresh
                    # info? Or at least update group_info with what's
                    # currently in 'err'
                    result['msg'] = err
                except Exception as e:
                    module.fail_json(msg=f"Error creating group {group}: {e}")

                result['msg'] = err

            result['changed'] = True
        else:
            # The group isn't supposed to exist.
            result['changed'] = False

    else:
        # The group exists
        if state == 'present':
            # The group is supposed to exist.
            #
            # compare 'group_info' to the module parameters and see if
            # anything needs to change.

            # Build up arguments to pass to group.update.
            arg = {}

            # gid
            if gid is not None and group_info['gid'] != gid:
                arg['gid'] = gid

            if sudo_commands is not None and \
               set(group_info.get('sudo_commands', [])) != set(sudo_commands):
                arg['sudo_commands'] = sudo_commands

            if sudo_commands_nopasswd is not None and \
               set(group_info.get('sudo_commands_nopasswd', [])) != set(sudo_commands_nopasswd):
                arg['sudo_commands_nopasswd'] = sudo_commands_nopasswd

            if len(arg) == 0:
                # Nothing to do
                result['changed'] = False
            else:
                # Something has changed.

                if module.check_mode:
                    result['msg'] = f"Would have updated group {group}: {arg}"
                else:
                    try:
                        err = mw.call("group.update",
                                      group_info['id'],
                                      arg)
                    except Exception as e:
                        # XXX
                        module.fail_json(msg=f"Error updating group {group}: {e}")
                result['changed'] = True
        else:
            # The group isn't supposed to exist.
            if module.check_mode:
                result['msg'] = "Would have deleted group {group}"
            else:
                # The id, here, is not the Unix GID. It's a unique
                # identifier in TrueNAS's own database. Two groups
                # with different names can have the same gid, but will
                # always have different id.

                # XXX - There's another optional parameter saying to
                # delete all users who have this as their primary
                # group. But that's dangerous, so let's not implement
                # it until needed.
                err = mw.call("group.delete",
                              group_info['id'],
                              )
                result['msg'] = err
            result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
