#!/usr/bin/env bash
# Run a read-only Gemini code review through the Antigravity CLI (agy).
#
# agy has no headless read-only mode: its default mode writes inside the
# workspace, and plan mode waits for a plan approval that print mode cannot
# give. So agy runs in a throwaway folder that holds copies of the review
# inputs. The real repo is never in the agy workspace, so an agy write can only
# land in the copy. agy soft-denies shell commands in print mode.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: agy-review.sh [options] [--uncommitted] [PATH...]

Copy the review inputs into a throwaway folder and run a Gemini review on
them with agy. Run it from inside the repo to review.

Targets:
  --uncommitted        Review staged, unstaged and untracked changes.
  PATH...              With --uncommitted, review only the changes under
                       these paths. Alone, review these files or folders.

Options:
  --focus TEXT         Add review instructions, for example "check the retry logic".
  --model MODEL        agy model (default: the model in agy settings).
  --effort LEVEL       low, medium, high or max (default: agy settings).
  --timeout DURATION   Print-mode time limit (default: 600s).
  --max-bytes N        Refuse a review larger than N bytes of input (default: 400000).
  -h, --help           Show this help.

Environment:
  AGY_REVIEW_GUIDE     Review style guide to copy in (default: none).
  AGY_REVIEW_STANDARDS Shared standards to add to the workspace AGENTS.md (default: none).

Output: the last line on stdout is the run folder. It holds review.md (the
review text), result.json (the raw agy output), stderr.txt, and workspace/
(the inputs agy saw).

Exit status: 0 on a complete review, 2 when agy timed out or failed, 1 on a
usage or input error.
EOF
}

die() {
  echo "agy-review: $*" >&2
  exit 1
}

uncommitted=false
focus=""
model=""
effort=""
timeout="600s"
max_bytes=400000
paths=()

while (($# > 0)); do
  case "$1" in
    -h | --help)
      usage
      exit 0
      ;;
    --uncommitted) uncommitted=true ;;
    --focus)
      focus="${2:?--focus needs a value}"
      shift
      ;;
    --model)
      model="${2:?--model needs a value}"
      shift
      ;;
    --effort)
      effort="${2:?--effort needs a value}"
      shift
      ;;
    --timeout)
      timeout="${2:?--timeout needs a value}"
      shift
      ;;
    --max-bytes)
      max_bytes="${2:?--max-bytes needs a value}"
      shift
      ;;
    --)
      shift
      paths+=("$@")
      break
      ;;
    -*) die "unknown option: $1 (see --help)" ;;
    *) paths+=("$1") ;;
  esac
  shift
done

if [[ "$uncommitted" == false && ${#paths[@]} -eq 0 ]]; then
  usage >&2
  exit 1
fi
command -v agy >/dev/null || die "agy is not installed. Run: brew install --cask antigravity-cli"
command -v jq >/dev/null || die "jq is not installed"

guide="${AGY_REVIEW_GUIDE:-}"
standards="${AGY_REVIEW_STANDARDS:-}"

if root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  in_git=true
else
  in_git=false
  root="$PWD"
fi
[[ "$uncommitted" == true && "$in_git" == false ]] && die "--uncommitted needs a git repo"

run_dir="$(mktemp -d "${TMPDIR:-/tmp}/agy-review.XXXXXX")"
ws="$run_dir/workspace"
mkdir -p "$ws"
file_list="$run_dir/files.txt"

# Convert each path to a path relative to $root. A diff review can name a
# deleted file or folder, so only a full review needs the path to exist.
# Without paths, "." stands for the whole repo. The array is never empty,
# because macOS Bash 3.2 rejects an empty array expansion under set -u.
prefix=""
[[ "$in_git" == true ]] && prefix="$(git rev-parse --show-prefix)"
rel_paths=(.)
if ((${#paths[@]} > 0)); then
  rel_paths=()
  for p in "${paths[@]}"; do
    [[ "$uncommitted" == false && ! -e "$p" ]] && die "no such path: $p"
    case "$p" in
      "$root") rel="." ;;
      /*)
        rel="${p#"$root"/}"
        [[ "$rel" == "$p" ]] && die "path is outside $root: $p"
        ;;
      *) rel="${prefix}${p}" ;;
    esac
    rel_paths+=("${rel%/}")
  done
fi

# Write the review files to $file_list as paths relative to $root.
if [[ "$uncommitted" == true ]]; then
  git -C "$root" rev-parse --verify --quiet HEAD >/dev/null || die "the repo has no commit to diff against"
  git -C "$root" diff HEAD -- "${rel_paths[@]}" >"$ws/REVIEW-DIFF.patch"
  {
    git -C "$root" diff HEAD --name-only --diff-filter=d -- "${rel_paths[@]}"
    git -C "$root" ls-files --others --exclude-standard -- "${rel_paths[@]}"
  } | sort -u >"$file_list"
  [[ -s "$file_list" ]] || die "no uncommitted changes to review"
  target="the uncommitted changes in this repo. REVIEW-DIFF.patch holds the diff of tracked files against HEAD. The folder holds full copies of every changed file and every untracked file. Review the changes, and use the full files for context"
else
  : >"$file_list"
  for rel in "${rel_paths[@]}"; do
    if [[ "$in_git" == true ]]; then
      git -C "$root" ls-files --cached --others --exclude-standard -- "$rel" >>"$file_list"
    else
      (cd "$root" && find "$rel" -type f -not -path '*/.git/*') >>"$file_list"
    fi
  done
  sort -u -o "$file_list" "$file_list"
  [[ -s "$file_list" ]] || die "the paths hold no files to review"
  target="these files and folders: ${paths[*]}"
fi

# Copy each review file into the workspace at the same relative path.
total=0
while IFS= read -r f; do
  [[ -f "$root/$f" ]] || continue
  mkdir -p "$ws/$(dirname "$f")"
  cp "$root/$f" "$ws/$f"
  total=$((total + $(wc -c <"$root/$f")))
done <"$file_list"
[[ -f "$ws/REVIEW-DIFF.patch" ]] && total=$((total + $(wc -c <"$ws/REVIEW-DIFF.patch")))

if ((total > max_bytes)); then
  echo "agy-review: $total bytes of input is over the --max-bytes limit of $max_bytes." >&2
  echo "agy-review: the largest input files:" >&2
  (cd "$ws" && find . -type f -exec wc -c {} + | sort -rn | sed -n '2,11p') >&2
  exit 1
fi

# agy loads AGENTS.md from the workspace. Put the shared standards and the repo's own rule files in
# it. agy does not follow a Claude `@` import and cannot read outside the workspace, so the text goes
# in whole.
rules=""
[[ -n "$standards" && -f "$standards" ]] && rules+="$(cat "$standards")"$'\n\n'
for name in CLAUDE.md AGENTS.md GEMINI.md; do
  [[ -f "$root/$name" ]] && rules+="$(cat "$root/$name")"$'\n\n'
done
if [[ -n "$rules" ]]; then
  printf '%s' "$rules" >"$ws/AGENTS.md"
fi

guide_line=""
if [[ -n "$guide" && -f "$guide" ]]; then
  cp "$guide" "$ws/REVIEW-GUIDE.md"
  guide_line="REVIEW-GUIDE.md is a copy of the user's review guide. AGENTS.md can name it as guides/code-review.md. Read REVIEW-GUIDE.md and follow it. Do not try to read the original."
fi

prompt="You are a read-only code reviewer. This folder holds copies of the review inputs. Do not edit any file. Do not run shell commands. Do the whole review yourself. Do not start a subagent, because this run ends before a subagent reports.

Review ${target}.

AGENTS.md, if present, holds the project rules. ${guide_line}

Report only real defects: wrong behavior, wrong logic, unsafe error handling, security problems, a broken project rule, new behavior without a test, and docs that contradict the code. Skip formatting and anything a linter reports.

For each finding, give:
- severity: high, medium or low
- the file path relative to this folder, and the line number
- a verbatim quote of the code or text
- the failure: the input or state, and the wrong result it causes
- one preferred fix

Rank the findings by severity. If a file you need is not in this folder, name it under a heading 'Missing context'. If you find no defect, write 'No findings'. Put the complete review in your final message."
[[ -n "$focus" ]] && prompt+=$'\n\nThe author also asks: '"$focus"

args=(--sandbox --output-format json --print-timeout "$timeout")
[[ -n "$model" ]] && args+=(--model "$model")
[[ -n "$effort" ]] && args+=(--effort "$effort")

echo "agy-review: reviewing $total bytes of input in $ws" >&2

# Remove Google key variables so agy can use only the subscription login.
status=0
(cd "$ws" && env -u GEMINI_API_KEY -u GOOGLE_API_KEY -u GOOGLE_CLOUD_PROJECT \
  -u GOOGLE_CLOUD_QUOTA_PROJECT -u GOOGLE_APPLICATION_CREDENTIALS -u GOOGLE_MAPS_API_KEY \
  agy "${args[@]}" -p "$prompt" </dev/null >"$run_dir/result.json" 2>"$run_dir/stderr.txt") || status=$?

if ! jq -e . "$run_dir/result.json" >/dev/null 2>&1; then
  echo "agy-review: agy exited with status $status and no JSON result. See $run_dir/stderr.txt" >&2
  echo "$run_dir"
  exit 2
fi

jq -r '.response // ""' "$run_dir/result.json" >"$run_dir/review.md"

denied="$(jq -r '[.denied_actions[]?.action] | join(", ")' "$run_dir/result.json")"
[[ -n "$denied" ]] && echo "agy-review: agy asked for actions it did not get: $denied. A denied read means it wanted a file that is not in the workspace." >&2

reason="$(jq -r '.finished_reason // ""' "$run_dir/result.json")"
result_status="$(jq -r '.status // ""' "$run_dir/result.json")"
if [[ "$reason" == "print_timeout" || "$result_status" != "SUCCESS" ]]; then
  echo "agy-review: the review is incomplete (status: $result_status, finished_reason: ${reason:-none}). review.md holds the partial text." >&2
  echo "$run_dir"
  exit 2
fi

# A complete review lists findings or says "No findings". A reply with neither stopped early.
if ! grep -qiE 'severity|no findings' "$run_dir/review.md"; then
  echo "agy-review: the review is incomplete. review.md holds no findings and no 'No findings' line." >&2
  echo "$run_dir"
  exit 2
fi

jq -r '"agy-review: tokens in \(.usage.input_tokens), out \(.usage.output_tokens), \(.duration_seconds | floor)s"' "$run_dir/result.json" >&2
echo "$run_dir"
