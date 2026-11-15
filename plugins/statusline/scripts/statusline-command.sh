#!/usr/bin/env bash
# Claude Code status line - mirrors ~/.bashrc PS1 style with Claude context info
# Input: JSON via stdin from Claude Code

input=$(cat)

# Colors via tput (matches ~/.bashrc style and git-prompt.sh colorize)
txtbld=$(tput bold)
txtred=$(tput setaf 1)
txtgrn=$(tput setaf 2)
txtpur=$(tput setaf 5)  # purple for branch (git-prompt.sh uses 1;35 bold)
txtblu=$(tput setaf 4)
txtrst=$(tput sgr0)

# Extract fields from JSON input
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
model=$(echo "$input" | jq -r '.model.display_name // ""')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
total_in=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_out=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')

# Save original path for git commands before shortening for display
cwd_full="$cwd"

# Shorten home directory and trim to last 2 components (matches PROMPT_DIRTRIM=2)
home="${HOME:-$(eval echo ~)}"
if [[ "$cwd" == "$home"* ]]; then
    cwd="~${cwd#"$home"}"
fi
IFS='/' read -ra parts <<< "$cwd"
if [ "${#parts[@]}" -gt 3 ]; then
    # Keep the first component (~, or empty for an absolute path) and the last 2 components
    cwd="${parts[0]}/…/${parts[-2]}/${parts[-1]}"
fi

# Git info (mirrors git-prompt.sh with GIT_PS1_SHOWCOLORHINTS, SHOWDIRTYSTATE, SHOWSTASHSTATE)
git_info=""
if GIT_OPTIONAL_LOCKS=0 git -C "$cwd_full" rev-parse --git-dir >/dev/null 2>&1; then
    if git_branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd_full" symbolic-ref --short HEAD 2>/dev/null); then
        branch_color="$txtpur"
    else
        # Detached HEAD — show short sha, colored red like git-prompt.sh
        git_branch="$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd_full" rev-parse --short HEAD 2>/dev/null)..."
        branch_color="$txtred"
    fi

    # Dirty state: unstaged (*) in red, staged (+) in green
    w="" i=""
    GIT_OPTIONAL_LOCKS=0 git -C "$cwd_full" diff --no-ext-diff --quiet 2>/dev/null || w="${txtred}*${txtrst}"
    GIT_OPTIONAL_LOCKS=0 git -C "$cwd_full" diff --no-ext-diff --cached --quiet 2>/dev/null || i="${txtgrn}+${txtrst}"

    # Stash indicator ($) in blue
    s=""
    if GIT_OPTIONAL_LOCKS=0 git -C "$cwd_full" rev-parse --verify --quiet refs/stash >/dev/null 2>&1; then
        s="${txtblu}\$${txtrst}"
    fi

    local_state="${w}${i}${s}"
    git_info=" (${branch_color}${git_branch}${txtrst}${local_state:+ ${local_state}})"
fi

# Context usage indicator
ctx_info=""
if [ -n "$used_pct" ]; then
    used_int=${used_pct%.*}
    if [ "$used_int" -ge 75 ]; then
        ctx_info=" ${txtbld}${txtred}[ctx:${used_pct}%]${txtrst}"
    else
        ctx_info=" [ctx:${used_pct}%]"
    fi
fi

# Session token usage (input + output, in K)
total_tokens=$((total_in + total_out))
if [ "$total_tokens" -ge 1000 ]; then
    token_str="$(awk "BEGIN { printf \"%.1f\", $total_tokens / 1000 }")k"
else
    token_str="${total_tokens}"
fi

# Model info
model_info=""
if [ -n "$model" ]; then
    model_info=" ${model}"
fi

printf '%s%s%s%s%s%s [tok:%s]\n' \
    "${txtblu}" "${cwd}" "${txtrst}" \
    "${git_info}" \
    "${ctx_info}" \
    "${model_info}" \
    "${token_str}"
