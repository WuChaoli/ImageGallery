from pathlib import Path

import pytest
from sqlalchemy import create_engine

from image_gallery.model_manager import ModelDefinition, ModelManager, ModelRegistrationError, ModelRuntimeError


class Runtime:
    def __init__(self, outputs: list[tuple[float, ...]]) -> None:
        self.outputs = outputs
        self.calls = 0
        self.closed = False

    def embed(self, images: list[bytes]) -> list[tuple[float, ...]]:
        self.calls += 1
        return self.outputs[: len(images)]

    def close(self) -> None:
        self.closed = True


def definition(*, model_id: str = "clip", config: dict[str, object] | None = None) -> ModelDefinition:
    return ModelDefinition(
        model_id=model_id,
        provider="test",
        artifact_uri="file:///models/clip.bin",
        artifact_revision="v1",
        artifact_checksum="sha256:" + "1" * 64,
        dimension=2,
        dtype="float32",
        config=config or {"normalize": True},
        credential_ref="secret://models/clip",
    )


def test_model_definition_fingerprint_is_stable_and_excludes_credential() -> None:
    first = definition(config={"b": 2, "a": 1})
    second = definition(config={"a": 1, "b": 2})

    assert first.fingerprint == second.fingerprint
    assert "secret://" not in first.fingerprint_payload


def test_model_registration_persists_and_rejects_identity_drift(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}").execution_options(
        schema_translate_map={"control": None}
    )
    first = ModelManager(engine=engine)
    registered = first.register(definition())
    first.close()

    restarted = ModelManager(engine=engine)
    assert restarted.get(model_id="clip") == registered
    assert restarted.register(definition()) == registered
    with pytest.raises(ModelRegistrationError):
        restarted.register(definition(config={"normalize": False}))


def test_runtime_is_lazy_cached_and_closed() -> None:
    runtime = Runtime([(1.0, 2.0)])
    manager = ModelManager(
        providers={"test": lambda _definition, _secrets: runtime},
        credential_provider=lambda _ref: {},
    )
    manager.register(definition())

    assert runtime.calls == 0
    assert manager.embed(model_id="clip", images=[b"image"]) == [(1.0, 2.0)]
    assert manager.embed(model_id="clip", images=[b"image"]) == [(1.0, 2.0)]
    assert runtime.calls == 2
    manager.close()
    assert runtime.closed is True
    with pytest.raises(ModelRuntimeError):
        manager.embed(model_id="clip", images=[b"image"])


@pytest.mark.parametrize(
    "outputs",
    [[], [(1.0,)], [(float("nan"), 1.0)], [(float("inf"), 1.0)]],
)
def test_model_manager_rejects_invalid_outputs(outputs: list[tuple[float, ...]]) -> None:
    runtime = Runtime(outputs)
    manager = ModelManager(
        providers={"test": lambda _definition, _secrets: runtime},
        credential_provider=lambda _ref: {},
    )
    manager.register(definition())

    with pytest.raises(ModelRuntimeError):
        manager.embed(model_id="clip", images=[b"image"])
