# Quality-Hardening Code Freeze

## Freeze boundary

The quality-hardening freeze applies after completion of Increment 8.

The frozen control surface includes:

- claim-integrity detection;
- qualification preservation;
- provider repair-call limit;
- useful rewrite-distance evaluation;
- intensity-specific structural requirements;
- deep-repair structural blueprint;
- structural-blueprint adherence validation;
- deterministic fallback behavior;
- evaluation corpus classifications;
- release thresholds;
- machine-readable release report;
- production release gate.

## Changes requiring explicit review

The following changes require an explicit control review and updated evidence:

- removing or weakening a claim-integrity rule;
- reducing qualification preservation;
- increasing the maximum provider-call count;
- lowering lexical or structural requirements;
- removing structural-blueprint validation;
- lowering release thresholds;
- excluding a failing case from the performance cohort without justification;
- converting a safety-control case into a passing case without preserving its
  original negative-test purpose;
- changing prompt behavior without increasing the prompt version;
- changing fallback semantics;
- changing production provider routing;
- changing the generated evaluation-report schema.

## Required evidence after frozen-control changes

Any approved frozen-control change must include:

1. updated tests;
2. updated deterministic corpus where applicable;
3. a regenerated evaluation report;
4. a passing complete repository gate;
5. a new production deployment;
6. readiness evidence;
7. production rewrite evidence;
8. an explicit change description in release documentation.

## Non-frozen work

The following may proceed as normal maintenance when they do not weaken the
frozen control surface:

- dependency updates;
- warning remediation;
- accessibility improvements;
- frontend presentation changes;
- observability improvements;
- performance optimization;
- documentation corrections;
- infrastructure reliability improvements;
- additional provider integrations that comply with the same release contract.
