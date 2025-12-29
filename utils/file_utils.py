import os
from typing import Optional

def ensure_directory_exists(path: str) -> None:
    """
    Ensures that the directory for the given path exists.
    If the path is a file, checks its parent directory.
    """
    if os.path.splitext(path)[1]:  # It's likely a file
        directory = os.path.dirname(path)
    else:
        directory = path

    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def get_file_path(directory: str, filename: str) -> str:
    """
    Joins directory and filename to return a full path.
    """
    return os.path.join(directory, filename)

def file_exists(path: str) -> bool:
    """
    Checks if a file exists.
    """
    return os.path.exists(path)
