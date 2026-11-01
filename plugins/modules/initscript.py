#!/usr/bin/python

# Manage init/shutdown scripts.

DOCUMENTATION = """
---
module: initscript
short_description: Manage init/shutdown scripts.
description:
  - Set up and manage init and shutdown scripts and commands.
options:
  name:
    description:
      - Name of the script. Acts as an identifier.
    type: str
    required: true
  cmd:
    description:
      - Command to execute.
      - Mutually exclusive with C(path).
    type: str
    aliases: [ command ]
  path:
    description:
      - Path to a script on the TrueNAS host to execute.
      - To manage the script's contents too, put it in place with
        M(ansible.builtin.copy) first; see the examples.
      - Mutually exclusive with C(cmd).
    type: str
  when:
    description:
      - "When to execute the script:"
      - "C(preinit): at boot time, before most services have started,
        but filesystems and network are available."
      - "C(postinit): late in the boot process, after most services have
        started, but before TrueNAS services."
      - "C(shutdown): during shutdown."
      - Required when creating a script.
    type: str
    choices:
      - preinit
      - postinit
      - shutdown
  enabled:
    description:
      - Whether the script should run.
      - New scripts are enabled unless this is false.
    type: bool
  timeout:
    description:
      - Time in seconds that the system should wait for the script to
        terminate.
    type: int
  state:
    description:
      - Whether the script should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
notes:
  - Supports C(check_mode).
  - The C(script) option (inline script text) was removed in 4.0.0;
    SCALE 25.10 middleware only runs scripts by path.
version_added: 1.10.0
"""

EXAMPLES = """
- name: Run a command late once everything has started
  griffdawg.truenas.initscript:
    name: Start Foo
    cmd: "service foo start"
    when: postinit

- name: Install a shutdown script
  ansible.builtin.copy:
    dest: /mnt/tank/scripts/cleanup.sh
    mode: "0700"
    content: |
      #!/bin/sh
      echo "Cleaning up before shutdown."
      rm -f /var/some-lock-file

- name: Run it at shutdown
  griffdawg.truenas.initscript:
    name: Cleaning up
    path: /mnt/tank/scripts/cleanup.sh
    when: shutdown

- name: Delete an init script
  griffdawg.truenas.initscript:
    name: Remove old cruft
    state: absent
"""

RETURN = """
script:
  returned: when a script was created or updated
  description:
    - The init script, as returned by middleware.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            cmd=dict(type="str", aliases=["command"]),
            path=dict(type="str"),
            when=dict(type="str", choices=["preinit", "postinit", "shutdown"]),
            enabled=dict(type="bool"),
            timeout=dict(type="int"),
            state=dict(type="str", default="present", choices=["absent", "present"]),
        ),
        supports_check_mode=True,
        # If the script should exist, exactly one of 'cmd' or 'path'
        # must be given.
        required_if=[("state", "present", ("cmd", "path"), True)],
        mutually_exclusive=[["cmd", "path"]],
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, msg="")

    mw = MW.client()

    name = module.params["name"]
    cmd = module.params["cmd"]
    path = module.params["path"]
    when = module.params["when"]
    state = module.params["state"]

    # Scripts are identified by their comment.
    try:
        found = mw.call("initshutdownscript.query", [["comment", "=", name]])
    except Exception as e:
        setup.fail(module, f"Error looking up script {name}: {e}")
    script_info = found[0] if found else None

    if state == "absent":
        if script_info is not None:
            if module.check_mode:
                result["msg"] = f"Would have deleted script {name}"
            else:
                try:
                    mw.call("initshutdownscript.delete", script_info["id"])
                except Exception as e:
                    setup.fail(module, f"Error deleting script {name}: {e}")
            result["changed"] = True
        module.exit_json(**result)

    # The script should exist. Build the full desired entry; fields
    # the caller didn't give are left alone.
    if cmd is not None:
        desired = {"type": "COMMAND", "command": cmd, "script": ""}
    else:
        desired = {"type": "SCRIPT", "command": "", "script": path}
    if when is not None:
        desired["when"] = when.upper()
    for key in ("enabled", "timeout"):
        if module.params[key] is not None:
            desired[key] = module.params[key]

    if script_info is None:
        if "when" not in desired:
            setup.fail(module, f"'when' is required when creating script {name}")
        arg = dict(desired, comment=name)
        if module.check_mode:
            result["msg"] = f"Would have created script {name} with {arg}"
        else:
            try:
                result["script"] = mw.call("initshutdownscript.create", arg)
            except Exception as e:
                setup.fail(module, f"Error creating script {name}: {e}", failed_invocation=arg)
        result["changed"] = True
        module.exit_json(**result)

    # Middleware may store None rather than "" for the unused one of
    # 'command'/'script'.
    current = dict(script_info)
    for key in ("command", "script"):
        current[key] = current.get(key) or ""
    arg = {k: v for k, v in desired.items() if current.get(k) != v}
    if arg:
        if module.check_mode:
            result["msg"] = f"Would have updated script {name}: {arg}"
        else:
            try:
                result["script"] = mw.call("initshutdownscript.update", script_info["id"], arg)
            except Exception as e:
                setup.fail(module, f"Error updating script {name} with {arg}: {e}")
        result["changed"] = True

    module.exit_json(**result)


if __name__ == "__main__":
    main()
