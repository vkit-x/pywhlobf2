#!/usr/bin/env bash
set -euo pipefail
trap "echo 'error: Script failed: see failed command above'" ERR

fixuid -q

if [ -z "$PYTHON_VERSION" ]; then
    echo "WARNING: PYTHON_VERSION not found, set to 3.8"
    PYTHON_VERSION='3.8'
fi

if [[ "$PYTHON_VERSION" == "3.7" ]]; then
    export PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG='cp37-cp37m'
elif [[ "$PYTHON_VERSION" == "3.8" ]]; then
    export PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG='cp38-cp38'
elif [[ "$PYTHON_VERSION" == "3.9" ]]; then
    export PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG='cp39-cp39'
elif [[ "$PYTHON_VERSION" == "3.10" ]]; then
    export PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG='cp310-cp310'
elif [[ "$PYTHON_VERSION" == "3.11" ]]; then
    export PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG='cp311-cp311'
else
    echo "FATEL: Invalid PYTHON_VERSION={PYTHON_VERSION}. Abort."
    exit 1
fi

PYWHLOBF="/opt/python/${PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG}/bin/pywhlobf"
if [ ! -f "$PYWHLOBF" ]; then
    echo "FATEL: PYWHLOBF=${PYWHLOBF} not found. Abort."
    exit 1
fi

"$PYWHLOBF" "$@"
