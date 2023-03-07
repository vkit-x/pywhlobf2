import sys
import subprocess
import os

import iolite as io

from pywhlobf.code_file_processor import (
    ExecutionContextCollection,
    CodeFileProcessorConfig,
    CodeFileProcessor,
)
from tests.opt import get_test_output_fd, get_test_py_file


def test_execution_context_collection():
    working_fd = get_test_output_fd()
    logging_fd = io.folder(working_fd, reset=True)

    execution_context_collection = ExecutionContextCollection(
        logging_fd=logging_fd,
        verbose=True,
    )

    with execution_context_collection.guard('foo') as should_run:
        assert should_run
        print('foo')
        print('foo err', file=sys.stderr)

    assert execution_context_collection.succeeded
    print(execution_context_collection.get_logging_message())

    with execution_context_collection.guard('bar') as should_run:
        assert should_run
        assert 0

    assert not execution_context_collection.succeeded
    print(execution_context_collection.get_logging_message())

    with execution_context_collection.guard('baz') as should_run:
        assert not should_run

    assert not execution_context_collection.succeeded
    print(execution_context_collection.get_logging_message())


def test_code_file_processor():
    working_fd = get_test_output_fd()
    test_py_file = get_test_py_file()

    config = CodeFileProcessorConfig()
    config.source_code_injector_config.fernet_key = 'WwAPKBMXKl-I43L4u8B5WD9xoperM9qhXDlLVWRFkiY='
    code_file_processor = CodeFileProcessor(config)

    output = code_file_processor.run(
        py_file=test_py_file,
        build_fd=working_fd,
        logging_fd=working_fd,
    )
    assert output.compiled_lib_file and output.compiled_lib_file.is_file()
    assert output.execution_context_collection.succeeded
    print(output.execution_context_collection.get_logging_message())

    # https://stackoverflow.com/questions/58997105/fatal-python-error-failed-to-get-random-numbers-to-initialize-python
    env = os.environ.copy()
    env['PYTHONPATH'] = str(working_fd)
    process = subprocess.run(
        [
            sys.executable,
            '-c',
            f'import {test_py_file.stem}',
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    print('-' * 40)
    print(process.stdout)
    print('-' * 40)
    print(process.stderr)
    print('-' * 40)
    encrypted_traceback = process.stderr
    assert 'wheel' not in encrypted_traceback
    assert encrypted_traceback.count('(pywhlobf') == 3
