# Ansible Collection - griffdawg.truenas

Manage a [TrueNAS](https://www.truenas.com/) machine.

This is a maintained fork of
[arensb/ansible-truenas](https://github.com/arensb/ansible-truenas)
(`arensb.truenas`), renamed to `griffdawg.truenas`. It targets current
TrueNAS SCALE releases (25.10+) and talks to the middleware directly
rather than through the deprecated `/api/v2.0` REST API.

## Included content

This collection consists primarily of a set of Ansible modules to
configure a TrueNAS machine, using the
[TrueNAS API](https://www.truenas.com/docs/api/websocket.html)
to control the Middleware Daemon.

It aims to be intuitive to use, and to avoid unpleasant surprises.

Each module documents its options and examples in its `DOCUMENTATION`
and `EXAMPLES` blocks; run `ansible-doc griffdawg.truenas.<module>`.

## Installing this collection

Install from git, pinned to a tag, via `requirements.yml`:

    collections:
      - name: https://github.com/griffdawg123/ansible-truenas.git
        type: git
        version: v3.0.0

then `ansible-galaxy collection install -r requirements.yml`.

## Examples

    - name: Example tasks
      collections:
        - griffdawg.truenas
      hosts: truenas-box
      become: yes
      tasks:
        - name: Set the hostname
          hostname:
            name: new-hostname
        - name: Turn on sshd
          service:
            name: sshd

Note that since several of the module names are the same as builtin
ones, you may want to use the full name to avoid confusion:

    - hosts: truenas-box
      become: yes
      tasks:
        - griffdawg.truenas.hostname:
            name: new-hostname

## Environment Variables

### `middleware_method`

There are two ways of communicating with the middleware daemon on
TrueNAS, referred to here as `midclt` and `client`. `midclt` is older
and better-tested, while `client` is faster but less-well-tested. The
default is `client`.

Set the `middleware_method` environment variable to either `client` or
`midclt` at either the play or task level in your playbook to manually
select how this module communicates with the middleware daemon.

Example:

    - collections: griffdawg.truenas
      hosts: my-nas
      become: yes
      environment:
        middleware_method: client
      tasks:
        - name: Create a jail
          jail:
            name: my-jail
            release: 13.1-RELEASE
            state: running

## Contributing to this collection
The best way to contribute a patch or feature is to create a pull request.

If you'd like to write your own module, the `extras/template` file
provides a good starting point.

The [HACKING](HACKING.md) file has some tips on how to get around.

## Documentation

Run `ansible-doc -l griffdawg.truenas` to list modules, and
`ansible-doc griffdawg.truenas.<module>` for details.

## Supported versions of Ansible
- Tested with 2.10.8

## Changelog

See [changelog.yaml](changelogs/changelog.yaml). Releases up to 2.0.3
are from upstream `arensb.truenas`.

## Authors and Contributors

- Andrew Arensburger ([@arensb](https://mastodon.social/@arensb))
- Ed Hull (https://github.com/edhull)
- Mozzie (https://github.com/MozzieBytes)
- bmarinov (https://github.com/bmarinov)
- Paul Heidenreich (https://github.com/Paulomart)
- Gustavo Campos (https://github.com/guhcampos)
- kamransaeed (https://github.com/kamransaeed)
- pofo14 (https://github.com/pofo14)
