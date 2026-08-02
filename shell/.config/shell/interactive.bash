# Modern CLI defaults. This file is sourced by ~/.bashrc.

# Do not let command aliases change script behaviour: these apply only to an
# interactive shell because ~/.bashrc returns early for non-interactive use.
if command -v eza >/dev/null 2>&1; then
    alias ls='eza --group-directories-first --icons=auto'
    alias ll='eza -alh --git --group-directories-first --icons=auto'
    alias tree='eza --tree --icons=auto'
fi
command -v bat >/dev/null 2>&1 && alias cat='bat --paging=never'
command -v btop >/dev/null 2>&1 && alias top='btop'

alias pacin='sudo pacman -S --needed'
alias pacup='sudo pacman -Syu'
alias orphaned="pacman -Qtdq"
alias sysinfo='fastfetch'

if command -v fzf >/dev/null 2>&1; then
    [[ -r /usr/share/fzf/key-bindings.bash ]] && . /usr/share/fzf/key-bindings.bash
    [[ -r /usr/share/fzf/completion.bash ]] && . /usr/share/fzf/completion.bash
    export FZF_DEFAULT_OPTS='--height=45% --layout=reverse --border=rounded --info=inline --preview-window=right:55%:wrap'
    export FZF_CTRL_T_OPTS="--preview 'bat --color=always --style=numbers --line-range=:300 {} 2>/dev/null || eza --tree --color=always {} 2>/dev/null'"
fi

command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init bash --cmd cd)"
command -v starship >/dev/null 2>&1 && eval "$(starship init bash)"

# Open Yazi and leave the shell in the directory selected on exit.
y() {
    local cwd_file cwd
    cwd_file="$(mktemp -t yazi-cwd.XXXXXX)" || return
    yazi "$@" --cwd-file="$cwd_file"
    IFS= read -r cwd < "$cwd_file"
    command rm -f -- "$cwd_file"
    [[ -n "$cwd" && "$cwd" != "$PWD" ]] && builtin cd -- "$cwd"
}

# Fast directory picker from anywhere under the home directory.
cdf() {
    local target
    target="$(find "$HOME" -mindepth 1 -type d \
        -not -path '*/.git/*' -not -path '*/node_modules/*' \
        -not -path '*/.cache/*' -not -path '*/.local/share/Trash/*' \
        2>/dev/null | fzf --prompt='directory> ')" && builtin cd -- "$target"
}
