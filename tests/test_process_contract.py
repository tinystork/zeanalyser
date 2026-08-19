"""Contract lock for the ZeAnalyser process protocol (interoperability).

This test does not import ZeAnalyser (no Qt dependency required): it reads
the source of ``analyse_gui_qt.py`` and verifies that the identifiers of the
documented process contract are still implemented.  Any accidental rename
breaks the lock and requires an explicit protocol version bump (see
``docs/zeanalyser_process_contract.md``, section 6).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "zeanalyser" / "analyse_gui_qt.py"
CONTRACT_DOC = ROOT / "docs" / "zeanalyser_process_contract.md"


def _source_text() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_command_file_env_var_identifier_present():
    """The env var documented in the contract is read by the source."""
    assert "ZEANALYSER_COMMAND_FILE" in _source_text()


def test_reference_protocol_identifiers_present():
    """The REFERENCE=/TIMESTAMP= key names documented in the contract exist."""
    src = _source_text()
    assert "REFERENCE=" in src
    assert "TIMESTAMP=" in src


def test_contract_doc_exists_and_covers_protocol():
    """The contract document exists and references the protocol v1 keys."""
    doc = CONTRACT_DOC.read_text(encoding="utf-8")
    assert "ZEANALYSER_COMMAND_FILE" in doc
    assert "REFERENCE=" in doc
    assert "TIMESTAMP=" in doc
    assert "protocol v1" in doc
