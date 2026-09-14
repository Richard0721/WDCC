#!/usr/bin/env python3
"""Validate append-only index progress submissions without third-party packages."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

RECORD_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
USER_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
ALLOWED_SUFFIXES = {".json", ".csv", ".tsv", ".md", ".txt", ".xlsx", ".xls", ".pdf", ".docx"}
STATUSES = {"not_started", "in_progress", "blocked", "complete"}
MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_BUNDLE_SIZE = 50 * 1024 * 1024
REQUIRED = {
    "schema_version",
    "record_id",
    "index_name",
    "status",
    "progress_percent",
    "updated_at",
    "submitted_by",
    "summary",
    "source_files",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def changed_files(base: str, head: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", base, head],
        check=True,
        capture_output=True,
        text=True,
    )
    changes: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        status = parts[0]
        for path in parts[1:]:
            changes.append((status, path.replace("\\", "/")))
    return changes


def parse_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
        return True
    except ValueError:
        return False


def validate_manifest(manifest_path: Path, actor: str | None, errors: list[str]) -> dict | None:
    relative = manifest_path.as_posix()
    parts = PurePosixPath(relative).parts
    if len(parts) != 4 or parts[0] != "submissions" or parts[3] != "submission.json":
        fail(errors, f"{relative}: expected submissions/<user>/<record-id>/submission.json")
        return None
    _, owner, record_id, _ = parts
    if not USER_RE.fullmatch(owner):
        fail(errors, f"{relative}: invalid GitHub user directory")
    if not RECORD_RE.fullmatch(record_id):
        fail(errors, f"{relative}: invalid record-id")
    if actor and owner.casefold() != actor.casefold():
        fail(errors, f"{relative}: contributor may only add records under submissions/{actor}/")

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(errors, f"{relative}: invalid UTF-8 JSON ({exc})")
        return None
    if not isinstance(data, dict):
        fail(errors, f"{relative}: root must be a JSON object")
        return None
    missing = REQUIRED - data.keys()
    extra = data.keys() - REQUIRED
    if missing:
        fail(errors, f"{relative}: missing fields: {', '.join(sorted(missing))}")
    if extra:
        fail(errors, f"{relative}: unknown fields: {', '.join(sorted(extra))}")
    if data.get("schema_version") != 1:
        fail(errors, f"{relative}: schema_version must be 1")
    if data.get("record_id") != record_id:
        fail(errors, f"{relative}: record_id must match its directory")
    if not isinstance(data.get("index_name"), str) or not 1 <= len(data["index_name"].strip()) <= 120:
        fail(errors, f"{relative}: index_name must contain 1-120 characters")
    if data.get("status") not in STATUSES:
        fail(errors, f"{relative}: invalid status")
    progress = data.get("progress_percent")
    if not isinstance(progress, int) or isinstance(progress, bool) or not 0 <= progress <= 100:
        fail(errors, f"{relative}: progress_percent must be an integer from 0 to 100")
    if not parse_timestamp(data.get("updated_at")):
        fail(errors, f"{relative}: updated_at must be an ISO 8601 UTC timestamp")
    submitter = data.get("submitted_by")
    if not isinstance(submitter, str) or submitter.casefold() != owner.casefold():
        fail(errors, f"{relative}: submitted_by must match the user directory")
    if not isinstance(data.get("summary"), str) or not 1 <= len(data["summary"].strip()) <= 1000:
        fail(errors, f"{relative}: summary must contain 1-1000 characters")

    source_files = data.get("source_files")
    if not isinstance(source_files, list) or not source_files or len(source_files) != len(set(map(str, source_files))):
        fail(errors, f"{relative}: source_files must be a non-empty unique list")
        source_files = []
    bundle_dir = manifest_path.parent
    listed: set[str] = set()
    for name in source_files:
        if not isinstance(name, str) or not FILE_RE.fullmatch(name) or name == "submission.json":
            fail(errors, f"{relative}: invalid source file name {name!r}")
            continue
        if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            fail(errors, f"{relative}: unsupported source file type {name!r}")
        listed.add(name)
        path = bundle_dir / name
        if not path.is_file():
            fail(errors, f"{relative}: listed source file is missing: {name}")

    actual = {p.name for p in bundle_dir.iterdir() if p.is_file() and p.name != "submission.json"}
    if actual != listed:
        fail(errors, f"{relative}: source_files must exactly list bundle files; actual={sorted(actual)}, listed={sorted(listed)}")
    total = 0
    for path in bundle_dir.iterdir():
        if not path.is_file():
            fail(errors, f"{relative}: nested directories are not allowed")
            continue
        size = path.stat().st_size
        total += size
        if size > MAX_FILE_SIZE:
            fail(errors, f"{path.as_posix()}: file exceeds 25 MiB")
    if total > MAX_BUNDLE_SIZE:
        fail(errors, f"{bundle_dir.as_posix()}: bundle exceeds 50 MiB")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--actor")
    parser.add_argument("--owner")
    args = parser.parse_args()
    errors: list[str] = []
    manifests: set[Path] = set()

    if bool(args.base) != bool(args.head):
        parser.error("--base and --head must be supplied together")
    if args.base:
        changes = changed_files(args.base, args.head)
        strict_actor = args.actor if args.actor and args.owner and args.actor.casefold() != args.owner.casefold() else None
        for status, path in changes:
            under_submissions = path.startswith("submissions/")
            if under_submissions and status[0] != "A":
                fail(errors, f"{path}: submissions are append-only; change status {status} is forbidden")
            if strict_actor and not under_submissions:
                fail(errors, f"{path}: contributors may only add submission records")
            if under_submissions and status[0] == "A":
                parts = PurePosixPath(path).parts
                if len(parts) >= 3:
                    manifests.add(Path(*parts[:3]) / "submission.json")
        if not manifests and strict_actor:
            fail(errors, "No submission bundle was added")
        actor = strict_actor
    else:
        manifests = set(Path("submissions").glob("*/*/submission.json")) if Path("submissions").exists() else set()
        actor = None

    for manifest in sorted(manifests):
        if not manifest.is_file():
            fail(errors, f"{manifest.as_posix()}: every new record requires submission.json")
        else:
            validate_manifest(manifest, actor, errors)

    if errors:
        print("Submission validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(manifests)} submission record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
