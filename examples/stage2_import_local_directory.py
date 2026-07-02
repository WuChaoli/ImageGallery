from pathlib import Path

from PIL import Image

from image_gallery.dataset import Dataset
from image_gallery.importers import ImportPipeline, LocalDirectoryReader
from image_gallery.storage import FileSystemStorage


def main() -> None:
    work_dir = Path("examples/.stage2_work").resolve()
    source_dir = work_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color="green").save(source_dir / "green.jpg")

    storage = FileSystemStorage(storage_name="local_main").connect(root=work_dir / "storage")
    result = ImportPipeline(storage, output_dir=work_dir / "outputs").run(LocalDirectoryReader(source_dir).read())
    raw_dataset = Dataset.from_path(result.raw_dataset_path)
    print(raw_dataset.count())
    print(result.report["success_count"])
    print(result.report["failure_count"])


if __name__ == "__main__":
    main()
