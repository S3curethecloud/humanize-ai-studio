import {
  useCallback,
  useEffect,
  useState
} from "react";

import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

import {
  analyzeVoiceProfile,
  createVoiceProfile,
  listVoiceProfiles,
  type VoiceAnalysisEvidence,
  type VoiceProfile
} from "../api/voice";

interface VoiceDnaPageProps {
  accessContext: EnterpriseAccessContextState;
}

export default function VoiceDnaPage({
  accessContext
}: VoiceDnaPageProps) {
  const [profiles, setProfiles] =
    useState<VoiceProfile[]>([]);

  const [selectedProfileId, setSelectedProfileId] =
    useState<string | null>(null);

  const [analysis, setAnalysis] =
    useState<VoiceAnalysisEvidence | null>(null);

  const [name, setName] =
    useState("Primary Voice");

  const [description, setDescription] =
    useState("");

  const [sampleText, setSampleText] =
    useState("");

  const [message, setMessage] =
    useState<string | null>(null);

  const [busy, setBusy] =
    useState(false);

  const canUse =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null;

  const workspaceId =
    accessContext.workspaceId;

  const userId =
    accessContext.userId;

  const loadProfiles = useCallback(
    async () => {
      if (
        !canUse ||
        workspaceId === null ||
        userId === null
      ) {
        setProfiles([]);
        return;
      }

      try {
        const next = await listVoiceProfiles(
          workspaceId,
          userId
        );

        setProfiles(next);

        if (
          selectedProfileId === null &&
          next.length > 0
        ) {
          setSelectedProfileId(
            next[0].profile_id
          );
        }
      } catch (error) {
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load Voice DNA profiles."
        );
      }
    },
    [
      canUse,
      selectedProfileId,
      userId,
      workspaceId
    ]
  );

  useEffect(() => {
    void loadProfiles();
  }, [loadProfiles]);

  const selectedProfile =
    profiles.find(
      (profile) =>
        profile.profile_id ===
        selectedProfileId
    ) ?? null;

  async function handleCreate() {
    if (
      workspaceId === null ||
      userId === null
    ) {
      return;
    }

    if (
      !name.trim() ||
      !sampleText.trim()
    ) {
      setMessage(
        "Profile name and writing sample are required."
      );
      return;
    }

    setBusy(true);
    setMessage(
      "Creating governed Voice DNA profile."
    );

    try {
      const profile =
        await createVoiceProfile(
          workspaceId,
          userId,
          {
            name: name.trim(),
            description:
              description.trim(),
            sampleText:
              sampleText.trim()
          }
        );

      setSelectedProfileId(
        profile.profile_id
      );

      setAnalysis(null);

      await loadProfiles();

      setMessage(
        "Voice DNA profile created. Analyze it before using it for governed rewrite guidance."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to create Voice DNA profile."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleAnalyze() {
    if (
      workspaceId === null ||
      userId === null ||
      selectedProfile === null
    ) {
      return;
    }

    setBusy(true);
    setMessage(
      "Analyzing Voice DNA from the stored source sample."
    );

    try {
      const result =
        await analyzeVoiceProfile(
          workspaceId,
          userId,
          selectedProfile.profile_id
        );

      setAnalysis(result.evidence);

      await loadProfiles();

      setMessage(
        "Voice DNA analysis completed."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to analyze Voice DNA profile."
      );
    } finally {
      setBusy(false);
    }
  }

  if (!canUse) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>Voice DNA unavailable</h1>
            <p>
              Canonical workspace access context
              is required before Voice DNA can
              be read or managed.
            </p>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="enterprise-page">
      <section className="enterprise-analytics-hero">
        <div>
          <p className="enterprise-eyebrow">
            Work · Voice DNA
          </p>

          <h1>Governed Voice DNA</h1>

          <p className="enterprise-hero__description">
            Build workspace-scoped writing profiles
            from source samples and analyze their
            stylistic characteristics before they
            are used as rewrite guidance.
          </p>
        </div>
      </section>

      {message && (
        <section className="enterprise-analytics-state">
          <div>
            <p>{message}</p>
          </div>
        </section>
      )}

      <section className="enterprise-dashboard-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Profiles
            </p>
            <h2>Workspace voice profiles</h2>
          </div>
        </div>

        {profiles.length === 0 ? (
          <p>
            No Voice DNA profiles exist in this
            workspace yet.
          </p>
        ) : (
          <div className="enterprise-analytics-operation-grid">
            {profiles.map((profile) => (
              <button
                className="enterprise-analytics-operation"
                type="button"
                key={profile.profile_id}
                onClick={() => {
                  setSelectedProfileId(
                    profile.profile_id
                  );
                  setAnalysis(null);
                }}
              >
                <div className="enterprise-analytics-operation__header">
                  <span>{profile.name}</span>
                  <strong>
                    {profile.status}
                  </strong>
                </div>

                <dl>
                  <div>
                    <dt>Analysis</dt>
                    <dd>
                      {profile.analysis_state}
                    </dd>
                  </div>

                  <div>
                    <dt>Samples</dt>
                    <dd>
                      {
                        profile.source_samples
                          .length
                      }
                    </dd>
                  </div>
                </dl>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="enterprise-dashboard-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Create
            </p>
            <h2>New Voice DNA profile</h2>
          </div>
        </div>

        <div className="source-workspace">
          <label>
            Profile name
            <input
              value={name}
              onChange={(event) =>
                setName(event.target.value)
              }
              disabled={busy}
            />
          </label>

          <label>
            Description
            <input
              value={description}
              onChange={(event) =>
                setDescription(
                  event.target.value
                )
              }
              disabled={busy}
            />
          </label>

          <label>
            Writing sample
            <textarea
              value={sampleText}
              onChange={(event) =>
                setSampleText(
                  event.target.value
                )
              }
              rows={10}
              disabled={busy}
            />
          </label>

          <button
            type="button"
            className="enterprise-secondary-button"
            onClick={() =>
              void handleCreate()
            }
            disabled={busy}
          >
            Create Voice DNA profile
          </button>
        </div>
      </section>

      {selectedProfile && (
        <section className="enterprise-dashboard-section">
          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Selected profile
              </p>
              <h2>
                {selectedProfile.name}
              </h2>
            </div>

            <button
              type="button"
              className="enterprise-secondary-button"
              onClick={() =>
                void handleAnalyze()
              }
              disabled={
                busy ||
                selectedProfile.status !==
                  "active"
              }
            >
              Analyze Voice DNA
            </button>
          </div>

          <div className="enterprise-analytics-metric-grid">
            {Object.entries(
              selectedProfile.style_attributes
            ).map(([key, value]) => (
              <article
                className="enterprise-analytics-metric"
                key={key}
              >
                <span>
                  {key.replaceAll("_", " ")}
                </span>
                <strong>{value}</strong>
              </article>
            ))}
          </div>
        </section>
      )}

      {analysis && (
        <section className="enterprise-dashboard-section">
          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Analysis evidence
              </p>
              <h2>
                Voice characteristics
              </h2>
            </div>
          </div>

          <div className="enterprise-analytics-metric-grid">
            <article className="enterprise-analytics-metric">
              <span>Sufficiency</span>
              <strong>
                {analysis.sufficiency}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>Consistency</span>
              <strong>
                {
                  analysis
                    .sample_consistency
                    .classification
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>Words</span>
              <strong>
                {analysis.word_count}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>Sentences</span>
              <strong>
                {analysis.sentence_count}
              </strong>
            </article>
          </div>
        </section>
      )}
    </div>
  );
}
