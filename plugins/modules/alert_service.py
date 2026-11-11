#!/usr/bin/python

# Manage alert services (where TrueNAS sends its alerts).

DOCUMENTATION = """
---
module: alert_service
short_description: Manage TrueNAS alert services
description:
  - Create, update or delete an alert service, the destination TrueNAS
    sends its alerts to (email, Slack, Telegram, PagerDuty, SNMP trap, and
    so on).
  - Services are identified by I(name).
options:
  name:
    description:
      - Name of the alert service. Acts as an identifier.
    type: str
    required: true
  type:
    description:
      - Service type, as listed by C(midclt call alertservice.list_types),
        e.g. C(Mail), C(Telegram), C(Slack), C(PagerDuty).
      - Required when creating a service. Changing the type of an existing
        service replaces all of its I(attributes).
    type: str
  attributes:
    description:
      - Type-specific settings, e.g. C(email) for C(Mail), or C(bot_token)
        and C(chat_ids) for C(Telegram).
      - Only the keys given are compared and changed; other stored keys
        are kept.
      - Values are hidden from logs, since they often hold tokens.
    type: dict
    default: {}
  level:
    description:
      - Lowest alert level sent to this service.
    type: str
    choices: [ INFO, NOTICE, WARNING, ERROR, CRITICAL, ALERT, EMERGENCY ]
  enabled:
    description:
      - Whether the service is enabled.
    type: bool
  state:
    description:
      - Whether the service should exist.
    type: str
    choices: [ absent, present ]
    default: present
notes:
  - Supports C(check_mode).
version_added: 4.2.0
"""

EXAMPLES = """
- name: Send WARNING and above to an address
  griffdawg.truenas.alert_service:
    name: E-Mail
    type: Mail
    attributes:
      email: alerts@example.com
    level: WARNING

- name: Also page via Telegram
  griffdawg.truenas.alert_service:
    name: Telegram
    type: Telegram
    attributes:
      bot_token: "{{ telegram_bot_token }}"
      chat_ids: [123456789]
    level: ERROR

- name: Remove the default SNMP trap service
  griffdawg.truenas.alert_service:
    name: SNMP Trap
    state: absent
"""

RETURN = """
service:
  description:
    - The alert service as returned by middleware after a create or update.
  type: dict
  returned: when created or updated, outside check mode
changed_keys:
  description:
    - Top-level fields and attribute keys that differ, e.g.
      C([level, attributes.email]). Values are not included.
  type: list
  elements: str
  returned: always
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            type=dict(type="str"),
            attributes=dict(type="dict", default={}, no_log=True),
            level=dict(
                type="str",
                choices=["INFO", "NOTICE", "WARNING", "ERROR", "CRITICAL", "ALERT", "EMERGENCY"],
            ),
            enabled=dict(type="bool"),
            state=dict(type="str", default="present", choices=["absent", "present"]),
        ),
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, msg="", changed_keys=[])

    mw = MW.client()

    name = module.params["name"]
    stype = module.params["type"]
    attributes = module.params["attributes"]
    state = module.params["state"]

    try:
        found = mw.call("alertservice.query", [["name", "=", name]])
    except Exception as e:
        setup.fail(module, f"Error looking up alert service {name}: {e}")
    current = found[0] if found else None

    if state == "absent":
        if current is not None:
            if module.check_mode:
                result["msg"] = f"Would have deleted alert service {name}"
            else:
                try:
                    mw.call("alertservice.delete", current["id"])
                except Exception as e:
                    setup.fail(module, f"Error deleting alert service {name}: {e}")
            result["changed"] = True
        module.exit_json(**result)

    if current is None:
        if stype is None:
            setup.fail(module, f"'type' is required when creating alert service {name}")
        arg = {
            "name": name,
            "attributes": dict(attributes, type=stype),
            "level": module.params["level"] or "WARNING",
            "enabled": True if module.params["enabled"] is None else module.params["enabled"],
        }
        result["changed_keys"] = ["name"]
        if module.check_mode:
            result["msg"] = f"Would have created alert service {name}"
        else:
            try:
                result["service"] = mw.call("alertservice.create", arg)
            except Exception as e:
                setup.fail(module, f"Error creating alert service {name}: {e}")
        result["changed"] = True
        module.exit_json(**result)

    # Update. 'attributes' carries the type and is replaced as a whole,
    # so send the merged dict whenever any of it changes.
    cur_attrs = dict(current.get("attributes") or {})
    cur_type = cur_attrs.get("type")
    changed_keys = []
    arg = {}

    if stype is not None and stype != cur_type:
        new_attrs = dict(attributes, type=stype)
        changed_keys.append("attributes.type")
    else:
        new_attrs = dict(cur_attrs)
        for key, value in attributes.items():
            if cur_attrs.get(key) != value:
                changed_keys.append(f"attributes.{key}")
            new_attrs[key] = value
    if changed_keys:
        arg["attributes"] = new_attrs

    for key in ("level", "enabled"):
        value = module.params[key]
        if value is not None and current.get(key) != value:
            arg[key] = value
            changed_keys.append(key)

    result["changed_keys"] = changed_keys
    if arg:
        # Middleware validates the full entry on update.
        full = {
            "name": name,
            "attributes": arg.get("attributes", cur_attrs),
            "level": arg.get("level", current.get("level")),
            "enabled": arg.get("enabled", current.get("enabled")),
        }
        if module.check_mode:
            result["msg"] = f"Would have updated alert service {name}: {', '.join(changed_keys)}"
        else:
            try:
                result["service"] = mw.call("alertservice.update", current["id"], full)
            except Exception as e:
                setup.fail(module, f"Error updating alert service {name} ({', '.join(changed_keys)}): {e}")
        result["changed"] = True

    module.exit_json(**result)


if __name__ == "__main__":
    main()
