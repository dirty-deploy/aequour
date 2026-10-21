"""Scan the git-tracked tree for credentials, emails, local paths and personal names.  python tools/scan_tree.py  (exit 1 on findings)"""
import re
import subprocess
import sys
from pathlib import Path

PATS = {"local_path": r"[A-Za-z]:[\\/]+(Users|autosettle|aequour|My Phone)|/c/Users", "user": r"\bASUS\b",
        "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}",
        "secret": r"(gho_|ghp_|hf_[A-Za-z0-9]{10}|sk-[A-Za-z0-9]{10}|api[_-]?key\s*[:=]\s*['\"][^'\"]{8,}|BEGIN (RSA|PRIVATE)|AKIA[0-9A-Z]{12})",
        "names": r"Aryan|Satwik|Ishan Paul|Rath\b"}
SKIP = (".jpg", ".png", ".woff2", ".pt", ".onnx", ".zip")


def main():
    root = Path(__file__).resolve().parent.parent
    files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True).stdout.split("\n")
    n = 0
    for f in filter(None, files):
        if f.endswith(SKIP) or f == "tools/scan_tree.py":
            continue
        t = (root / f).read_text(encoding="utf-8", errors="ignore")
        for k, p in PATS.items():
            for m in re.finditer(p, t):
                if k == "email" and ("noreply" in m.group(0) or "example" in m.group(0)):
                    continue
                n += 1
                print(f"{k:<10} {f}:{t[:m.start()].count(chr(10)) + 1}  {m.group(0)[:60]}")
    print(f"\n{n} findings")
    return n == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
