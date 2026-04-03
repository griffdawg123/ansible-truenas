#!/usr/bin/python
# -*- coding: utf-8 -*-
__metaclass__ = type

# Manage UI preferences for the current TrueNAS user.
#
# Preferences are stored in user attributes under the "preferences" key.
# The API uses auth.set_attribute("preferences", {...}) which operates
# on the currently authenticated user.
#
# midclt call auth.me  (to see current user info)
# midclt call auth.set_attribute "preferences" '{"lifetime": 300}'

DOCUMENTATION = '''
---
module: user_preferences
short_description: Manage UI preferences for the connection user
description:
  - Set TrueNAS web UI preferences for the currently authenticated user
    (the user Ansible connects as).
  - Preferences include session timeout, theme, language, date/time
    format, and various UI defaults.
  - Only specified preferences are changed; others are left as-is.
  - To set preferences for multiple users, run this module with
    different connection credentials (e.g., C(ansible_user)).
options:
  lifetime:
    description:
      - Session timeout in seconds.
      - Controls how long web UI sessions last before requiring re-login.
    type: int
  language:
    description:
      - UI language code (e.g., C(en), C(es), C(de)).
    type: str
  userTheme:
    description:
      - UI theme name (e.g., C(ix-dark), C(ix-blue)).
    type: str
  dateFormat:
    description:
      - Date display format (e.g., C(yyyy-MM-dd)).
    type: str
  timeFormat:
    description:
      - Time display format (e.g., C(HH:mm:ss)).
    type: str
  hideBuiltinUsers:
    description:
      - If true, hide built-in users in the UI by default.
    type: bool
  hideBuiltinGroups:
    description:
      - If true, hide built-in groups in the UI by default.
    type: bool
  autoRefreshReports:
    description:
      - If true, auto-refresh reporting charts.
    type: bool
  rebootAfterManualUpdate:
    description:
      - If true, reboot automatically after a manual update.
    type: bool
  showSnapshotExtraColumns:
    description:
      - If true, show extra columns in snapshot listings.
    type: bool
  terminalFontSize:
    description:
      - Font size for the web shell terminal.
    type: int
notes:
  - Supports C(check_mode).
  - This module sets preferences for the user that Ansible connects as
    (via C(midclt) or the middleware client). The TrueNAS API does not
    support setting preferences for other users.
  - Only the specified preferences are updated. Unspecified preferences
    retain their current values.
version_added: 1.15.0
'''

EXAMPLES = '''
- name: Set session timeout to 5 minutes
  arensb.truenas.user_preferences:
    lifetime: 300

- name: Set theme and language
  arensb.truenas.user_preferences:
    userTheme: ix-dark
    language: en

- name: Configure date/time format and hide builtins
  arensb.truenas.user_preferences:
    dateFormat: yyyy-MM-dd
    timeFormat: HH:mm:ss
    hideBuiltinUsers: true
    hideBuiltinGroups: true

- name: Set preferences for multiple users using different credentials
  arensb.truenas.user_preferences:
    lifetime: 300
    userTheme: ix-dark
  vars:
    ansible_user: "{{ item }}"
  loop:
    - truenas_admin
    - jacobo
'''

RETURN = '''
preferences:
  description:
    - The full preferences dict after the update.
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ..module_utils.middleware import MiddleWare as MW


PREF_FIELDS = {
    'lifetime': 'lifetime',
    'language': 'language',
    'userTheme': 'userTheme',
    'dateFormat': 'dateFormat',
    'timeFormat': 'timeFormat',
    'hideBuiltinUsers': 'hideBuiltinUsers',
    'hideBuiltinGroups': 'hideBuiltinGroups',
    'autoRefreshReports': 'autoRefreshReports',
    'rebootAfterManualUpdate': 'rebootAfterManualUpdate',
    'showSnapshotExtraColumns': 'showSnapshotExtraColumns',
    'terminalFontSize': 'terminalFontSize',
}


def main():
    module = AnsibleModule(
        argument_spec=dict(
            lifetime=dict(type='int'),
            language=dict(type='str'),
            userTheme=dict(type='str'),
            dateFormat=dict(type='str'),
            timeFormat=dict(type='str'),
            hideBuiltinUsers=dict(type='bool'),
            hideBuiltinGroups=dict(type='bool'),
            autoRefreshReports=dict(type='bool'),
            rebootAfterManualUpdate=dict(type='bool'),
            showSnapshotExtraColumns=dict(type='bool'),
            terminalFontSize=dict(type='int'),
        ),
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    # Get current user info and preferences
    try:
        me = mw.call("auth.me")
        attributes = me.get('attributes', {})
        current_prefs = attributes.get('preferences', {})
    except Exception as e:
        module.fail_json(msg=f"Error getting current user info: {e}")

    # Build desired changes
    changes = {}
    for param_name, pref_key in PREF_FIELDS.items():
        value = module.params[param_name]
        if value is None:
            continue
        if current_prefs.get(pref_key) != value:
            changes[pref_key] = value

    if len(changes) == 0:
        result['changed'] = False
        result['preferences'] = current_prefs
    else:
        # Merge changes into current preferences
        new_prefs = dict(current_prefs)
        new_prefs.update(changes)

        if module.check_mode:
            result['msg'] = f"Would have updated preferences: {changes}"
            result['preferences'] = new_prefs
        else:
            try:
                mw.call("auth.set_attribute", "preferences", new_prefs)
                result['preferences'] = new_prefs
            except Exception as e:
                module.fail_json(
                    msg=f"Error updating preferences: {e}")
        result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
