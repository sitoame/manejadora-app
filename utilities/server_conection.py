import subprocess


def has_connectivity(host: str = "192.168.30.11", count: int = 1, timeout: int = 1) -> bool:
    """Ping rápido para verificar conectividad con el servidor de ingesta."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False
