# pyright: reportUnboundVariable=false
from typing import List, Optional
from pathlib import Path
import os
import sys
from contextlib import contextmanager
import traceback

import attrs

from .component.cpp_generator import (
    CppGeneratorConfig,
    CppGenerator,
)
from .component.string_literal_obfuscator import (
    StringLiteralObfuscatorConfig,
    StringLiteralObfuscator,
)
from .component.source_code_injector import (
    SourceCodeInjectorConfig,
    SourceCodeInjector,
)
from .component.cpp_compiler import (
    CppCompilerConfig,
    CppCompiler,
)


@attrs.define
class CodeFileProcessorConfig:
    cpp_generator_config: CppGeneratorConfig = attrs.field(factory=CppGeneratorConfig)
    string_literal_obfuscator_config: StringLiteralObfuscatorConfig = attrs.field(
        factory=StringLiteralObfuscatorConfig
    )
    source_code_injector_config: SourceCodeInjectorConfig = attrs.field(
        factory=SourceCodeInjectorConfig
    )
    cpp_compiler_config: CppCompilerConfig = attrs.field(factory=CppCompilerConfig)
    verbose: bool = False


class ExecutionContext:

    def __init__(self, logging_fd: Path, component_name: str):
        self.component_name = component_name
        self.stdout_file = logging_fd / f'{component_name}_stdout.txt'
        self.stderr_file = logging_fd / f'{component_name}_stderr.txt'
        self.executed = False
        self.succeeded = False

    @contextmanager
    def guard(self):
        with self.stdout_file.open('w') as stdout_fout, self.stderr_file.open('w') as stderr_fout:
            prev_stdout_fileno = os.dup(sys.stdout.fileno())
            prev_stderr_fileno = os.dup(sys.stderr.fileno())

            os.dup2(stdout_fout.fileno(), sys.stdout.fileno())
            os.dup2(stderr_fout.fileno(), sys.stderr.fileno())

            try:
                self.executed = True
                yield
                self.succeeded = True
            except Exception:
                # Dump the full exception traceback.
                stderr_fout.write('\n')
                stderr_fout.write(traceback.format_exc())
                self.succeeded = False

            os.dup2(prev_stdout_fileno, sys.stdout.fileno())
            os.dup2(prev_stderr_fileno, sys.stderr.fileno())

    def get_logging_message(self, verbose: bool):
        lines = [
            '###',
            f'Component: {self.component_name}',
            f'executed={self.executed}, succeeded={self.succeeded}',
            '###',
        ]

        gap_line = '---'
        if self.executed:
            if verbose:
                stdout = self.stdout_file.read_text().strip()
                lines.append(gap_line)
                lines.append('>>> STDOUT')
                lines.append(gap_line)
                lines.append(stdout or 'NO MESSAGE')
                lines.append(gap_line)

            stderr = self.stderr_file.read_text().strip()
            lines.append(gap_line)
            lines.append('>>> STDERR')
            lines.append(gap_line)
            lines.append(stderr or 'NO MESSAGE')
            lines.append(gap_line)

        else:
            lines.append(gap_line)
            lines.append('NOT EXECUTED')
            lines.append(gap_line)

        return '\n'.join(lines)


class ExecutionContextCollection:

    def __init__(self, logging_fd: Path, verbose: bool):
        self.logging_fd = logging_fd
        self.verbose = verbose
        self.execution_contexts: List[ExecutionContext] = []
        self.succeeded = True

    @contextmanager
    def guard(self, component_name: str):
        execution_context = ExecutionContext(self.logging_fd, component_name)

        if self.succeeded:
            with execution_context.guard():
                # Exception is caught.
                yield True
            if not execution_context.succeeded:
                self.succeeded = False
        else:
            yield False

        self.execution_contexts.append(execution_context)

    def get_logging_message(self):
        lines = []
        for execution_context in self.execution_contexts:
            lines.extend([
                execution_context.get_logging_message(self.verbose),
                '',
                '',
            ])
        return '\n'.join(lines)


@attrs.define
class CodeFileProcessorOutput:
    py_file: Path
    compiled_lib_file: Optional[Path]
    execution_context_collection: ExecutionContextCollection


class CodeFileProcessor:

    def __init__(self, config: CodeFileProcessorConfig):
        self.config = config

        self.cpp_generator = CppGenerator(config.cpp_generator_config)
        self.string_literal_obfuscator = \
            StringLiteralObfuscator(config.string_literal_obfuscator_config)
        self.source_code_injector = SourceCodeInjector(config.source_code_injector_config)
        self.cpp_compiler = CppCompiler(config.cpp_compiler_config)

    @classmethod
    def prep_fds(
        cls,
        py_file: Path,
        build_fd: Path,
        logging_fd: Path,
        py_root_fd: Optional[Path] = None,
    ):
        if py_root_fd:
            rel_path = py_file.relative_to(py_root_fd)
            cpp_generator_working_fd = build_fd / py_root_fd.name / rel_path.parent

            rel_path = rel_path.with_name(rel_path.name.replace('.', '_'))
            logging_fd = logging_fd / py_root_fd.name / rel_path

        else:
            cpp_generator_working_fd = build_fd

        build_fd.mkdir(exist_ok=True, parents=True)
        logging_fd.mkdir(exist_ok=True, parents=True)
        cpp_generator_working_fd.mkdir(exist_ok=True, parents=True)

        return build_fd, logging_fd, cpp_generator_working_fd

    def run(
        self,
        py_file: Path,
        build_fd: Path,
        logging_fd: Path,
        py_root_fd: Optional[Path] = None,
    ):
        include_fds: List[Path] = []

        build_fd, logging_fd, cpp_generator_working_fd = self.prep_fds(
            py_file=py_file,
            build_fd=build_fd,
            logging_fd=logging_fd,
            py_root_fd=py_root_fd,
        )

        execution_context_collection = ExecutionContextCollection(
            logging_fd=logging_fd,
            verbose=self.config.verbose,
        )

        with execution_context_collection.guard('prep') as should_run:
            assert should_run
            assert py_file.is_file()
            assert py_file.suffix in ('.py', '.pyx')

        with execution_context_collection.guard('cpp_generator') as should_run:
            if should_run:
                cpp_file, ext_module = self.cpp_generator.run(
                    py_file=py_file,
                    working_fd=cpp_generator_working_fd,
                )

        with execution_context_collection.guard('string_literal_obfuscator') as should_run:
            if should_run:
                (
                    string_literal_obfuscator_activated,
                    include_fd,
                ) = self.string_literal_obfuscator.run(cpp_file=cpp_file)
                if include_fd:
                    include_fds.append(include_fd)

        with execution_context_collection.guard('source_code_injector') as should_run:
            if should_run:
                source_code_injector_activated = self.source_code_injector.run(
                    py_file=py_file,
                    cpp_file=cpp_file,
                    py_root_fd=py_root_fd,
                )

        compiled_lib_file = None
        with execution_context_collection.guard('cpp_compiler') as should_run:
            if should_run:
                compiled_lib_file = self.cpp_compiler.run(
                    ext_module=ext_module,
                    working_fd=build_fd,
                    include_fds=include_fds,
                    string_literal_obfuscator_activated=string_literal_obfuscator_activated,
                    source_code_injector_activated=source_code_injector_activated,
                )

        return CodeFileProcessorOutput(
            py_file=py_file,
            compiled_lib_file=compiled_lib_file,
            execution_context_collection=execution_context_collection,
        )
