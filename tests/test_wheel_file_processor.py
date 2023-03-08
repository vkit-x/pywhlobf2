from pywhlobf.wheel_file_processor import (
    WheelFileProcessorConfig,
    WheelFileProcessor,
)
from tests.opt import get_test_output_fd, get_test_wheel_file


def test_wheel_file_processor():
    working_fd = get_test_output_fd()
    wheel_file = get_test_wheel_file()
    wheel_file_processor = WheelFileProcessor(WheelFileProcessorConfig())
    output = wheel_file_processor.run(wheel_file=wheel_file, working_fd=working_fd)
    assert output.succeeded
