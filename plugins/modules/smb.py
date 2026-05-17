#!/usr/bin/python

# Configure the SMB service on TrueNAS.
#
# midclt call smb.config
# midclt call smb.update '{"workgroup": "WORKGROUP"}'

DOCUMENTATION = """
---
module: smb
short_description: Configure SMB service
description:
  - Configure the SMB/CIFS service settings on TrueNAS.
  - For managing individual SMB shares, use the C(sharing_smb) module.
  - For starting/stopping/enabling the service, use the C(service) module.
options:
  netbiosname:
    description:
      - NetBIOS name of the server.
    type: str
  netbiosalias:
    description:
      - List of NetBIOS aliases.
    type: list
    elements: str
  workgroup:
    description:
      - Windows workgroup or domain name.
    type: str
  description:
    description:
      - Server description string.
    type: str
  enable_smb1:
    description:
      - If true, enable SMB1 protocol support.
      - SMB1 is insecure and deprecated. Only enable if required by
        legacy clients.
    type: bool
  unixcharset:
    description:
      - Character set used for Unix filenames.
    type: str
  localmaster:
    description:
      - If true, the server will try to become the local master browser.
    type: bool
  syslog:
    description:
      - If true, use syslog for logging.
    type: bool
  aapl_extensions:
    description:
      - If true, enable Apple SMB2/3 protocol extensions.
    type: bool
  admin_group:
    description:
      - Group that has full admin privileges for SMB shares.
      - Set to null or empty string to disable.
    type: str
  guest:
    description:
      - Account to use for guest access.
    type: str
  filemask:
    description:
      - Default file creation mask.
      - Set to C(DEFAULT) to use the server default.
    type: str
  dirmask:
    description:
      - Default directory creation mask.
      - Set to C(DEFAULT) to use the server default.
    type: str
  ntlmv1_auth:
    description:
      - If true, allow NTLMv1 authentication.
      - NTLMv1 is insecure. Only enable if required by legacy clients.
    type: bool
  multichannel:
    description:
      - If true, enable SMB multichannel support.
    type: bool
  encryption:
    description:
      - SMB encryption mode.
    type: str
    choices: [ DEFAULT, NEGOTIATE, DESIRED, REQUIRED ]
  bindip:
    description:
      - List of IP addresses to listen on.
      - If empty, listen on all available addresses.
    type: list
    elements: str
  smb_options:
    description:
      - Additional smb.conf parameters, as a raw string.
    type: str
  debug:
    description:
      - If true, enable debug logging.
    type: bool
notes:
  - Supports C(check_mode).
seealso:
  - module: jdevera.truenas.sharing_smb
  - module: jdevera.truenas.service
version_added: 1.15.0
"""

EXAMPLES = """
- name: Set workgroup and description
  jdevera.truenas.smb:
    workgroup: MYWORKGROUP
    description: "File Server"

- name: Enable Apple extensions and multichannel
  jdevera.truenas.smb:
    aapl_extensions: true
    multichannel: true

- name: Require encryption
  jdevera.truenas.smb:
    encryption: REQUIRED
"""

RETURN = """
status:
  returned: always
  description:
    - The SMB service configuration after any changes.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW

FIELDS = {
    "netbiosname": "netbiosname",
    "netbiosalias": "netbiosalias",
    "workgroup": "workgroup",
    "description": "description",
    "enable_smb1": "enable_smb1",
    "unixcharset": "unixcharset",
    "localmaster": "localmaster",
    "syslog": "syslog",
    "aapl_extensions": "aapl_extensions",
    "admin_group": "admin_group",
    "guest": "guest",
    "filemask": "filemask",
    "dirmask": "dirmask",
    "ntlmv1_auth": "ntlmv1_auth",
    "multichannel": "multichannel",
    "encryption": "encryption",
    "bindip": "bindip",
    "smb_options": "smb_options",
    "debug": "debug",
}

SET_FIELDS = {"netbiosalias", "bindip"}


def main():
    module = AnsibleModule(
        argument_spec=dict(
            netbiosname=dict(type="str"),
            netbiosalias=dict(type="list", elements="str"),
            workgroup=dict(type="str"),
            description=dict(type="str"),
            enable_smb1=dict(type="bool"),
            unixcharset=dict(type="str"),
            localmaster=dict(type="bool"),
            syslog=dict(type="bool"),
            aapl_extensions=dict(type="bool"),
            admin_group=dict(type="str"),
            guest=dict(type="str"),
            filemask=dict(type="str"),
            dirmask=dict(type="str"),
            ntlmv1_auth=dict(type="bool"),
            multichannel=dict(type="bool"),
            encryption=dict(type="str", choices=["DEFAULT", "NEGOTIATE", "DESIRED", "REQUIRED"]),
            bindip=dict(type="list", elements="str"),
            smb_options=dict(type="str"),
            debug=dict(type="bool"),
        ),
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, msg="")

    mw = MW.client()

    try:
        smb_info = mw.call("smb.config")
    except Exception as e:
        module.fail_json(msg=f"Error looking up SMB configuration: {e}")

    result["status"] = smb_info

    arg = {}
    for param_name, api_field in FIELDS.items():
        value = module.params[param_name]
        if value is None:
            continue
        current = smb_info.get(api_field)
        if param_name in SET_FIELDS:
            if set(value) != set(current or []):
                arg[api_field] = value
        elif value != current:
            arg[api_field] = value

    if len(arg) == 0:
        result["changed"] = False
    else:
        if module.check_mode:
            result["msg"] = f"Would have updated SMB: {arg}"
        else:
            try:
                err = mw.call("smb.update", arg)
                result["status"] = err
            except Exception as e:
                module.fail_json(msg=f"Error updating SMB with {arg}: {e}")
        result["changed"] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
