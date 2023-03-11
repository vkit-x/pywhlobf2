#!/usr/bin/env bash
set -euo pipefail
trap "echo 'error: Script failed: see failed command above'" ERR

declare -a ABI_TAGS=(
    # EOL.
    # cp35-cp35m
    # cp36-cp36m
    # cp37-cp37m
    cp38-cp38
    cp39-cp39
    cp310-cp310
    cp311-cp311
)

for ABI_TAG in "${ABI_TAGS[@]}"; do
    echo "Installing pywhlobf to ${ABI_TAG}."
    PIP_FILE="/opt/python/${ABI_TAG}/bin/pip"
    if [[ ! -f "$PIP_FILE" ]]; then
        echo "${ABI_TAG} not found, skip."
        continue
    fi
    "$PIP_FILE" install --no-cache-dir -U pip
    if [ "$PYWHLOBF_CYTHON3" = 'no' ]; then
        "$PIP_FILE" install --no-cache-dir pywhlobf=="$PYWHLOBF_VERSION"
    elif [ "$PYWHLOBF_CYTHON3" = 'yes' ]; then
        "$PIP_FILE" install --no-cache-dir 'pywhlobf[cython3]'=="$PYWHLOBF_VERSION"
    else
        exit 1
    fi
done
