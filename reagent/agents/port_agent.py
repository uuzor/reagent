"""Port finder agent.

Replaces hardcoded port 8001 in main.py with a tool that finds available ports.
"""

import socket


def find_available_port(preferred: int = 8001, fallback_range: tuple = (8000, 8100)) -> int:
    """
    Find an available TCP port.

    Tries the preferred port first, then scans the fallback range.

    Args:
        preferred: Preferred port number
        fallback_range: (start, end) range to scan if preferred is taken

    Returns:
        Available port number.
    """
    # Try preferred port
    if _is_port_available(preferred):
        return preferred

    # Scan fallback range
    start, end = fallback_range
    for port in range(start, end + 1):
        if port == preferred:
            continue
        if _is_port_available(port):
            return port

    # Last resort: let OS assign
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a TCP port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex((host, port))
            return result != 0  # 0 means connection succeeded (port in use)
    except Exception:
        return True
