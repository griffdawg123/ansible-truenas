#!/usr/bin/python
# -*- coding: utf-8 -*-
__metaclass__ = type

# Query ZFS dataset information from TrueNAS.
#
# midclt call pool.dataset.query
# midclt call pool.dataset.query '[["name", "=", "tank/data"]]'
# midclt call pool.dataset.query '[["pool", "=", "tank"]]'

DOCUMENTATION = '''
---
module: dataset_info
short_description: Gather information about ZFS datasets
description:
  - Query ZFS dataset (filesystem/volume) information from a TrueNAS host.
  - Returns a list of datasets with their properties (name, type, mountpoint,
    used space, available space, compression, etc.).
  - This is an info module that returns data in the result. It does not
    modify anything on the host.
options:
  name:
    description:
      - Full ZFS path of a specific dataset to query (e.g., C(tank/data)).
      - If not specified, all datasets are returned.
      - Mutually exclusive with I(pool).
    type: str
  pool:
    description:
      - Name of a pool to filter datasets by.
      - Returns all datasets belonging to the specified pool.
      - Mutually exclusive with I(name).
    type: str
  type:
    description:
      - Filter datasets by type.
    type: str
    choices: [ FILESYSTEM, VOLUME ]
notes:
  - Supports C(check_mode).
version_added: 1.15.0
'''

EXAMPLES = '''
- name: Get all datasets
  arensb.truenas.dataset_info:
  register: datasets

- name: Show dataset names and types
  debug:
    msg: "{{ item.name }} ({{ item.type }})"
  loop: "{{ datasets.datasets }}"

- name: Get a specific dataset
  arensb.truenas.dataset_info:
    name: tank/data
  register: my_dataset

- name: Get all datasets in a pool
  arensb.truenas.dataset_info:
    pool: tank
  register: tank_datasets

- name: Get only filesystems (no volumes)
  arensb.truenas.dataset_info:
    type: FILESYSTEM
  register: filesystems
'''

RETURN = '''
datasets:
  description:
    - A list of dataset objects with their properties.
  type: list
  elements: dict
  returned: always
'''

from ansible.module_utils.basic import AnsibleModule
from ..module_utils.middleware import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str'),
            pool=dict(type='str'),
            type=dict(type='str', choices=['FILESYSTEM', 'VOLUME']),
        ),
        mutually_exclusive=[
            ['name', 'pool'],
        ],
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        datasets=[],
    )

    mw = MW.client()

    name = module.params['name']
    pool = module.params['pool']
    ds_type = module.params['type']

    # Build query filters
    filters = []
    if name is not None:
        filters.append(["name", "=", name])
    if pool is not None:
        filters.append(["pool", "=", pool])
    if ds_type is not None:
        filters.append(["type", "=", ds_type])

    try:
        if filters:
            datasets = mw.call("pool.dataset.query", filters)
        else:
            datasets = mw.call("pool.dataset.query")
        result['datasets'] = datasets
    except Exception as e:
        module.fail_json(msg=f"Error querying datasets: {e}")

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
