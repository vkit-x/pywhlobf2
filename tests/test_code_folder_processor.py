from pywhlobf.code_file_processor import CodeFileProcessorConfig
from pywhlobf.code_folder_processor import (
    CodeFolderProcessorConfig,
    CodeFolderProcessor,
)
from tests.opt import get_test_output_fd, get_test_code_fd


def test_code_folder_processor():
    test_output_fd = get_test_output_fd()
    working_fd = test_output_fd / 'working'
    output_fd = test_output_fd / 'output'

    code_folder_processor = CodeFolderProcessor(
        CodeFolderProcessorConfig(
            wrap_code_file_processor_outputs_in_tqdm=True,
            code_file_processor_config=CodeFileProcessorConfig(verbose=True),
        )
    )
    output = code_folder_processor.run(
        input_fd=get_test_code_fd(),
        output_fd=output_fd,
        working_fd=working_fd,
    )
    if output.failed_outputs:
        for failed_output in output.failed_outputs:
            print('!!! DEBUG !!!')
            print(failed_output.execution_context_collection.get_logging_message())
        assert 0
