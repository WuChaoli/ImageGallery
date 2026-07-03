import ipaddress
from pathlib import Path
from urllib.parse import urlparse

import requests

from image_gallery.importers.config import SourceRecord

SUPPORTED_URL_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
IMAGE_MAGIC_PREFIXES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"RIFF")


class UrlPathParser:
    """解析 URL 清单文件，执行安全校验并可下载到本地临时文件。"""

    def __init__(
        self,
        url_list_path: str | Path,
        download_dir: str | Path,
        download: bool = True,
        timeout_seconds: int = 10,
        max_file_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self.url_list_path = Path(url_list_path)
        self.download_dir = Path(download_dir)
        self.download = download
        self.timeout_seconds = timeout_seconds
        self.max_file_bytes = max_file_bytes

    def parse(self) -> list[SourceRecord]:
        """读取 URL 清单；download=False 时只生成外部来源记录。"""
        records: list[SourceRecord] = []
        for line in self.url_list_path.read_text(encoding="utf-8").splitlines():
            url = line.strip()
            if not url:
                continue
            self._validate_url(url)
            file_name = Path(urlparse(url).path).name or "downloaded-image"
            if Path(file_name).suffix.lower() not in SUPPORTED_URL_IMAGE_SUFFIXES:
                raise ValueError(f"unsupported image extension: {file_name}")
            local_path = self._download(url, file_name) if self.download else None
            records.append(
                SourceRecord(
                    source_uri=url,
                    source_type="url_path",
                    source_file_name=file_name,
                    source_relative_path=file_name,
                    local_path=local_path,
                )
            )
        return records

    def _validate_url(self, url: str) -> None:
        """校验 URL scheme 和明显不安全的本地/内网 host。"""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"unsupported url scheme: {parsed.scheme}")
        host = parsed.hostname or ""
        if host in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError(f"unsafe url host: {host}")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f"unsafe url host: {host}")

    def _download(self, url: str, file_name: str) -> Path:
        """下载单个 URL，并用基础响应头和文件魔数做边界校验。"""
        response = requests.get(url, timeout=self.timeout_seconds, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";")[0].lower()
        if not content_type.startswith("image/"):
            raise ValueError(f"unsupported content-type: {content_type}")
        content_length = int(response.headers.get("content-length") or len(response.content))
        if content_length > self.max_file_bytes:
            raise ValueError(f"url content too large: {content_length}")
        if len(response.content) > self.max_file_bytes:
            raise ValueError(f"url content too large: {len(response.content)}")
        if not response.content.startswith(IMAGE_MAGIC_PREFIXES):
            raise ValueError("unsupported image magic")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.download_dir / file_name
        output_path.write_bytes(response.content)
        return output_path
