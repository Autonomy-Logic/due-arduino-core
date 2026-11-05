#!/usr/bin/env python3
"""
Build the autonomylogic:sam platform for the Arduino Due and the board manager
index that describes it.

The platform is Arduino's official SAM core (arduino:sam) at the version and
SHA-256 pinned in upstream.json, with platform.txt switched to the newer Arm
GCC that Arduino publishes for its SAMD core, so sketches build as C++14.
The toolchain and bossac are referenced from Arduino's own index, never
redistributed here.

    tools/ci/build-release.py --version 0.1.0 --out dist

Produces, under --out:
    autonomylogic-sam-<ver>.tar.bz2          the platform
    package_autonomylogic_sam_index.json     the index

Standard library only.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
UPSTREAM_JSON = HERE / "upstream.json"

REPO = "Autonomy-Logic/due-arduino-core"
PACKAGER = "autonomylogic"
ARCH = "sam"
PLATFORM_NAME = "Autonomy Logic SAM (Arduino Due, C++14)"
INDEX_NAME = "package_autonomylogic_sam_index.json"
BOARD_NAMES = ["Arduino Due"]
GCC_VERSION = "7-2017q4"
CXX_STD = "-std=gnu++14 -fno-sized-deallocation"
DEFAULT_MTIME = 1767225600  # 2026-01-01T00:00:00Z


def fail(msg):
    sys.exit(f"build-release.py: {msg}")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest, sha256):
    if dest.exists() and sha256_file(dest) == sha256:
        return dest
    print(f"downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    got = sha256_file(part)
    if got != sha256:
        part.unlink()
        fail(f"{url}: SHA-256 is {got}, upstream.json pins {sha256}")
    part.replace(dest)
    return dest


def extract(archive, root, dest):
    """Extract `archive` and move its top-level folder `root` to `dest`."""
    tmp = dest.with_name(dest.name + ".extract")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(archive) as t:
        t.extractall(tmp, filter="data")
    if not (tmp / root).is_dir():
        fail(f"{archive.name}: no top-level folder {root}")
    shutil.rmtree(dest, ignore_errors=True)
    (tmp / root).rename(dest)
    shutil.rmtree(tmp)


def sub_line(text, pattern, repl, what):
    text, n = re.subn(pattern, repl, text, flags=re.M)
    if n != 1:
        fail(f"platform.txt: expected one {what}, found {n}")
    return text


def patch_platform(path, version):
    text = path.read_text(encoding="utf-8")
    text = sub_line(text, r"^name=.*$", f"name={PLATFORM_NAME}", "name=")
    text = sub_line(text, r"^version=.*$", f"version={version}", "version=")
    text = sub_line(text, r"^compiler\.path=\{runtime\.tools\.arm-none-eabi-gcc-[^}]+\.path\}/bin/$",
                    f"compiler.path={{runtime.tools.arm-none-eabi-gcc-{GCC_VERSION}.path}}/bin/", "compiler.path=")
    text = sub_line(text, r"^(compiler\.cpp\.flags=.*?) -std=gnu\+\+11 ", rf"\1 {CXX_STD} ", "-std=gnu++11 in compiler.cpp.flags")
    if "4.8.3" in text:
        fail("platform.txt still names the gcc 4.8.3 toolchain")
    path.write_text(text, encoding="utf-8")


def clean_tree(root):
    """Drop macOS metadata files so they never reach an archive."""
    for p in sorted(root.rglob("*")):
        if p.is_file() and (p.name.startswith("._") or p.name == ".DS_Store"):
            p.unlink()


def make_archive(src, archive, top, mtime):
    def normalize(ti):
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = ""
        ti.mtime = mtime
        if ti.isdir():
            ti.mode = 0o755
        elif ti.isfile():
            ti.mode = 0o755 if ti.mode & 0o111 else 0o644
        return ti

    archive.parent.mkdir(parents=True, exist_ok=True)
    # tarfile.add recurses in sorted order, so equal inputs give equal archives.
    with tarfile.open(archive, "w:bz2") as t:
        t.add(src, arcname=top, filter=normalize)


def asset(path, base_url):
    return {
        "url": f"{base_url}/{path.name}",
        "archiveFileName": path.name,
        "checksum": f"SHA-256:{sha256_file(path)}",
        "size": str(path.stat().st_size),
    }


def build(args):
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?", args.version):
        fail(f"--version {args.version!r} is not a semantic version")
    base_url = (args.base_url or f"https://github.com/{REPO}/releases/download/v{args.version}").rstrip("/")
    up = json.loads(UPSTREAM_JSON.read_text(encoding="utf-8"))

    out = Path(args.out).resolve()
    work = Path(args.work).resolve()
    mtime = int(os.environ.get("SOURCE_DATE_EPOCH", DEFAULT_MTIME))

    c = up["core"]
    archive_in = fetch(c["url"], work / "cache" / c["url"].rsplit("/", 1)[1], c["sha256"])
    core = work / "stage" / "platform"
    print(f"extracting {archive_in.name}")
    extract(archive_in, c["root"], core)
    patch_platform(core / "platform.txt", args.version)
    clean_tree(core)

    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(f"{PACKAGER}-{ARCH}-*.tar.bz2"):
        old.unlink()
    archive = out / f"{PACKAGER}-{ARCH}-{args.version}.tar.bz2"
    print(f"packing {archive.name}")
    make_archive(core, archive, f"{ARCH}-{args.version}", mtime)

    platform = {
        "name": PLATFORM_NAME,
        "architecture": ARCH,
        "version": args.version,
        "category": "Contributed",
        "help": {"online": f"https://github.com/{REPO}"},
        **asset(archive, base_url),
        "boards": [{"name": n} for n in BOARD_NAMES],
        "toolsDependencies": up["toolsDependencies"],
    }
    index = {"packages": [{
        "name": PACKAGER,
        "maintainer": "Autonomy Logic",
        "websiteURL": f"https://github.com/{REPO}",
        "email": "support@autonomylogic.com",
        "help": {"online": f"https://github.com/{REPO}"},
        "platforms": [platform],
        "tools": [],
    }]}
    (out / INDEX_NAME).write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    print(f"{archive}: {platform['size']} bytes, sha256 {platform['checksum'][8:]}")
    print(f"{out / INDEX_NAME}: FQBN {PACKAGER}:{ARCH}:arduino_due_x, served from {base_url}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", required=True, help="platform version, e.g. 0.1.0")
    ap.add_argument("--out", default=str(REPO_ROOT / "dist"), help="output folder (default: dist/)")
    ap.add_argument("--work", default=str(REPO_ROOT / "build"), help="download cache and staging (default: build/)")
    ap.add_argument("--base-url", help="URL the files in --out are served from (default: the GitHub release)")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
