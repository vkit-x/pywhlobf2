from pathlib import Path
import shutil
import re

import attrs


@attrs.define
class FlagSetterConfig:
    enable: bool = True
    flag_name: str = '_PYWHLOBF_FLAG'


class FlagSetter:

    def __init__(self, config: FlagSetterConfig):
        self.config = config

    def run(self, cpp_file: Path):
        if not self.config.enable:
            return False

        # Backup for debugging.
        shutil.copyfile(cpp_file, cpp_file.with_suffix('.cpp.bak_before_flag_setter'))

        # Change cpp file inplace.
        code = cpp_file.read_text()

        flag_name = self.config.flag_name.lstrip('_')
        code = re.sub(
            rf'(PyDict_SetItem\(__pyx_d, __pyx_n_s_{flag_name}, )([^\)]+)\)',
            # Always set to True.
            r'\1' + 'Py_True /* Changed by pywhlobf FlagSetter (prev: `\\2`) */ )',
            code,
        )

        cpp_file.write_text(code)

        return True
