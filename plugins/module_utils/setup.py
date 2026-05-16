# Common utility functions.
# Code that it'd be nice to have in Ansible's 'setup' module.

import re
import sys

from ..module_utils.middleware import MiddleWare as MW


def _parse_version(s):
    """Parse a dotted version string into a tuple of ints for comparison.

    Non-numeric trailing pieces (e.g. '-U5', 'a1') are stripped so that
    'TrueNAS-13.0-U5' compares cleanly against '25.10'. Stdlib only,
    so this works inside ansible-test sanity venvs (which don't
    install the 'packaging' library).
    """
    return tuple(int(m) for m in re.findall(r'\d+', s))


# Lowest TrueNAS SCALE version supported by this collection.
MIN_SCALE_VERSION = _parse_version("25.10")

# Version of TrueNAS we're running, so that we know how to invoke
# middlewared.
tn_version = None


# XXX - It would be nice to extend the 'setup' module to gather this
# information, set some facts, and then any module that needs them can
# refer to those facts.
def get_tn_version():
    """Get the version of TrueNAS being run"""

    # Return memoized data if we've already looked it up.
    global tn_version
    if tn_version is not None:
        return tn_version

    mw = MW.client()

    product_name = None
    product_type = None
    try:
        # product_type is a string like "CORE", "SCALE", or
        # "ENTERPRISE".
        product_type = mw.call("system.product_type", output='str')

        # product_version is a string like "TrueNAS-13.0-U5", or
        # "TrueNAS-SCALE-22.12.3.1"
        full_version = mw.call("system.version", output='str')

        # product_name is a string like "TrueNAS".
        #
        # TrueNAS CORE has `system.product_name' but SCALE doesn't, at
        # least not after some version.
        if product_type in ("CORE"):
            product_name = mw.call("system.product_name", output='str')
    except Exception:
        # XXX - Maybe try to soldier on with what we've got?
        raise

    # Extract additional information from 'full_version'.
    # This is a string of the form
    #
    # <product_name>-<version>
    # <product_name>-<product_type>-<version>
    #
    # Though you probably shouldn't rely on this too much
    match = re.match(r'^(?:(\w+)-)(?:(\w+)-)?(\d.*)', full_version)
    if match:
        if product_name is None:
            product_name = match[1]
        if product_type is None and match[2] != "":
            product_type = match[2]
        sys_version = match[3]
    else:
        # Can't parse the version string, so just use what we were
        # given.
        sys_version = full_version

    # Parse to a tuple of ints so version-gated callers can compare
    # against MIN_SCALE_VERSION (and each other) without depending on
    # 'packaging'.
    sys_version = _parse_version(sys_version)

    tn_version = {
        "name": product_name,
        "type": product_type,
        "version": sys_version,
    }

    return tn_version


def require_scale_min_version():
    """Fail fast if the host isn't running TrueNAS SCALE >= MIN_SCALE_VERSION.

    Modules in this collection target current SCALE; calling this at
    the top of main() short-circuits unsupported hosts with a clear
    message instead of letting middleware emit a cryptic error.
    """
    try:
        tn = get_tn_version()
    except Exception as e:
        print(f'{{"failed":true, "msg": "Error getting TrueNAS version: {e}"}}')
        sys.exit(1)

    if not (tn['name'] == "TrueNAS" and
            tn['type'] in {"SCALE", "COMMUNITY_EDITION"} and
            tn['version'] >= MIN_SCALE_VERSION):
        print(
            '{"failed":true, "msg": "This collection requires '
            f'TrueNAS SCALE {MIN_SCALE_VERSION} or newer."}}'
        )
        sys.exit(1)
