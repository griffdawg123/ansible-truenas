#!/bin/sh
# Ensure this checkout is visible at ansible_collections/<ns>/<name>/
# so tools that expect Ansible's standard collection layout (mypy,
# ansible-doc, ansible-test) can resolve `from ..module_utils import ...`
# as `ansible_collections.<ns>.<name>.plugins.module_utils.*`.
set -e

NS=griffdawg
NAME=truenas

mkdir -p "ansible_collections/$NS"
[ -e "ansible_collections/$NS/$NAME" ] || ln -s ../.. "ansible_collections/$NS/$NAME"
