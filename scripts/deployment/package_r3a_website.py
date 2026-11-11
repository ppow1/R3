#!/usr/bin/env python3
"""Create and verify a deterministic, source-pinned R3A Website release bundle.

The bundle contains the complete tracked application source, deployment
configuration and runbooks at one Git commit. The visual concept library ZIP is
excluded because it is not loaded by the application or deployment.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile

SHA = re.compile(r"^[0-9a-f]{40}$")
EXCLUDED = {
    "assets/visual-concepts/Riverview3_Visual_Concept_Library.zip":
    "design reference archive; not loaded or installed by the Website",
}


def git(source: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(source), *args], timeout=60)


def tree_entries(source: Path, commit: str):
    raw = git(source, "ls-tree", "-rz", "--full-tree", commit)
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, kind, oid = meta.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if kind != "blob":
            continue
        if path in EXCLUDED:
            continue
        if mode not in {"100644", "100755"}:
            raise ValueError(f"Unsupported tracked file mode for {path}")
        entries.append((path, oid, mode))
    return sorted(entries)


def create(source: Path, commit: str, output: Path):
    if not SHA.fullmatch(commit):
        raise ValueError("commit must be a lowercase 40-character Git SHA")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite package path: {output}")
    resolved = git(source, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    if resolved != commit:
        raise ValueError("resolved source commit does not match requested commit")

    entries = tree_entries(source, commit)
    files = []
    contents = []
    for path, oid, mode in entries:
        data = git(source, "cat-file", "blob", oid)
        files.append({"path": path, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        contents.append((path, data, mode))
    manifest = {
        "contract": "r3a.website-release-package.v1",
        "source_repository": "ppow1/R3",
        "source_commit": commit,
        "entrypoint": "r3_app:app",
        "python": ">=3.12",
        "dependencies": "requirements-deploy.lock (pip --require-hashes)",
        "excluded_files": EXCLUDED,
        "files": files,
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as archive_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=archive_file, mtime=0, compresslevel=6) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for path, data, mode in contents:
                    info = tarfile.TarInfo(f"website/{path}")
                    info.size = len(data)
                    info.mode = 0o755 if mode == "100755" else 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))
                info = tarfile.TarInfo("WEBSITE_PACKAGE_MANIFEST.json")
                info.size = len(manifest_bytes)
                info.mode = 0o644
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(manifest_bytes))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return verify(output, expected_digest=digest)


def verify(package: Path, expected_digest: str | None = None):
    actual_digest = hashlib.sha256(package.read_bytes()).hexdigest()
    if expected_digest and actual_digest != expected_digest:
        raise ValueError("package digest mismatch")
    with tarfile.open(package, "r:gz") as archive:
        members = archive.getmembers()
        by_name = {member.name: member for member in members}
        if len(by_name) != len(members) or any(not member.isfile() for member in members):
            raise ValueError("package contains duplicate or non-regular entries")
        manifest_member = by_name.get("WEBSITE_PACKAGE_MANIFEST.json")
        if not manifest_member:
            raise ValueError("package manifest missing")
        manifest = json.load(archive.extractfile(manifest_member))
        if manifest.get("contract") != "r3a.website-release-package.v1" or not SHA.fullmatch(manifest.get("source_commit", "")):
            raise ValueError("unsupported package manifest")
        expected = {f"website/{item['path']}": item for item in manifest.get("files", [])}
        if set(by_name) != set(expected) | {"WEBSITE_PACKAGE_MANIFEST.json"}:
            raise ValueError("package entry list differs from manifest")
        for name, item in expected.items():
            data = archive.extractfile(by_name[name]).read()
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError(f"content digest mismatch: {name}")
        required = {
            "website/r3_app.py", "website/requirements-deploy.lock",
            "website/web/steward.html", "website/web/steward-workspace-api.mjs",
            "website/deploy/systemd/r3a-ap3-website-lan-https-backend.conf",
            "website/deploy/nginx/r3a-website-lan-https.conf",
            "website/r3a_plugins/steward_access.r3a-native.config.example.json",
        }
        if not required <= set(by_name):
            raise ValueError("package is missing required Website/runtime/config files")
        if "website/assets/visual-concepts/Riverview3_Visual_Concept_Library.zip" in by_name:
            raise ValueError("non-runtime design archive must not be packaged")
    return {
        "package": str(package), "package_sha256": actual_digest,
        "source_commit": manifest["source_commit"], "file_count": len(expected),
        "verified": True,
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--commit", required=True)
    build.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--package", type=Path, required=True)
    check.add_argument("--sha256")
    args = parser.parse_args()
    result = create(args.source.resolve(strict=True), args.commit, args.output) if args.command == "build" else verify(args.package, args.sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"PACKAGE_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
