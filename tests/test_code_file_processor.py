import sys
# import importlib.util
# import traceback

from pywhlobf.code_file_processor import (
    ExecutionContextCollection,
    CodeFileProcessorConfig,
    CodeFileProcessor,
)

import iolite as io
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

    compiled_lib_file, execution_context_collection = code_file_processor.run(
        py_file=test_py_file,
        working_fd=working_fd,
    )
    assert compiled_lib_file and compiled_lib_file.is_file()
    assert execution_context_collection.succeeded
    print(execution_context_collection.get_logging_message())

    # module_name = compiled_lib_file.stem.split('.')[0]
    # spec = importlib.util.spec_from_file_location(module_name, str(compiled_lib_file))
    # assert spec and spec.loader
    # module = importlib.util.module_from_spec(spec)
    # sys.modules[module_name] = module
    # try:
    #     spec.loader.exec_module(module)
    # except ImportError:
    #     encrypted_traceback = traceback.format_exc()
    #     print(encrypted_traceback)
    #     assert 'wheel' not in encrypted_traceback
    #     assert encrypted_traceback.count('(pywhlobf') == 3
