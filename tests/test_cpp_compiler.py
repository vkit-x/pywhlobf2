import importlib.util
import sys
import traceback
from pywhlobf.component.cpp_generator import CppGeneratorConfig, CppGenerator
from pywhlobf.component.string_literal_obfuscator import (
    StringLiteralObfuscatorConfig,
    StringLiteralObfuscator,
)
from pywhlobf.component.source_code_injector import (
    SourceCodeInjectorConfig,
    SourceCodeInjector,
)
from pywhlobf.component.cpp_compiler import (
    CppCompilerConfig,
    CppCompiler,
)
import iolite as io
from tests.opt import get_test_output_fd, get_test_py_file


def test_cpp_compiler():
    output_fd = get_test_output_fd()
    test_py_file = get_test_py_file('for_test_cpp_compiler.py')

    cpp_generator = CppGenerator(CppGeneratorConfig())
    cpp_file, ext_module = cpp_generator.run(test_py_file, output_fd)

    string_literal_obfuscator = StringLiteralObfuscator(StringLiteralObfuscatorConfig())
    string_literal_obfuscator_activated, include_fd = string_literal_obfuscator.run(cpp_file)
    assert string_literal_obfuscator_activated and include_fd

    source_code_injector = SourceCodeInjector(
        SourceCodeInjectorConfig(fernet_key='WwAPKBMXKl-I43L4u8B5WD9xoperM9qhXDlLVWRFkiY=')
    )
    source_code_injector_activated = source_code_injector.run(
        py_file=test_py_file,
        cpp_file=cpp_file,
    )
    assert source_code_injector_activated

    cpp_compiler = CppCompiler(CppCompilerConfig())
    compiled_lib_file = cpp_compiler.run(
        cpp_file=cpp_file,
        ext_module=ext_module,
        include_fds=[include_fd],
        temp_fd=io.folder(output_fd / 'cpp_compiler_temp', reset=True),
        string_literal_obfuscator_activated=string_literal_obfuscator_activated,
        source_code_injector_activated=source_code_injector_activated,
    )
    assert compiled_lib_file.is_file()

    module_name = compiled_lib_file.stem.split('.')[0]
    spec = importlib.util.spec_from_file_location(module_name, str(compiled_lib_file))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except ImportError:
        encrypted_traceback = traceback.format_exc()
        print(encrypted_traceback)
        assert 'wheel' not in encrypted_traceback
        assert encrypted_traceback.count('(pywhlobf') == 3
