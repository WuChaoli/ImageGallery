from pathlib import Path

import pytest

from image_gallery.importers import UrlListReader


def test_url_list_reader_rejects_localhost(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text("http://localhost/a.jpg\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe url host"):
        list(UrlListReader(url_list, download_dir=tmp_path / "downloads").read())


def test_url_list_reader_accepts_https_urls_as_source_records(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text("https://example.com/a.jpg\n", encoding="utf-8")

    records = list(UrlListReader(url_list, download_dir=tmp_path / "downloads", download=False).read())

    assert records[0].source_uri == "https://example.com/a.jpg"
    assert records[0].source_type == "url_list"
    assert records[0].source_file_name == "a.jpg"


def test_url_list_reader_rejects_unsupported_image_extension(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text("https://example.com/a.txt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported image extension"):
        list(UrlListReader(url_list, download_dir=tmp_path / "downloads", download=False).read())


def test_url_list_reader_downloads_image_to_local_path(tmp_path: Path, monkeypatch) -> None:
    class FakeResponse:
        content = b"\xff\xd8\xffabc"
        headers = {"content-type": "image/jpeg", "content-length": str(len(content))}

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int, allow_redirects: bool):
        assert url == "https://example.com/a.jpg"
        assert timeout == 10
        assert allow_redirects is True
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)
    url_list = tmp_path / "urls.txt"
    url_list.write_text("https://example.com/a.jpg\n", encoding="utf-8")

    records = list(UrlListReader(url_list, download_dir=tmp_path / "downloads").read())

    assert records[0].local_path == tmp_path / "downloads" / "a.jpg"
    assert records[0].local_path.read_bytes() == b"\xff\xd8\xffabc"
