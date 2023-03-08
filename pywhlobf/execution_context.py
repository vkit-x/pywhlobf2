from typing import List
from pathlib import Path
import os
import sys
from contextlib import contextmanager
import traceback


class ExecutionContext:

    def __init__(self, logging_fd: Path, context_name: str):
        self.context_name = context_name
        self.stdout_file = logging_fd / f'{context_name}_stdout.txt'
        self.stderr_file = logging_fd / f'{context_name}_stderr.txt'
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
            f'ExecutionContext: {self.context_name}',
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
    def guard(self, context_name: str):
        execution_context = ExecutionContext(self.logging_fd, context_name)

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
