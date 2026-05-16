#!/usr/bin/python
# -*- coding: utf-8 -*-
__metaclass__ = type

# Query ZFS pool information from TrueNAS.
#
# midclt call pool.query
# midclt call pool.query '[["name", "=", "tank"]]'

DOCUMENTATION = '''
---
module: pool_info
short_description: Gather information about ZFS pools
description:
  - Query ZFS pool information from a TrueNAS host.
  - Returns a list of pools with their properties (name, status, size,
    topology, etc.).
  - This is an info module that returns data in the result. It does not
    modify anything on the host.
options:
  name:
    description:
      - Name of a specific pool to query.
      - If not specified, all pools are returned.
    type: str
notes:
  - Supports C(check_mode).
version_added: 1.15.0
'''

EXAMPLES = '''
- name: Get all pools
  jdevera.truenas.pool_info:
  register: pools

- name: Show pool names
  debug:
    msg: "{{ item.name }}"
  loop: "{{ pools.pools }}"

- name: Get a specific pool
  jdevera.truenas.pool_info:
    name: tank
  register: tank_pool
'''

RETURN = '''
pools:
  description:
    - A list of pool objects with their properties.
  type: list
  elements: dict
  returned: always
'''

from ansible.module_utils.basic import AnsibleModule
from ..module_utils.middleware import MiddleWare as MW
from ..module_utils import setup


def main():
    setup.require_scale_min_version()

    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str'),
        ),
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        pools=[],
    )

    mw = MW.client()

    name = module.params['name']

    try:
        if name is not None:
            pools = mw.call("pool.query",
                            [["name", "=", name]])
        else:
            pools = mw.call("pool.query")
        result['pools'] = pools
    except Exception as e:
        module.fail_json(msg=f"Error querying pools: {e}")

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
