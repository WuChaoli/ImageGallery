from pathlib import Path

import pytest

from image_gallery.dataset_manager import ConflictError, DatasetManager, VectorCommit, VectorValidationItem
from image_gallery.storage_manager import StorageManager

pytestmark = pytest.mark.dataset_backend


def test_real_backend_end_to_end(
    dataset_postgres_url: str,
    dataset_catalog_url: str,
    dataset_warehouse: str,
    dataset_minio_config: dict[str, str],
    tmp_path: Path,
) -> None:
    secrets = {
        "secret://minio/tests": {
            "key": dataset_minio_config["key"],
            "secret": dataset_minio_config["secret"],
        }
    }
    storage = StorageManager(credential_provider=lambda ref: secrets[ref])
    manager = DatasetManager.postgres(
        control_url=dataset_postgres_url,
        catalog_url=dataset_catalog_url,
        warehouse=dataset_warehouse,
        storage_manager=storage,
    )
    file_prefix = storage.register_file_prefix(name="file", root=tmp_path / "images")
    s3_prefix = storage.register_s3_prefix(
        name="s3",
        root=f"{dataset_minio_config['bucket']}/images",
        endpoint_url=dataset_minio_config["endpoint_url"],
        credential_ref="secret://minio/tests",
    )
    first_repo = manager.create_repo(name="First")
    second_repo = manager.create_repo(name="Second")
    for prefix_id in (file_prefix.prefix_id, s3_prefix.prefix_id):
        first_repo.bind_storage_prefix(prefix_id=prefix_id)
    second_repo.bind_storage_prefix(prefix_id=file_prefix.prefix_id)
    dataset = first_repo.create_dataset(name="Raw")
    file_object = storage.write_managed(prefix_id=file_prefix.prefix_id, data=b"file-image")
    storage.write_bytes(prefix_id=s3_prefix.prefix_id, relative_path="external/s3.jpg", data=b"s3-image")
    s3_object = storage.verify_external(prefix_id=s3_prefix.prefix_id, relative_path="external/s3.jpg")
    tag = first_repo.create_tag(name="reviewed")
    rows = [
        {
            "asset_id": stored.asset_id,
            "storage_prefix_id": stored.storage_prefix_id,
            "relative_path": stored.relative_path,
            "source_uri": None,
            "tag_ids": [tag.tag_id],
        }
        for stored in (file_object, s3_object)
    ]
    field = first_repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"probe", expected=(0.1, 0.2))],
    )
    base = dataset.open_branch()
    committed = dataset.commit(
        branch="main",
        base=base,
        rows=rows,
        vectors=[
            VectorCommit(
                field=field,
                items={file_object.asset_id: (1.0, 2.0)},
                validation_outputs=[(0.1, 0.2)],
            )
        ],
    ).view
    checkpoint = dataset.create_checkpoint(name="raw", source=committed)
    experiment = dataset.create_branch(name="experiment", source=checkpoint)
    clone = first_repo.clone_dataset(source=checkpoint, name="Clone")

    with pytest.raises(ConflictError):
        dataset.commit(branch="main", base=base, rows=[])
    assert committed.read_image(asset_id=file_object.asset_id) == b"file-image"
    assert committed.read_image(asset_id=s3_object.asset_id) == b"s3-image"
    expected_rows = sorted(rows, key=lambda row: str(row["asset_id"]))
    assert sorted(experiment.scan(), key=lambda row: str(row["asset_id"])) == expected_rows
    assert sorted(clone.open_branch().scan(), key=lambda row: str(row["asset_id"])) == expected_rows
    assert field.get(asset_id=file_object.asset_id) == (1.0, 2.0)
    assert first_repo.repo_id != second_repo.repo_id
