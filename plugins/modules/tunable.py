#!/usr/bin/python

# Manage TrueNAS tunables (sysctl, udev, ZFS module parameters).
#
# midclt call tunable.query
# midclt call tunable.create '{"type": "SYSCTL", "var": "...", "value": "1"}'
# midclt call tunable.update <id> '{"value": "0"}'
# midclt call tunable.delete <id>

DOCUMENTATION = """
---
module: tunable
short_description: Manage TrueNAS tunables
description:
  - Manage persistent TrueNAS tunables, which survive reboots and
    upgrades.
  - A tunable is identified by the pair (C(type), C(var)). This module
    looks up an existing tunable by that pair, then creates, updates, or
    deletes it as needed.
options:
  type:
    description:
      - The kind of tunable.
      - C(SYSCTL) sets a kernel sysctl parameter.
      - C(UDEV) installs a udev rule.
      - C(ZFS) sets a ZFS kernel module parameter.
      - Together with C(var), this is the natural key used for lookup.
    type: str
    required: true
    choices: [ SYSCTL, UDEV, ZFS ]
  var:
    description:
      - The variable name, e.g. C(net.ipv6.conf.enp1s0.disable_ipv6) for
        a C(SYSCTL) tunable, or the rule file name for a C(UDEV) tunable.
      - Together with C(type), this is the natural key used for lookup.
    type: str
    required: true
  value:
    description:
      - The value to set.
      - TrueNAS stores tunable values as strings, even for numeric
        sysctls, so this is always a string. Quote numeric values
        (e.g. C("1")) to keep them from being interpreted as integers.
      - Required when O(state=present).
    type: str
  enabled:
    description:
      - Whether the tunable is enabled.
      - A disabled tunable exists on the system but is not applied.
    type: bool
    default: true
  comment:
    description:
      - Optional freeform comment stored with the tunable.
    type: str
  state:
    description:
      - Whether the tunable should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
notes:
  - Supports C(check_mode).
  - C(type) and C(var) are immutable once a tunable is created. Changing
    either selects a different tunable for lookup, which this module
    treats as a separate resource (it will not rename an existing one).
  - Some tunables only take effect after a reboot. This module does not
    reboot the host; orchestrate that yourself if required.
version_added: 3.0.0
"""

EXAMPLES = """
- name: Disable IPv6 on enp1s0 via TrueNAS sysctl tunable
  griffdawg.truenas.tunable:
    type: SYSCTL
    var: net.ipv6.conf.enp1s0.disable_ipv6
    value: "1"
    comment: "Suppresses link-local mDNS so Windows SMB doesn't pick fe80::"
    state: present

- name: Remove a stale ZFS arc_max tunable
  griffdawg.truenas.tunable:
    type: ZFS
    var: zfs_arc_max
    state: absent

- name: Persist a udev rule from inventory
  griffdawg.truenas.tunable:
    type: UDEV
    var: 99-my-rule
    value: 'ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd?", ATTR{queue/scheduler}="none"'
    state: present
"""

RETURN = """
tunable:
  returned: success and O(state=present)
  type: dict
  description:
    - The live tunable after any changes, as returned by the TrueNAS
      middleware.
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            type=dict(type="str", required=True, choices=["SYSCTL", "UDEV", "ZFS"]),
            var=dict(type="str", required=True),
            value=dict(type="str"),
            enabled=dict(type="bool", default=True),
            comment=dict(type="str"),
            state=dict(type="str", default="present", choices=["absent", "present"]),
        ),
        supports_check_mode=True,
        required_if=[["state", "present", ["value"]]],
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, msg="")

    mw = MW.client()

    type_ = module.params["type"]
    var = module.params["var"]
    value = module.params["value"]
    enabled = module.params["enabled"]
    comment = module.params["comment"]
    state = module.params["state"]

    # Look up the tunable by its natural key (type, var).
    try:
        tunables = mw.call("tunable.query", [["type", "=", type_], ["var", "=", var]])
    except Exception as e:
        setup.fail(module, f"Error looking up tunable {type_} {var}: {e}")

    if len(tunables) > 1:
        setup.fail(
            module,
            f"Found {len(tunables)} tunables matching type={type_} var={var}; "
            "expected at most one. Clean up the duplicates via the TrueNAS UI.",
        )

    tunable = tunables[0] if tunables else None

    if tunable is None:
        # The tunable doesn't exist.
        if state == "present":
            arg = {
                "type": type_,
                "var": var,
                "value": value,
                "enabled": enabled,
            }
            if comment is not None:
                arg["comment"] = comment

            if module.check_mode:
                result["msg"] = f"Would have created tunable: {arg}"
            else:
                try:
                    tunable = mw.call("tunable.create", arg)
                except Exception as e:
                    result["failed_invocation"] = arg
                    setup.fail(module, f"Error creating tunable {type_} {var}: {e}")
                result["tunable"] = tunable

            result["changed"] = True
        else:
            # Tunable is absent and should be absent. Nothing to do.
            result["changed"] = False

    else:
        # The tunable exists.
        if state == "present":
            # Build the set of fields that differ from the live tunable.
            arg = {}

            if value != tunable["value"]:
                arg["value"] = value

            if enabled != tunable["enabled"]:
                arg["enabled"] = enabled

            if comment is not None and comment != tunable["comment"]:
                arg["comment"] = comment

            if len(arg) == 0:
                # Already in the desired state.
                result["changed"] = False
                result["tunable"] = tunable
            else:
                if module.check_mode:
                    result["msg"] = f"Would have updated tunable {type_} {var}: {arg}"
                    result["tunable"] = tunable
                else:
                    try:
                        tunable = mw.call("tunable.update", tunable["id"], arg)
                    except Exception as e:
                        result["failed_invocation"] = arg
                        setup.fail(module, f"Error updating tunable {type_} {var}: {e}")
                    result["tunable"] = tunable
                result["changed"] = True
        else:
            # Tunable exists but should be absent. Delete it.
            if module.check_mode:
                result["msg"] = f"Would have deleted tunable {type_} {var}"
            else:
                try:
                    mw.call("tunable.delete", tunable["id"])
                except Exception as e:
                    setup.fail(module, f"Error deleting tunable {type_} {var}: {e}")
            result["changed"] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
