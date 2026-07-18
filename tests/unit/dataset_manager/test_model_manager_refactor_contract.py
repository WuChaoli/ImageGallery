from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

from image_gallery.model_manager import ModelDefinition, ModelManager, ModelRuntimeError


class TrackingRuntime:
    def __init__(self, outputs: list[tuple[object, ...]]) -> None:
        self.outputs = outputs
        self.close = MagicMock()

    def embed(self, images: list[bytes]) -> list[tuple[object, ...]]:
        return self.outputs[: len(images)]


def _definition() -> ModelDefinition:
    return ModelDefinition(
        model_id="clip",
        provider="test",
        artifact_uri="file:///models/clip.bin",
        artifact_revision="v1",
        artifact_checksum="sha256:" + "1" * 64,
        dimension=2,
        dtype="float32",
        config={"normalize": True},
        credential_ref="secret://models/clip",
    )


def test_bind_engine_migrates_definitions_and_transfers_engine_ownership(tmp_path: Path) -> None:
    manager = ModelManager()
    manager.register(_definition())
    owned_engine = manager._engine
    owned_dispose = MagicMock(wraps=owned_engine.dispose)
    owned_engine.dispose = owned_dispose
    external_engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}").execution_options(
        schema_translate_map={"control": None}
    )
    external_dispose = MagicMock(wraps=external_engine.dispose)
    external_engine.dispose = external_dispose

    manager.bind_engine(external_engine)

    assert manager.get(model_id="clip") == _definition()
    owned_dispose.assert_called_once_with()
    manager.close()
    external_dispose.assert_not_called()
    external_engine.dispose()


def test_runtime_and_credentials_are_loaded_once_and_closed_once() -> None:
    runtime = TrackingRuntime([(1.0, 2.0)])
    credential_provider = MagicMock(return_value={"token": "secret"})
    factory = MagicMock(return_value=runtime)
    manager = ModelManager(providers={"test": factory}, credential_provider=credential_provider)
    manager.register(_definition())

    assert manager.embed(model_id="clip", images=[b"first"]) == [(1.0, 2.0)]
    assert manager.embed(model_id="clip", images=[b"second"]) == [(1.0, 2.0)]
    manager.close()
    manager.close()

    credential_provider.assert_called_once_with("secret://models/clip")
    factory.assert_called_once()
    runtime.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("outputs", "message"),
    [
        ([(1.0, "invalid")], "dtype"),
        ([(1.0,)], "dimension"),
        ([(1.0, float("nan"))], "dimension"),
    ],
)
def test_invalid_runtime_output_fails_without_partial_results(
    outputs: list[tuple[object, ...]],
    message: str,
) -> None:
    runtime = TrackingRuntime(outputs)
    manager = ModelManager(
        providers={"test": lambda _definition, _secrets: runtime},
        credential_provider=lambda _ref: {},
    )
    manager.register(_definition())

    with pytest.raises(ModelRuntimeError, match=message):
        manager.embed(model_id="clip", images=[b"image"])
