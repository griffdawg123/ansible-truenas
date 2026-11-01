#!/usr/bin/python

# Manage certificate authorities.

# This module has an associated action module, which is a wrapper around
# this module to handle file slurping.

# XXX - This API allows you to create CA certs, but I don't want to
# implement that just yet. It seems fraught with peril. It might even
# be better to write a different module for this.

# XXX - Can't delete a CA while it's in use by a cert. Make sure this
# is indicated in an error message if it happens.

DOCUMENTATION = """
---
module: certificate_authority
short_description: Manage Certificate Authorities.
description:
  - Allows uploading CA certificates. These CA certs are used as part
    of a key infrastructure to sign host certificates.
  - On TrueNAS SCALE 25.10 the separate C(certificateauthority)
    middleware namespace was merged into C(certificate); a CA is now
    just a certificate created with C(cert_extensions.BasicConstraints.ca = True),
    which this module handles transparently.
options:
  name:
    description:
      - Name of the CA. Acts as the identifier for Ansible.
    type: str
    required: true
  src:
    description:
      - Pathname of the file containing the certificate.
      - See also O(certificate).
    type: path
  certificate:
    description:
      - Used instead of O(src) to specify a certificate inline.
    type: str
    aliases: [ ca, cert, ca_cert ]
  private_keyfile:
    description:
      - Pathname of the file containing the CA's private key.
    type: path
  private_key:
    description:
      - Used instead of O(private_keyfile) to specify a CA private key inline.
      - When uploading a CA certificate, the private key must be supplied, if there is one.
    type: str
  passphrase:
    description:
      - Passphrase for the CA cert's private key, if it has one.
    type: str
  state:
    description:
      - "C(present): Ensure that the CA cert is installed."
      - "C(absent): Ensure that the CA cert is not installed."
    type: str
    choices: [ absent, present ]
    default: present
notes:
  - Although TrueNAS supports creating CAs in the console, this module
    does not. It is not immediately clear how this should work in an
    idempotent Ansible module. At least for now, it is recommended that
    you generate CAs as part of your PKI system and upload them to
    TrueNAS devices. Failing that, you can manually generate a CA in
    the TrueNAS console and download it to your Ansible server.
  - SCALE 25.10's C(certificate.update) endpoint cannot toggle the
    revoked flag, so this module does not expose a C(revoked) option.
    Once installed, a CA can only be deleted.
version_added: 1.12.0
"""

EXAMPLES = """
- name: Install a CA cert from a file
  griffdawg.truenas.certificate_authority:
    name: my_ca_cert
    src: /etc/pki/my-ca.cert

- name: Install a CA cert and its key
  griffdawg.truenas.certificate_authority:
    name: my_ca_cert
    src: /etc/pki/my-ca.cert
    private_keyfile: /etc/pki/my-ca.key
    passphrase: "Open, sesame!"

- name: Install a CA cert from a string
  griffdawg.truenas.certificate_authority:
    name: my_ca_cert
    certificate: |-
      -----BEGIN CERTIFICATE-----
      MIIFdTCCA12gAwIBAgIUQZLjifloJRGBwalKcoODV20BmhUwDQYJKoZIhvcNAQEL
      ...
      B5A/Sn7DTfQz
      -----END CERTIFICATE-----

- name: Remove a CA cert
  griffdawg.truenas.certificate_authority:
    name: my_ca_cert
    state: absent
"""

RETURN = """
ca_cert:
  returned: always
  description:
    - A data structure describing a newly-installed CA certificate.
    - Only returned when a certificate is created.
  type: dict
  sample:
    id: 42
    name: imported_ca
    certificate: "-----BEGIN CERTIFICATE-----\\n..."
    privatekey: "-----BEGIN PRIVATE KEY-----\\n..."
    cert_type_CA: true
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
    certificate=dict(type="str", aliases=["ca", "cert", "ca_cert"]),
    private_keyfile=dict(type="path"),
    private_key=dict(type="str", no_log=True),
    passphrase=dict(type="str", no_log=True),
)
required_if = [
    ("state", "present", ("src", "certificate"), True),
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

    name = module.params["name"]
    state = module.params["state"]
    certificate = module.params["certificate"]
    private_key = module.params["private_key"]
    passphrase = module.params["passphrase"]

    # Look up the CA. On 25.10 CAs are filtered out of certificate.query
    # by cert_type_CA so we don't pick up a same-named host cert.
    try:
        ca_cert_info = mw.call(
            "certificate.query",
            [["name", "=", name], ["cert_type_CA", "=", True]],
        )
        ca_cert_info = ca_cert_info[0] if ca_cert_info else None
    except Exception as e:
        setup.fail(module, f"Error looking up CA cert {name}: {e}")

    if ca_cert_info is None:
        # CA cert doesn't exist.

        if state == "present":
            # Marking the imported cert as a CA: per the 25.10
            # certificate.create schema, cert_extensions.BasicConstraints.ca
            # is what flips cert_type_CA on the resulting record.
            arg = {
                "name": name,
                "create_type": "CERTIFICATE_CREATE_IMPORTED",
                "cert_extensions": {
                    "BasicConstraints": {
                        "ca": True,
                    },
                },
            }

            if certificate is not None:
                arg["certificate"] = certificate
            if private_key is not None:
                arg["privatekey"] = private_key
            if passphrase is not None:
                arg["passphrase"] = passphrase

            if module.check_mode:
                result["msg"] = f"Would have created CA certificate {name} with {arg}"
            else:
                try:
                    # certificate.create is a job on 25.10.
                    # XXX - There's a midclt request-size limit
                    # (around 4096 bytes) that can bite when the cert
                    # plus private key are large. If that happens
                    # we'll need to break the upload into a
                    # certificate.create followed by a separate
                    # privatekey update — but update doesn't accept
                    # the key field yet, so for now we just hope.
                    err = mw.job("certificate.create", arg)
                except Exception as e:
                    result["failed_invocation"] = arg
                    setup.fail(module, f"Error creating CA certificate {name}: {e}")
                result["ca_cert"] = err

            result["changed"] = True
        else:
            # CA isn't supposed to exist; already absent.
            result["changed"] = False

    else:
        # CA exists.
        if state == "present":
            # 25.10's certificate.update only accepts name (and we use
            # name as the identifier), so an existing CA has nothing
            # we can change.
            result["changed"] = False
        else:
            # CA is not supposed to exist.
            if module.check_mode:
                result["msg"] = f"Would have deleted CA {name}"
            else:
                try:
                    # certificate.delete is a job on 25.10.
                    err = mw.job("certificate.delete", ca_cert_info["id"])
                except Exception as e:
                    setup.fail(module, f"Error deleting CA cert {name}: {e}")
                result["status"] = err
            result["changed"] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
