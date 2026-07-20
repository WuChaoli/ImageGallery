"""增加 Dataset 名称 durable reservation。"""

from alembic import op
from sqlalchemy import text

revision = "0002_dataset_name_reservation"
down_revision = "0001_dataset_manager_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建名称预留关系并为既有 Dataset 回填永久占用。"""
    connection = op.get_bind()
    rows = connection.execute(text("SELECT dataset_id, repo_id, name FROM control.datasets")).mappings().all()
    normalized: dict[tuple[str, str], str] = {}
    for row in rows:
        display_name = str(row["name"]).strip()
        name_key = display_name.casefold()
        identity = (str(row["repo_id"]), name_key)
        if not display_name or identity in normalized:
            raise RuntimeError("Dataset names collide after trim/case normalization")
        normalized[identity] = str(row["dataset_id"])
        connection.execute(
            text(
                """
                UPDATE control.datasets
                SET name = :name, name_key = :name_key
                WHERE dataset_id = :dataset_id
                """
            ),
            {"name": display_name, "name_key": name_key, "dataset_id": str(row["dataset_id"])},
        )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS control.dataset_name_reservations (
            repo_id VARCHAR(32) NOT NULL REFERENCES control.repos(repo_id),
            name_key VARCHAR(255) NOT NULL,
            operation_id VARCHAR(32) NOT NULL UNIQUE REFERENCES control.operations(operation_id),
            target_dataset_id VARCHAR(32) NOT NULL UNIQUE,
            PRIMARY KEY (repo_id, name_key)
        )
        """
    )
    op.execute(
        """
        INSERT INTO control.dataset_name_reservations (
            repo_id,
            name_key,
            operation_id,
            target_dataset_id
        )
        SELECT
            dataset.repo_id,
            dataset.name_key,
            MIN(operation.operation_id),
            dataset.dataset_id
        FROM control.datasets AS dataset
        JOIN control.operations AS operation
          ON operation.repo_id = dataset.repo_id
         AND operation.dataset_id = dataset.dataset_id
        GROUP BY dataset.repo_id, dataset.name_key, dataset.dataset_id
        ON CONFLICT (repo_id, name_key) DO NOTHING
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON control.dataset_name_reservations TO dataset_manager_control")


def downgrade() -> None:
    """删除 Dataset 名称预留关系。"""
    op.execute("DROP TABLE IF EXISTS control.dataset_name_reservations")
