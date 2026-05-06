from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API_URL = "https://www.virustotal.com/api/v3/files"


def upload_file(path: Path, api_key: str) -> dict:
    boundary = f"----tweetkb-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
    )
    body.extend(path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        API_URL,
        data=bytes(body),
        headers={
            "x-apikey": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload release artifacts to VirusTotal.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)

    api_key = os.environ.get("VT_API_KEY")
    if not api_key:
        print("VT_API_KEY is not set", file=sys.stderr)
        return 2

    exit_code = 0
    for path in args.paths:
        if not path.is_file():
            print(f"{path}: not a file", file=sys.stderr)
            exit_code = 1
            continue
        try:
            result = upload_file(path, api_key)
        except urllib.error.HTTPError as exc:
            print(f"{path}: VirusTotal HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
            exit_code = 1
            continue
        except Exception as exc:
            print(f"{path}: upload failed: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        analysis_id = result.get("data", {}).get("id", "")
        print(f"{path}: submitted analysis={analysis_id}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
