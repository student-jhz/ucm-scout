import os
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ucm_src")

UCM_GIT_URL = "git@github.com:ModelEngine-Group/unified-cache-management.git"
UCM_TAG = "v0.6.0"

KEEP_TOP = [
    "setup.py",
    "CMakeLists.txt",
    "MANIFEST.in",
    "ucm_patch.pth",
]

KEEP_DIRS = [
    "ucm",
]

DEPENDENCIES = OrderedDict([
    ("fmt", {
        "url": "https://gitcode.com/GitHub_Trending/fm/fmt.git",
        "tag": "11.2.0",
        "dest": "ucm/shared/vendor/fmt",
    }),
    ("spdlog", {
        "url": "https://gitcode.com/GitHub_Trending/sp/spdlog.git",
        "tag": "v1.15.3",
        "dest": "ucm/shared/vendor/spdlog",
    }),
    ("pybind11", {
        "url": "https://gitcode.com/GitHub_Trending/py/pybind11.git",
        "tag": "v3.0.1",
        "dest": "ucm/shared/vendor/pybind11",
    }),
    ("zlib", {
        "url": "https://gitcode.com/gh_mirrors/zl/zlib.git",
        "tag": "v1.3.1",
        "dest": "ucm/shared/vendor/zlib",
    }),
])


def _run_git(args, cwd=None):
    cmd = ["git"] + args
    print(f"  $ git {' '.join(args)}")
    subprocess.check_call(cmd, cwd=cwd)


def _rsync_files(src_dir, dst_dir):
    """Copy files from src_dir to dst_dir using robocopy on Windows, cp -r on Linux."""
    os.makedirs(dst_dir, exist_ok=True)
    if sys.platform == "win32":
        subprocess.check_call(
            ["robocopy", src_dir, dst_dir, "/E", "/NFL", "/NDL", "/NJH", "/NJS"],
        )
    else:
        subprocess.check_call(["cp", "-r", f"{src_dir}/.", dst_dir])


def download_ucm():
    print(f"[UCM] cloning {UCM_GIT_URL}#{UCM_TAG} ...")
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = os.path.join(tmp, "ucm-clone")
        _run_git(["clone", "--depth", "1", "--branch", UCM_TAG, UCM_GIT_URL, clone_dir])

        for rel in KEEP_TOP:
            src = os.path.join(clone_dir, rel)
            dst = os.path.join(OUTPUT_DIR, rel)
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  [UCM] {rel}")
            elif os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                print(f"  [UCM] {rel}/")

        for d in KEEP_DIRS:
            src = os.path.join(clone_dir, d)
            dst = os.path.join(OUTPUT_DIR, d)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                file_count = sum(1 for _ in _walk_files(dst))
                print(f"  [UCM] {d}/ ({file_count} files)")

    print(f"[UCM] done")


def download_dependencies():
    vendor_dir = os.path.join(OUTPUT_DIR, "ucm", "shared", "vendor")
    os.makedirs(vendor_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        for dep_name, dep_info in DEPENDENCIES.items():
            url = dep_info["url"]
            tag = dep_info["tag"]
            dest = os.path.join(OUTPUT_DIR, dep_info["dest"].replace("/", os.sep))

            print(f"[dep:{dep_name}] cloning {url}#{tag} ...")
            clone_dir = os.path.join(tmp, dep_name)
            if os.path.exists(clone_dir):
                shutil.rmtree(clone_dir)
            _run_git(["clone", "--depth", "1", "--branch", tag, url, clone_dir])

            if os.path.exists(dest):
                shutil.rmtree(dest)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            _rsync_files(clone_dir, dest)
            file_count = sum(1 for _ in _walk_files(dest))
            print(f"  [dep:{dep_name}] {file_count} files -> {dep_info['dest']}")


def _walk_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def print_tree(root, prefix=""):
    entries = sorted(os.listdir(root))
    for i, entry in enumerate(entries):
        path = os.path.join(root, entry)
        is_last = i == len(entries) - 1
        connector = "\\-- " if is_last else "+-- "
        print(f"{prefix}{connector}{entry}")
        if os.path.isdir(path):
            next_prefix = prefix + ("    " if is_last else "|   ")
            _print_dir_limited(path, next_prefix)


def _print_dir_limited(root, prefix, max_items=6):
    entries = sorted(os.listdir(root))
    for i, entry in enumerate(entries[:max_items]):
        path = os.path.join(root, entry)
        is_last = i == min(len(entries), max_items) - 1
        connector = "\\-- " if is_last else "+-- "
        print(f"{prefix}{connector}{entry}")
    if len(entries) > max_items:
        print(f"{prefix}\\-- ... ({len(entries) - max_items} more)")


if __name__ == "__main__":
    print("=" * 60)
    download_ucm()
    print("=" * 60)
    download_dependencies()
    print("=" * 60)
    print(f"[done] UCM + {len(DEPENDENCIES)} dependencies extracted to {OUTPUT_DIR}")
    print_tree(OUTPUT_DIR)
