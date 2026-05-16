#!/usr/bin/python
# -*- coding: utf-8 -*-
__metaclass__ = type

# Configure TrueNAS advanced system settings.
#
# midclt call system.advanced.config
# midclt call system.advanced.update '{"motd": "Welcome"}'

DOCUMENTATION = '''
---
module: system_advanced
short_description: Configure advanced system settings
description:
  - Configure advanced system settings on TrueNAS, including MOTD,
    serial console, syslog, boot scrub, and debug options.
options:
  advancedmode:
    description:
      - If true, enable advanced mode in the UI.
    type: bool
  autotune:
    description:
      - If true, enable system autotuning.
    type: bool
  kdump_enabled:
    description:
      - If true, enable kernel crash dumps.
    type: bool
  boot_scrub:
    description:
      - Number of days between automatic boot pool scrubs.
    type: int
  consolemenu:
    description:
      - If true, enable the console setup menu.
    type: bool
  consolemsg:
    description:
      - If true, show console messages.
    type: bool
  debugkernel:
    description:
      - If true, use the debug kernel.
    type: bool
  fqdn_syslog:
    description:
      - If true, use FQDN for syslog messages.
    type: bool
  motd:
    description:
      - Message of the day shown at login.
    type: str
  login_banner:
    description:
      - Banner text shown before login prompt.
    type: str
  serialconsole:
    description:
      - If true, enable serial console.
    type: bool
  serialport:
    description:
      - Serial port device (e.g., C(ttyS0)).
    type: str
  serialspeed:
    description:
      - Serial port baud rate.
    type: str
    choices: [ '9600', '19200', '38400', '57600', '115200' ]
  sysloglevel:
    description:
      - Minimum syslog level.
    type: str
    choices: [ F_EMERG, F_ALERT, F_CRIT, F_ERR, F_WARNING, F_NOTICE, F_INFO, F_DEBUG ]
  syslog_audit:
    description:
      - If true, include audit messages in syslog.
    type: bool
  kernel_extra_options:
    description:
      - Extra kernel boot options, as a raw string.
    type: str
  powerdaemon:
    description:
      - If true, enable the power daemon.
    type: bool
  traceback:
    description:
      - If true, include Python tracebacks in error reports.
    type: bool
  uploadcrash:
    description:
      - If true, automatically upload crash reports.
    type: bool
  anonstats:
    description:
      - If true, send anonymous usage statistics.
    type: bool
notes:
  - Supports C(check_mode).
version_added: 1.15.0
'''

EXAMPLES = '''
- name: Set MOTD and login banner
  jdevera.truenas.system_advanced:
    motd: "Welcome to TrueNAS"
    login_banner: "Authorized users only"

- name: Configure syslog level
  jdevera.truenas.system_advanced:
    sysloglevel: F_WARNING
    fqdn_syslog: true

- name: Enable serial console
  jdevera.truenas.system_advanced:
    serialconsole: true
    serialport: ttyS0
    serialspeed: '115200'
'''

RETURN = '''
status:
  description:
    - The system advanced configuration after any changes.
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ..module_utils.middleware import MiddleWare as MW
from ..module_utils import setup


FIELDS = {
    'advancedmode': 'advancedmode',
    'autotune': 'autotune',
    'kdump_enabled': 'kdump_enabled',
    'boot_scrub': 'boot_scrub',
    'consolemenu': 'consolemenu',
    'consolemsg': 'consolemsg',
    'debugkernel': 'debugkernel',
    'fqdn_syslog': 'fqdn_syslog',
    'motd': 'motd',
    'login_banner': 'login_banner',
    'serialconsole': 'serialconsole',
    'serialport': 'serialport',
    'serialspeed': 'serialspeed',
    'sysloglevel': 'sysloglevel',
    'syslog_audit': 'syslog_audit',
    'kernel_extra_options': 'kernel_extra_options',
    'powerdaemon': 'powerdaemon',
    'traceback': 'traceback',
    'uploadcrash': 'uploadcrash',
    'anonstats': 'anonstats',
}


def main():
    setup.require_scale_min_version()

    module = AnsibleModule(
        argument_spec=dict(
            advancedmode=dict(type='bool'),
            autotune=dict(type='bool'),
            kdump_enabled=dict(type='bool'),
            boot_scrub=dict(type='int'),
            consolemenu=dict(type='bool'),
            consolemsg=dict(type='bool'),
            debugkernel=dict(type='bool'),
            fqdn_syslog=dict(type='bool'),
            motd=dict(type='str'),
            login_banner=dict(type='str'),
            serialconsole=dict(type='bool'),
            serialport=dict(type='str'),
            serialspeed=dict(type='str',
                             choices=['9600', '19200', '38400',
                                      '57600', '115200']),
            sysloglevel=dict(type='str',
                             choices=['F_EMERG', 'F_ALERT', 'F_CRIT',
                                      'F_ERR', 'F_WARNING', 'F_NOTICE',
                                      'F_INFO', 'F_DEBUG']),
            syslog_audit=dict(type='bool'),
            kernel_extra_options=dict(type='str'),
            powerdaemon=dict(type='bool'),
            traceback=dict(type='bool'),
            uploadcrash=dict(type='bool'),
            anonstats=dict(type='bool'),
        ),
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    try:
        config = mw.call("system.advanced.config")
    except Exception as e:
        module.fail_json(msg=f"Error looking up system advanced config: {e}")

    result['status'] = config

    arg = {}
    for param_name, api_field in FIELDS.items():
        value = module.params[param_name]
        if value is None:
            continue
        current = config.get(api_field)
        if value != current:
            arg[api_field] = value

    if len(arg) == 0:
        result['changed'] = False
    else:
        if module.check_mode:
            result['msg'] = f"Would have updated system advanced: {arg}"
        else:
            try:
                err = mw.call("system.advanced.update", arg)
                result['status'] = err
            except Exception as e:
                module.fail_json(
                    msg=f"Error updating system advanced with {arg}: {e}")
        result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
