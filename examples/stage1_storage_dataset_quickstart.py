from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset
from image_gallery.schemas import validate_raw_dataset
from image_gallery.storage import StorageRegistry


def main() -> None:
    work_dir = Path("examples/.stage1_work").resolve()
    registry = StorageRegistry.from_config(
        {
            "default_storage": "local_main",
            "storages": [
                {"name": "local_main", "type": "filesystem", "root": str(work_dir / "storage")},
            ],
        }
    )

    storage = registry.connect()
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
                "checksum": "sha256:demo",
                "image_format": "JPEG",
                "width": 1,
                "height": 1,
                "channels": 3,
                "color_mode": "RGB",
                "import_status": "imported",
                "imported_at": "2026-07-02T00:00:00Z",
            }
        ]
    )
    validate_raw_dataset(frame)

    dataset = Dataset.write(frame, str(work_dir / "raw.parquet"))
    print(dataset.count())
    print(dataset.fingerprint())


if __name__ == "__main__":
    main()
