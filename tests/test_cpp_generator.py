from pywhlobf.component.cpp_generator import CppGeneratorConfig, CppGenerator
from tests.opt import get_test_output_fd, get_test_py_file


def test_cpp_generator():
    output_fd = get_test_output_fd()
    test_py_file = get_test_py_file()

    cpp_generator = CppGenerator(CppGeneratorConfig(options={'annotate': True}))
    cpp_file, ext_module = cpp_generator.run(test_py_file, output_fd)
    assert cpp_file.exists()
    assert ext_module
