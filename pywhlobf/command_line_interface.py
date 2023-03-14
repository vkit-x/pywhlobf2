from typing import Any, Optional, Mapping, TypeVar, Type
from collections import abc
import sys
from pathlib import Path
from importlib.machinery import ExtensionFileLoader, ModuleSpec
from importlib.util import module_from_spec
import json
import tempfile
import shutil
import os

import iolite as io
import cattrs
from cryptography.fernet import Fernet
import pyperclip
import fire
import fire.core

from .component.source_code_injector import SourceCodeInjector
from .code_file_processor import CodeFileProcessorConfig, CodeFileProcessor
from .package_folder_processor import PackageFolderProcessorConfig, PackageFolderProcessor
from .wheel_file_processor import WheelFileProcessorConfig, WheelFileProcessor


def run_extension_file(extension_file: Path):
    name = extension_file.name.split('.')[0]
    extension_file = extension_file.absolute()
    loader = ExtensionFileLoader(name=name, path=str(extension_file))
    spec = ModuleSpec(name=name, loader=loader, origin=str(extension_file))
    module = module_from_spec(spec)
    module.__name__ = '__main__'
    sys.modules[name] = module
    loader.exec_module(module)


def assign_fernet_key(config: CodeFileProcessorConfig, fernet_key: Optional[str]):
    if not fernet_key:
        fernet_key = Fernet.generate_key().decode()
    else:
        try:
            Fernet(fernet_key.encode())
        except Exception:
            print(f'Invalid fernet_key={fernet_key}', file=sys.stderr)
            sys.exit(1)

    config.source_code_injector_config.fernet_key = fernet_key


def write_json(path: Optional[str], struct: Mapping[str, Any]):
    try:
        text = json.dumps(struct, ensure_ascii=True, indent=2)
    except Exception:
        print(f'Failed to dump struct={struct}', file=sys.stderr)
        sys.exit(1)

    if path:
        io.file(path).write_text(text)
    else:
        print(text)


_T = TypeVar('_T')


def read_config(config_file: str, config_cls: Type[_T]) -> _T:
    try:
        config_json = io.file(config_file, exists=True)
    except Exception:
        print(f'config_file={config_file} not found.', file=sys.stderr)
        sys.exit(1)

    try:
        struct = io.read_json(config_json)
    except Exception:
        print(f'Failed to parse config_file={config_file}', file=sys.stderr)
        sys.exit(1)

    try:
        config = cattrs.structure(struct, config_cls)
    except Exception:
        print(f'Failed to parse config_file={config_file}', file=sys.stderr)
        sys.exit(1)

    return config


def search_fernet_key(struct: Mapping[str, Any]):
    fernet_key = struct.get('fernet_key')
    if fernet_key:
        return fernet_key
    else:
        for sub_struct in struct.values():
            if isinstance(sub_struct, abc.Mapping):
                fernet_key = search_fernet_key(sub_struct)
                if fernet_key:
                    return fernet_key
        return None


def prep_fd(folder: Optional[str]):
    if not folder:
        return io.folder(tempfile.mkdtemp(), exists=True)
    else:
        return io.folder(folder)


class CommandLineInterface:

    def code_file_config(
        self,
        config_file: Optional[str] = None,
        fernet_key: Optional[str] = None,
    ):
        '''
        Generate the JSON config required by `code_file` command.

        :param config_file:
            An optional path to save the JSON config. If not provided, the program will print
            the JSON config to stdout.
        :param fernet_key:
            An opitonal key used in source code injector. If not provided, the program will
            generate a random key.
        '''
        config = CodeFileProcessorConfig()
        assign_fernet_key(config, fernet_key)
        write_json(config_file, cattrs.unstructure(config))

    def code_file(
        self,
        config_file: str,
        input_file: str,
        output_folder: Optional[str] = None,
        working_folder: Optional[str] = None,
        verbose: bool = False,
    ):
        '''
        Obfuscate a single code file.

        :param config_file:
            The JSON config path.
        :param input_file:
            The code file to be processed.
        :param output_folder:
            An optional output folder. If not provided, the program will save the output next to
            the code file.
        :param working_folder:
            An optional working folder. If not provided, the program will create a temporary folder.
        :param verbose:
            An optional flag. If set, the program will print the logging message.
        '''
        config = read_config(config_file, CodeFileProcessorConfig)
        code_file_processor = CodeFileProcessor(config)

        try:
            py_file = io.file(input_file, exists=True)
        except Exception:
            print(f'input_file={input_file} not found.', file=sys.stderr)
            sys.exit(1)

        working_fd = prep_fd(working_folder)
        print(f'Processing {py_file},\nwith working_fd={working_fd}')

        output = code_file_processor.run(
            py_file=py_file,
            build_fd=working_fd / 'b',
            logging_fd=working_fd / 'l',
        )

        if output.compiled_lib_file:
            if verbose:
                print('logging message:')
                print(output.execution_context_collection.get_logging_message())

            if output_folder:
                output_fd = io.folder(output_folder, touch=True)
            else:
                output_fd = py_file.parent

            output_file = output_fd / output.compiled_lib_file.name
            print(f'Saving to {output_file}')
            shutil.copyfile(output.compiled_lib_file, output_file)
            print('Done.')

        else:
            print('Failed!', file=sys.stderr)
            print('logging message:', file=sys.stderr)
            print(output.execution_context_collection.get_logging_message(), file=sys.stderr)
            sys.exit(1)

    def package_folder_config(
        self,
        config_file: Optional[str] = None,
        fernet_key: Optional[str] = None,
    ):
        '''
        Generate the JSON config required by `package_folder` command.

        :param config_file:
            An optional path to save the JSON config. If not provided, the program will print
            the JSON config to stdout.
        :param fernet_key:
            An opitonal key used in source code injector. If not provided, the program will
            generate a random key.
        '''
        config = PackageFolderProcessorConfig()
        assign_fernet_key(config.code_file_processor_config, fernet_key)
        write_json(config_file, cattrs.unstructure(config))

    def package_folder(
        self,
        config_file: str,
        input_folder: str,
        output_folder: Optional[str] = None,
        working_folder: Optional[str] = None,
        verbose: bool = False,
    ):
        '''
        Obfuscate a package folder.

        :param config_file:
            The JSON config path.
        :param input_folder:
            The package folder to be processed. The package should be a regular package.
        :param output_folder:
            An optional output folder. If not provided, the program will save the output next to
            the code file.
        :param working_folder:
            An optional working folder. If not provided, the program will create a temporary folder.
        :param verbose:
            An optional flag. If set, the program will print the logging message.
        '''
        config = read_config(config_file, PackageFolderProcessorConfig)
        package_folder_processor = PackageFolderProcessor(config)

        try:
            input_fd = io.folder(input_folder, exists=True)
        except Exception:
            print(f'input_folder={input_folder} not found.', file=sys.stderr)
            sys.exit(1)

        output_fd = None
        if output_folder:
            output_fd = io.folder(output_folder)

        working_fd = prep_fd(working_folder)
        print(f'Processing {input_fd},\nwith output_fd={output_fd}, working_fd={working_fd}')

        output = package_folder_processor.run(
            input_fd=input_fd,
            output_fd=output_fd,
            working_fd=working_fd,
        )

        if output.succeeded:
            if verbose:
                print('logging message:')
                print(output.get_logging_message(verbose))
            print('Done.')

        else:
            print('Failed!', file=sys.stderr)
            print('logging message:', file=sys.stderr)
            print(output.get_logging_message(verbose), file=sys.stderr)
            sys.exit(1)

    def wheel_file_config(
        self,
        config_file: Optional[str] = None,
        fernet_key: Optional[str] = None,
    ):
        '''
        Generate the JSON config required by `wheel_file` command.

        :param config_file:
            An optional path to save the JSON config. If not provided, the program will print
            the JSON config to stdout.
        :param fernet_key:
            An opitonal key used in source code injector. If not provided, the program will
            generate a random key.
        '''
        config = WheelFileProcessorConfig()
        assign_fernet_key(
            config.package_folder_processor_config.code_file_processor_config,
            fernet_key,
        )
        write_json(config_file, cattrs.unstructure(config))

    def wheel_file(
        self,
        config_file: str,
        input_file: str,
        output_folder: Optional[str] = None,
        output_abi_tag: Optional[str] = None,
        output_platform_tag: Optional[str] = None,
        working_folder: Optional[str] = None,
        verbose: bool = False,
    ):
        '''
        Obfuscate a wheel file.

        :param config_file:
            The JSON config path.
        :param input_file:
            The wheel file to be processed.
        :param output_folder:
            An optional output folder. If not provided, the program will save the output next to
            the code file.
        :param output_abi_tag:
            An optional ABI tag. If not provided, the program will attempt to load envrionment
            variable `PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG`. If `PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG`
            is not defined, the program will attempt to assign the ABI tag based on system config.
        :param output_platform_tag:
            An optional platform tag. If not provided, the program will attempt to load envrionment
            variable `PYWHLOBF_WHEEL_FILE_OUTPUT_PLATFORM_TAG`. If
            `PYWHLOBF_WHEEL_FILE_OUTPUT_PLATFORM_TAG` is not defined, the program will attempt to
            assign the platform tag based on system config.
        :param working_folder:
            An optional working folder. If not provided, the program will create a temporary folder.
        :param verbose:
            An optional flag. If set, the program will print the logging message.
        '''
        config = read_config(config_file, WheelFileProcessorConfig)
        wheel_file_processor = WheelFileProcessor(config)

        try:
            wheel_file = io.file(input_file, exists=True)
        except Exception:
            print(f'input_file={input_file} not found.', file=sys.stderr)
            sys.exit(1)

        if not output_abi_tag:
            output_abi_tag = os.environ.get('PYWHLOBF_WHEEL_FILE_OUTPUT_ABI_TAG')

        if not output_platform_tag:
            output_platform_tag = os.environ.get('PYWHLOBF_WHEEL_FILE_OUTPUT_PLATFORM_TAG')

        working_fd = prep_fd(working_folder)
        print(
            f'Processing {wheel_file},\n'
            f'with output_abi_tag={output_abi_tag}, output_platform_tag={output_platform_tag}\n'
            f'working_fd={working_fd}'
        )

        output = wheel_file_processor.run(
            wheel_file=wheel_file,
            output_abi_tag=output_abi_tag,
            output_platform_tag=output_platform_tag,
            working_fd=working_fd,
        )

        if output.succeeded:
            if verbose:
                print('logging message:')
                print(output.get_logging_message(verbose))

            if output_folder:
                output_fd = io.folder(output_folder, touch=True)
            else:
                output_fd = wheel_file.parent

            assert output.output_wheel_file
            output_file = output_fd / output.output_wheel_file.name
            print(f'Saving to {output_file}')
            shutil.copyfile(output.output_wheel_file, output_file)

        else:
            print('Failed!', file=sys.stderr)
            print('logging message:', file=sys.stderr)
            print(output.get_logging_message(verbose), file=sys.stderr)
            sys.exit(1)

    def run_extension_file(self, extension_file_path: str, *args: Any, **kwargs: Any):
        '''
        Run an extension file.

        :param extension_file_path:
            The extension file path.
        '''
        extension_file = io.file(extension_file_path, exists=True).absolute()
        assert io.file(sys.argv[2]).absolute() == extension_file
        sys.argv = sys.argv[2:]
        run_extension_file(extension_file)

    def decrypt_message(
        self,
        config_file: Optional[str] = None,
        fernet_key: Optional[str] = None,
        input_file: Optional[str] = None,
        output_file: Optional[str] = None,
    ):
        '''
        Decrypt the message.

        :param config_file:
            An optional config file generated by `code_file_config`, `package_folder_config`,
            or `wheel_file_config`. If provided, the program will search for the `fernet_key`
            in the config file.
        :param fernet_key:
            An optional fernet key. If `config_file` is not provided, user should explicitly provide
            the key here. If `fernet_key` is provided, the program will use this key and ignore
            `config_file`.
        :param input_file:
            An optional text file to be decrypted. If not provided, the program will wait until the
            clipboard changes, and decrypt the text in clipboard.
        :param output_file:
            An optional output file to keep the decrypted message. If not provided, the program will
            print the decrypted message to stdout.
        '''
        if not fernet_key:
            if not config_file:
                print('Neither `config_file` nor `fernet_key` is provided.')
                sys.exit(1)

            try:
                config_json = io.file(config_file, exists=True)
            except Exception:
                print(f'config_file={config_file} not found.', file=sys.stderr)
                sys.exit(1)

            try:
                struct = io.read_json(config_json)
            except Exception:
                print(f'Failed to parse config_file={config_file}.', file=sys.stderr)
                sys.exit(1)

            fernet_key = search_fernet_key(struct)  # type: ignore
            if not fernet_key:
                print(f'config_file={config_file} not found.', file=sys.stderr)
                sys.exit(1)

        try:
            fernet = Fernet(fernet_key.encode())
        except Exception:
            print(f'Invalid fernet_key={fernet_key}', file=sys.stderr)
            sys.exit(1)

        if input_file:
            try:
                encrypted_message = io.file(input_file, exists=True).read_text()
            except Exception:
                print(f'Failed to load input_file={input_file}', file=sys.stderr)
                sys.exit(1)
        else:
            print('Awaiting for clipboard to update...')
            pyperclip.waitForNewPaste()
            encrypted_message = str(pyperclip.paste())

        message = SourceCodeInjector.decrept(fernet, encrypted_message)

        if output_file:
            print(f'Saving decrypted message to {output_file}')
            io.file(output_file).write_text(message)
        else:
            print('Decrypted message:')
            print(message)


def main():
    # https://github.com/google/python-fire/issues/188
    def Display(lines, out):  # type: ignore
        text = "\n".join(lines) + "\n"
        out.write(text)

    fire.core.Display = Display

    fire.Fire(CommandLineInterface)
