#!/bin/sh
# Run 'ansible-test sanity' against this collection.
#
# ansible-test insists that the working directory be a real path under
# ansible_collections/<ns>/<name>/, and it resolves symlinks before
# checking — so the compatibility-link approach doesn't satisfy it. We
# rsync the source into a temp tree shaped that way and run from there.
set -e

NS=jdevera
NAME=truenas

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

dest="$tmp/ansible_collections/$NS/$NAME"
mkdir -p "$dest"

rsync -aq \
    --exclude=.git \
    --exclude=ansible_collections \
    --exclude=__pycache__ \
    --exclude=venv-docs \
    --exclude=tests/output \
    --exclude=.venv \
    --exclude=.local \
    --exclude=docs/build \
    --exclude=docs/rst \
    --exclude=docs/temp-rst \
    ./ "$dest/"

cd "$dest"
ansible-test sanity --venv --color
