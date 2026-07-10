from image_gallery.cleaning.events import ProgressReporter, RuntimeEvent


def test_progress_reporter_sends_callback_events() -> None:
    received: list[RuntimeEvent] = []
    reporter = ProgressReporter(callback=received.append)

    reporter.emit(
        event_type="node_started",
        run_id="run-1",
        node_id="parameter.demo",
        message="started",
    )

    assert received[0].event_type == "node_started"
    assert received[0].node_id == "parameter.demo"
