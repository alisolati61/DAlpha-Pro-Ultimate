"""Regression tests for the deterministic repository secret scanner."""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest

from scripts import scan_repository_secrets as scanner


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repository: Path, message: str) -> None:
    _git(repository, "add", ".")
    _git(
        repository,
        "-c",
        "user.name=Secret Scan Test",
        "-c",
        "user.email=secret-scan@example.invalid",
        "commit",
        "-m",
        message,
    )


def _initialize_repository(repository: Path) -> str:
    _git(repository, "init")
    (repository / "safe.txt").write_text("safe\n", encoding="utf-8")
    _commit(repository, "baseline")
    return _git(repository, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "path",
    (
        ".env",
        ".env.local",
        "credentials.json",
        "private.pem",
        "secrets.toml",
    ),
)
def test_forbidden_credential_filename_is_rejected(path: str) -> None:
    findings = scanner.scan_text(path, "", source="test")

    assert {finding.rule_id for finding in findings} == {
        "forbidden_credential_file"
    }


def test_placeholder_environment_example_is_allowed() -> None:
    findings = scanner.scan_text(
        ".env.example",
        "API_KEY=replace-with-placeholder\n",
        source="test",
    )

    assert findings == ()


def test_production_credential_literal_is_rejected_and_redacted() -> None:
    candidate_value = "live-value-" + ("A" * 24)
    candidate_text = "api_" + f'key="{candidate_value}"'

    findings = scanner.scan_text(
        "src/example.py",
        candidate_text,
        source="worktree",
    )

    assert [finding.rule_id for finding in findings] == [
        "credential_assignment"
    ]
    assert candidate_value not in findings[0].render()


def test_reviewed_fake_is_allowed_only_under_tests() -> None:
    candidate_text = "api_" + 'key="api-key"'

    assert (
        scanner.scan_text(
            "tests/test_example.py",
            candidate_text,
            source="worktree",
        )
        == ()
    )
    assert {
        finding.rule_id
        for finding in scanner.scan_text(
            "src/example.py",
            candidate_text,
            source="worktree",
        )
    } == {"credential_assignment"}


@pytest.mark.parametrize(
    ("candidate_text", "rule_id"),
    (
        (
            "-----BEGIN " + "PRIVATE KEY-----",
            "private_key_material",
        ),
        (
            "gh" + "p_" + ("A" * 24),
            "provider_token",
        ),
        (
            "Bearer " + ("A1" * 12),
            "bearer_token",
        ),
        (
            "https://" + "operator:" + ("A" * 24) + "@example.invalid/",
            "credential_url",
        ),
    ),
)
def test_strong_secret_forms_are_never_test_allowlisted(
    candidate_text: str,
    rule_id: str,
) -> None:
    findings = scanner.scan_text(
        "tests/test_example.py",
        candidate_text,
        source="worktree",
    )

    assert rule_id in {finding.rule_id for finding in findings}
    assert candidate_text not in "\n".join(
        finding.render() for finding in findings
    )


def test_import_has_no_git_or_network_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("import must not execute a subprocess")

    monkeypatch.setattr(subprocess, "run", fail)

    importlib.reload(scanner)


def test_committed_scan_catches_secret_introduced_then_removed(
    tmp_path: Path,
) -> None:
    base_ref = _initialize_repository(tmp_path)
    candidate_value = "live-value-" + ("B" * 24)
    candidate_text = "client_" + f'secret="{candidate_value}"\n'
    candidate = tmp_path / "configuration.py"
    candidate.write_text(candidate_text, encoding="utf-8")
    _commit(tmp_path, "introduce")
    candidate.unlink()
    _commit(tmp_path, "remove")

    findings = scanner.scan_committed_changes(tmp_path, base_ref)

    assert {finding.rule_id for finding in findings} == {
        "credential_assignment"
    }
    assert all(candidate_value not in finding.render() for finding in findings)


def test_committed_scan_ignores_secret_only_deleted_after_baseline(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init")
    candidate = tmp_path / "legacy.py"
    candidate_value = "legacy-value-" + ("C" * 24)
    candidate.write_text(
        "api_" + f'secret="{candidate_value}"\n',
        encoding="utf-8",
    )
    _commit(tmp_path, "baseline")
    base_ref = _git(tmp_path, "rev-parse", "HEAD")
    candidate.unlink()
    _commit(tmp_path, "remove")

    assert scanner.scan_committed_changes(tmp_path, base_ref) == ()


def test_worktree_scan_checks_non_ignored_untracked_content(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path)
    candidate_value = "worktree-value-" + ("D" * 24)
    (tmp_path / "new.py").write_text(
        "access_" + f'token="{candidate_value}"\n',
        encoding="utf-8",
    )

    findings = scanner.scan_worktree(tmp_path)

    assert {finding.rule_id for finding in findings} == {
        "credential_assignment"
    }
    assert all(candidate_value not in finding.render() for finding in findings)


def test_index_scan_checks_staged_content_not_present_in_worktree(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path)
    candidate_value = "index-value-" + ("E" * 24)
    candidate = tmp_path / "staged.py"
    candidate.write_text(
        "private_" + f'key="{candidate_value}"\n',
        encoding="utf-8",
    )
    _git(tmp_path, "add", "staged.py")
    candidate.write_text("safe = True\n", encoding="utf-8")

    findings = scanner.scan_index(tmp_path)

    assert {finding.rule_id for finding in findings} == {
        "credential_assignment"
    }
    assert all(candidate_value not in finding.render() for finding in findings)


def test_current_repository_scan_is_clean() -> None:
    repository = Path(__file__).resolve().parents[1]

    assert scanner.scan_repository(repository) == ()
