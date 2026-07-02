from dataclasses import dataclass


@dataclass(frozen=True)
class ImportResult:
    """导入闭环的三个标准产物入口。"""

    raw_dataset_path: str
    import_report_path: str
    failure_manifest_path: str
    report: dict[str, int]
