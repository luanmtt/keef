import json
from datetime import datetime
from pathlib import Path
from typing import Any

from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def create_output_dir(root: Path, now: datetime | None = None) -> Path:
    """
    create_output_dir: cria um diretório temporal de relatório.

    input:
        root, diretório raiz das saídas.
        now, horário opcional usado para testes.

    output:
        Path, diretório criado no formato outputs/DD-HH-MM[-N].
    """
    timestamp = now or datetime.now()
    base_dir = root / timestamp.strftime("%d-%H-%M")
    output_dir = base_dir
    suffix = 1

    while output_dir.exists():
        output_dir = base_dir.with_name(f"{base_dir.name}-{suffix:02d}")
        suffix += 1

    output_dir.mkdir(parents=True)

    return output_dir


def write_metadata_report(
    output_dir: Path,
    tracks: list[MusicTrack],
    errors: list[dict[str, str]],
) -> Path:
    """
    write_metadata_report: grava o relatório de parsing em JSON.

    input:
        output_dir, diretório temporal de saída.
        tracks, músicas lidas com sucesso.
        errors, falhas individuais com caminho e diagnóstico.

    output:
        Path, caminho do arquivo metadata.json criado.
    """
    report_path = output_dir / "metadata.json"
    payload: dict[str, Any] = {
        "tracks": [track.model_dump() for track in tracks],
        "errors": errors,
    }

    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    return report_path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
