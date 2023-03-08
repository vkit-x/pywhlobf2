from typing import Optional, Sequence, List
from pathlib import Path
import tempfile
import zipfile
import sys

import attrs
import iolite as io
from wheel.bdist_wheel import get_abi_tag, get_platform
from wheel.wheelfile import WheelFile

from .code_folder_processor import (
    CodeFolderProcessorConfig,
    CodeFolderProcessorOutput,
    CodeFolderProcessor,
)


@attrs.define
class WheelFileProcessorConfig:
    code_folder_processor_config: CodeFolderProcessorConfig = attrs.field(
        factory=CodeFolderProcessorConfig
    )


@attrs.define
class WheelFileProcessorOutput:
    output_wheel_file: Optional[Path]
    code_folder_processor_outputs: Sequence[CodeFolderProcessorOutput]

    @property
    def succeeded(self):
        return bool(self.output_wheel_file)


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

    # NOTE: archive_root is only used in `calculate_macosx_platform_tag`, which could be ignored. See:
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
        self.code_folder_processor = CodeFolderProcessor(config.code_folder_processor_config)

    def run(
        self,
        wheel_file: Path,
        working_fd: Optional[Path] = None,
        output_wheel_abi_tag: Optional[str] = None,
        output_wheel_platform_tag: Optional[str] = None,
    ):
        # Prepare the working folder.
        if working_fd is None:
            working_fd = io.folder(tempfile.mkdtemp(), exists=True)
        else:
            working_fd = io.folder(working_fd, reset=True)

        # Unzip wheel.
        wheel_fd = io.folder(working_fd / 'wheel', touch=True)
        assert wheel_file.is_file()
        with zipfile.ZipFile(wheel_file) as zip_file:
            zip_file.extractall(wheel_fd)

        # Process.
        code_folder_processor_outputs: List[CodeFolderProcessorOutput] = []
        # https://peps.python.org/pep-0427/#file-contents
        for input_fd in wheel_fd.glob('*/'):
            if not input_fd.is_dir():
                continue
            if input_fd.suffix in ('.dist-info', '.data'):
                continue
            code_folder_processor_outputs.append(
                self.code_folder_processor.run(
                    input_fd=input_fd,
                    working_fd=(working_fd / 'working' / input_fd.name),
                )
            )

        failed = False
        for code_folder_processor_output in code_folder_processor_outputs:
            if not code_folder_processor_output.succeeded:
                failed = True
                break

        if failed:
            return WheelFileProcessorOutput(
                output_wheel_file=None,
                code_folder_processor_outputs=code_folder_processor_outputs,
            )

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
            abi_tag=output_wheel_abi_tag,
            platform_tag=output_wheel_platform_tag,
        )
        output_wheel_file = working_fd / output_wheel_name
        with WheelFile(output_wheel_file, 'w') as wf:
            wf.write_files(wheel_fd)

        return WheelFileProcessorOutput(
            output_wheel_file=output_wheel_file,
            code_folder_processor_outputs=code_folder_processor_outputs,
        )
