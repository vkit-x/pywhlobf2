# pyright: reportUnboundVariable=false
from typing import Optional, Sequence, List
from pathlib import Path
import tempfile
import zipfile
import sys
import logging

import attrs
import iolite as io
from wheel.bdist_wheel import get_abi_tag, get_platform
from wheel.wheelfile import WheelFile

from .package_folder_processor import (
    PackageFolderProcessorConfig,
    PackageFolderProcessorOutput,
    PackageFolderProcessor,
)
from .execution_context import ExecutionContextCollection

logger = logging.getLogger(__name__)


@attrs.define
class WheelFileProcessorConfig:
    package_folder_processor_config: PackageFolderProcessorConfig = attrs.field(
        factory=PackageFolderProcessorConfig
    )
    verbose: bool = False


@attrs.define
class WheelFileProcessorOutput:
    output_wheel_file: Optional[Path]
    package_folder_processor_outputs: Optional[Sequence[PackageFolderProcessorOutput]]
    execution_context_collection: ExecutionContextCollection

    @property
    def succeeded(self):
        return bool(self.output_wheel_file)

    def get_logging_message(self, verbose: bool = False):
        logging_messages: List[str] = []

        logging_messages.append(self.execution_context_collection.get_logging_message())
        if self.package_folder_processor_outputs:
            for output in self.package_folder_processor_outputs:
                logging_messages.append(output.get_logging_message(verbose))

        return '\n'.join(logging_messages)


def extract_components_from_wheel_file_stem(wheel_file_stem: str):
    # https://www.python.org/dev/peps/pep-0427/
    components = wheel_file_stem.split('-')

    build_tag = None
    if len(components) == 5:
        distribution, version, _, _, _ = components
    elif len(components) == 6:
        distribution, version, build_tag, _, _, _ = components
    else:
        raise NotImplementedError()

    return distribution, version, build_tag


def generate_wheel_name(
    distribution: str,
    version: str,
    build_tag: Optional[str] = None,
    abi_tag: Optional[str] = None,
    platform_tag: Optional[str] = None,
):
    '''
    See https://peps.python.org/pep-0425/
    '''
    python_tag = 'cp' + ''.join(map(str, sys.version_info[:2]))

    abi_tag = abi_tag or get_abi_tag()
    assert abi_tag

    # NOTE: archive_root is only used in `calculate_macosx_platform_tag`, which could be ignored.
    # https://github.com/pypa/wheel/blob/895558fc74f694dc6132723cfee58752d14c1482/src/wheel/bdist_wheel.py#L47
    platform_tag = platform_tag or get_platform(None)
    # https://peps.python.org/pep-0425/#platform-tag
    platform_tag = platform_tag.replace('-', '_').replace('.', '_')

    components = [distribution, version]
    if build_tag:
        components.append(build_tag)
    components.extend([python_tag, abi_tag, platform_tag])

    return '-'.join(components) + '.whl'


class WheelFileProcessor:

    def __init__(self, config: WheelFileProcessorConfig):
        self.config = config
        self.package_folder_processor = \
            PackageFolderProcessor(config.package_folder_processor_config)

    def run(
        self,
        wheel_file: Path,
        output_abi_tag: Optional[str] = None,
        output_platform_tag: Optional[str] = None,
        working_fd: Optional[Path] = None,
    ):
        # Prepare the working folder.
        if working_fd is None:
            working_fd = io.folder(tempfile.mkdtemp(), exists=True)
        else:
            working_fd = io.folder(working_fd, reset=True)

        logging_fd = io.folder(working_fd / 'logging', touch=True)

        execution_context_collection = ExecutionContextCollection(
            logging_fd=logging_fd,
            verbose=self.config.verbose,
        )

        with execution_context_collection.guard('unzip_wheel') as should_run:
            assert should_run
            # Unzip wheel.
            wheel_fd = io.folder(working_fd / 'wheel', touch=True)
            logger.info(f'Unzip wheel_file={wheel_file} to wheel_fd={wheel_fd}')
            assert wheel_file.is_file()
            with zipfile.ZipFile(wheel_file) as zip_file:
                zip_file.extractall(wheel_fd)

        package_folder_processor_outputs: Optional[List[PackageFolderProcessorOutput]] = None
        with execution_context_collection.guard('process_wheel') as should_run:
            if should_run:
                # Process.
                package_folder_processor_outputs = []
                # https://peps.python.org/pep-0427/#file-contents
                for input_fd in wheel_fd.glob('*/'):
                    if not input_fd.is_dir():
                        continue
                    if input_fd.suffix in ('.dist-info', '.data'):
                        continue
                    logger.info(f'Processing input_fd={input_fd}')
                    package_folder_processor_outputs.append(
                        self.package_folder_processor.run(
                            input_fd=input_fd,
                            working_fd=(working_fd / 'working' / input_fd.name),
                        )
                    )

                failed = False
                for package_folder_processor_output in package_folder_processor_outputs:
                    if not package_folder_processor_output.succeeded:
                        failed = True
                        break
                if failed:
                    raise RuntimeError('Failed to process code folder.')

        output_wheel_file = None
        with execution_context_collection.guard('zip_wheel') as should_run:
            if should_run:
                # Zip wheel.
                (
                    distribution,
                    version,
                    build_tag,
                ) = extract_components_from_wheel_file_stem(wheel_file.stem)
                output_wheel_name = generate_wheel_name(
                    distribution=distribution,
                    version=version,
                    build_tag=build_tag,
                    abi_tag=output_abi_tag,
                    platform_tag=output_platform_tag,
                )
                output_wheel_file = working_fd / output_wheel_name
                with WheelFile(output_wheel_file, 'w') as wf:
                    wf.write_files(wheel_fd)

        return WheelFileProcessorOutput(
            output_wheel_file=output_wheel_file,
            package_folder_processor_outputs=package_folder_processor_outputs,
            execution_context_collection=execution_context_collection,
        )
