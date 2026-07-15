from pathlib import Path

from tests.helpers.sample_dataset import (
    get_sample_10_fixture_path,
    load_sample_10_frame,
    materialize_sample_10_dataset,
)


def test_sample_10_fixture_has_stable_local_records(tmp_path: Path) -> None:
    fixture_path = get_sample_10_fixture_path()
    frame = load_sample_10_frame()

    assert fixture_path == Path(__file__).parents[2] / "fixtures" / "sample_10" / "raw.parquet"
    assert len(frame) == 10
    assert frame["image_id"].is_unique
    assert all(str(uri).startswith("images/") for uri in frame["image_uri"])
    assert not any("s3://" in str(uri) for uri in frame["image_uri"])

    dataset = materialize_sample_10_dataset(tmp_path)
    materialized = dataset.to_frame()
    assert len(materialized) == 10
    assert dataset.storage is None
    assert all(image.read_bytes() for image in dataset.iter_images())
    assert dataset.fingerprint() == materialize_sample_10_dataset(tmp_path / "again").fingerprint()


def test_sample_10_materialization_is_independent_of_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    dataset = materialize_sample_10_dataset(tmp_path / "runtime")

    assert len(dataset.to_frame()) == 10
    assert all(image.read_image().width > 0 for image in dataset.iter_images())
