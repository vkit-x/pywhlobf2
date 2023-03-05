from typing import Sequence, Optional, List, Callable
from pathlib import Path
import tempfile
import functools
from concurrent.futures import ProcessPoolExecutor
import shutil

import attrs
import iolite as io
from tqdm import tqdm

from .code_file_processor import (
    CodeFileProcessorConfig,
    CodeFileProcessorOutput,
    CodeFileProcessor,
)


@attrs.define
class CodeFolderProcessorConfig:
    code_file_processor_config: CodeFileProcessorConfig = attrs.field(
        factory=CodeFileProcessorConfig
    )
    patterns: Sequence[str] = (
        '**/*.py',
        '**/*.pyx',
    )
    delete_processed_code_file: bool = True
    num_processes: Optional[int] = None
    reset_output_fd: bool = False
    wrap_code_file_processor_outputs_in_tqdm: bool = False


@attrs.define
class CodeFolderProcessorOutput:
    succeeded_outputs: Sequence[CodeFileProcessorOutput]
    failed_outputs: Sequence[CodeFileProcessorOutput]


def process_py_file(
    num_processes: Optional[int],
    func_process_py_file: Callable[[Path], CodeFileProcessorOutput],
    py_files: Sequence[Path],
):
    if num_processes != 0:
        # NOTE: multiprocessing.Pool creates daemonic process, which is unsuitable.
        with ProcessPoolExecutor(max_workers=num_processes) as pool:
            yield from pool.map(
                func_process_py_file,
                py_files,
            )
    else:
        for py_file in py_files:
            yield func_process_py_file(py_file)


class CodeFolderProcessor:

    def __init__(self, config: CodeFolderProcessorConfig):
        self.config = config
        self.code_file_processor = CodeFileProcessor(config.code_file_processor_config)

    def run(
        self,
        input_fd: Path,
        output_fd: Optional[Path] = None,
        working_fd: Optional[Path] = None,
    ):
        # Prepare the working folder.
        if working_fd is None:
            working_fd = io.folder(tempfile.mkdtemp(), exists=True)

        # Collect code files to process.
        py_files: List[Path] = []
        for pattern in self.config.patterns:
            py_files.extend(input_fd.glob(pattern))

        # Process.
        outputs = process_py_file(
            num_processes=self.config.num_processes,
            func_process_py_file=functools.partial(
                self.code_file_processor.run,
                py_root_fd=input_fd,
                working_fd=working_fd,
                working_fd_is_root=True,
            ),
            py_files=py_files,
        )
        if self.config.wrap_code_file_processor_outputs_in_tqdm:
            outputs = tqdm(outputs, total=len(py_files))

        succeeded_outputs: List[CodeFileProcessorOutput] = []
        failed_outputs: List[CodeFileProcessorOutput] = []
        for output in outputs:
            if output.compiled_lib_file:
                succeeded_outputs.append(output)
            else:
                failed_outputs.append(output)

        # Post.
        if not failed_outputs:
            if output_fd is None:
                output_fd = input_fd
            else:
                output_fd = io.folder(
                    output_fd,
                    touch=True,
                    reset=self.config.reset_output_fd,
                )
                for input_file in input_fd.glob('**/*'):
                    if not input_file.is_file():
                        continue
                    output_file = output_fd / input_file.relative_to(input_fd)
                    output_file.parent.mkdir(exist_ok=True, parents=True)
                    shutil.copyfile(input_file, output_file)

            if self.config.delete_processed_code_file:
                for succeeded_output in succeeded_outputs:
                    output_py_file = output_fd / succeeded_output.py_file.relative_to(input_fd)
                    output_py_file.unlink()

            for succeeded_output in succeeded_outputs:
                output_py_file = output_fd / succeeded_output.py_file.relative_to(input_fd)
                compiled_lib_file = succeeded_output.compiled_lib_file
                assert compiled_lib_file
                shutil.copyfile(
                    compiled_lib_file,
                    output_py_file.parent / compiled_lib_file.name,
                )

        return CodeFolderProcessorOutput(
            succeeded_outputs=succeeded_outputs,
            failed_outputs=failed_outputs,
        )
