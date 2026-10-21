"""Download the approved Wikimedia Commons test photos (1280 px renditions) and write SOURCES.csv with attribution."""
import csv
import re
import sys
import time
from pathlib import Path

import requests

LIST = Path(__file__).with_name("commons_list.tsv")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "test_photos/commons")
UA = {"User-Agent": "AutoSettleAI-hackathon-testset/0.1 (Confluentia 2026 student project)"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for line in LIST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        idx, title, lic, artist, url, page = line.split("\t")
        url = url.split("?")[0]
        ext = Path(title).suffix.lower().replace(".jpeg", ".jpg") or ".jpg"
        name = f"c{int(idx):02d}_" + re.sub(r"[^A-Za-z0-9]+", "_", Path(title).stem)[:40].strip("_") + ext
        dest = OUT / name
        if not dest.exists():
            for wait in (5, 15, 30, 60, 0):
                r = requests.get(url, headers=UA, timeout=60)
                if r.status_code != 429 or not wait:
                    break
                time.sleep(wait)
            if r.status_code != 200:
                print("SKIPPED", r.status_code, name)
                continue
            dest.write_bytes(r.content)
            time.sleep(3)
        rows.append({"file": name, "title": title, "author": artist or "see page", "licence": lic, "page": page,
                     "bytes": dest.stat().st_size})
        print(name, rows[-1]["bytes"])
    with open(OUT / "SOURCES.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "files,", sum(r["bytes"] for r in rows) // 1024, "KB")


if __name__ == "__main__":
    main()
