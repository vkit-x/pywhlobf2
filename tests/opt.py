import os
import os.path
import inspect

import iolite as io
from Cython.Compiler.Version import version as cython_version


def get_data_folder(code_path: str):
    proj_root = os.getenv('PYWHLOBF_ROOT')
    data_root = os.getenv('PYWHLOBF_DATA')
    assert proj_root and data_root

    if os.path.isabs(code_path):
        code_path = os.path.relpath(code_path, proj_root)

    rel_folder = code_path.split('.')[0]
    data_folder = os.path.join(data_root, rel_folder)

    io.folder(data_folder, touch=True)

    return data_folder


def get_test_output_fd(frames_offset: int = 0):
    if not os.getenv('PYWHLOBF_ROOT') or not os.getenv('PYWHLOBF_DATA'):
        raise NotImplementedError()

    frames = inspect.stack()
    frames_offset += 1
    module_path = frames[frames_offset].filename
    function_name = frames[frames_offset].function
    module_fd = io.folder(get_data_folder(module_path))
    test_fd = io.folder(module_fd / function_name, reset=True)
    return test_fd


def get_test_py_file():
    if cython_version[0] != '3':
        return io.file(
            '$PYWHLOBF_DATA/test-data/wheel-0.37.1/wheel/bdist_wheel.py',
            expandvars=True,
            exists=True,
        )
    else:
        return io.file(
            '$PYWHLOBF_DATA/test-data/wheel-0.38.4/wheel/bdist_wheel.py',
            expandvars=True,
            exists=True,
        )


def get_test_code_fd():
    if cython_version[0] != '3':
        return io.folder(
            '$PYWHLOBF_DATA/test-data/wheel-0.37.1/wheel/',
            expandvars=True,
            exists=True,
        )
    else:
        return io.folder(
            '$PYWHLOBF_DATA/test-data/wheel-0.38.4/wheel/',
            expandvars=True,
            exists=True,
        )


def get_test_wheel_file():
    if cython_version[0] != '3':
        return io.file(
            '$PYWHLOBF_DATA/test-data/wheel-0.37.1/wheel-0.37.1-py2.py3-none-any.whl',
            expandvars=True,
            exists=True,
        )
    else:
        return io.file(
            '$PYWHLOBF_DATA/test-data/wheel-0.38.4/wheel-0.38.4-py3-none-any.whl',
            expandvars=True,
            exists=True,
        )


def get_test_customized_py_file():
    py_file = io.file(
        '$PYWHLOBF_DATA/test-data/customized.py',
        expandvars=True,
    )
    code = '''\
import os

a = True
b = False
_PYWHLOBF_FLAG = False

print('a')
if _PYWHLOBF_FLAG:
    print('_PYWHLOBF_FLAG is set.')
print('b')
'''
    py_file.write_text(code)
    return py_file
