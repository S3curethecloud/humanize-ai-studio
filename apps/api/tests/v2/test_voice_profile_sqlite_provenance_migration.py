import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.v2.repositories.sqlite import (
    SQLiteVoiceProfileRepository,
)


def test_legacy_voice_profile_schema_migrates_to_provenance_contract(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy-voice.db"

    created_at = datetime(
        2026,
        8,
        1,
        12,
        0,
        tzinfo=UTC,
    )
    updated_at = datetime(
        2026,
        8,
        2,
        12,
        0,
        tzinfo=UTC,
    )

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE voice_profiles (
                profile_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                created_by_user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                formality TEXT NOT NULL,
                sentence_length TEXT NOT NULL,
                directness TEXT NOT NULL,
                warmth TEXT NOT NULL,
                concision TEXT NOT NULL,
                first_person_frequency TEXT NOT NULL,
                contraction_preference TEXT NOT NULL,
                transition_style TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE voice_source_samples (
                sample_id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                text TEXT NOT NULL,
                label TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

        connection.execute(
            """
            INSERT INTO voice_profiles (
                profile_id,
                workspace_id,
                created_by_user_id,
                name,
                description,
                status,
                formality,
                sentence_length,
                directness,
                warmth,
                concision,
                first_person_frequency,
                contraction_preference,
                transition_style,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                "voice_legacy",
                "workspace_legacy",
                "user_legacy",
                "Legacy Voice",
                "Created before provenance support.",
                "active",
                "balanced",
                "mixed",
                "balanced",
                "balanced",
                "balanced",
                "moderate",
                "mixed",
                "natural",
                created_at.isoformat(),
                updated_at.isoformat(),
            ),
        )

        # Insert in reverse order deliberately. The old repository
        # reconstructed samples by created_at, sample_id rather than
        # physical insertion order.
        connection.execute(
            """
            INSERT INTO voice_source_samples (
                sample_id,
                profile_id,
                text,
                label,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "sample_2",
                "voice_legacy",
                "Second legacy sample.",
                "Second",
                datetime(
                    2026,
                    8,
                    1,
                    12,
                    2,
                    tzinfo=UTC,
                ).isoformat(),
            ),
        )

        connection.execute(
            """
            INSERT INTO voice_source_samples (
                sample_id,
                profile_id,
                text,
                label,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "sample_1",
                "voice_legacy",
                "First legacy sample.",
                "First",
                datetime(
                    2026,
                    8,
                    1,
                    12,
                    1,
                    tzinfo=UTC,
                ).isoformat(),
            ),
        )

    repository = SQLiteVoiceProfileRepository(database_path)

    profile = repository.get("voice_legacy")

    assert profile is not None
    assert profile.analysis_state.value == "never_analyzed"
    assert profile.analysis_provenance is None

    assert tuple(sample.sample_id for sample in profile.source_samples) == (
        "sample_1",
        "sample_2",
    )

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        profile_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(voice_profiles)").fetchall()
        }

        assert {
            "analysis_state",
            "analysis_analyzer_version",
            "analysis_analyzed_at",
            "analysis_source_sample_ids",
            "analysis_source_fingerprint",
            "analysis_sample_count",
            "analysis_sufficiency",
            "analysis_consistency",
        }.issubset(profile_columns)

        sample_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(voice_source_samples)").fetchall()
        }

        assert "sample_position" in sample_columns

        rows = connection.execute(
            """
            SELECT
                sample_id,
                sample_position
            FROM voice_source_samples
            WHERE profile_id = ?
            ORDER BY sample_position
            """,
            ("voice_legacy",),
        ).fetchall()

    assert [
        (
            row["sample_id"],
            row["sample_position"],
        )
        for row in rows
    ] == [
        ("sample_1", 0),
        ("sample_2", 1),
    ]
