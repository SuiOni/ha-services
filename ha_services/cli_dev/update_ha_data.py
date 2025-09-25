import logging
import tempfile
from pathlib import Path

from bx_py_utils.path import assert_is_file
from cli_base.cli_tools.subprocess_utils import ToolsExecutor, verbose_check_call
from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

from ha_services.cli_dev import PACKAGE_ROOT, app


logger = logging.getLogger(__name__)


@app.command
def update_ha_data(verbosity: TyroVerbosityArgType):
    """
    Update Home Assistant data files for custom components.

    Creates a venv in /tmp/, installs `homeassistant` package and runs a script to collect data.
    """
    setup_logging(verbosity=verbosity)

    output_path = PACKAGE_ROOT / 'ha_services/ha_data/data_sensors.py'

    collect_script_path = PACKAGE_ROOT / 'ha_services/ha_data/collect_ha_data.py'
    assert_is_file(collect_script_path)

    temp_path = Path(tempfile.gettempdir())
    temp_venv_path = temp_path / 'ha_services_ha_data_venv'
    print(f'Create virtual env in: {temp_venv_path}')

    tools_executor = ToolsExecutor()

    # Install https://pypi.org/project/homeassistant/ package in a virtual env in /tmp/
    tools_executor.verbose_check_call(
        'uv',
        'venv',
        '--allow-existing',
        temp_venv_path,
    )

    collect_script_venv_path = temp_venv_path / 'collect_ha_data.py'
    if collect_script_venv_path.exists():
        collect_script_venv_path.unlink()
    collect_script_venv_path.symlink_to(collect_script_path)

    verbose_check_call(temp_venv_path / 'bin' / 'python', '-V')
    verbose_check_call(temp_venv_path / 'bin' / 'python', '-m', 'ensurepip')
    verbose_check_call(temp_venv_path / 'bin' / 'python', '-m', 'pip', 'install', 'uv')
    verbose_check_call(temp_venv_path / 'bin' / 'uv', 'pip', 'install', 'homeassistant')
    verbose_check_call(
        temp_venv_path / 'bin' / 'python',
        'collect_ha_data.py',
        '--output',
        output_path,
        cwd=temp_venv_path,
    )
    tools_executor.verbose_check_call('ruff', 'format', output_path)
