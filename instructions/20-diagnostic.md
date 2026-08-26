# Diagnostic

Run this phase only after intake has been imported and validated.

The diagnostic is a placement step, not a lesson, interview marathon or exhaustive exam. Its only purpose is to collect enough evidence to choose a responsible starting depth.

## Use existing evidence first

Before asking anything, read the intake, prior evidence and any existing diagnostic summary. Do not ask for facts that are already reliable. Cover only the dimensions still needed for placement:

- prior exposure and retention;
- conceptual understanding;
- practical application;
- one likely misconception or boundary case.

Do not test every possible curriculum topic. Remaining gaps belong in the learning path.

## Question budget

For a learner declared as `none` or `beginner`:

- target 3 to 5 questions;
- hard maximum of 7 questions.

For a learner declared as `intermediate` or `advanced`:

- target 4 to 7 questions;
- hard maximum of 10 questions.

Exceed the hard maximum only when the owner explicitly requests a comprehensive assessment. Record `owner_requested_comprehensive` in the diagnostic summary. Never continue merely because more questions could produce more detail.

At the first turn, briefly state the expected maximum and ask the first question. Stop earlier when evidence is sufficient. If the hard maximum is reached with uncertainty remaining, choose a conservative starting depth and record `evidence_sufficiency: limited` instead of asking indefinitely.

## Interaction style

- Ask exactly one short question or practical task at a time.
- Do not present the entire questionnaire at once.
- Do not praise, restate or interpret every answer before asking the next question.
- Avoid mini-lessons during assessment. Correct a misconception only when the correction is needed to continue, using at most two short sentences.
- Ask the next question directly when no clarification is required.
- Do not send a separate transition message such as “there is enough evidence; I will register it”. Once evidence is sufficient, perform the repository operation and send only the guided completion response.
- Do not generate the curriculum during this phase.

## Stopping rule

Stop as soon as all of the following are true:

1. a starting depth can be selected with responsible confidence;
2. at least one conceptual and one applied signal are available, unless reliable prior evidence already covers one of them;
3. any remaining uncertainty can safely become a curriculum topic rather than another placement question.

Repeated answers that confirm the same pattern do not justify additional questions.

## Output

Create `state/diagnostic-summary.json` from `templates/state/diagnostic-summary.json` and validate it against `schemas/diagnostic-summary.schema.json`.

Record:

- question count and budget;
- evidence sufficiency;
- confirmed competencies;
- knowledge gaps;
- misconceptions only when actually observed;
- required prerequisites;
- recommended starting depth;
- material caveats.

Do not persist the raw transcript, unnecessary personal details or conversational filler. Update `.open-study-path/instance.yml` with `status.diagnostic_complete: true`.

## Independent diagnostic review

After the authoring pass, run `instructions/04-review-generated-artifacts.md` with the `diagnostic` profile.

The diagnostic reviewer must reconstruct each placement conclusion from the bounded evidence recorded in the summary. It must verify that:

- the starting depth is supported rather than guessed;
- transferable experience was not treated as subject mastery;
- observed gaps and misconceptions were not invented;
- the question budget and stopping rule were respected;
- raw answers and unnecessary personal data were not persisted;
- the next phase is generation, not additional teaching disguised as diagnosis.

Store the review separately under `state/reviews/<diagnostic-operation>.yml`. The manifest keeps this in `review_outputs`; it is audit evidence rather than a diagnostic-domain output.

## Diagnostic pull-request policy

Read `workflow.diagnostic_merge_policy` from `.open-study-path/instance.yml`. If it is missing, use `manual`.

The diagnostic domain output may change only:

- `.open-study-path/instance.yml`;
- `state/diagnostic-summary.json`.

The pull request also includes exactly one diagnostic review artifact under `state/reviews/`. No other generated path is allowed.

For `auto_when_unambiguous`, self-review the diff and merge after required checks pass only when:

- the diagnostic summary validates;
- the question budget was respected or has an allowed explicit exception;
- the domain diff contains only the two files above;
- the diagnostic review covers both current files with exact SHA-256 fingerprints;
- every diagnostic review check passed and no blocking finding remains;
- no raw transcript or unnecessary personal data was persisted;
- the starting depth is supported by the recorded evidence;
- no unresolved contradiction requires owner review.

Do not attempt to formally approve a PR authored by the same account. Verification against the phase contract, the separate diagnostic reviewer pass and successful CI constitute the automated review before merge.

## Completion

Follow `instructions/phase-completion.md`. By default, report only the starting depth, artifact link, merge state and next command. Do not list all competencies and gaps in chat unless the owner asks for an audit.

Guide the owner to the roadmap-proposal suboperation with:

`Gere uma proposta de trilha com base no intake e no diagnóstico. Abra um pull request e não publique tarefas ainda.`

This wording is authored by the system itself. It authorizes the normal proposal workflow: create a draft as a temporary work area, run the independent curriculum review, correct findings, validate, mark ready and merge under `agent_review_then_merge`. It does not ask the learner to review the pull request and does not request that it remain open. `Não publique tarefas ainda` restricts only the later publication operation.
