from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset
from image_gallery.schemas import validate_raw_dataset
from image_gallery.storage import FileSystemStorage


def main() -> None:
    work_dir = Path("examples/.stage1_work").resolve()
    storage = FileSystemStorage(storage_name="local_main").connect(root=work_dir / "storage")
    image_bytes = b"demo-image-bytes"
    image_uri = storage.write_bytes("images/a.jpg", image_bytes, overwrite=True)

    frame = pd.DataFrame(
        [
            {
                "image_id": "img-1",
                "source_uri": "example://a.jpg",
                "source_type": "example",
                "source_file_name": "a.jpg",
                "storage_name": "local_main",
                "image_uri": image_uri,
                "file_size_bytes": len(image_bytes),
                "image_content_hash": "sha256:demo",
                "file_extension": ".jpg",
                "mime_type": "image/jpeg",
                "image_format": "JPEG",
                "width": 1,
                "height": 1,
                "pixel_count": 1,
                "aspect_ratio": 1.0,
                "orientation": "square",
                "channels": 3,
                "color_mode": "RGB",
                "has_alpha": False,
                "animated": False,
                "frame_count": 1,
                "icc_profile_present": False,
                "dpi_x": None,
                "dpi_y": None,
                "exif_orientation": None,
                "exif_datetime": None,
                "camera_make": None,
                "camera_model": None,
                "gps_present": False,
                "gps_latitude": None,
                "gps_longitude": None,
                "import_status": "imported",
                "imported_at": "2026-07-02T00:00:00Z",
                "schema_version": "raw.v1",
                "tags": [],
            }
        ]
    )
    validate_raw_dataset(frame)

    dataset = Dataset.write(frame, str(work_dir / "raw.parquet"))
    print(dataset.count())
    print(dataset.fingerprint())


if __name__ == "__main__":
    main()
