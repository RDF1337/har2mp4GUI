# core.py

import re
import json
import shutil
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import time

rx_idx = re.compile(r"/(\d+)\.bin(?:\?|$)")
rx_q = re.compile(r"/(\d{3,4})/(\d+)\.bin")

class HarProcessor:

    def __init__(self, root, progress_callback=None, log_callback=None):
        self.root = Path(root)
        self.ffmpeg = self.root / "source" / "ffmpeg.exe"
        self.output = self.root / "output"
        self.temp = self.root / "temp"
        self.progress_callback = progress_callback
        self.log_callback = log_callback

        self.output.mkdir(exist_ok=True)

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def parse_har(self, har_path):
        with open(har_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = data.get("log", {}).get("entries", [])
        candidates = []

        for e in entries:
            url = e.get("request", {}).get("url")
            if not url or ".bin" not in url:
                continue

            m = rx_idx.search(url)
            if not m:
                continue

            idx = int(m.group(1))
            q = None
            mq = rx_q.search(url)
            if mq:
                q = int(mq.group(1))

            size = None
            headers = e.get("response", {}).get("headers", [])
            for h in headers:
                if h.get("name", "").lower() == "content-length":
                    try:
                        size = int(h.get("value"))
                    except:
                        pass

            candidates.append({
                "url": url,
                "index": idx,
                "quality": q,
                "size": size
            })

        best = {}

        for item in candidates:
            idx = item["index"]
            if idx not in best:
                best[idx] = item
                continue

            cur = best[idx]

            q_it = item["quality"] if item["quality"] is not None else -1
            q_cur = cur["quality"] if cur["quality"] is not None else -1

            if q_it > q_cur:
                best[idx] = item
            elif q_it == q_cur:
                s_it = item["size"] if item["size"] is not None else -1
                s_cur = cur["size"] if cur["size"] is not None else -1
                if s_it > s_cur:
                    best[idx] = item

        return sorted(best.values(), key=lambda x: x["index"])

    def download_segment(self, item):
        url = item["url"]
        index = item["index"]
        expected_size = item["size"]

        dst = self.temp / "segments" / f"{index:05}.bin"

        for attempt in range(3):
            try:
                r = requests.get(url, timeout=30)
                r.raise_for_status()

                with open(dst, "wb") as f:
                    f.write(r.content)

                if expected_size and dst.stat().st_size != expected_size:
                    raise Exception("Size mismatch")

                return True

            except Exception:
                time.sleep(1)

        return False

    def process(self, har_path):

        if self.temp.exists():
            shutil.rmtree(self.temp)

        (self.temp / "segments").mkdir(parents=True)

        items = self.parse_har(har_path)
        total = len(items)

        if total == 0:
            raise Exception("No segments found")

        completed = 0

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(self.download_segment, it) for it in items]

            for f in as_completed(futures):
                if not f.result():
                    raise Exception("Download failed")

                completed += 1
                if self.progress_callback:
                    self.progress_callback(completed / total)

        combined = self.temp / "combined.mp4"

        with open(combined, "wb") as outfile:
            for file in sorted((self.temp / "segments").glob("*.bin")):
                with open(file, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)

        final = self.output / (har_path.stem + ".mp4")

        cmd = [
            str(self.ffmpeg),
            "-y",
            "-loglevel", "error",
            "-i", str(combined),
            "-c", "copy",
            "-movflags", "+faststart",
            str(final)
        ]

        result = subprocess.run(cmd)

        if result.returncode != 0:
            raise Exception("ffmpeg error")

        har_path.unlink()
        shutil.rmtree(self.temp)

        return final
