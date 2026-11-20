#!/usr/bin/env bash
# Wrapper script to run reimport-odt commands on LfL server.
set -euo pipefail

# --- Defaults ----------------------------------------------------------------
local_base_dir="${LFL_LOCAL_DIR:-${HOME}/dev/lfl-temp}"
remote_user=ubuntu
remote_base=/tmp/reimport-odt
remote_app_dir=/var/www/lessons-from-luke/current

usage() {
    cat <<USAGE
Usage: $(basename "$0") <command> [options]

Commands:
  evaluate     Upload the ODT files and run 'reimport-odt evaluate'
  conflicts    Run 'reimport-odt conflicts'
  resolve      Upload the local conflicts.tsv and run 'reimport-odt resolve'
  apply        Back up the DB, then run 'reimport-odt apply'
  backup       Back up the DB only
  clean        Delete the lesson's files on the server

Options:
  -l, --lesson NAME   Lesson file base name, e.g. Luke-Q1-L02 (required)
  -d, --dir DIR       Local base folder (default: $local_base_dir)
  -n, --dry-run       With 'apply': run 'apply --dry-run' (skips the DB backup)
  -h, --help          Show this help

Environment:
  LFL_HOST            Server host name (required)
  LFL_LOCAL_DIR       Default for --dir
USAGE
}

die() { echo "Error: $*" >&2; exit 1; }

# --- Parse arguments (options may come before or after the command) ----------
command=""
lesson=""
dry_run=false

while (( $# )); do
    case "$1" in
        -l|--lesson) (( $# >= 2 )) || die "$1 needs a value"; lesson="$2"; shift ;;
        --lesson=*)  lesson="${1#*=}" ;;
        -d|--dir)    (( $# >= 2 )) || die "$1 needs a value"; local_base_dir="$2"; shift ;;
        --dir=*)     local_base_dir="${1#*=}" ;;
        -n|--dry-run) dry_run=true ;;
        -h|--help)   usage; exit 0 ;;
        -*)          die "unknown option: $1 (see --help)" ;;
        *)           [[ -z $command ]] || die "only one command allowed (got '$command' and '$1')"
                     command="$1" ;;
    esac
    shift
done

case "$command" in
    evaluate|conflicts|resolve|apply|backup|clean) ;;
    "") usage >&2; exit 1 ;;
    *)  die "unknown command: $command (see --help)" ;;
esac

[[ $dry_run == false || $command == apply ]] || die "--dry-run only applies to 'apply'"
[[ -n ${LFL_HOST:-} ]] || die "LFL_HOST must be set."
if [[ $command != backup ]]; then
    [[ -n $lesson ]] || die "--lesson is required (e.g. -l Luke-Q1-L02)"
    [[ $lesson =~ ^[A-Za-z0-9._-]+$ ]] || die "invalid lesson name: '$lesson'"
fi
remote="${remote_user}@${LFL_HOST}"

filename_base="$lesson"
odt_filename="Sango_${filename_base}.odt"
local_eval_dir="${local_base_dir}/${filename_base}"
local_old_file="${local_eval_dir}/old/${odt_filename}"
local_new_file="${local_eval_dir}/${odt_filename}"

remote_new="${remote_base}/${filename_base}"
remote_old="${remote_new}/old"
remote_evaluation_file="${remote_new}/Sango_${filename_base}.evaluation.json"
remote_conflicts_file="${remote_new}/conflicts.tsv"

# --- Helpers -----------------------------------------------------------------
remote_has() {   # true if the file exists and is readable on the server
    ssh "$remote" "test -r $(printf %q "$1")"
}

require_evaluation() {
    remote_has "$remote_evaluation_file" || die "evaluation not done."
}

# run_reimport LOGFILE ARGS... : runs 'yarn reimport-odt ARGS...' as 'lessons',
# writing output to LOGFILE in the lesson's remote folder.
run_reimport() {
    local log="${remote_new}/$1"; shift
    local args
    args=$(printf '%q ' "$@")
    ssh "$remote" "sudo -iu lessons bash -s" <<EOF
        export NVM_DIR="\$HOME/.nvm"
        export BETTER_AUTH_URL=https://fake
        export NODE_ENVIRONMENT=production
        . "\$NVM_DIR/nvm.sh"
        cd "$remote_app_dir"
        if ! yarn reimport-odt $args > "$log" 2>&1; then
            echo "Failed. Last lines of $log:" >&2
            tail -n 20 "$log" >&2
            exit 1
        fi
EOF
}

# --- Commands ----------------------------------------------------------------
backup_db() {
    echo "Backing up DB..."
    ssh "$remote" "mkdir -p -m700 /home/${remote_user}/pg_dumps"
    ssh "$remote" "sudo -iu postgres pg_dump -Fc lfldb > /home/${remote_user}/pg_dumps/prod-bak-$(date +%Y-%m-%dT%H%M).dump"
}

prepare_server() {
    echo "Preparing server at ${LFL_HOST}..."
    ssh "$remote" "sudo -iu lessons bash -s" <<EOF
        mkdir -p -m777 "$remote_new"
        mkdir -p -m777 "$remote_old"
EOF
}

upload_files() {
    echo "Uploading ODT files..."
    rsync --progress --times "$local_old_file" "${remote}:${remote_old}/"
    rsync --progress --times "$local_new_file" "${remote}:${remote_new}/"
}

evaluate() {
    [[ -r $local_old_file ]] || die "missing $local_old_file"
    [[ -r $local_new_file ]] || die "missing $local_new_file"
    prepare_server
    upload_files
    if remote_has "$remote_evaluation_file"; then
        echo " > evaluation already done."
        return
    fi
    echo "Running 'evaluate'..."
    run_reimport evaluate.log evaluate "${remote_old}/${odt_filename}" "${remote_new}/${odt_filename}" --language-id 5
}

conflicts() {
    require_evaluation
    if remote_has "$remote_conflicts_file"; then
        echo " > conflict check already done."
        return
    fi
    echo "Running 'conflicts'..."
    run_reimport conflicts.log conflicts "$remote_evaluation_file"
}

resolve() {
    [[ -r ${local_eval_dir}/conflicts.tsv ]] || die "missing ${local_eval_dir}/conflicts.tsv"
    require_evaluation
    echo "Uploading local 'conflicts.tsv'..."
    rsync --progress --times "${local_eval_dir}/conflicts.tsv" "${remote}:${remote_new}/"
    echo "Running 'resolve'..."
    run_reimport resolve.log resolve "$remote_evaluation_file" --from "${remote_new}/conflicts.tsv"
}

apply() {
    require_evaluation
    if [[ $dry_run == true ]]; then
        echo "Running 'apply --dry-run'..."
        run_reimport apply-dry-run.log apply --dry-run "$remote_evaluation_file"
    else
        backup_db
        echo "Running 'apply'..."
        run_reimport apply.log apply "$remote_evaluation_file"
    fi
}

clean() {
    echo "Removing files in ${remote_new} on the server..."
    ssh "$remote" "find $(printf %q "${remote_new:?}") -mindepth 1 -delete"
}

# --- Main --------------------------------------------------------------------
# Pull the remote results (logs, evaluation, conflicts.tsv) back locally when
# the script exits, even if the command failed, so the logs are at hand.
sync_results() {
    echo "Syncing results to ${local_eval_dir}..."
    mkdir -p "$local_eval_dir"
    rsync --progress --recursive --times "${remote}:${remote_new}/" "$local_eval_dir" \
        || echo "Warning: could not sync results from the server." >&2
}

case "$command" in
    evaluate|conflicts|resolve|apply) trap sync_results EXIT; "$command" ;;
    backup) backup_db ;;
    clean)  clean ;;
esac
