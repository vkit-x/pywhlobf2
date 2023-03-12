#!/usr/bin/env bash
set -eo pipefail
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

if [ "$PYWHLOBF_CYTHON3" = 'no' ]; then
    PYWHLOBF_EXTRA=""
elif [ "$PYWHLOBF_CYTHON3" = 'yes' ]; then
    PYWHLOBF_EXTRA="[cython3]"
else
    exit 1
fi

if [ -n "$PYWHLOBF_WHELL_NAME" ]; then
    PYWHLOBF_REQUIREMENT_SPECIFIER="pywhlobf${PYWHLOBF_EXTRA}@file:///b/dist/${PYWHLOBF_WHELL_NAME}"
else
    if [ -z "$PYWHLOBF_VERSION" ]; then
        echo "FATAL: Missing PYWHLOBF_VERSION when PYWHLOBF_WHELL_NAME is not provided."
        exit 1
    fi
    PYWHLOBF_REQUIREMENT_SPECIFIER="pywhlobf${PYWHLOBF_EXTRA}==${PYWHLOBF_VERSION}"
fi

for ABI_TAG in "${ABI_TAGS[@]}"; do
    echo "Installing ${PYWHLOBF_REQUIREMENT_SPECIFIER} to ${ABI_TAG}."
    PIP_FILE="/opt/python/${ABI_TAG}/bin/pip"
    if [[ ! -f "$PIP_FILE" ]]; then
        echo "FATAL: ABI_TAG=${ABI_TAG} is not supported, skip."
        exit 1
    fi
    "$PIP_FILE" install --no-cache-dir -U pip
    "$PIP_FILE" install --no-cache-dir $PYWHLOBF_REQUIREMENT_SPECIFIER
done
