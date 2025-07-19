import importlib.resources
import logging
import shutil
import sys
from pathlib import Path

import xdg_base_dirs

LOG = logging.getLogger(__name__)


class AnsiblePaths:
    def __init__(self, base_data_dir: str | Path | None = None):
        if base_data_dir is None:
            base_data_dir = xdg_base_dirs.xdg_data_home() / "filipstack" / str(id(self))
        self._base = Path(base_data_dir)

    def initialize_resources(self, force: bool = False):
        LOG.info("Initializing Ansible paths in data directory: %s", self.data_dir)
        if self.data_dir.exists():
            if not self.data_dir.is_dir():
                raise FileExistsError(
                    f"Path {self.data_dir} exists but is not a directory."
                )
            if force:
                LOG.warning(
                    "Forcing recreation of base data directory: %s", self.data_dir
                )
                shutil.rmtree(self.data_dir)
            else:
                raise FileExistsError(
                    f"Base data directory {self.data_dir} already exists."
                )
        else:
            LOG.info("Base data directory does not exist, creating: %s", self.data_dir)
            self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.main_playbook.exists() or force:
            LOG.info("Initializing main playbook at: %s", self.main_playbook)
            self.main_playbook.write_text(
                importlib.resources.files("filipstack")
                .joinpath("playbooks", "main.yml")
                .read_text()
            )
        else:
            raise FileExistsError(f"Main playbook {self.main_playbook} already exists.")

        if not self.updates_playbook.exists() or force:
            LOG.info("Initializing updates playbook at: %s", self.updates_playbook)
            self.updates_playbook.write_text(
                importlib.resources.files("filipstack")
                .joinpath("playbooks", "updates.yml")
                .read_text()
            )
        else:
            raise FileExistsError(
                f"Updates playbook {self.updates_playbook} already exists."
            )

        if not self.inventory.exists() or force:
            LOG.info("Initializing inventory at: %s", self.inventory)
            self.inventory.write_text(
                importlib.resources.files("filipstack")
                .joinpath("inventory.yml")
                .read_text()
            )
        else:
            raise FileExistsError(f"Inventory file {self.inventory} already exists.")

    def destroy(self):
        LOG.info("Destroying Ansible paths in data directory: %s", self.data_dir)
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
            LOG.info("Successfully destroyed Ansible paths.")
        else:
            LOG.warning("Data directory %s does not exist, nothing to destroy.")

    @property
    def data_dir(self) -> Path:
        return self._base

    @property
    def main_playbook(self) -> Path:
        return self.data_dir / "playbook_main.yml"

    @property
    def updates_playbook(self) -> Path:
        return self.data_dir / "playbook_updates.yml"

    @property
    def inventory(self) -> Path:
        return self.data_dir / "inventory.yml"

    def __enter__(self):
        self.initialize_resources()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy()


def get_executable_path(name: str) -> str:
    """Get the path to an executable, searching first in the directory the Python executable is in, then in the system PATH."""
    env_bin = Path(sys.executable).parent
    if result := shutil.which(name, path=str(env_bin)):
        return result

    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(f"Executable '{name}' not found in PATH.")
    return path
