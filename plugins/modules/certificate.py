#!/usr/bin/python

# Manage certificates.

# XXX - What should happen with
# certificate:
#   name: my_cert
#   revoked: yes
# when the cert doesn't exist?
#
# Right now, it tries to install the cert, and immediately revoke it.
# And that's what it should do: if the caller wanted the cert to not
# exist, they'd have used "state: absent", not "revoked: yes".
# So the cert needs to be installed for it to be revoked.
#
# Maybe add "state: revoked_or_absent"? Or "revoke: if_present"?

# XXX - There might be a chicken-and-egg problem: how do we update the
# host's https cert while also using https to talk to the API
# endpoint?

DOCUMENTATION = """
---
module: certificate
short_description: Manage host certificates.
description:
  - Allows uploading and revoking host certificates.
options:
  name:
    description:
      - Name of the certificate. This serves as an identifier
        for Ansible.
    type: str
    required: true
  src:
    description:
      - Pathname of the file containing the certificate.
      - See also O(certificate).
      - This file must only contain the certificate, not any signing certificates.
    type: path
  certificate:
    description:
      - Used instead of O(src) to specify a certificate inline.
    type: str
  private_keyfile:
    description:
      - Pathname of the file containing the certificate's private key.
    type: path
  private_key:
    description:
      - Used instead of O(private_keyfile) to specify a private key inline.
    type: str
  passphrase:
    description:
      - Passphrase for the certificate's private key, if it has one.
    type: str
  state:
    description:
      - Whether the certificate should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  revoked:
    description:
      - Set to true to revoke a certificate at upload time. It is possible
        to upload a certificate and immediately revoke it, though it is
        not clear why this might be useful.
      - "Perhaps counterintuitively, only specifying O(name) and
        O(revoked=yes) will cause an error when the cert does not exist.
        This is because the cert needs to be uploaded before it can be
        revoked."
      - Note that under TrueNAS SCALE 25.10 the C(certificate.update)
        endpoint cannot toggle the revoked flag on an existing
        certificate. The middleware accepts only a name change there.
        For new certificates this option still triggers a revoke
        immediately after creation.
    type: bool
    default: false
notes:
  - Although TrueNAS supports creating certificates in the console,
    this module does not. It is not immediately clear how this should work
    in an idempotent Ansible module. At least for now, it is recommended
    that you generate certificates as part of your PKI system, and upload
    them to TrueNAS devices. Failing that, you can manually generate a cert
    in the TrueNAS console, and download it to your Ansible server.
version_added: 1.12.0
"""

EXAMPLES = """
- name: Install an existing cert from a file.
  jdevera.truenas.certificate:
    name: my_cert
    src: /etc/pki/truenas-host.cert

- name: Same, but include a private key and passphrase.
  jdevera.truenas.certificate:
    name: my_cert
    src: /etc/pki/truenas-host.cert
    private_key: |-
      -----BEGIN PRIVATE KEY-----
      MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC9QCpnXKNXoOdx
      ...
    passphrase: "squeamish ossifrage"

- name: Revoke a cert at upload time
  jdevera.truenas.certificate:
    name: my_cert
    src: /etc/pki/truenas-host.cert
    revoked: true

- name: Remove a cert
  jdevera.truenas.certificate:
    name: my_cert
    state: absent
"""

RETURN = """
certificate:
  returned: always
  description:
    - A data structure describing a newly-created or -installed certificate.
    - Only returned when a certificate is created.
  type: dict
  sample:
    id: 42
    name: imported_cert
    type: CERTIFICATE
    certificate: "-----BEGIN CERTIFICATE-----\\n..."
    privatekey: "-----BEGIN PRIVATE KEY-----\\n..."
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils import setup
from ..module_utils.middleware import MiddleWare as MW

# Defined at module scope so the matching action plugin can import them
# to validate arguments before file slurping.
argument_spec = dict(
    name=dict(type="str", required=True),
    state=dict(type="str", default="present", choices=["absent", "present"]),
    src=dict(type="path"),
    certificate=dict(type="str"),
    private_keyfile=dict(type="path"),
    private_key=dict(type="str", no_log=True),
    passphrase=dict(type="str", no_log=True),
    revoked=dict(type="bool", default=False),
)
required_if = [
    ("state", "present", ("src", "certificate", "revoked"), True),
]
mutually_exclusive = [
    ("src", "certificate"),
    ("private_keyfile", "private_key"),
]


def main():
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=required_if,
        mutually_exclusive=mutually_exclusive,
    )

    setup.require_scale_min_version(module)

    result = dict(changed=False, msg="")
    mw = MW.client()

    # Assign variables from properties, for convenience
    name = module.params["name"]
    state = module.params["state"]
    certificate = module.params["certificate"]
    private_key = module.params["private_key"]
    passphrase = module.params["passphrase"]
    revoked = module.params["revoked"]

    # Look up the certificate. On SCALE 25.10 certificate.query also
    # returns CA certs (the two stores were merged), so callers should
    # keep cert and CA names distinct.
    try:
        cert_info = mw.call("certificate.query", [["name", "=", name]])
        cert_info = cert_info[0] if cert_info else None
    except Exception as e:
        setup.fail(module, f"Error looking up certificate {name}: {e}")

    if cert_info is None:
        # Cert doesn't exist.

        if state == "present":
            # Cert is supposed to exist, so create it.
            arg = {
                "name": name,
                "create_type": "CERTIFICATE_CREATE_IMPORTED",
            }

            if certificate is not None:
                arg["certificate"] = certificate
            if private_key is not None:
                arg["privatekey"] = private_key
            if passphrase is not None:
                arg["passphrase"] = passphrase

            if module.check_mode:
                result["msg"] = f"Would have created certificate {name} with {arg}"
            else:
                try:
                    # certificate.create is a job, not a regular call.
                    err = mw.job("certificate.create", arg)
                except Exception as e:
                    result["failed_invocation"] = arg
                    setup.fail(module, f"Error creating certificate {name}: {e}")
                result["certificate"] = err

            if revoked:
                # XXX - To revoke a cert, need its private key. Add
                # this to requirements when we have one.
                if module.check_mode:
                    result["msg"] += f"\nWould mark certificate {name} as revoked."
                else:
                    try:
                        err2 = mw.call("certificate.update", err["id"], {"revoked": revoked})
                        result["certificate"] = err2
                    except Exception as e:
                        # XXX - Roll back the create? Can we?
                        setup.fail(module, f"Error revoking certificate {name}: {e}")

            result["changed"] = True
        else:
            # Cert is not supposed to exist; nothing to do.
            result["changed"] = False

    else:
        # Cert exists.
        if state == "present":
            # certificate.update on 25.10 only accepts name and revoked,
            # but middleware rejects toggling 'revoked' here — and we
            # use name as the identifier, so there's nothing legitimate
            # to update on an existing cert. Treat as a no-op.
            result["changed"] = False
        else:
            # Cert is not supposed to exist.
            if module.check_mode:
                result["msg"] = f"Would have deleted certificate {name}"
            else:
                try:
                    # certificate.delete is a job on 25.10.
                    err = mw.job("certificate.delete", cert_info["id"])
                except Exception as e:
                    setup.fail(module, f"Error deleting certificate {name}: {e}")
                result["status"] = err
            result["changed"] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
