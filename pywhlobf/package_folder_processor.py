from typing import Sequence, Optional, List, Callable
from pathlib import Path
import tempfile
import functools
from concurrent.futures import ProcessPoolExecutor
import shutil

import attrs
import iolite as io

from .code_file_processor import (
    CodeFileProcessorConfig,
    CodeFileProcessorOutput,
    CodeFileProcessor,
)


@attrs.define
class PackageFolderProcessorConfig:
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


@attrs.define
class PackageFolderProcessorOutput:
    succeeded_outputs: Sequence[CodeFileProcessorOutput]
    failed_outputs: Sequence[CodeFileProcessorOutput]

    @property
    def succeeded(self):
        return (not self.failed_outputs)

    def get_logging_message(self, verbose: bool = False):
        logging_messages: List[str] = []

        if verbose:
            for succeeded_output in self.succeeded_outputs:
                logging_messages.append('Succeeded log:')
                logging_messages.append(
                    succeeded_output.execution_context_collection.get_logging_message()
                )

        for failed_output in self.failed_outputs:
            logging_messages.append('Failed log:')
            logging_messages.append(
                failed_output.execution_context_collection.get_logging_message()
            )

        return '\n'.join(logging_messages)


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


class PackageFolderProcessor:

    def __init__(self, config: PackageFolderProcessorConfig):
        self.config = config
        self.code_file_processor = CodeFileProcessor(config.code_file_processor_config)

    def run(
        self,
        input_fd: Path,
        output_fd: Optional[Path] = None,
        working_fd: Optional[Path] = None,
    ):
        '''
        `input_fd` should be a regular package.
        See https://docs.python.org/3/glossary.html#term-regular-package
        '''
        # Prepare the working folder.
        if working_fd is None:
            working_fd = io.folder(tempfile.mkdtemp(), exists=True)
        else:
            working_fd = io.folder(working_fd, reset=True)

        # Make it short to aboid path too long issue.
        # `b` for build, `l` for logging.
        build_fd = working_fd / 'b'
        logging_fd = working_fd / 'l'

        # Copy __init__.* to the build folder, which is required by build_ext.
        for init_py_file in input_fd.glob('**/__init__.*'):
            _, _, cpp_generator_working_fd = CodeFileProcessor.prep_fds(
                py_file=init_py_file,
                build_fd=build_fd,
                logging_fd=logging_fd,
                py_root_fd=input_fd,
            )
            shutil.copyfile(init_py_file, cpp_generator_working_fd / init_py_file.name)

        # Collect code files to process.
        py_files: List[Path] = []
        for pattern in self.config.patterns:
            py_files.extend(input_fd.glob(pattern))

        # Process.
        outputs = process_py_file(
            num_processes=self.config.num_processes,
            func_process_py_file=functools.partial(
                self.code_file_processor.run,
                build_fd=build_fd,
                logging_fd=logging_fd,
                py_root_fd=input_fd,
            ),
            py_files=py_files,
        )

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

        return PackageFolderProcessorOutput(
            succeeded_outputs=succeeded_outputs,
            failed_outputs=failed_outputs,
        )
