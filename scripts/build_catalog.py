#!/usr/bin/env python3
"""Build the read-only GPT catalog from immutable submission records."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

REPOSITORY = "Richard0721/WDCC"


def api_url(path: str) -> str:
    return f"https://api.github.com/repos/{REPOSITORY}/contents/{quote(path, safe='/')}?ref=main"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    records: list[dict] = []

    root = Path("submissions")
    for manifest in sorted(root.glob("*/*/submission.json")) if root.exists() else []:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        bundle = manifest.parent.as_posix()
        record = dict(data)
        record["manifest_path"] = manifest.as_posix()
        record["manifest_api_url"] = api_url(manifest.as_posix())
        record["documents"] = [
            {"name": name, "path": f"{bundle}/{name}", "api_url": api_url(f"{bundle}/{name}")}
            for name in data["source_files"]
        ]
        records.append(record)

    records.sort(key=lambda item: (item["updated_at"], item["record_id"]), reverse=True)
    latest: dict[str, dict] = {}
    for record in records:
        latest.setdefault(record["index_name"], record)
    catalog = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repository": REPOSITORY,
        "source_ref": "main",
        "record_count": len(records),
        "latest_by_index": list(latest.values()),
        "records": records,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {output} with {len(records)} record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
