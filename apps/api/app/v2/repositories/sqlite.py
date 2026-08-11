from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.v2.domain.models import (
    RewriteHistoryRecord,
    RewriteRecordStatus,
    UserRecord,
    VoiceAnalysisConsistency,
    VoiceAnalysisProvenance,
    VoiceAnalysisState,
    VoiceAnalysisSufficiency,
    VoiceConcision,
    VoiceContractionPreference,
    VoiceDirectness,
    VoiceFirstPersonFrequency,
    VoiceFormality,
    VoiceProfileRecord,
    VoiceProfileStatus,
    VoiceRewriteAnalysisSnapshot,
    VoiceSentenceLength,
    VoiceSourceSample,
    VoiceStyleAttributes,
    VoiceTransitionStyle,
    VoiceWarmth,
    WorkspaceMembership,
    WorkspaceRecord,
    WorkspaceRole,
)


def _connect(
    database_path: str | Path,
) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(
    database_path: str | Path,
) -> None:
    with _connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_by_user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (
                    created_by_user_id
                )
                REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS memberships (
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (
                    workspace_id,
                    user_id
                ),
                FOREIGN KEY (
                    workspace_id
                )
                REFERENCES workspaces(workspace_id),
                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS rewrite_history (
                rewrite_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                source_text TEXT NOT NULL,
                rewritten_text TEXT NOT NULL,
                document_type TEXT NOT NULL,
                audience TEXT NOT NULL,
                tone TEXT NOT NULL,
                intensity TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                voice_profile_id TEXT,
                voice_guidance_version TEXT,
                voice_analysis_snapshot TEXT,
                fallback_used INTEGER NOT NULL,
                verification_decision TEXT NOT NULL,
                editorial_quality_decision TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (
                    workspace_id
                )
                REFERENCES workspaces(workspace_id),
                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS
                idx_rewrite_history_workspace_created
            ON rewrite_history (
                workspace_id,
                created_at DESC
            );

            CREATE TABLE IF NOT EXISTS voice_profiles (
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
                analysis_state TEXT NOT NULL DEFAULT 'never_analyzed',
                analysis_analyzer_version TEXT,
                analysis_analyzed_at TEXT,
                analysis_source_sample_ids TEXT,
                analysis_source_fingerprint TEXT,
                analysis_sample_count INTEGER,
                analysis_sufficiency TEXT,
                analysis_consistency TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (
                    workspace_id
                )
                REFERENCES workspaces(workspace_id),
                FOREIGN KEY (
                    created_by_user_id
                )
                REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS voice_source_samples (
                sample_id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                text TEXT NOT NULL,
                label TEXT,
                sample_position INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (
                    profile_id
                )
                REFERENCES voice_profiles(profile_id)
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_voice_profiles_workspace_updated
            ON voice_profiles (
                workspace_id,
                updated_at DESC
            );

            CREATE INDEX IF NOT EXISTS
                idx_voice_samples_profile
            ON voice_source_samples (
                profile_id,
                created_at
            );
            """
        )

        rewrite_history_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(rewrite_history)").fetchall()
        }

        if "voice_profile_id" not in rewrite_history_columns:
            connection.execute("ALTER TABLE rewrite_history ADD COLUMN voice_profile_id TEXT")

        if "voice_guidance_version" not in rewrite_history_columns:
            connection.execute("ALTER TABLE rewrite_history ADD COLUMN voice_guidance_version TEXT")

        if "voice_analysis_snapshot" not in rewrite_history_columns:
            connection.execute(
                "ALTER TABLE rewrite_history ADD COLUMN voice_analysis_snapshot TEXT"
            )

        voice_profile_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(voice_profiles)").fetchall()
        }

        profile_migrations = (
            (
                "analysis_state",
                "ALTER TABLE voice_profiles "
                "ADD COLUMN analysis_state TEXT "
                "NOT NULL DEFAULT 'never_analyzed'",
            ),
            (
                "analysis_analyzer_version",
                "ALTER TABLE voice_profiles ADD COLUMN analysis_analyzer_version TEXT",
            ),
            (
                "analysis_analyzed_at",
                "ALTER TABLE voice_profiles ADD COLUMN analysis_analyzed_at TEXT",
            ),
            (
                "analysis_source_sample_ids",
                "ALTER TABLE voice_profiles ADD COLUMN analysis_source_sample_ids TEXT",
            ),
            (
                "analysis_source_fingerprint",
                "ALTER TABLE voice_profiles ADD COLUMN analysis_source_fingerprint TEXT",
            ),
            (
                "analysis_sample_count",
                "ALTER TABLE voice_profiles ADD COLUMN analysis_sample_count INTEGER",
            ),
            (
                "analysis_sufficiency",
                "ALTER TABLE voice_profiles ADD COLUMN analysis_sufficiency TEXT",
            ),
            (
                "analysis_consistency",
                "ALTER TABLE voice_profiles ADD COLUMN analysis_consistency TEXT",
            ),
        )

        for column_name, statement in profile_migrations:
            if column_name not in voice_profile_columns:
                connection.execute(statement)

        voice_sample_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(voice_source_samples)").fetchall()
        }

        if "sample_position" not in voice_sample_columns:
            connection.execute(
                "ALTER TABLE voice_source_samples ADD COLUMN sample_position INTEGER"
            )

            rows = connection.execute(
                """
                SELECT
                    profile_id,
                    sample_id
                FROM voice_source_samples
                ORDER BY
                    profile_id,
                    created_at,
                    sample_id
                """
            ).fetchall()

            positions: dict[str, int] = {}

            for row in rows:
                profile_id = row["profile_id"]
                position = positions.get(profile_id, 0)

                connection.execute(
                    """
                    UPDATE voice_source_samples
                    SET sample_position = ?
                    WHERE sample_id = ?
                    """,
                    (
                        position,
                        row["sample_id"],
                    ),
                )

                positions[profile_id] = position + 1


class SQLiteUserRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        user: UserRecord,
    ) -> UserRecord:
        with _connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO users (
                    user_id,
                    email,
                    display_name,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.email,
                    user.display_name,
                    user.created_at.isoformat(),
                ),
            )

        return user

    def get(
        self,
        user_id: str,
    ) -> UserRecord | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    email,
                    display_name,
                    created_at
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return UserRecord(
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteWorkspaceRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        workspace: WorkspaceRecord,
    ) -> WorkspaceRecord:
        with _connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO workspaces (
                    workspace_id,
                    name,
                    created_by_user_id,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    workspace.workspace_id,
                    workspace.name,
                    workspace.created_by_user_id,
                    workspace.created_at.isoformat(),
                ),
            )

        return workspace

    def get(
        self,
        workspace_id: str,
    ) -> WorkspaceRecord | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    workspace_id,
                    name,
                    created_by_user_id,
                    created_at
                FROM workspaces
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        if row is None:
            return None

        return WorkspaceRecord(
            workspace_id=row["workspace_id"],
            name=row["name"],
            created_by_user_id=(row["created_by_user_id"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteMembershipRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership:
        with _connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO memberships (
                    workspace_id,
                    user_id,
                    role,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    membership.workspace_id,
                    membership.user_id,
                    membership.role.value,
                    membership.created_at.isoformat(),
                ),
            )

        return membership

    def get(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceMembership | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    workspace_id,
                    user_id,
                    role,
                    created_at
                FROM memberships
                WHERE workspace_id = ?
                  AND user_id = ?
                """,
                (
                    workspace_id,
                    user_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return WorkspaceMembership(
            workspace_id=row["workspace_id"],
            user_id=row["user_id"],
            role=WorkspaceRole(row["role"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteRewriteHistoryRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        record: RewriteHistoryRecord,
    ) -> RewriteHistoryRecord:
        with _connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO rewrite_history (
                    rewrite_id,
                    workspace_id,
                    user_id,
                    trace_id,
                    source_text,
                    rewritten_text,
                    document_type,
                    audience,
                    tone,
                    intensity,
                    provider_name,
                    model_name,
                    prompt_version,
                    voice_profile_id,
                    voice_guidance_version,
                    voice_analysis_snapshot,
                    fallback_used,
                    verification_decision,
                    editorial_quality_decision,
                    status,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    record.rewrite_id,
                    record.workspace_id,
                    record.user_id,
                    record.trace_id,
                    record.source_text,
                    record.rewritten_text,
                    record.document_type,
                    record.audience,
                    record.tone,
                    record.intensity,
                    record.provider_name,
                    record.model_name,
                    record.prompt_version,
                    record.voice_profile_id,
                    record.voice_guidance_version,
                    (
                        json.dumps(
                            record.voice_analysis_snapshot.model_dump(mode="json"),
                            separators=(",", ":"),
                        )
                        if record.voice_analysis_snapshot is not None
                        else None
                    ),
                    int(record.fallback_used),
                    record.verification_decision,
                    (record.editorial_quality_decision),
                    record.status.value,
                    record.created_at.isoformat(),
                ),
            )

        return record

    def get(
        self,
        rewrite_id: str,
    ) -> RewriteHistoryRecord | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM rewrite_history
                WHERE rewrite_id = ?
                """,
                (rewrite_id,),
            ).fetchone()

        if row is None:
            return None

        return self._to_record(row)

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 50,
    ) -> tuple[RewriteHistoryRecord, ...]:
        with _connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM rewrite_history
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    workspace_id,
                    limit,
                ),
            ).fetchall()

        return tuple(self._to_record(row) for row in rows)

    def _to_record(
        self,
        row: sqlite3.Row,
    ) -> RewriteHistoryRecord:
        return RewriteHistoryRecord(
            rewrite_id=row["rewrite_id"],
            workspace_id=row["workspace_id"],
            user_id=row["user_id"],
            trace_id=row["trace_id"],
            source_text=row["source_text"],
            rewritten_text=row["rewritten_text"],
            document_type=row["document_type"],
            audience=row["audience"],
            tone=row["tone"],
            intensity=row["intensity"],
            provider_name=row["provider_name"],
            model_name=row["model_name"],
            prompt_version=row["prompt_version"],
            voice_profile_id=row["voice_profile_id"],
            voice_guidance_version=row["voice_guidance_version"],
            voice_analysis_snapshot=(
                VoiceRewriteAnalysisSnapshot.model_validate(
                    json.loads(row["voice_analysis_snapshot"])
                )
                if row["voice_analysis_snapshot"] is not None
                else None
            ),
            fallback_used=bool(row["fallback_used"]),
            verification_decision=(row["verification_decision"]),
            editorial_quality_decision=(row["editorial_quality_decision"]),
            status=RewriteRecordStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteVoiceProfileRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        profile: VoiceProfileRecord,
    ) -> VoiceProfileRecord:
        with _connect(self._database_path) as connection:
            existing = connection.execute(
                """
                SELECT profile_id
                FROM voice_profiles
                WHERE profile_id = ?
                """,
                (profile.profile_id,),
            ).fetchone()

            if existing is not None:
                raise ValueError(f"Voice profile already exists: {profile.profile_id}")

            self._insert_profile(
                connection,
                profile,
            )
            self._insert_samples(
                connection,
                profile,
            )

        return profile

    def get(
        self,
        profile_id: str,
    ) -> VoiceProfileRecord | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM voice_profiles
                WHERE profile_id = ?
                """,
                (profile_id,),
            ).fetchone()

            if row is None:
                return None

            return self._to_record(
                connection,
                row,
            )

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        profile_status: VoiceProfileStatus | None = None,
        limit: int = 50,
    ) -> tuple[VoiceProfileRecord, ...]:
        with _connect(self._database_path) as connection:
            if profile_status is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM voice_profiles
                    WHERE workspace_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (
                        workspace_id,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM voice_profiles
                    WHERE workspace_id = ?
                      AND status = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (
                        workspace_id,
                        profile_status.value,
                        limit,
                    ),
                ).fetchall()

            return tuple(
                self._to_record(
                    connection,
                    row,
                )
                for row in rows
            )

    def update(
        self,
        profile: VoiceProfileRecord,
    ) -> VoiceProfileRecord:
        with _connect(self._database_path) as connection:
            existing = connection.execute(
                """
                SELECT
                    profile_id,
                    workspace_id
                FROM voice_profiles
                WHERE profile_id = ?
                """,
                (profile.profile_id,),
            ).fetchone()

            if existing is None:
                raise ValueError(f"Unknown voice profile: {profile.profile_id}")

            if existing["workspace_id"] != profile.workspace_id:
                raise ValueError("Voice profile workspace cannot be changed.")

            attributes = profile.style_attributes
            provenance = profile.analysis_provenance

            connection.execute(
                """
                UPDATE voice_profiles
                SET
                    workspace_id = ?,
                    created_by_user_id = ?,
                    name = ?,
                    description = ?,
                    status = ?,
                    formality = ?,
                    sentence_length = ?,
                    directness = ?,
                    warmth = ?,
                    concision = ?,
                    first_person_frequency = ?,
                    contraction_preference = ?,
                    transition_style = ?,
                    analysis_state = ?,
                    analysis_analyzer_version = ?,
                    analysis_analyzed_at = ?,
                    analysis_source_sample_ids = ?,
                    analysis_source_fingerprint = ?,
                    analysis_sample_count = ?,
                    analysis_sufficiency = ?,
                    analysis_consistency = ?,
                    created_at = ?,
                    updated_at = ?
                WHERE profile_id = ?
                """,
                (
                    profile.workspace_id,
                    profile.created_by_user_id,
                    profile.name,
                    profile.description,
                    profile.status.value,
                    attributes.formality.value,
                    attributes.sentence_length.value,
                    attributes.directness.value,
                    attributes.warmth.value,
                    attributes.concision.value,
                    attributes.first_person_frequency.value,
                    attributes.contraction_preference.value,
                    attributes.transition_style.value,
                    profile.analysis_state.value,
                    (provenance.analyzer_version if provenance is not None else None),
                    (provenance.analyzed_at.isoformat() if provenance is not None else None),
                    (json.dumps(provenance.source_sample_ids) if provenance is not None else None),
                    (provenance.source_fingerprint if provenance is not None else None),
                    (provenance.sample_count if provenance is not None else None),
                    (provenance.sufficiency.value if provenance is not None else None),
                    (provenance.consistency.value if provenance is not None else None),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                    profile.profile_id,
                ),
            )

            connection.execute(
                """
                DELETE FROM voice_source_samples
                WHERE profile_id = ?
                """,
                (profile.profile_id,),
            )

            self._insert_samples(
                connection,
                profile,
            )

        return profile

    def _insert_profile(
        self,
        connection: sqlite3.Connection,
        profile: VoiceProfileRecord,
    ) -> None:
        attributes = profile.style_attributes
        provenance = profile.analysis_provenance

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
                analysis_state,
                analysis_analyzer_version,
                analysis_analyzed_at,
                analysis_source_sample_ids,
                analysis_source_fingerprint,
                analysis_sample_count,
                analysis_sufficiency,
                analysis_consistency,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                profile.profile_id,
                profile.workspace_id,
                profile.created_by_user_id,
                profile.name,
                profile.description,
                profile.status.value,
                attributes.formality.value,
                attributes.sentence_length.value,
                attributes.directness.value,
                attributes.warmth.value,
                attributes.concision.value,
                attributes.first_person_frequency.value,
                attributes.contraction_preference.value,
                attributes.transition_style.value,
                profile.analysis_state.value,
                (provenance.analyzer_version if provenance is not None else None),
                (provenance.analyzed_at.isoformat() if provenance is not None else None),
                (json.dumps(provenance.source_sample_ids) if provenance is not None else None),
                (provenance.source_fingerprint if provenance is not None else None),
                (provenance.sample_count if provenance is not None else None),
                (provenance.sufficiency.value if provenance is not None else None),
                (provenance.consistency.value if provenance is not None else None),
                profile.created_at.isoformat(),
                profile.updated_at.isoformat(),
            ),
        )

    def _insert_samples(
        self,
        connection: sqlite3.Connection,
        profile: VoiceProfileRecord,
    ) -> None:
        connection.executemany(
            """
            INSERT INTO voice_source_samples (
                sample_id,
                profile_id,
                text,
                label,
                sample_position,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    sample.sample_id,
                    profile.profile_id,
                    sample.text,
                    sample.label,
                    position,
                    sample.created_at.isoformat(),
                )
                for position, sample in enumerate(profile.source_samples)
            ),
        )

    def _to_record(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> VoiceProfileRecord:
        sample_rows = connection.execute(
            """
            SELECT
                sample_id,
                text,
                label,
                sample_position,
                created_at
            FROM voice_source_samples
            WHERE profile_id = ?
            ORDER BY sample_position, sample_id
            """,
            (row["profile_id"],),
        ).fetchall()

        samples = tuple(
            VoiceSourceSample(
                sample_id=sample["sample_id"],
                text=sample["text"],
                label=sample["label"],
                created_at=datetime.fromisoformat(sample["created_at"]),
            )
            for sample in sample_rows
        )

        attributes = VoiceStyleAttributes(
            formality=VoiceFormality(row["formality"]),
            sentence_length=VoiceSentenceLength(row["sentence_length"]),
            directness=VoiceDirectness(row["directness"]),
            warmth=VoiceWarmth(row["warmth"]),
            concision=VoiceConcision(row["concision"]),
            first_person_frequency=(VoiceFirstPersonFrequency(row["first_person_frequency"])),
            contraction_preference=(VoiceContractionPreference(row["contraction_preference"])),
            transition_style=VoiceTransitionStyle(row["transition_style"]),
        )

        provenance = None

        if row["analysis_analyzer_version"] is not None:
            provenance = VoiceAnalysisProvenance(
                analyzer_version=row["analysis_analyzer_version"],
                analyzed_at=datetime.fromisoformat(row["analysis_analyzed_at"]),
                source_sample_ids=tuple(json.loads(row["analysis_source_sample_ids"])),
                source_fingerprint=row["analysis_source_fingerprint"],
                sample_count=row["analysis_sample_count"],
                sufficiency=VoiceAnalysisSufficiency(row["analysis_sufficiency"]),
                consistency=VoiceAnalysisConsistency(row["analysis_consistency"]),
            )

        return VoiceProfileRecord(
            profile_id=row["profile_id"],
            workspace_id=row["workspace_id"],
            created_by_user_id=(row["created_by_user_id"]),
            name=row["name"],
            description=row["description"],
            status=VoiceProfileStatus(row["status"]),
            source_samples=samples,
            style_attributes=attributes,
            analysis_state=VoiceAnalysisState(row["analysis_state"]),
            analysis_provenance=provenance,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
