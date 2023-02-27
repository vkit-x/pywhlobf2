from pywhlobf.component.cpp_generator import CppGeneratorConfig, CppGenerator
from pywhlobf.component.string_literal_obfuscator import (
    StringLiteralObfuscatorConfig,
    StringLiteralObfuscator,
)
from tests.opt import get_test_output_fd, get_test_py_file


def test_test_string_literal_obfuscator():
    output_fd = get_test_output_fd()
    test_py_file = get_test_py_file()

    cpp_generator = CppGenerator(CppGeneratorConfig())
    cpp_file, _ = cpp_generator.run(test_py_file, output_fd)

    string_literal_obfuscator = StringLiteralObfuscator(StringLiteralObfuscatorConfig())
    _, include_fd = string_literal_obfuscator.run(cpp_file)
    assert include_fd
