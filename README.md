# Tommy's Arch dotfiles

Managed with GNU Stow. From this directory, apply them with:

```sh
stow --target="$HOME" shell apps bin
```

The main `.bashrc` only contains a one-line loader for the managed shell
fragment, preserving the older machine-specific functions and aliases.

`restic-home` intentionally stores no password or repository URL. Configure
those through `RESTIC_REPOSITORY` and `RESTIC_PASSWORD_FILE` (or
`RESTIC_PASSWORD_COMMAND`) after choosing an external or remote destination.
