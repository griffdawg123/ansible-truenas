#!/usr/bin/python
# -*- coding: utf-8 -*-
__metaclass__ = type

# Configure TrueNAS general system settings.
#
# midclt call system.general.config
# midclt call system.general.update '{"timezone": "UTC"}'

DOCUMENTATION = '''
---
module: system_general
short_description: Configure general system settings
description:
  - Configure general system settings on TrueNAS, including UI ports,
    HTTPS settings, timezone, and keyboard layout.
options:
  ui_port:
    description:
      - HTTP port for the web UI.
    type: int
  ui_httpsport:
    description:
      - HTTPS port for the web UI.
    type: int
  ui_httpsredirect:
    description:
      - If true, redirect HTTP to HTTPS.
    type: bool
  ui_httpsprotocols:
    description:
      - List of TLS protocol versions to allow.
    type: list
    elements: str
  ui_address:
    description:
      - List of IPv4 addresses the web UI listens on.
      - Use C(0.0.0.0) to listen on all addresses.
    type: list
    elements: str
  ui_v6address:
    description:
      - List of IPv6 addresses the web UI listens on.
      - Use C(::) to listen on all addresses.
    type: list
    elements: str
  ui_allowlist:
    description:
      - List of IP addresses/networks allowed to access the UI.
      - Empty list means no restrictions.
    type: list
    elements: str
  ui_consolemsg:
    description:
      - If true, show console messages in the UI footer.
    type: bool
  ui_x_frame_options:
    description:
      - X-Frame-Options header for the web UI.
    type: str
    choices: [ SAMEORIGIN, DENY, ALLOW_ALL ]
  kbdmap:
    description:
      - Keyboard layout map (e.g., C(us), C(uk), C(de)).
    type: str
  timezone:
    description:
      - System timezone (e.g., C(UTC), C(America/New_York)).
    type: str
  usage_collection:
    description:
      - If true, allow anonymous usage statistics collection.
    type: bool
  ui_certificate:
    description:
      - Name of the SSL certificate to use for the web UI.
      - The certificate must already exist on the system (see the
        C(certificate) module).
    type: str
  ds_auth:
    description:
      - If true, enable directory service authentication for the UI.
    type: bool
notes:
  - Supports C(check_mode).
version_added: 1.15.0
'''

EXAMPLES = '''
- name: Set timezone and keyboard layout
  arensb.truenas.system_general:
    timezone: America/New_York
    kbdmap: us

- name: Configure HTTPS only on port 443
  arensb.truenas.system_general:
    ui_httpsport: 443
    ui_httpsredirect: true
    ui_httpsprotocols:
      - TLSv1.2
      - TLSv1.3

- name: Restrict UI access to a subnet
  arensb.truenas.system_general:
    ui_allowlist:
      - 10.0.0.0/24

- name: Set the web UI SSL certificate
  arensb.truenas.system_general:
    ui_certificate: my_custom_cert
'''

RETURN = '''
status:
  description:
    - The system general configuration after any changes.
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ..module_utils.middleware import MiddleWare as MW
from ..module_utils import setup


FIELDS = {
    'ui_port': 'ui_port',
    'ui_httpsport': 'ui_httpsport',
    'ui_httpsredirect': 'ui_httpsredirect',
    'ui_httpsprotocols': 'ui_httpsprotocols',
    'ui_address': 'ui_address',
    'ui_v6address': 'ui_v6address',
    'ui_allowlist': 'ui_allowlist',
    'ui_consolemsg': 'ui_consolemsg',
    'ui_x_frame_options': 'ui_x_frame_options',
    'kbdmap': 'kbdmap',
    'timezone': 'timezone',
    'usage_collection': 'usage_collection',
    'ds_auth': 'ds_auth',
}

SET_FIELDS = {'ui_httpsprotocols', 'ui_address', 'ui_v6address', 'ui_allowlist'}


def main():
    setup.require_scale_min_version()

    module = AnsibleModule(
        argument_spec=dict(
            ui_port=dict(type='int'),
            ui_httpsport=dict(type='int'),
            ui_httpsredirect=dict(type='bool'),
            ui_httpsprotocols=dict(type='list', elements='str'),
            ui_address=dict(type='list', elements='str'),
            ui_v6address=dict(type='list', elements='str'),
            ui_allowlist=dict(type='list', elements='str'),
            ui_consolemsg=dict(type='bool'),
            ui_x_frame_options=dict(type='str',
                                    choices=['SAMEORIGIN', 'DENY',
                                             'ALLOW_ALL']),
            kbdmap=dict(type='str'),
            timezone=dict(type='str'),
            usage_collection=dict(type='bool'),
            ui_certificate=dict(type='str'),
            ds_auth=dict(type='bool'),
        ),
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    try:
        config = mw.call("system.general.config")
    except Exception as e:
        module.fail_json(msg=f"Error looking up system general config: {e}")

    result['status'] = config

    arg = {}
    for param_name, api_field in FIELDS.items():
        value = module.params[param_name]
        if value is None:
            continue
        current = config.get(api_field)
        if param_name in SET_FIELDS:
            if set(value) != set(current or []):
                arg[api_field] = value
        elif value != current:
            arg[api_field] = value

    # Handle ui_certificate by name -> ID resolution
    cert_name = module.params['ui_certificate']
    if cert_name is not None:
        current_cert = config.get('ui_certificate') or {}
        if current_cert.get('name') != cert_name:
            try:
                certs = mw.call("certificate.query",
                                [["name", "=", cert_name]])
                if len(certs) == 0:
                    module.fail_json(
                        msg=f"Certificate '{cert_name}' not found")
                arg['ui_certificate'] = certs[0]['id']
            except Exception as e:
                module.fail_json(
                    msg=f"Error looking up certificate '{cert_name}': {e}")

    if len(arg) == 0:
        result['changed'] = False
    else:
        if module.check_mode:
            result['msg'] = f"Would have updated system general: {arg}"
        else:
            try:
                err = mw.call("system.general.update", arg)
                result['status'] = err
            except Exception as e:
                module.fail_json(
                    msg=f"Error updating system general with {arg}: {e}")
        result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
