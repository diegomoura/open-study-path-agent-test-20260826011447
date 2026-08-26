# Etapa 9d — a real text-field form for answering the diagnostic

Status: **implemented**, requested after Etapa 9c's single-form-batch redesign
(`docs/claude-agent-pilot-etapa9c-diagnostic-single-form.md`): typing a reply
to five questions in one raw GitHub comment box is worse UX than real text
fields per question.

## Why this needed its own workflow

`intake` already has a real Issue Form
(`.github/ISSUE_TEMPLATE/create-study-path.yml`). The reason `diagnostic`
couldn't just reuse that pattern directly is that GitHub Issue Forms only
ever **create a new issue** -- there is no GitHub mechanism for a form to
post into an *existing* issue's comment thread. The diagnostic session,
though, is identified by its own issue (carrying the `diagnostic:in-progress`
label), and `agent-pilot-diagnostic.yml` only ever reads that one issue's
thread (`scripts/build_diagnostic_context.py`). A learner filling in a form
produces a second, unrelated issue that has to be resolved back to the first.

## The bridge

`.github/ISSUE_TEMPLATE/diagnostic-answer.yml` is a generic, reusable form:
a `session_issue_number` field plus ten optional `answer_N` text areas (the
Etapa 9c question budget's hard maximum). Turn 1's question-batch comment
now includes a direct pre-filled link
(`.../issues/new?template=diagnostic-answer.yml&session_issue_number=<N>`)
alongside the plain question list -- both channels remain available; nothing
requires the form.

Submitting it creates a new issue labeled `diagnostic:answer`. A new,
narrow workflow, `.github/workflows/agent-pilot-diagnostic-answer-bridge.yml`
(triggered by `issues: opened`, guarded to that label), resolves it:

1. `scripts/diagnostic_answer_resolution.py` (pure, offline-testable)
   extracts the session issue number and every non-empty `answer_N` field
   from the rendered body, and classifies the submission -- rejecting a pull
   request, an already-imported submission, a missing/unparseable session
   number, a session issue that doesn't exist or isn't
   `diagnostic:in-progress`, or an empty answer set. This is the same
   "deterministic code decides identity, the model never does" split
   `scripts/intake_resolution.py` established for intake.
2. `scripts/bridge_diagnostic_answer.py` does the only I/O: fetch the answer
   issue, fetch the referenced session issue to check its labels, and either
   -- if accepted -- repost the answers as one plain numbered comment on the
   *session* issue, label the answer issue `diagnostic:answer-imported`, and
   close it; or -- if rejected -- post an explanatory comment on the answer
   issue itself (which reason, in Portuguese) and leave it open, exactly like
   `intake`'s "return the form link, do not silently guess" posture for an
   ambiguous or absent candidate.

**No Anthropic API call happens in this bridge at all.** It is pure
deterministic GitHub glue code, zero LLM cost. By the time
`agent-pilot-diagnostic.yml`'s existing `issue_comment` trigger fires on the
session issue (because the bridge just posted a comment there), the
diagnostic author sees a perfectly ordinary comment -- there is no marker
distinguishing a form-originated answer from one typed by hand, and the
author does not need to know or care which channel was used.

## What changed elsewhere

- `instructions/20-diagnostic.md`'s Turn 1 description now mentions the form
  link.
- `scripts/build_agent_prompt.py`'s `AUTHOR_DIAGNOSTIC_NOTE` was rewritten to
  match Etapa 9c's actual two-turn design (it had drifted: it still described
  one-question-per-turn after Etapa 9c shipped, a real gap found while
  building this feature -- see "Bonus finding" below) and now tells the
  author to include the pre-filled link and to expect a form-originated reply
  to look identical to a typed one.
- `scripts/ensure_repository_labels.py`'s `REQUIRED_LABELS` gained
  `diagnostic:in-progress`, `diagnostic:answer` and
  `diagnostic:answer-imported`, so a fresh instance provisions all five
  labels (the two intake ones plus these three) the same automatic way.

## Bonus finding: Etapa 9c's author addendum had drifted

While updating `AUTHOR_DIAGNOSTIC_NOTE` for this form, it turned out the
addendum still told the author to "call post_issue_comment... with exactly
one short next question... never the whole remaining questionnaire" --
the literal opposite of Etapa 9c's redesign, which had only updated
`instructions/20-diagnostic.md` itself. The real dispatch that validated
Etapa 9c (docs/claude-agent-pilot-etapa9c-diagnostic-single-form.md) still
produced the correct single-form-batch behavior despite this, meaning the
model followed the more specific/recent instruction file over the stale
addendum -- but shipping two contradictory instructions in the same prompt
was fragile regardless of that one run's outcome. Fixed as part of this
change, not deferred.

## Testing

`scripts/test_diagnostic_answer_resolution.py` (13 cases) and
`scripts/test_bridge_diagnostic_answer.py` (3 cases, fake API) cover the
parsing/classification logic and the orchestration script's branches
(accepted, missing session number, session not found) entirely offline --
no real dispatch needed to validate the deterministic half. The one thing
only a real dispatch can confirm is that the pre-filled form link actually
round-trips end to end against a live GitHub Issue Form; that is Etapa 9d's
real-dispatch validation step, tracked separately from this commit.
