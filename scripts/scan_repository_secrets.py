"""Deterministic, value-redacting secret scan for repository and CI use."""

from __future__ import annotations

import argparse
import difflib
import io
import os
import re
import subprocess
import sys
import tarfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_BASE_REF = "vst-runtime-freeze-v1"
_CREDENTIAL_FILE_SUFFIXES = frozenset({".key", ".p12", ".pem", ".pfx"})
_CREDENTIAL_FILE_NAMES = frozenset(
    {
        "credentials",
        "credentials.json",
        "credentials.toml",
        "credentials.yaml",
        "credentials.yml",
        "id_dsa",
        "id_ed25519",
        "id_ecdsa",
        "id_rsa",
        "secrets",
        "secrets.json",
        "secrets.toml",
        "secrets.yaml",
        "secrets.yml",
    }
)
_CONFIG_SUFFIXES = frozenset({".cfg", ".ini", ".json", ".toml", ".yaml", ".yml"})
_REVIEWED_FAKE_TEST_VALUES = frozenset(
    {
        "<redacted>",
        "abc",
        "api-key",
        "api-secret",
        "bearer token",
        "do-not-leak",
        "hidden",
        "hidden-key",
        "hidden-secret",
        "key",
        "key-only",
        "must-not-be-read",
        "must-not-be-sent",
        "not-used",
        "one",
        "password",
        "private",
        "private-key",
        "private-secret",
        "private-signature",
        "public",
        "public-secret",
        "raw-secret",
        "read-key",
        "read-secret",
        "redacted",
        "refresh",
        "refresh-secret",
        "refresh-token",
        "secret",
        "secret-signature",
        "super-secret",
        "token",
        "topkey",
        "topsecret",
        "two",
        "unused",
        "user",
        "value",
        "vst-key",
        "vst-secret",
    }
)

_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
)
_PROVIDER_TOKEN_PATTERNS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
        r"\.[A-Za-z0-9_-]{10,}\b"
    ),
)
_BEARER_PATTERN = re.compile(
    r"\bBearer[ \t]+(?P<value>"
    r"(?=[A-Za-z0-9._~+/-]{12,})"
    r"(?=[A-Za-z0-9._~+/-]*[0-9._~+/-])"
    r"[A-Za-z0-9._~+/-]{12,})",
    re.IGNORECASE,
)
_CREDENTIAL_URL_PATTERN = re.compile(
    r"https?://(?P<user>[^/\s:@]+):(?P<password>[^@\s/]+)@",
    re.IGNORECASE,
)
_SENSITIVE_LITERAL_PATTERN = re.compile(
    r"""
    (?:
        (?P<key_quote>["'])
        (?:
            api[_-]?key
            |api[_-]?secret
            |client[_-]?secret
            |access[_-]?token
            |refresh[_-]?token
            |auth[_-]?token
            |authorization
            |password
            |passwd
            |passphrase
            |private[_-]?key
            |signature
            |secret
            |token
        )
        (?P=key_quote)
        \s*(?:=|:)\s*
        |
        (?<![A-Za-z0-9_])
        (?:
            api[_-]?key
            |api[_-]?secret
            |client[_-]?secret
            |access[_-]?token
            |refresh[_-]?token
            |auth[_-]?token
            |authorization
            |password
            |passwd
            |passphrase
            |private[_-]?key
            |signature
            |secret
            |token
        )
        (?![A-Za-z0-9_])
        \s*=\s*
    )
    (?P<quote>["'])
    (?P<value>[^"'\r\n]{1,512})
    (?P=quote)
    """,
    re.IGNORECASE | re.VERBOSE,
)
_UNQUOTED_CONFIG_PATTERN = re.compile(
    r"""
    ^\s*(?:export\s+)?
    (?P<key>
        (?:[A-Z0-9]+_)?API[_-]?KEY
        |(?:[A-Z0-9]+_)?API[_-]?SECRET
        |CLIENT[_-]?SECRET
        |ACCESS[_-]?TOKEN
        |REFRESH[_-]?TOKEN
        |AUTH[_-]?TOKEN
        |PASSWORD
        |PASSPHRASE
        |PRIVATE[_-]?KEY
        |SIGNATURE
        |SECRET
        |TOKEN
    )
    \s*(?:=|:)\s*
    (?P<value>[^#\s][^#\r\n]*?)
    \s*$
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)


class SecretScanError(RuntimeError):
    """Raised when repository evidence cannot be collected safely."""


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """Secret finding metadata that deliberately excludes the matched value."""

    source: str
    path: str
    line: int
    rule_id: str
    commit: str | None = None

    def render(self) -> str:
        commit = f":{self.commit}" if self.commit is not None else ""
        return (
            f"{self.source}{commit}:{self.path}:{self.line}:"
            f" {self.rule_id}"
        )


def scan_text(
    path: str,
    text: str,
    *,
    source: str,
    commit: str | None = None,
    line_offset: int = 0,
    check_path: bool = True,
) -> tuple[SecretFinding, ...]:
    """Scan text while retaining only sanitized location and rule metadata."""

    normalized_path = _normalize_path(path)
    findings: list[SecretFinding] = []

    if check_path and _is_forbidden_credential_path(normalized_path):
        findings.append(
            SecretFinding(
                source,
                normalized_path,
                1,
                "forbidden_credential_file",
                commit,
            )
        )

    for match in _PRIVATE_KEY_PATTERN.finditer(text):
        findings.append(
            _finding(
                source,
                normalized_path,
                text,
                match.start(),
                "private_key_material",
                commit,
                line_offset,
            )
        )

    for pattern in _PROVIDER_TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                _finding(
                    source,
                    normalized_path,
                    text,
                    match.start(),
                    "provider_token",
                    commit,
                    line_offset,
                )
            )

    for match in _BEARER_PATTERN.finditer(text):
        if not _is_reviewed_fake(normalized_path, match.group("value")):
            findings.append(
                _finding(
                    source,
                    normalized_path,
                    text,
                    match.start(),
                    "bearer_token",
                    commit,
                    line_offset,
                )
            )

    for match in _CREDENTIAL_URL_PATTERN.finditer(text):
        fake_user = _is_reviewed_fake(normalized_path, match.group("user"))
        fake_password = _is_reviewed_fake(
            normalized_path,
            match.group("password"),
        )
        if not (fake_user and fake_password):
            findings.append(
                _finding(
                    source,
                    normalized_path,
                    text,
                    match.start(),
                    "credential_url",
                    commit,
                    line_offset,
                )
            )

    for match in _SENSITIVE_LITERAL_PATTERN.finditer(text):
        value = match.group("value")
        if (
            not _is_dynamic_literal(value)
            and not _is_reviewed_fake(normalized_path, value)
        ):
            findings.append(
                _finding(
                    source,
                    normalized_path,
                    text,
                    match.start(),
                    "credential_assignment",
                    commit,
                    line_offset,
                )
            )

    if _is_configuration_path(normalized_path):
        for match in _UNQUOTED_CONFIG_PATTERN.finditer(text):
            if not _is_reviewed_fake(normalized_path, match.group("value")):
                findings.append(
                    _finding(
                        source,
                        normalized_path,
                        text,
                        match.start(),
                        "credential_assignment",
                        commit,
                        line_offset,
                    )
                )

    return tuple(findings)


def scan_repository(
    repository: Path,
    *,
    base_ref: str = _DEFAULT_BASE_REF,
) -> tuple[SecretFinding, ...]:
    """Scan current tracked/intended content and every commit after a base."""

    root = _repository_root(repository)
    findings = [
        *scan_index(root),
        *scan_worktree(root),
        *scan_committed_changes(root, base_ref),
    ]
    return _deduplicate(findings)


def scan_index(repository: Path) -> tuple[SecretFinding, ...]:
    """Scan committed HEAD content plus every staged addition/change."""

    findings: list[SecretFinding] = []
    archive = _git(repository, "archive", "--format=tar", "HEAD")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as stream:
            for member in stream.getmembers():
                if not (member.isfile() or member.issym() or member.islnk()):
                    continue
                if member.issym() or member.islnk():
                    content = member.linkname.encode("utf-8")
                else:
                    extracted = stream.extractfile(member)
                    if extracted is None:
                        continue
                    content = extracted.read()
                findings.extend(
                    _scan_bytes(
                        member.name,
                        content,
                        source="index",
                    )
                )
    except (tarfile.TarError, UnicodeError) as error:
        raise SecretScanError("Git index archive is invalid") from error

    for path in _git_paths(
        repository,
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACM",
    ):
        blob = _git_blob(repository, f":{path}")
        if blob is None:
            continue
        findings.extend(_scan_bytes(path, blob, source="index"))

    return tuple(findings)


def scan_worktree(repository: Path) -> tuple[SecretFinding, ...]:
    """Scan tracked and non-ignored untracked files in the working tree."""

    findings: list[SecretFinding] = []
    root = repository.resolve()
    paths = _git_paths(
        repository,
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
    )
    for path in paths:
        candidate = repository / path
        if candidate.is_symlink():
            try:
                content = os.readlink(candidate).encode("utf-8")
            except OSError as error:
                raise SecretScanError(
                    "repository symlink is unreadable"
                ) from error
            findings.extend(
                _scan_bytes(
                    path,
                    content,
                    source="worktree",
                )
            )
            continue
        if not candidate.exists() or not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise SecretScanError("repository path escapes the worktree")
        try:
            content = candidate.read_bytes()
        except OSError as error:
            raise SecretScanError("repository content is unreadable") from error
        findings.extend(
            _scan_bytes(
                path,
                content,
                source="worktree",
            )
        )
    return tuple(findings)


def scan_committed_changes(
    repository: Path,
    base_ref: str,
) -> tuple[SecretFinding, ...]:
    """Scan added/replaced lines in each commit after the trusted baseline."""

    _git(repository, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    commits = _git(repository, "rev-list", "--reverse", f"{base_ref}..HEAD")
    commit_ids = commits.decode("ascii").split()
    findings: list[SecretFinding] = []

    for commit_id in commit_ids:
        parents = _git(
            repository,
            "rev-list",
            "--parents",
            "-n",
            "1",
            commit_id,
        ).decode("ascii").split()
        parent = parents[1] if len(parents) > 1 else None
        if parent is None:
            paths = _git_paths(
                repository,
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--name-only",
                "--diff-filter=ACM",
                "-r",
                commit_id,
            )
        else:
            paths = _git_paths(
                repository,
                "diff",
                "--name-only",
                "--no-renames",
                "--diff-filter=ACM",
                parent,
                commit_id,
            )

        for path in paths:
            current = _git_blob(repository, f"{commit_id}:{path}")
            if current is None:
                continue
            previous = (
                b""
                if parent is None
                else (_git_blob(repository, f"{parent}:{path}") or b"")
            )
            findings.extend(
                _scan_added_content(
                    path,
                    previous,
                    current,
                    commit_id=commit_id[:12],
                )
            )

    return tuple(findings)


def _scan_added_content(
    path: str,
    previous: bytes,
    current: bytes,
    *,
    commit_id: str,
) -> tuple[SecretFinding, ...]:
    current_text = _decode_text(current)
    previous_text = _decode_text(previous)
    findings: list[SecretFinding] = []

    if _is_forbidden_credential_path(_normalize_path(path)):
        findings.append(
            SecretFinding(
                "commit",
                _normalize_path(path),
                1,
                "forbidden_credential_file",
                commit_id,
            )
        )

    old_lines = previous_text.splitlines(keepends=True)
    new_lines = current_text.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(
        None,
        old_lines,
        new_lines,
        autojunk=False,
    )
    for operation, _old_start, _old_end, new_start, new_end in matcher.get_opcodes():
        if operation == "equal" or new_start == new_end:
            continue
        fragment = "".join(new_lines[new_start:new_end])
        findings.extend(
            scan_text(
                path,
                fragment,
                source="commit",
                commit=commit_id,
                line_offset=new_start,
                check_path=False,
            )
        )
    return tuple(findings)


def _scan_bytes(
    path: str,
    content: bytes,
    *,
    source: str,
) -> tuple[SecretFinding, ...]:
    text = _decode_text(content)
    return scan_text(path, text, source=source)


def _decode_text(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _is_forbidden_credential_path(path: str) -> bool:
    if path == ".env.example":
        return False
    name = Path(path).name.casefold()
    if name == ".env" or name.startswith(".env."):
        return True
    if name in _CREDENTIAL_FILE_NAMES:
        return True
    return Path(name).suffix in _CREDENTIAL_FILE_SUFFIXES


def _is_configuration_path(path: str) -> bool:
    candidate = Path(path)
    return (
        path == ".env.example"
        or candidate.name.casefold().startswith(".env")
        or candidate.suffix.casefold() in _CONFIG_SUFFIXES
    )


def _is_reviewed_fake(path: str, value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"", "***", "<redacted>", "redacted"}:
        return True
    if path == ".env.example" and normalized.startswith("replace-with-"):
        return True
    return (
        path.startswith("tests/")
        and normalized in _REVIEWED_FAKE_TEST_VALUES
    )


def _is_dynamic_literal(value: str) -> bool:
    return (
        re.fullmatch(
            r"(?:\{[A-Za-z_][A-Za-z0-9_.]*\})+",
            value.strip(),
        )
        is not None
    )


def _finding(
    source: str,
    path: str,
    text: str,
    position: int,
    rule_id: str,
    commit: str | None,
    line_offset: int,
) -> SecretFinding:
    return SecretFinding(
        source,
        path,
        line_offset + text.count("\n", 0, position) + 1,
        rule_id,
        commit,
    )


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def _repository_root(repository: Path) -> Path:
    result = _git(repository, "rev-parse", "--show-toplevel")
    try:
        return Path(result.decode("utf-8").strip()).resolve()
    except (OSError, UnicodeError) as error:
        raise SecretScanError("repository root is invalid") from error


def _git_paths(repository: Path, *arguments: str) -> tuple[str, ...]:
    payload = _git(repository, *arguments, "-z")
    try:
        return tuple(
            entry.decode("utf-8", errors="surrogateescape")
            for entry in payload.split(b"\0")
            if entry
        )
    except UnicodeError as error:
        raise SecretScanError("repository path encoding is invalid") from error


def _git_blob(repository: Path, specification: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "show", specification],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise SecretScanError("Git evidence collection failed") from error
    if result.returncode != 0:
        return None
    return result.stdout


def _git(repository: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise SecretScanError("Git evidence collection failed") from error
    if result.returncode != 0:
        raise SecretScanError("Git evidence collection failed")
    return result.stdout


def _deduplicate(
    findings: Sequence[SecretFinding],
) -> tuple[SecretFinding, ...]:
    selected: dict[
        tuple[str, int, str, str | None],
        SecretFinding,
    ] = {}
    for finding in findings:
        key = (
            finding.path,
            finding.line,
            finding.rule_id,
            finding.commit,
        )
        selected.setdefault(key, finding)
    return tuple(
        sorted(
            selected.values(),
            key=lambda item: (
                item.path,
                item.line,
                item.rule_id,
                item.commit or "",
                item.source,
            ),
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scan repository content and committed changes without "
            "printing matched values."
        )
    )
    parser.add_argument(
        "--base-ref",
        default=_DEFAULT_BASE_REF,
        help="Trusted Git ref preceding the committed change scan.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        findings = scan_repository(
            Path.cwd(),
            base_ref=arguments.base_ref,
        )
    except SecretScanError:
        print("secret scan unavailable: repository evidence error", file=sys.stderr)
        return 2

    if findings:
        print(f"secret scan failed: {len(findings)} finding(s)", file=sys.stderr)
        for finding in findings:
            print(finding.render(), file=sys.stderr)
        return 1

    print(
        "secret scan passed: index, worktree, and committed changes are clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "SecretFinding",
    "SecretScanError",
    "main",
    "scan_committed_changes",
    "scan_index",
    "scan_repository",
    "scan_text",
    "scan_worktree",
)
