import json
from datetime import datetime
from pathlib import Path

from keef.models import MusicTrack
from keef.outputs import create_output_dir, write_metadata_report

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_create_output_dir_uses_expected_timestamp(tmp_path) -> None:
    """
    test_create_output_dir_uses_expected_timestamp: verifica formato temporal.

    input:
        raiz temporária e data conhecida.

    output:
        None, teste aprovado quando diretório segue DD/MM-HH-mm.
    """
    output_dir = create_output_dir(
        tmp_path / "outputs",
        datetime(2026, 9, 3, 18, 42),
    )

    assert output_dir.relative_to(tmp_path) == Path("outputs/03-18-42")


def test_create_output_dir_avoids_collision(tmp_path) -> None:
    """
    test_create_output_dir_avoids_collision: preserva execução repetida.

    input:
        raiz e mesmo timestamp usados duas vezes.

    output:
        None, teste aprovado quando segundo diretório recebe sufixo.
    """
    timestamp = datetime(2026, 9, 3, 18, 42)
    root = tmp_path / "outputs"

    first = create_output_dir(root, timestamp)
    second = create_output_dir(root, timestamp)

    assert first != second
    assert second.name == "03-18-42-01"


def test_write_metadata_report_writes_tracks_and_errors(tmp_path) -> None:
    """
    test_write_metadata_report_writes_tracks_and_errors: verifica JSON.

    input:
        diretório, track válida e erro de parsing.

    output:
        None, teste aprovado quando relatório contém ambos.
    """
    track = MusicTrack(path="song.mp3", title="Blue")
    report_path = write_metadata_report(
        tmp_path,
        [track],
        [{"path": "broken.mp3", "error": "invalid"}],
    )

    payload = json.loads(report_path.read_text())

    assert payload["tracks"][0]["title"] == "Blue"
    assert payload["errors"][0]["path"] == "broken.mp3"
