"""DatasetManager PostgreSQL control plane migration entrypoints。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine


def upgrade_control_database(engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
    """将 control/vectors schema 升级到当前 revision。"""
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).with_name("alembic")))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
