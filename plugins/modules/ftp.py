#!/usr/bin/python

# Configure the FTP service on TrueNAS.
#
# midclt call ftp.config
# midclt call ftp.update '{"onlyanonymous": false}'

DOCUMENTATION = '''
---
module: ftp
short_description: Configure FTP service
description:
  - Configure the FTP daemon service settings on TrueNAS.
  - For starting/stopping/enabling the service, use the C(service) module.
options:
  onlyanonymous:
    description:
      - If true, allow only anonymous logins.
    type: bool
  onlylocal:
    description:
      - If true, allow only local user logins.
    type: bool
  defaultroot:
    description:
      - If true, jail all logged-in users to their home directory.
      - For per-group jailing, leave this false and use I(options) with a
        ProFTPD C(DefaultRoot) directive.
    type: bool
  filemask:
    description:
      - Octal umask applied to newly uploaded files (e.g., C("022")).
    type: str
  dirmask:
    description:
      - Octal umask applied to newly created directories (e.g., C("022")).
    type: str
  options:
    description:
      - Additional ProFTPD configuration directives, as a raw string.
    type: str
notes:
  - Supports C(check_mode).
  - "On TrueNAS SCALE 25.10 the C(ftp.update) API exposes additional
    fields not yet supported by this module. They can be added on
    demand:"
  - "Connection limits: C(port), C(clients), C(ipconnections),
    C(loginattempt), C(timeout), C(timeout_notransfer)."
  - "Anonymous / banner: C(anonpath), C(banner)."
  - "Transfer features: C(fxp), C(resume), C(ident), C(reversedns)."
  - "Passive / NAT: C(masqaddress), C(passiveportsmin),
    C(passiveportsmax)."
  - "Bandwidth: C(localuserbw), C(localuserdlbw), C(anonuserbw),
    C(anonuserdlbw)."
  - "TLS: C(tls), C(tls_policy), C(ssltls_certificate), and the
    C(tls_opt_*) booleans."
seealso:
  - module: jdevera.truenas.service
version_added: 1.15.0
'''

EXAMPLES = '''
- name: Allow only local users and set umasks
  jdevera.truenas.ftp:
    onlyanonymous: false
    onlylocal: true
    filemask: "002"
    dirmask: "002"

- name: Jail one group to a specific directory via ProFTPD options
  jdevera.truenas.ftp:
    defaultroot: false
    options: "DefaultRoot /mnt/tank/documents scanner"
'''

RETURN = '''
status:
  returned: always
  description:
    - The FTP service configuration after any changes.
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW

# Maps Ansible param name -> API field name.
FIELDS = {
    'onlyanonymous': 'onlyanonymous',
    'onlylocal': 'onlylocal',
    'defaultroot': 'defaultroot',
    'filemask': 'filemask',
    'dirmask': 'dirmask',
    'options': 'options',
}

# Fields where order doesn't matter (compare as sets).
SET_FIELDS: set[str] = set()


def main():
    module = AnsibleModule(
        argument_spec=dict(
            onlyanonymous=dict(type='bool'),
            onlylocal=dict(type='bool'),
            defaultroot=dict(type='bool'),
            filemask=dict(type='str'),
            dirmask=dict(type='str'),
            options=dict(type='str'),
        ),
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    try:
        ftp_info = mw.call("ftp.config")
    except Exception as e:
        module.fail_json(msg=f"Error looking up FTP configuration: {e}")

    result['status'] = ftp_info

    arg = {}
    for param_name, api_field in FIELDS.items():
        value = module.params[param_name]
        if value is None:
            continue
        current = ftp_info.get(api_field)
        if param_name in SET_FIELDS:
            if set(value) != set(current or []):
                arg[api_field] = value
        elif value != current:
            arg[api_field] = value

    if len(arg) == 0:
        result['changed'] = False
    else:
        if module.check_mode:
            result['msg'] = f"Would have updated FTP: {arg}"
        else:
            try:
                err = mw.call("ftp.update", arg)
                result['status'] = err
            except Exception as e:
                module.fail_json(msg=f"Error updating FTP with {arg}: {e}")
        result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
