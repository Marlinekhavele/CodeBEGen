import os
import platform
from pathlib import Path


def get_default_download_directory() -> Path:
    """
    Returns the default downloads directory based on the operating system.

    Returns:
        Path: Path to the default download directory
    """
    system = platform.system()

    if system == "Linux":

        # Linux: Use XDG_DOWNLOAD_DIR if defined, otherwise fallback to ~/Downloads
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        user_dirs_file = Path(xdg_config_home) / "user-dirs.dirs"

        if user_dirs_file.exists():
            with open(user_dirs_file, "r") as f:
                for line in f:
                    if line.startswith("XDG_DOWNLOAD_DIR="):
                        # Extract the path from the line (remove quotes and expand ~)
                        download_dir = line.split("=")[1].strip().strip('"').replace("$HOME",
                                                                                     os.path.expanduser("~"))
                        return Path(download_dir)

        # Fallback to ~/Downloads
        return Path(os.path.expanduser("~")) / "Downloads"

    else:
        # Fallback for other systems (Windows, MacOS, e.t.c)
        return Path(os.path.expanduser("~")) / "Downloads"