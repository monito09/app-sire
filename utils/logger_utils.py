from datetime import datetime
from typing import Callable, Optional

def get_timestamp() -> str:
    """Returns the current timestamp in a formatted string."""
    return datetime.now().strftime("%H:%M:%S")

def format_log_message(message: str) -> str:
    """Formats a log message with a timestamp."""
    return f"[{get_timestamp()}] {message}"

def log_to_console(message: str) -> None:
    """Prints a formatted log message to the console."""
    print(format_log_message(message))
