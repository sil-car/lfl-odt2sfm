#! /usr/bin/env bash

repo_dir="$(realpath "$(dirname "$(dirname $0)")")"
if [[ ! -d ${repo_dir}/.git ]]; then
    echo "Error: Not a git repo: $repo_dir"
    exit 1
fi
pytest --cov=odt2sfm --cov-report=term-missing "${repo_dir}/tests/"