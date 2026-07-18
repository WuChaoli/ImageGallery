from image_gallery.storage.base import StorageBatchResult, _collect_batch_results


def test_private_batch_executor_preserves_order_and_isolates_errors() -> None:
    def operation(value: tuple[str, int]) -> int:
        if value[0] == "broken":
            raise RuntimeError("backend unavailable")
        return value[1] * 2

    results = _collect_batch_results(
        [("first", 1), ("broken", 2), ("last", 3)],
        object_path=lambda item: item[0],
        operation=operation,
    )

    assert results == [
        StorageBatchResult("first", True, 2),
        StorageBatchResult("broken", False, error="backend unavailable"),
        StorageBatchResult("last", True, 6),
    ]
