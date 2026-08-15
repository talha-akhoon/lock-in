"""The schema is only trustworthy if it can be rebuilt from the migrations."""

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.postgres


def test_schema_matches_the_models(engine: Engine) -> None:
    """An empty autogenerate diff proves the DDL and the ORM agree."""
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    from app.db.session import Base
    from app.models import domain  # noqa: F401  (registers every table)

    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"schema drift: {diff}"


def test_upgrade_is_idempotent(engine: Engine) -> None:
    from alembic import command

    from tests.conftest import TEST_DATABASE_URL, _alembic_config

    command.upgrade(_alembic_config(TEST_DATABASE_URL), "head")
    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar()
    assert version == "0004"


def test_goal_category_is_religious_not_islamic(engine: Engine) -> None:
    with engine.connect() as conn:
        labels = (
            conn.execute(
                text(
                    "select enumlabel from pg_enum "
                    "join pg_type on pg_enum.enumtypid = pg_type.oid "
                    "where typname = 'goalcategory'"
                )
            )
            .scalars()
            .all()
        )
    assert "RELIGIOUS" in labels
    assert "ISLAMIC" not in labels


@pytest.mark.parametrize(
    ("index_name", "table"),
    [
        ("uq_team_members_one_active_team", "team_members"),
        ("uq_challenges_one_open_per_team", "challenges"),
    ],
)
def test_partial_unique_indexes_exist(
    engine: Engine, index_name: str, table: str
) -> None:
    with engine.connect() as conn:
        definition = conn.execute(
            text(
                "select indexdef from pg_indexes "
                "where tablename = :table and indexname = :name"
            ),
            {"table": table, "name": index_name},
        ).scalar()
    assert definition is not None, f"{index_name} is missing"
    assert "UNIQUE" in definition
    assert "WHERE" in definition, "index must be partial, not a blanket unique"
