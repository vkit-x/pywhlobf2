import os
import sys
import subprocess

from pywhlobf.code_file_processor import CodeFileProcessorConfig
from pywhlobf.code_folder_processor import (
    CodeFolderProcessorConfig,
    CodeFolderProcessor,
)
from tests.opt import get_test_output_fd, get_test_code_fd


def test_code_folder_processor():
    test_output_fd = get_test_output_fd()
    working_fd = test_output_fd / 'working'
    input_fd = get_test_code_fd()
    output_fd = test_output_fd / 'output' / input_fd.name

    code_folder_processor = CodeFolderProcessor(
        CodeFolderProcessorConfig(
            code_file_processor_config=CodeFileProcessorConfig(verbose=True),
        )
    )
    output = code_folder_processor.run(
        input_fd=input_fd,
        output_fd=output_fd,
        working_fd=working_fd,
    )
    if output.failed_outputs:
        for failed_output in output.failed_outputs:
            print('!!! DEBUG !!!')
            print(failed_output.execution_context_collection.get_logging_message())
        assert 0

    env = os.environ.copy()
    env['PYTHONPATH'] = str(test_output_fd / 'output')
    process = subprocess.run(
        [
            sys.executable,
            '-c',
            f'import {input_fd.name}; print(wheel.__file__)',
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

    assert not process.stderr
    assert process.stdout and not process.stdout.strip().endswith('.py')
