from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.execution import CleanerExecution


def test_basic_cleaner_compile_returns_execution() -> None:
    execution = BasicCleaner([{"format.decode_check": {}}]).compile()

    assert isinstance(execution, CleanerExecution)
    assert "evaluation.format.decode_check" in execution.plan()["node_id"].tolist()


def test_dry_run_reports_selected_operator() -> None:
    execution = BasicCleaner([{"format.decode_check": {}}]).compile()

    dry_run = execution.dry_run(dataset=None)

    assert "format.decode_check" in dry_run.selected_operators
    assert dry_run.errors == []
