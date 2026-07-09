from pathlib import Path

import pandas as pd

from image_gallery.cleaning.result import CleanerResult


def test_result_export_table_writes_copy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    tables_dir = run_dir / "tables"
    tables_dir.mkdir(parents=True)
    pd.DataFrame({"image_id": ["img-1"], "decode_ok": [True]}).to_parquet(
        tables_dir / "parameter_table.parquet",
        index=False,
    )
    result = CleanerResult(run_id="run-1", cache_root=tmp_path)

    output = result.export_table("parameter", tmp_path / "parameter_copy.parquet")

    assert output == tmp_path / "parameter_copy.parquet"
    assert pd.read_parquet(output)["image_id"].tolist() == ["img-1"]


def test_result_does_not_expose_work_dir() -> None:
    result = CleanerResult(run_id="run-1", cache_root=Path("/tmp/run"))

    assert not hasattr(result, "work_dir")
