from datetime import datetime
from pathlib import Path

from utilities import load_file, save_file
from utilities.server_conection import has_connectivity
from var import const


def _backup_path(name: str) -> Path:
    base_dir = getattr(const, "backup_dir", Path(__file__).resolve().parents[1] / "backup")
    path = Path(base_dir) / f"{name}.pkl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def writeData(name, data, write_api):
    backup_path = _backup_path(name)
    batch_size = getattr(const, "ingest_batch_size", 20)

    def _load_queue():
        if not backup_path.exists():
            return []
        try:
            loaded = load_file.loadFileAsDictionary(backup_path)
            if isinstance(loaded, list):
                return loaded
            return [loaded]
        except Exception as e:
            print(datetime.now(), "Fallo al cargar backup", e)
            return []

    def _save_queue(queue):
        try:
            save_file.saveFileAsDictionary(queue, backup_path)
        except Exception as e:
            print(datetime.now(), "Fallo al guardar backup", e)

    if not has_connectivity():
        # Sin conectividad: encola y sal
        queue = _load_queue()
        queue.append(data)
        _save_queue(queue)
        return

    # Conectividad OK: encola dato actual y trata de vaciar en lotes pequeños
    queue = _load_queue()
    queue.append(data)

    while queue:
        chunk = queue[:batch_size]
        try:
            write_api.write(bucket=const.bucket, record=chunk)
            queue = queue[len(chunk):]
        except Exception as e:
            print(datetime.now(), "Fallo en la ingesta", e)
            _save_queue(queue)
            return

    # Todo enviado, limpiar backup
    backup_path.unlink(missing_ok=True)
