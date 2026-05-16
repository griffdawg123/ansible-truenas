macbackups
==========

Set up a volume for MacOS Time Machine to write backups.

Role Variables
--------------

`backup_user`
: Name of the user that will own the backup volume. Will be created if it doesn't already.
Default: `macbackups`.

*`backup_user_passwd`*
: Password for `backup_user`. Mac clients will use this password to
connect. Since this is a secret, it should be stored in a secure
location, e.g., an ansible-vault-encrypted inventory file.

`backup_user_name`
: Descriptive name for `backup_user`.
Default: "Mac Time Machine backups".

*`homes_dir`*
: The directory that contains user home directories. Must start with
`/mnt`. The `backup_user`'s home directory will be created here.

*`vol_pool`*
: The pool that the backup volume will go in. This must be specified,
as there is no good default.

`vol_name`
: Name of the backup volume. Default: `macbackups`.

`allow_hosts`
: A list of hosts that may have access to the backup volume. Elements
may be hostnames, IP addresses, or IP ranges in CIDR notation.
Default: empty list.

`deny_hosts`
: A list of hosts that do not have access to the backup volume.
Elements are as for `allow_hosts`. Defaults to `[ ALL ]`. In case of
conflict, `allow_hosts` takes precedence over `deny_hosts`, so it is
safe (and recommended) to keep the default.

Dependencies
------------

A list of other roles hosted on Galaxy should go here, plus any details in regards to parameters that may need to be set for other roles, or variables that are used from other roles.

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: servers
      roles:
        - role: jdevera.truenas.macbackups
          backup_user_passwd: "{{ macbackups_passwd }}"
          homes_dir: /mnt/mypool/home
          vol_pool: mypool
          allow_hosts:
            - 10.20.1.1
            - 192.168.1.0/24

Version Added
-------------
1.14.3
