from pywhlobf.component.cpp_generator import CppGeneratorConfig, CppGenerator
from pywhlobf.component.source_code_injector import (
    SourceCodeInjectorConfig,
    SourceCodeInjector,
)
from tests.opt import get_test_output_fd, get_test_py_file


def test_source_code_injector():
    output_fd = get_test_output_fd()
    test_py_file = get_test_py_file()

    cpp_generator = CppGenerator(CppGeneratorConfig())
    cpp_file, _ = cpp_generator.run(test_py_file, output_fd)

    string_literal_obfuscator = SourceCodeInjector(
        SourceCodeInjectorConfig(fernet_key='WwAPKBMXKl-I43L4u8B5WD9xoperM9qhXDlLVWRFkiY=')
    )
    good = string_literal_obfuscator.run(
        py_file=test_py_file,
        cpp_file=cpp_file,
    )
    assert good
