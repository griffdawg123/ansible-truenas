#!/usr/bin/python

# Configure the UPS service on TrueNAS.
#
# midclt call ups.config
# midclt call ups.update '{"mode": "MASTER"}'

DOCUMENTATION = '''
---
module: ups
short_description: Configure UPS service
description:
  - Configure the UPS (Uninterruptible Power Supply) service settings
    on TrueNAS.
  - For starting/stopping/enabling the service, use the C(service) module.
options:
  identifier:
    description:
      - UPS identifier name.
    type: str
  mode:
    description:
      - UPS mode.
      - C(MASTER) if the UPS is directly connected to this system.
      - C(SLAVE) if the UPS is monitored through another system.
    type: str
    choices: [ MASTER, SLAVE ]
  driver:
    description:
      - NUT driver for the UPS (e.g., C(usbhid-ups), C(apcsmart)).
    type: str
  port:
    description:
      - Serial or USB port the UPS is connected to.
      - For USB UPS devices, this is typically C(auto).
    type: str
  description:
    description:
      - Description of the UPS.
    type: str
  monuser:
    description:
      - Username for the UPS monitor user.
    type: str
  monpwd:
    description:
      - Password for the UPS monitor user.
    type: str
    no_log: true
  extrausers:
    description:
      - Additional users for upsd.users, as a raw string.
    type: str
  options:
    description:
      - Additional options for the UPS driver, as a raw string.
    type: str
  optionsupsd:
    description:
      - Additional options for upsd.conf, as a raw string.
    type: str
  shutdown:
    description:
      - When to shut down the system.
      - C(LOWBATT) shuts down when the UPS reports low battery.
      - C(BATT) shuts down immediately when power is lost.
    type: str
    choices: [ LOWBATT, BATT ]
  shutdowntimer:
    description:
      - Time in seconds to wait before initiating shutdown after power
        loss (when C(shutdown) is C(BATT)).
    type: int
  shutdowncmd:
    description:
      - Custom command to run for shutdown.
      - Set to null to use the default.
    type: str
  nocommwarntime:
    description:
      - Time in seconds before warning about communication loss with
        the UPS.
      - Set to null to use the default.
    type: int
  hostsync:
    description:
      - Time in seconds to wait for slave systems to disconnect
        during shutdown.
    type: int
  powerdown:
    description:
      - If true, signal the UPS to power off after system shutdown.
    type: bool
  rmonitor:
    description:
      - If true, enable remote monitoring of the UPS.
    type: bool
  remotehost:
    description:
      - Remote UPS host (when C(mode) is C(SLAVE)).
    type: str
  remoteport:
    description:
      - Remote UPS port (when C(mode) is C(SLAVE)).
    type: int
notes:
  - Supports C(check_mode).
seealso:
  - module: jdevera.truenas.service
version_added: 1.15.0
'''

EXAMPLES = '''
- name: Configure a USB UPS in master mode
  jdevera.truenas.ups:
    identifier: myups
    mode: MASTER
    driver: usbhid-ups
    port: auto
    shutdown: LOWBATT

- name: Configure as slave monitoring a remote UPS
  jdevera.truenas.ups:
    mode: SLAVE
    remotehost: 192.168.1.10
    remoteport: 3493
'''

RETURN = '''
status:
  description:
    - The UPS service configuration after any changes.
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW

FIELDS = {
    'identifier': 'identifier',
    'mode': 'mode',
    'driver': 'driver',
    'port': 'port',
    'description': 'description',
    'monuser': 'monuser',
    'monpwd': 'monpwd',
    'extrausers': 'extrausers',
    'options': 'options',
    'optionsupsd': 'optionsupsd',
    'shutdown': 'shutdown',
    'shutdowntimer': 'shutdowntimer',
    'shutdowncmd': 'shutdowncmd',
    'nocommwarntime': 'nocommwarntime',
    'hostsync': 'hostsync',
    'powerdown': 'powerdown',
    'rmonitor': 'rmonitor',
    'remotehost': 'remotehost',
    'remoteport': 'remoteport',
}


def main():
    module = AnsibleModule(
        argument_spec=dict(
            identifier=dict(type='str'),
            mode=dict(type='str', choices=['MASTER', 'SLAVE']),
            driver=dict(type='str'),
            port=dict(type='str'),
            description=dict(type='str'),
            monuser=dict(type='str'),
            monpwd=dict(type='str', no_log=True),
            extrausers=dict(type='str'),
            options=dict(type='str'),
            optionsupsd=dict(type='str'),
            shutdown=dict(type='str', choices=['LOWBATT', 'BATT']),
            shutdowntimer=dict(type='int'),
            shutdowncmd=dict(type='str'),
            nocommwarntime=dict(type='int'),
            hostsync=dict(type='int'),
            powerdown=dict(type='bool'),
            rmonitor=dict(type='bool'),
            remotehost=dict(type='str'),
            remoteport=dict(type='int'),
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
        ups_info = mw.call("ups.config")
    except Exception as e:
        module.fail_json(msg=f"Error looking up UPS configuration: {e}")

    result['status'] = ups_info

    arg = {}
    for param_name, api_field in FIELDS.items():
        value = module.params[param_name]
        if value is None:
            continue
        current = ups_info.get(api_field)
        if value != current:
            arg[api_field] = value

    if len(arg) == 0:
        result['changed'] = False
    else:
        if module.check_mode:
            result['msg'] = f"Would have updated UPS: {arg}"
        else:
            try:
                err = mw.call("ups.update", arg)
                result['status'] = err
            except Exception as e:
                module.fail_json(msg=f"Error updating UPS with {arg}: {e}")
        result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
