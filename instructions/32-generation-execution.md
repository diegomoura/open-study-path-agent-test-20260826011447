# Efficient curriculum generation execution

Apply this contract during initial curriculum generation and later rolling materialization. It governs repository execution; pedagogical and integration requirements remain in the phase-specific instructions.

## Connector-first execution

When connected repository tools already provide file, branch, commit, pull-request, check, job, log and artifact access, use them as the authoritative path.

Do not attempt `gh`, `git clone`, `curl`, raw GitHub URLs or unauthenticated network access merely to duplicate an available connector operation. Do not begin with shell authentication probes when the repository connector is already available. A failed local command is not useful evidence about connector access.

A local checkout is optional acceleration, not a prerequisite. When command execution, DNS or package installation is unavailable, stop probing that unavailable path and continue through the connector and inherited GitHub Actions.

Read reusable slide assets from the instance repository. Do not download templates from the canonical repository during an instance operation; inherited files are already versioned locally.

Do not use fixed `sleep` loops to poll checks. Re-read the workflow or pull request through the connector with bounded attempts. A queued or in-progress check is a pending technical state, not curriculum success and not a learner decision.

## Capability preflight

Perform one bounded preflight before authoring:

1. confirm repository identity and instance mode through repository files;
2. confirm connector read and write capabilities without invoking a local CLI;
3. inspect Python, Node and pinned dependencies only when local validation is actually available;
4. choose one execution path and do not alternate repeatedly between connector, shell and unauthenticated network attempts.

The curriculum agent does not install Chromium or Mermaid. When the render toolchain is unavailable locally, use the CI render handoff.

## Build the complete diff before publishing

1. Read the active instance configuration, approved intake, diagnostic summary, roadmap, templates and validators.
2. Assemble the complete allowed phase diff in memory or an isolated workspace.
3. Finish every selected topic contract, lesson, assessment, review, semantic slide source and Mermaid source before the first repository write.
4. Calculate review fingerprints in one deterministic pass after authored files are final.
5. Open the pull request only after the complete initial diff exists on its branch.

Do not publish topics, modules, diagrams, rubrics, forms or review files one at a time while the operation is incomplete.

## Batched GitHub writes

For an operation that changes more than three files, use the Git Data API as one batch:

1. create every required blob;
2. create one tree from the branch base;
3. create one coherent commit;
4. move the branch with one `update_ref` call.

Use `create_blob`, `create_tree`, `create_commit` and `update_ref` rather than the Contents API for a multi-file operation. The Contents API is acceptable only for up to three isolated files or a focused correction.

Prefer one authoring commit. Use additional commits only for focused corrections discovered by independent review or CI; never create one commit per generated file, diagram, PDF or refreshed fingerprint.

If a branch was accidentally built through dozens of serial commits, reconstruct its final tree as one commit on top of the pull-request base and force-update the operation branch before merge.

Every intermediate and final commit must respect the phase's allowed-diff contract.

## Slide authoring boundary

The authoring pass creates only lightweight, reviewable sources:

```text
study/slides/TOPIC-000/
  index.html
  slides.css
  diagrams/*.mmd
```

Do not author `slides.js`, `slides.zip`, PNG diagrams or complete-slide images. Do not place a Mermaid runtime in learner artifacts. The generated SVG, PDF and render metadata are deterministic build outputs.

A normal 45–90 minute lesson derives 12–24 topic-specific slides according to its estimated effort. The deck must preserve required concepts, at least two worked examples, outcome coverage and the real explanatory depth of the lesson. A fixed ten-slide shell or generic filler does not satisfy the contract.

## Local validation when available

When a usable local environment already exists, run the lightweight suite before the first push:

```text
python scripts/validate_template.py all
python scripts/validate_intake_resolution.py
python scripts/validate_guided_lifecycle.py
python scripts/test_review_framework.py
python scripts/validate_review_framework.py
python scripts/test_instance_operation_scope.py
python scripts/validate_instance_operation_scope.py
python scripts/validate_generation_efficiency.py
python scripts/test_generation_terminal_state.py
python scripts/test_curriculum_placeholder_detection.py
python scripts/test_study_slides.py
python scripts/validate_study_slides.py
python scripts/validate_curriculum_safe.py
```

Never run `scripts/validate_curriculum.py` directly for learner content. The safe validator is the active contract.

When the pinned renderer dependencies are already available, the repository owner may additionally run:

```text
node scripts/render_study_slides.mjs
node scripts/render_study_slides.mjs --check
```

The curriculum agent must not install Chromium in chat. GitHub Actions is the final rendering environment and final confirmation, not the primary trial-and-error linter.

## CI render handoff

A runtime without local Chromium or Mermaid CLI may open the draft pull request after all pedagogical artifacts, semantic slide sources and both specialized reviews are complete.

The inherited workflow installs the pinned renderer, converts every `diagrams/*.mmd` file to static SVG, blocks external requests, checks slide overflow, renders one 1280×720 PDF page per slide and compares the result with committed artifacts.

When generated SVGs, `slides.pdf` or `slides.meta.json` are missing or stale, the workflow uploads the internal artifact `study-slide-render-output` containing only those generated paths under `.open-study-path/rendered-slides/`.

Download that workflow artifact through the GitHub connector, visually inspect the PDFs, add all generated SVG/PDF/metadata files to the existing branch in one batched commit, refresh affected review fingerprints once and rerun current-head checks.

The artifact is an internal transfer mechanism with short retention. It is never a learner resource. Do not attach it to the learner response and do not ask the learner to build or print slides manually.

## Independent review before final validation

After authoring, run specialized reviews in this order:

1. curriculum architecture through `instructions/35-review-curriculum.md`;
2. complete lesson, practice and assessment through `instructions/36-review-course-content.md`;
3. derived visual explanation through `instructions/37-review-study-slides.md`;
4. static SVG and PDF rendering validation;
5. `instructions/04-review-generated-artifacts.md` using the phase review profile.

Create or update the shared review only after actively checking the complete operation output. Cover every generated path changed by the pull request with current SHA-256 evidence. Correct blocking findings before approval.

## Immutable infrastructure in instance mode

During curriculum generation or materialization, never modify reusable infrastructure, even temporarily:

- `AGENTS.md`;
- `.github/workflows/`;
- `scripts/`;
- `instructions/`;
- `templates/`;
- `schemas/`;
- reusable `docs/`.

A canonical defect belongs in a separate template change and migration. Do not change a validator to make generated content pass. `scripts/validate_instance_operation_scope.py` rejects mixed curriculum and infrastructure changes.

## Failure handling

When CI fails:

1. inspect the exact failed step and log once;
2. resolve the complete deterministic failure class;
3. correct only allowed operation files;
4. rerun every affected specialized review;
5. batch the correction and refresh fingerprints once;
6. wait for checks on the new unchanged head.

A failed locator, fingerprint, schema, path, placeholder, render, link, integration-plan or review-coverage check is internal correction work. It is not a learner blocker.

Batch every failure of the same deterministic class before the next remote run. Do not add instrumentation commits or modify repository infrastructure to diagnose learner content.

After a second remote failure, stop speculative edits and inspect the exact current log before another push.

## Final current-head read-back

Apply `scripts/generation_terminal_state.py` before composing the response. The expected head SHA, pull-request state, required checks and unresolved-thread state must come from one final read-back.

The resolver may return:

- `correct_and_revalidate` for failed editorial or deterministic checks;
- `wait_and_reread` for queued or in-progress checks;
- `merge_current_head` for a green open pull request;
- `refresh_current_state` when the head moved;
- `owner_action_required` only for a concrete material decision;
- `technical_blocked` only when safe execution is genuinely unavailable;
- `success` only after merge confirmation.

Never say that the trail is generated while the pull request remains open. Never describe an auto-correctable technical failure as the final result.

After merge, fetch the pull request again and read persisted instance state from the default branch. If the pull request merged between observations, report the merged result rather than an earlier pending state.

## Terminal condition

The operation is complete only when the current unchanged head has:

- an allowed, coherent diff;
- a bounded commit history;
- complete curriculum, course-content and study-slide reviews;
- current static SVG diagrams, `slides.pdf` and `slides.meta.json` for every materialized topic;
- direct learner-facing PDF links with no ZIP/HTML instructions;
- approved shared review coverage;
- passing required checks;
- a mergeable pull request with no unresolved review thread;
- no pedagogical or integration-policy decision requiring owner input.

At that point, do not perform further research, regenerate content or rerun unchanged checks. Merge according to policy, perform the final read-back and return the learner-facing completion response.

## Diagnostic artifacts

Logs and workflow artifacts are internal debugging aids. Do not attach or list them as primary learner artifacts after success. Mention one only when the final state remains genuinely blocked and the owner must inspect it to make a concrete decision.
