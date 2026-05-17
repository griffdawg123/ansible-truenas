#!/usr/bin/python

# Configure the SSH service on TrueNAS.
#
# midclt call ssh.config
# midclt call ssh.update '{"tcpport": 22}'

DOCUMENTATION = """
---
module: ssh
short_description: Configure SSH service
description:
  - Configure the SSH daemon service settings on TrueNAS.
  - For starting/stopping/enabling the service, use the C(service) module.
options:
  bindiface:
    description:
      - List of network interfaces to bind to.
      - If empty, SSH listens on all available addresses.
    type: list
    elements: str
  tcpport:
    description:
      - TCP port for the SSH daemon to listen on.
    type: int
  passwordauth:
    description:
      - If true, allow password authentication.
    type: bool
  password_login_groups:
    description:
      - List of group names allowed to use password login.
      - If empty, all groups may use password login (when C(passwordauth)
        is enabled).
    type: list
    elements: str
  kerberosauth:
    description:
      - If true, enable Kerberos authentication.
    type: bool
  tcpfwd:
    description:
      - If true, allow TCP forwarding.
    type: bool
  compression:
    description:
      - If true, enable compression.
    type: bool
  sftp_log_level:
    description:
      - Log level for SFTP.
      - Empty string means default.
    type: str
    choices: [ '', QUIET, FATAL, ERROR, INFO, VERBOSE, DEBUG, DEBUG2, DEBUG3 ]
  sftp_log_facility:
    description:
      - Syslog facility for SFTP logging.
      - Empty string means default.
    type: str
    choices: [ '', DAEMON, USER, AUTH, LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4, LOCAL5, LOCAL6, LOCAL7 ]
  weak_ciphers:
    description:
      - List of weak ciphers to allow.
      - Valid values are C(AES128-CBC) and C(NONE).
    type: list
    elements: str
  options:
    description:
      - Additional sshd_config options, as a raw string.
    type: str
notes:
  - Supports C(check_mode).
seealso:
  - module: jdevera.truenas.service
version_added: 1.15.0
"""

EXAMPLES = """
- name: Set SSH port and disable password auth
  jdevera.truenas.ssh:
    tcpport: 2222
    passwordauth: false

- name: Bind SSH to a specific interface
  jdevera.truenas.ssh:
    bindiface:
      - br0

- name: Enable compression and TCP forwarding
  jdevera.truenas.ssh:
    compression: true
    tcpfwd: true
"""

RETURN = """
status:
  returned: always
  description:
    - The SSH service configuration after any changes.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW

# Maps Ansible param name -> API field name.
# Only includes fields where they differ or need explicit mapping.
FIELDS = {
    "bindiface": "bindiface",
    "tcpport": "tcpport",
    "passwordauth": "passwordauth",
    "password_login_groups": "password_login_groups",
    "kerberosauth": "kerberosauth",
    "tcpfwd": "tcpfwd",
    "compression": "compression",
    "sftp_log_level": "sftp_log_level",
    "sftp_log_facility": "sftp_log_facility",
    "weak_ciphers": "weak_ciphers",
    "options": "options",
}

# Fields where order doesn't matter (compare as sets)
SET_FIELDS = {"bindiface", "password_login_groups", "weak_ciphers"}


def main():
    module = AnsibleModule(
        argument_spec=dict(
            bindiface=dict(type="list", elements="str"),
            tcpport=dict(type="int"),
            passwordauth=dict(type="bool"),
            password_login_groups=dict(type="list", elements="str", no_log=False),
            kerberosauth=dict(type="bool"),
            tcpfwd=dict(type="bool"),
            compression=dict(type="bool"),
            sftp_log_level=dict(
                type="str",
                choices=[
                    "",
                    "QUIET",
                    "FATAL",
                    "ERROR",
                    "INFO",
                    "VERBOSE",
                    "DEBUG",
                    "DEBUG2",
                    "DEBUG3",
                ],
            ),
            sftp_log_facility=dict(
                type="str",
                choices=[
                    "",
                    "DAEMON",
                    "USER",
                    "AUTH",
                    "LOCAL0",
                    "LOCAL1",
                    "LOCAL2",
                    "LOCAL3",
                    "LOCAL4",
                    "LOCAL5",
                    "LOCAL6",
                    "LOCAL7",
                ],
            ),
            weak_ciphers=dict(type="list", elements="str"),
            options=dict(type="str"),
        ),
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, msg="")

    mw = MW.client()

    try:
        ssh_info = mw.call("ssh.config")
    except Exception as e:
        module.fail_json(msg=f"Error looking up SSH configuration: {e}")

    result["status"] = ssh_info

    # Build diff
    arg = {}
    for param_name, api_field in FIELDS.items():
        value = module.params[param_name]
        if value is None:
            continue
        current = ssh_info.get(api_field)
        if param_name in SET_FIELDS:
            if set(value) != set(current or []):
                arg[api_field] = value
        elif value != current:
            arg[api_field] = value

    if len(arg) == 0:
        result["changed"] = False
    else:
        if module.check_mode:
            result["msg"] = f"Would have updated SSH: {arg}"
        else:
            try:
                err = mw.call("ssh.update", arg)
                result["status"] = err
            except Exception as e:
                module.fail_json(msg=f"Error updating SSH with {arg}: {e}")
        result["changed"] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
