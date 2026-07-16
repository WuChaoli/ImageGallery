"""定时检查 Markdown 外部 HTTP 链接。"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from pathlib import Path

_URL = re.compile(r"https?://[^\s)>\]]+")
_SKIPPED_PARTS = {".git", ".qoder", ".tmp", ".venv", ".worktrees"}


def main() -> int:
    """报告不可访问的外部链接，供非 PR 定时任务使用。"""
    urls: set[str] = set()
    for path in Path(".").rglob("*.md"):
        if _SKIPPED_PARTS.intersection(path.parts):
            continue
        urls.update(_URL.findall(path.read_text(encoding="utf-8")))

    failures: list[str] = []
    for url in sorted(urls):
        # URL 已由正则限定为 HTTP(S)，不会开放本地文件或自定义协议。
        request = urllib.request.Request(url, headers={"User-Agent": "ImageGallery-CI/1.0"})  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
                if response.status >= 400:
                    failures.append(f"{response.status} {url}")
        except (urllib.error.URLError, TimeoutError) as error:
            failures.append(f"{url}: {error}")
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
