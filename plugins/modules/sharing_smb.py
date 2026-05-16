#!/usr/bin/python

# Create and manage SMB shares.
# Updated for TrueNAS SCALE 25.10+ API where many fields moved under 'options'.

DOCUMENTATION = '''
---
module: sharing_smb
short_description: Manage SMB sharing
description:
  - Create, manage, and delete SMB shares.
  - Supports TrueNAS SCALE 25.10+ API format.
options:
  abe:
    description:
      - Enable Access Based Share Enumeration.
    type: bool
  acl:
    description:
      - When set, enables ACL support for the share.
    type: bool
  apple_encoding:
    description:
      - Use Apple-style character encoding.
      - By default, Samba uses a hashing algorithm for filename characters
        that are illegal in NTFS. This option causes it to translate such
        characters to the Unicode private range.
    type: bool
  auxsmbconf:
    description:
      - Additional smb4.conf options.
      - Only available when C(purpose) is C(LEGACY_SHARE).
    type: str
  browsable:
    description:
      - If true, share is visible when browsing shares.
    type: bool
  comment:
    description:
      - Description of the share, for the system maintainer.
    type: str
  durablehandle:
    description:
      - Enables using file handles that can withstand short disconnections.
      - Enables support for POSIX byte-range locks.
    type: bool
  enabled:
    description:
      - If true, the share is enabled. Otherwise, it is present but
        disabled.
    type: bool
  fsrvp:
    description:
      - Enable File Server Remote VSS Protocol (FSRVP).
      - This allows RPC clients to manage snapshots for the share.
    type: bool
  guestok:
    description:
      - Enables guest access (no login).
    type: bool
  hostsallow:
    description:
      - List of hostnames/IP addresses of hosts that are allowed access
        to the share.
      - If C(hostsallow) and C(hostsdeny) conflict, C(hostsallow) takes
        precedence.
    type: list
    elements: str
  home:
    description:
      - If true, this share may be used for home directories.
      - Only one such share is allowed.
      - In TrueNAS 25.10+, this translates to setting the share purpose
        to C(PRIVATE_DATASETS_SHARE). When I(home) is set, any explicit
        I(purpose) value is overridden.
    type: bool
  hostsdeny:
    description:
      - List of hostnames/IP addresses of hosts that are denied access
        to the share.
      - If C(hostsallow) and C(hostsdeny) conflict, C(hostsallow) takes
        precedence.
    type: list
    elements: str
  name:
    description:
      - Name of the share, as seen by the SMB client.
    type: str
    required: true
  path:
    description:
      - Directory to share, on the server.
    type: str
    required: true
  path_suffix:
    description:
      - Suffix appended to the share connection path. This may contain
        macros, as defined in smb.conf(5).
    type: str
  purpose:
    description:
      - |
        Specifies a family of configuration parameters for different use
        cases. Legal values include:
      - C(DEFAULT_SHARE), C(LEGACY_SHARE), C(TIMEMACHINE_SHARE),
        C(MULTIPROTOCOL_SHARE), C(TIME_LOCKED_SHARE), C(PRIVATE_DATASETS_SHARE),
        C(EXTERNAL_SHARE), C(VEEAM_REPOSITORY_SHARE), C(FCP_SHARE).
      - Note that the C(purpose) parameter may override other parameters.
        In particular, C(DEFAULT_SHARE) specifies an empty C(hostsallow)
        and C(hostsdeny).
  recyclebin:
    description:
      - |
        If true, enables Windows Recycle Bin: deleted files are moved to the
        Recycle Bin. If false, deleted files are immediately deleted.
    type: bool
  ro:
    description:
      - If true, share is read-only.
    type: bool
  shadowcopy:
    description:
      - When set, export ZFS snapshots as VSS shadow copies.
    type: bool
  state:
    description:
      - Whether the share should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  streams:
    description:
      - Allow multiple NTFS data streams.
    type: bool
  timemachine:
    description:
      - Enables support for Apple Time Machine backups.
    type: bool
version_added: 1.4.3
'''

EXAMPLES = '''
- name: Simple default share
  sharing_smb:
    name: export1
    path: /mnt/path1

- name: Share with host lists
  sharing_smb:
    name: export2
    path: /mnt/path2
    comment: "Shared to just a few hosts."
    purpose: DEFAULT_SHARE
    hostsallow:
      - host1.dom.ain
      - host2.dom.ain
      - 10.2.3.0/24
    hostsdeny:
      - ALL
'''

RETURN = '''
share:
  description:
    - A data structure describing a newly-created share.
  type: dict
status:
  description:
    - When this module exits abnormally, C(status) contains an error message.
  type: str
'''

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW

# Fields that are top-level in the 25.10+ API response.
# Maps Ansible param name -> API field name (when different).
TOP_LEVEL_FIELDS = {
    'name': 'name',
    'purpose': 'purpose',
    'enabled': 'enabled',
    'comment': 'comment',
    'ro': 'readonly',
    'browsable': 'browsable',
    'abe': 'access_based_share_enumeration',
}

# In 25.10+, 'home' is no longer a field — home shares are created by
# setting purpose to PRIVATE_DATASETS_SHARE.
HOME_PURPOSE = 'PRIVATE_DATASETS_SHARE'

# Fields that live under 'options' in the 25.10+ API response.
# Maps Ansible param name -> API field name (when different).
OPTIONS_FIELDS = {
    'hostsallow': 'hostsallow',
    'hostsdeny': 'hostsdeny',
    'path_suffix': 'path_suffix',
    'auxsmbconf': 'auxsmbconf',
    'guestok': 'guestok',
    'timemachine': 'timemachine',
    'recyclebin': 'recyclebin',
    'apple_encoding': 'aapl_name_mangling',
    'acl': 'acl',
    'durablehandle': 'durablehandle',
    'shadowcopy': 'shadowcopy',
    'streams': 'streams',
    'fsrvp': 'fsrvp',
}

# Fields where order doesn't matter (compare as sets)
SET_FIELDS = {'hostsallow', 'hostsdeny'}


def get_share_value(share_info, api_field, is_option):
    """Get a field value from the share_info response.

    In 25.10+, some fields are top-level while others are under 'options'.
    Fields under 'options' may be absent depending on the share's purpose.
    """
    if is_option:
        options = share_info.get('options', {})
        return options.get(api_field)
    return share_info.get(api_field)


def values_differ(param_value, current_value, param_name):
    """Check if a parameter value differs from the current share value."""
    if current_value is None:
        # Field not present in the response (e.g., purpose doesn't include it)
        return False
    if param_name in SET_FIELDS:
        return set(param_value) != set(current_value)
    return param_value != current_value


def main():
    setup.require_scale_min_version()

    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type='str', required=True),
            name=dict(type='str', required=True),
            state=dict(type='str', default='present',
                       choices=['absent', 'present']),
            purpose=dict(type='str',
                         choices=['DEFAULT_SHARE', 'LEGACY_SHARE',
                                  'TIMEMACHINE_SHARE', 'MULTIPROTOCOL_SHARE',
                                  'TIME_LOCKED_SHARE', 'PRIVATE_DATASETS_SHARE',
                                  'EXTERNAL_SHARE', 'VEEAM_REPOSITORY_SHARE',
                                  'FCP_SHARE']),
            hostsallow=dict(type='list', elements='str'),
            hostsdeny=dict(type='list', elements='str'),
            enabled=dict(type='bool'),
            path_suffix=dict(type='str'),
            comment=dict(type='str'),
            auxsmbconf=dict(type='str'),
            home=dict(type='bool'),
            ro=dict(type='bool'),
            browsable=dict(type='bool'),
            timemachine=dict(type='bool'),
            recyclebin=dict(type='bool'),
            guestok=dict(type='bool'),
            abe=dict(type='bool'),
            apple_encoding=dict(type='bool'),
            acl=dict(type='bool'),
            durablehandle=dict(type='bool'),
            shadowcopy=dict(type='bool'),
            streams=dict(type='bool'),
            fsrvp=dict(type='bool'),
            ),
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    name = module.params['name']
    path = module.params['path']
    state = module.params['state']

    # Look up the share
    try:
        share_info = mw.call("sharing.smb.query",
                             [["path", "=", path]])
        if len(share_info) == 0:
            share_info = None
        else:
            share_info = share_info[0]
    except Exception as e:
        module.fail_json(msg=f"Error looking up share {name}: {e}")

    if share_info is None:
        # Share doesn't exist

        if state == 'present':
            # Build arguments for sharing.smb.create()
            arg = {
                "path": path,
                "name": name,
            }
            options = {}

            for param_name, api_field in TOP_LEVEL_FIELDS.items():
                value = module.params[param_name]
                if value is not None:
                    arg[api_field] = value

            for param_name, api_field in OPTIONS_FIELDS.items():
                value = module.params[param_name]
                if value is not None:
                    options[api_field] = value

            # home: true translates to purpose: PRIVATE_DATASETS_SHARE
            if module.params['home']:
                arg['purpose'] = HOME_PURPOSE

            if options:
                arg['options'] = options
                # 25.10+ API requires 'purpose' when 'options' is set
                if 'purpose' not in arg:
                    arg['purpose'] = 'DEFAULT_SHARE'

            if module.check_mode:
                result['msg'] = f"Would have created share {name} with {arg}"
            else:
                try:
                    err = mw.call("sharing.smb.create", arg)
                    result['share'] = err
                except Exception as e:
                    result['failed_invocation'] = arg
                    module.fail_json(msg=f"Error creating share {name}: {e}")

            result['changed'] = True
        else:
            result['changed'] = False

    else:
        # Share exists
        if state == 'present':
            # Build list of differences
            arg = {}
            options = {}

            # Check top-level fields
            for param_name, api_field in TOP_LEVEL_FIELDS.items():
                value = module.params[param_name]
                if value is not None:
                    current = get_share_value(share_info, api_field, False)
                    if values_differ(value, current, param_name):
                        arg[api_field] = value

            # Check options fields
            for param_name, api_field in OPTIONS_FIELDS.items():
                value = module.params[param_name]
                if value is not None:
                    current = get_share_value(share_info, api_field, True)
                    if values_differ(value, current, param_name):
                        options[api_field] = value

            # home: true translates to purpose: PRIVATE_DATASETS_SHARE
            home = module.params['home']
            if home is not None:
                current_is_home = share_info.get('purpose') == HOME_PURPOSE
                if home and not current_is_home:
                    arg['purpose'] = HOME_PURPOSE
                elif not home and current_is_home:
                    arg['purpose'] = 'DEFAULT_SHARE'

            if options:
                arg['options'] = options
                # 25.10+ API requires 'purpose' when 'options' is set.
                # Carry forward the existing purpose if not explicitly changed.
                if 'purpose' not in arg:
                    arg['purpose'] = share_info.get('purpose', 'DEFAULT_SHARE')

            if len(arg) == 0:
                result['changed'] = False
            else:
                if module.check_mode:
                    result['msg'] = f"Would have updated share {name}: {arg}"
                else:
                    try:
                        err = mw.call("sharing.smb.update",
                                      share_info['id'],
                                      arg)
                    except Exception as e:
                        module.fail_json(msg=f"Error updating share {name} with {arg}: {e}")
                result['changed'] = True
        else:
            # Share is not supposed to exist
            if module.check_mode:
                result['msg'] = f"Would have deleted share {name}"
            else:
                try:
                    err = mw.call("sharing.smb.delete",
                                  share_info['id'])
                except Exception as e:
                    module.fail_json(msg=f"Error deleting share {name}: {e}")
            result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
