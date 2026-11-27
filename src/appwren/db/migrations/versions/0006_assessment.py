"""Assessment and scoring: the question bank and scoring model in versions, assessments,
portfolio snapshots, and score snapshots (SCR-01 to SCR-10).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("ASM", "PSN")


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "questionnaire",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("definition", appwren.db.types.JsonType, nullable=False),
        sa.Column("published_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questionnaire")),
        sa.UniqueConstraint("version", name=op.f("uq_questionnaire_version")),
    )
    op.create_table(
        "scoring_model",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("definition", appwren.db.types.JsonType, nullable=False),
        sa.Column("published_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scoring_model")),
        sa.UniqueConstraint("version", name=op.f("uq_scoring_model_version")),
    )
    op.create_table(
        "portfolio_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("taken_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("taken_by", sa.Integer(), nullable=True),
        sa.Column("taken_by_name", sa.String(length=200), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["scoring_model.id"],
            name=op.f("fk_portfolio_snapshot_model_id_scoring_model"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolio_snapshot")),
        sa.UniqueConstraint("ref", name=op.f("uq_portfolio_snapshot_ref")),
    )
    op.create_table(
        "assessment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("questionnaire_id", sa.Integer(), nullable=False),
        sa.Column("answers", appwren.db.types.JsonType, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("assessed_by", sa.Integer(), nullable=True),
        sa.Column("assessed_by_name", sa.String(length=200), nullable=False),
        sa.Column("assessed_on", sa.Date(), nullable=False),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_assessment_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_id"],
            ["questionnaire.id"],
            name=op.f("fk_assessment_questionnaire_id_questionnaire"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment")),
        sa.UniqueConstraint("ref", name=op.f("uq_assessment_ref")),
    )
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.create_index("ix_assessment_application_id", ["application_id"], unique=False)

    op.create_table(
        "score_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("taken_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("profile_key", sa.String(length=40), nullable=False),
        sa.Column("bv", sa.Float(), nullable=True),
        sa.Column("th", sa.Float(), nullable=True),
        sa.Column("cb", sa.Float(), nullable=True),
        sa.Column("re", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("recommendation", sa.String(length=24), nullable=True),
        sa.Column("flags", appwren.db.types.JsonType, nullable=False),
        sa.Column("working", appwren.db.types.JsonType, nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_score_snapshot_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["scoring_model.id"],
            name=op.f("fk_score_snapshot_model_id_scoring_model"),
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_snapshot_id"],
            ["portfolio_snapshot.id"],
            name=op.f("fk_score_snapshot_portfolio_snapshot_id_portfolio_snapshot"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score_snapshot")),
        sa.UniqueConstraint(
            "application_id",
            "portfolio_snapshot_id",
            name=op.f("uq_score_snapshot_application_id_portfolio_snapshot_id"),
        ),
    )
    with op.batch_alter_table("score_snapshot", schema=None) as batch_op:
        batch_op.create_index("ix_score_snapshot_application_id", ["application_id"], unique=False)
        batch_op.create_index(
            "ix_score_snapshot_portfolio_snapshot_id", ["portfolio_snapshot_id"], unique=False
        )


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("score_snapshot", schema=None) as batch_op:
        batch_op.drop_index("ix_score_snapshot_portfolio_snapshot_id")
        batch_op.drop_index("ix_score_snapshot_application_id")

    op.drop_table("score_snapshot")
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.drop_index("ix_assessment_application_id")

    op.drop_table("assessment")
    op.drop_table("portfolio_snapshot")
    op.drop_table("scoring_model")
    op.drop_table("questionnaire")
