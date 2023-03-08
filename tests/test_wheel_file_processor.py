from pywhlobf.component.cpp_compiler import CppCompilerConfig
from pywhlobf.code_file_processor import CodeFileProcessorConfig
from pywhlobf.package_folder_processor import PackageFolderProcessorConfig
from pywhlobf.wheel_file_processor import (
    WheelFileProcessorConfig,
    WheelFileProcessor,
)
from tests.opt import get_test_output_fd, get_test_wheel_file


def test_wheel_file_processor():
    working_fd = get_test_output_fd()
    wheel_file = get_test_wheel_file()
    wheel_file_processor = WheelFileProcessor(
        WheelFileProcessorConfig(
            package_folder_processor_config=PackageFolderProcessorConfig(
                code_file_processor_config=CodeFileProcessorConfig(
                    cpp_compiler_config=CppCompilerConfig(setup_build_ext_timeout=600)
                )
            )
        )
    )
    output = wheel_file_processor.run(wheel_file=wheel_file, working_fd=working_fd)
    print(output.execution_context_collection.get_logging_message())
    assert output.succeeded
