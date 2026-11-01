#!/bin/sh
# Run module logic tests against a fake, in-memory middleware.
#
# tests/local/fakemw stands in for truenas_api_client: each call reads
# and writes a JSON state file seeded from state.json. Nothing talks to
# a real TrueNAS host.
set -e

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)

state=$(mktemp)
trap 'rm -f "$state"' EXIT
cp "$here/state.json" "$state"

"$root/scripts/prepare-collection-layout.sh" >/dev/null
ANSIBLE_COLLECTIONS_PATH="$root" ANSIBLE_LOCALHOST_WARNING=0 \
    ansible-playbook -i localhost, "$here/playbook.yml" \
    -e state_file="$state" -e fake="$here/fakemw" "$@"
