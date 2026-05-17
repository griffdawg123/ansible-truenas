# Common utility functions.
# Code that it'd be nice to have in Ansible's 'setup' module.

import re
from typing import NoReturn

from ..module_utils.middleware import MiddleWare as MW


def _parse_version(s):
    """Parse a dotted version string into a tuple of ints for comparison.

    Non-numeric trailing pieces (e.g. '-U5', 'a1') are stripped so that
    'TrueNAS-13.0-U5' compares cleanly against '25.10'. Stdlib only,
    so this works inside ansible-test sanity venvs (which don't
    install the 'packaging' library).
    """
    return tuple(int(m) for m in re.findall(r"\d+", s))


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
        product_type = mw.call("system.product_type", output="str")

        # product_version is a string like "TrueNAS-13.0-U5", or
        # "TrueNAS-SCALE-22.12.3.1"
        full_version = mw.call("system.version", output="str")

        # product_name is a string like "TrueNAS".
        #
        # TrueNAS CORE has `system.product_name' but SCALE doesn't, at
        # least not after some version.
        if product_type in ("CORE"):
            product_name = mw.call("system.product_name", output="str")
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
    match = re.match(r"^(?:(\w+)-)(?:(\w+)-)?(\d.*)", full_version)
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


def fail(module, msg: str, **kwargs) -> NoReturn:
    """Report a module error via fail_json and never return.

    AnsibleModule.fail_json calls sys.exit(0) with a failure JSON
    payload, but it isn't typed as NoReturn, so static analyzers
    don't prune subsequent control flow. This wrapper carries the
    NoReturn annotation; the trailing raise is a defensive backstop
    in case fail_json's behavior ever changes.
    """
    module.fail_json(msg=msg, **kwargs)
    raise SystemExit(0)


def require_scale_min_version(module) -> None:
    """Fail the module if the host isn't running SCALE >= MIN_SCALE_VERSION.

    Must be called after AnsibleModule construction so fail_json can
    report the version mismatch through the standard Ansible protocol.
    """
    try:
        tn = get_tn_version()
    except Exception as e:
        fail(module, f"Error getting TrueNAS version: {e}")

    minimum = ".".join(str(p) for p in MIN_SCALE_VERSION)
    if not (
        tn["name"] == "TrueNAS"
        and tn["type"] in {"SCALE", "COMMUNITY_EDITION"}
        and tn["version"] >= MIN_SCALE_VERSION
    ):
        fail(module, f"This collection requires TrueNAS SCALE {minimum} or newer.")
