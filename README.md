# Ansible Collection - jdevera.truenas

Manage a [TrueNAS SCALE](https://www.truenas.com/) machine.

This collection is a personal fork of
[arensb.truenas](https://github.com/arensb/ansible-truenas), maintained
against my own homelab. It targets TrueNAS SCALE 25.10 and newer only.
All pre-25.10 compatibility (and the jail/plugin modules that no longer
have a TrueNAS API to talk to) has been removed.

## Differences from `arensb.truenas`

- **Floor raised to TrueNAS SCALE 25.10.** Every module calls
  `setup.require_scale_min_version()` and refuses to run on anything
  older. No CORE/TrueNAS-13 branches remain.
- **Modules removed:** `jail`, `jails`, `jail_fstab`, `plugin` — jails
  are gone from SCALE, so the modules can't function.
- **Options removed** that the modern SCALE middleware no longer
  accepts: `sharing_nfs`'s `alldirs`, `quiet`, `paths`; `nfs`'s
  `nfsv4`; `group`'s `non_unique`; `user`'s deprecated `sudo`,
  `sudo_nopasswd`.
- **`home: /nonexistent`** is no longer documented; the `user` module
  expects `/var/empty` to match what 25.10 middleware stores and
  returns.
- **Added module:** `ftp` for configuring the FTP service.

## Installing

Install directly from git via `ansible-galaxy`:

    ansible-galaxy collection install \
        git+https://github.com/jdevera/ansible-truenas.git

Or with a `requirements.yml`:

    collections:
      - name: https://github.com/jdevera/ansible-truenas.git
        type: git
        version: main

## Usage

    - hosts: truenas-box
      become: yes
      tasks:
        - jdevera.truenas.hostname:
            name: new-hostname
        - jdevera.truenas.service:
            name: sshd
            state: started

Several module names overlap with builtins (`user`, `group`,
`hostname`, `service`, ...), so prefer the fully-qualified
`jdevera.truenas.NAME` form rather than the unqualified one.

## Changelog

See [changelogs/changelog.yaml](changelogs/changelog.yaml).

## License

Apache-2.0. See [LICENSE](LICENSE).

## Authors

This fork is maintained by Jacobo de Vera ([@jdevera](https://github.com/jdevera)).

Upstream `arensb.truenas` was written and is maintained by Andrew
Arensburger and contributors. Most of the modules in this collection
are their work; thank you. The full upstream author list is preserved
in [galaxy.yml](galaxy.yml).
