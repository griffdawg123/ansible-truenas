#!/bin/sh
# Validate that every module's DOCUMENTATION parses via ansible-doc.
#
# ansible-doc looks for modules at
# $ANSIBLE_COLLECTIONS_PATH/ansible_collections/<ns>/<name>/plugins/modules/,
# so we expose this checkout at that path with a symlink. The symlink is
# under .gitignore — created on demand.
set -e

NS=jdevera
NAME=truenas

mkdir -p "ansible_collections/$NS"
[ -e "ansible_collections/$NS/$NAME" ] || ln -s ../.. "ansible_collections/$NS/$NAME"

modules=$(
    for f in plugins/modules/*.py; do
        base=$(basename "$f" .py)
        printf '%s.%s.%s ' "$NS" "$NAME" "$base"
    done
)

# shellcheck disable=SC2086
ANSIBLE_COLLECTIONS_PATH=. \
    ansible-doc -M . --json --type module $modules >/dev/null
