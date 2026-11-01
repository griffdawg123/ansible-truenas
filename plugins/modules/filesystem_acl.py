#!/usr/bin/python

# Manage filesystem ACLs.
#
# Ported from normalerweise/ansible-truenas (l1.filesystem_acl), with
# reworked change detection.
#
# midclt call filesystem.getacl /mnt/pool/path
# midclt call -j filesystem.setacl '{"path": "...", "dacl": [...], ...}'

DOCUMENTATION = """
---
module: filesystem_acl
short_description: Manage filesystem ACLs via TrueNAS middleware
description:
  - Set and manage NFSv4 or POSIX ACLs on TrueNAS SCALE filesystems.
  - Uses the filesystem.setacl middleware API.
  - Supports both NFSv4 and POSIX1E ACL types.
options:
  path:
    description:
      - Absolute filesystem path to set ACL on.
    required: true
    type: str
  dacl:
    description:
      - Array of Access Control Entries to apply to the filesystem object.
      - Format depends on the ACL type (NFSv4 or POSIX1E).
      - Required unless C(stripacl) is true.
      - An entry matches an existing one when every key given here has
        the same value there; keys you omit (e.g. C(who) when C(id) is
        given) are not compared. Order is not compared.
    type: list
    elements: dict
  uid:
    description:
      - Numeric user ID to set as owner.
      - Omit to keep the existing owner.
    type: int
  user:
    description:
      - Username to set as owner.
      - Cannot be used together with uid.
    type: str
  gid:
    description:
      - Numeric group ID to set as group.
      - Omit to keep the existing group.
    type: int
  group:
    description:
      - Group name to set as group.
      - Cannot be used together with gid.
    type: str
  stripacl:
    description:
      - Whether to remove the ACL entirely and revert to basic POSIX permissions.
      - Reports no change if the path's ACL is already trivial.
    type: bool
    default: false
  recursive:
    description:
      - Whether to apply ACL changes recursively to all child files and directories.
    type: bool
    default: false
  traverse:
    description:
      - Whether to traverse filesystem boundaries during recursive operations.
    type: bool
    default: false
  canonicalize:
    description:
      - Whether to reorder ACL entries in Windows canonical order.
    type: bool
    default: true
  validate_effective_acl:
    description:
      - Whether to validate that users/groups granted access can actually access the path.
    type: bool
    default: true
  acltype:
    description:
      - ACL type to use. If not specified, auto-detected from filesystem.
    type: str
    choices: ['NFS4', 'POSIX1E']
  nfs41_flags:
    description:
      - NFS4 ACL flags for inheritance and protection behavior.
    type: dict
    suboptions:
      autoinherit:
        description: Whether inheritance is automatically applied from parent directories.
        type: bool
        default: false
      protected:
        description: Whether the ACL is protected from inheritance modifications.
        type: bool
        default: false
      defaulted:
        description: Whether this ACL was created by default rules.
        type: bool
        default: false
version_added: 4.0.0
"""

EXAMPLES = r"""
- name: Set NFSv4 ACL on a directory
  griffdawg.truenas.filesystem_acl:
    path: /mnt/tank/shared
    dacl:
      - tag: "owner@"
        type: "ALLOW"
        perms:
          BASIC: "FULL_CONTROL"
        flags:
          BASIC: "INHERIT"
      - tag: "USER"
        id: 2001
        who: "alice"
        type: "ALLOW"
        perms:
          BASIC: "FULL_CONTROL"
        flags:
          BASIC: "INHERIT"
    uid: 3000
    gid: 3000

- name: Set POSIX ACL on a directory
  griffdawg.truenas.filesystem_acl:
    path: /mnt/tank/posix_dir
    dacl:
      - tag: "USER_OBJ"
        perms:
          READ: true
          WRITE: true
          EXECUTE: true
        default: false
      - tag: "USER"
        id: 2001
        who: "alice"
        perms:
          READ: true
          WRITE: true
          EXECUTE: true
        default: false
    acltype: "POSIX1E"

- name: Strip ACL and revert to basic permissions
  griffdawg.truenas.filesystem_acl:
    path: /mnt/tank/simple
    stripacl: true
"""

RETURN = r"""
acl_info:
  description: ACL information for the filesystem path after setting.
  type: dict
  returned: always
  sample:
    path: "/mnt/tank/shared"
    user: "alice"
    group: "users"
    uid: 2001
    gid: 4000
    acltype: "NFS4"
    trivial: false
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW


def subset_matches(desired, current):
    """
    Return True if every key in 'desired' has the same value in
    'current', recursing into dicts. Keys only present in 'current'
    (middleware fills in 'who', 'id', etc.) are ignored.
    """
    if isinstance(desired, dict):
        if not isinstance(current, dict):
            return False
        return all(k in current and subset_matches(v, current[k]) for k, v in desired.items())
    return desired == current


def acl_matches(desired_dacl, current_dacl):
    """
    Return True if the two ACLs have the same entries, regardless of
    order, comparing each entry with subset_matches().
    """
    if len(desired_dacl) != len(current_dacl):
        return False
    unmatched = list(current_dacl)
    for want in desired_dacl:
        for i, have in enumerate(unmatched):
            if subset_matches(want, have):
                del unmatched[i]
                break
        else:
            return False
    return True


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type="str", required=True),
            dacl=dict(type="list", elements="dict"),
            uid=dict(type="int"),
            user=dict(type="str"),
            gid=dict(type="int"),
            group=dict(type="str"),
            stripacl=dict(type="bool", default=False),
            recursive=dict(type="bool", default=False),
            traverse=dict(type="bool", default=False),
            canonicalize=dict(type="bool", default=True),
            validate_effective_acl=dict(type="bool", default=True),
            acltype=dict(type="str", choices=["NFS4", "POSIX1E"]),
            nfs41_flags=dict(
                type="dict",
                options=dict(
                    autoinherit=dict(type="bool", default=False),
                    protected=dict(type="bool", default=False),
                    defaulted=dict(type="bool", default=False),
                ),
            ),
        ),
        mutually_exclusive=[
            ("uid", "user"),
            ("gid", "group"),
        ],
        required_if=[("stripacl", False, ("dacl",))],
        supports_check_mode=True,
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, acl_info={})

    mw = MW.client()

    p = module.params
    path = p["path"]

    acl_params = {
        "path": path,
        "dacl": p["dacl"] or [],
        "options": {
            "stripacl": p["stripacl"],
            "recursive": p["recursive"],
            "traverse": p["traverse"],
            "canonicalize": p["canonicalize"],
            "validate_effective_acl": p["validate_effective_acl"],
        },
    }
    for key in ("uid", "user", "gid", "group", "acltype"):
        if p[key] is not None:
            acl_params[key] = p[key]
    if p["nfs41_flags"] is not None:
        acl_params["nfs41_flags"] = p["nfs41_flags"]

    try:
        current_acl = mw.call("filesystem.getacl", path)
    except Exception as e:
        # Under check mode the path may belong to a dataset an earlier
        # task would have created; report the pending change.
        if module.check_mode and "ENOENT" in str(e):
            result["changed"] = True
            result["msg"] = f"Would set ACL on '{path}' (path does not exist yet)"
            module.exit_json(**result)
        setup.fail(module, f"Failed to get current ACL for '{path}': {e}")

    if p["stripacl"]:
        needs_change = not current_acl.get("trivial", False)
    else:
        needs_change = not acl_matches(p["dacl"], current_acl.get("acl", []))
        if p["acltype"] is not None and current_acl.get("acltype") != p["acltype"]:
            needs_change = True
        if p["nfs41_flags"] is not None and not subset_matches(
            p["nfs41_flags"], current_acl.get("aclflags") or {}
        ):
            needs_change = True

    for key in ("uid", "user", "gid", "group"):
        if p[key] is not None and current_acl.get(key) != p[key]:
            needs_change = True

    if not needs_change:
        result["acl_info"] = current_acl
        module.exit_json(**result)

    result["changed"] = True
    if module.check_mode:
        result["msg"] = f"Would set ACL on '{path}'"
        result["acl_info"] = current_acl
        module.exit_json(**result)

    try:
        result["acl_info"] = mw.job("filesystem.setacl", acl_params)
    except Exception as e:
        setup.fail(module, f"Failed to set ACL on '{path}': {e}", failed_invocation=acl_params)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
