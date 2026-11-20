[Home](../README.md) > [DCR/CCR preparation](prep_dcr_ccr.md) > Prepacked sessions

# Prepacked sessions for pairwise comparisons

## When to use prepacked sessions

Use prepacked sessions when your study needs control over which comparisons appear together
across repeated listening tasks. For example, you may want each pair to be heard alongside different
comparisons, prevent multiple comparisons from the same source recording in one task, or require
fixed category counts per task and exact A-first/B-first balance across planned CCR appearances.

This can be useful for comparing microphones, speech enhanced by different systems, or other
versions of the same speech. Neither member of a CCR pair needs to be a clean reference. These
comparison types do not by themselves require prepacking: use `random` or `balanced_block` when
their session layouts and playback-order handling are sufficient.

`prepacked` tells the master script to use supplied session memberships instead of constructing
them with `random` or `balanced_block`. `pack_sessions.py` is an optional planner for that input.

This guide covers the pipeline:

```text
comparisons.csv
    -> pack_sessions.py -> assignments.csv + assignment_audit.json
    -> convert_assignments.py -> prepacked_sessions.csv
    -> master_script.py -> HIT HTML + publish-batch CSV + result-parser config
```

## Example: choosing a microphone, without a clean reference

Suppose the same meeting moment was recorded by a laptop microphone, a USB microphone and a
speakerphone. We want to know whether a model's predicted MOS difference identifies the device
listeners judge to sound better. Neither recording is necessarily clean or the correct answer.

For each comparison, choose stable labels **A** and **B**, for example current device A and
alternative device B. Align and crop the same speech interval, and decide the processing chain
before constructing the pairs. If evaluating enhanced audio, apply the intended enhancement
consistently. Clip selection, enhancement and model inference are outside the packing tools.

The existing CSV names are retained for compatibility:

| Field | Meaning in this CCR use case |
| --- | --- |
| `references` / `Qn_R` | Canonical clip A, not necessarily a clean reference |
| `rating_clips` / `Qn_P` | Canonical clip B, not necessarily a processed version of A |
| `comparison_id` / `Qn_ID` | Identity of the complete A/B comparison |
| `scene` | Underlying meeting moment shared by related comparisons |

Listeners hear the clips sequentially and rate the second relative to the first on the CCR
scale from -3 (much worse) to +3 (much better), including 0 (about the same). The template records
the answer in the canonical **B-minus-A** direction, regardless of playback order. Thus a positive
mean supports switching from A to B. This is a relative-quality judgment, not an absolute MOS.
Compare its direction/ranking with `predicted MOS(B) - predicted MOS(A)`; the numeric scales differ.

One audio file may participate in several comparisons. Aggregate by **comparison ID**, not by a
single audio filename: the quality of B relative to A is not the same question as B relative to C.
Keep A/B orientation fixed for each ID; use `order` to vary playback, not reversed copies of the input.

A *session* is one listening task/HIT. Its *bundle* is the set of main comparisons assigned to it,
excluding practice and controls. A/B and A/C from one meeting moment are different comparisons
but share the same scene. Preventing exact pair repeats alone does not prevent this scene repetition.

## What this adds to the existing workflows

The usual workflow lets `master_script.py` pack the clip list, then collects assignments for the
generated HITs. Repeating a HIT collects additional opinions on the same bundle. Listing comparisons
multiple times allows more bundles, but does not by itself control their context or playback order.

A *stratum* is a category assigned to each comparison; quotas specify how many comparisons from
each category appear in each bundle.

| Requirement | Built-in `random` / `balanced_block` | Planner + `prepacked` |
| --- | --- | --- |
| Session membership | Random split, or configured condition blocks | Planned jointly across repeated comparisons |
| Within-session pair repeats | Avoided when feasible; clear warning and repeated output otherwise | Prohibited in a successful plan |
| Different pairs from the same scene | No scene-exclusion guarantee | At most one per bundle with `--group-column` |
| Appearances per comparison | Supplied occurrences plus any padding and platform assignments | Exactly `--repeats` planned appearances, no padding |
| CCR playback order | Randomized independently in the browser | Exactly half `ab`, half `ba` for each comparison |
| Session composition | `balanced_block` balances configured conditions | Optional fixed counts per stratum with `--quota` |
| Repeated context | No bundle/context-diversity guarantee | Distinct bundle memberships; local search tries to reduce repeated companions |
| Reproducibility | Save the generated batch | Save the seed, input, plan, audit hashes and converted batch |

Exact A-first/B-first balance controls planned order exposure; it does not guarantee that all
listener biases cancel. Context optimization is a seeded local search, not a global optimum.
`balanced_block` remains useful for condition-balanced experiments; the planner does not automatically
translate its `block_keys` into constraints.

For scale, 800 comparisons with 10 planned ratings each and 8 main comparisons per session require
1,000 sessions. This means generating one joint plan, not running the master script 1,000 times.
The walkthrough below uses a small design to make the files and commands easy to inspect.

## Worked CCR pipeline

Follow [general preparation](preparation.md) first. Run these PowerShell commands from the repository
root. All paths are relative to that working directory. Use new output paths on reruns: the planner
and converter refuse to overwrite existing files.

### 1. Prepare comparisons and practice

Save this as `comparisons.csv`. These are **illustrative URLs**; replace them with accessible hosted
audio before listening or publishing. Each row is one unique pair, listed once, not once per rater.
The two strata illustrate different sampling categories, not known correct preferences.

```csv
comparison_id,scene,stratum,references,rating_clips
scene01-ab,scene01,representative,https://example.org/scene01_micA.wav,https://example.org/scene01_micB.wav
scene01-ac,scene01,supplementary,https://example.org/scene01_micA.wav,https://example.org/scene01_micC.wav
scene02-ab,scene02,representative,https://example.org/scene02_micA.wav,https://example.org/scene02_micB.wav
scene02-ac,scene02,supplementary,https://example.org/scene02_micA.wav,https://example.org/scene02_micC.wav
scene03-ab,scene03,representative,https://example.org/scene03_micA.wav,https://example.org/scene03_micB.wav
scene03-ac,scene03,supplementary,https://example.org/scene03_micA.wav,https://example.org/scene03_micC.wav
scene04-ab,scene04,representative,https://example.org/scene04_micA.wav,https://example.org/scene04_micB.wav
scene04-ac,scene04,supplementary,https://example.org/scene04_micA.wav,https://example.org/scene04_micC.wav
```

Prepare separate, representative practice examples as `training_clips.csv`:

```csv
training_clips,training_references
https://example.org/practice01_micB.wav,https://example.org/practice01_micA.wav
https://example.org/practice02_micB.wav,https://example.org/practice02_micA.wav
```

Choose the real session size, repeat count, practice examples and controls for your study; this
two-comparison example is a tooling demonstration, not a recommended study size.

### 2. Plan the sessions

```powershell
python src\pack_sessions.py --input comparisons.csv --output assignments.csv --audit assignment_audit.json `
    --id-column comparison_id --group-column scene --stratum-column stratum `
    --quota representative=1 --quota supplementary=1 --session-size 2 --repeats 2 --seed 17
```

This creates **8 bundles of 2 comparisons**: 16 appearances, with each comparison shown once in
each playback order. Every bundle has one comparison from each stratum and two different scenes.
Inspect `assignment_audit.json` for counts, per-item order balance, context statistics and file hashes.

`assignments.csv` is long-format: `bundle_id,position,item_id,order`. Each row assigns one comparison
to a one-based position in a bundle. It contains IDs, not audio URLs, and is not the upload CSV.

`--repeats` must be positive and even. Total appearances must divide exactly by session size; each
stratum must supply the requested quota at that repeat count, and enough distinct bundles/scenes
must exist. Unlike the permissive built-in strategies, this planner fails rather than weakening
its hard constraints. A search failure can also require another seed or revised constraints.
Omit both `--stratum-column` and `--quota` if quotas are not needed.

### 3. Convert the saved plan to the master's format

```powershell
python src\convert_assignments.py --assignments assignments.csv --clips comparisons.csv `
    --id-column comparison_id --method ccr --output prepacked_sessions.csv
```

The converter joins IDs to URLs and writes one row per bundle. Position 1 becomes `Q0_*`,
position 2 becomes `Q1_*`, and so on. It writes `Qn_R`, `Qn_P`, `Qn_ID`, `Qn_ROLE`, `Qn_EXPOSURE`
and `Qn_ORDER`. Without optional lookup columns, role defaults to `main` and exposure is empty.

Canonical URLs **never swap**: `Qn_R` remains A and `Qn_P` remains B even for `ba`. Only `Qn_ORDER`
changes playback. Conversion does not repack, redesign controls, or infer exposure from practice.

### 4. Configure and generate the HIT

Copy the repository config, then edit the named sections rather than adding duplicate sections:

```powershell
Copy-Item src\configurations\master.cfg mic_comparison.cfg
```

```ini
[create_input]
clip_packing_strategy: prepacked
prepacked_sessions: prepacked_sessions.csv
number_of_clips_per_session: 2
number_of_trapping_per_session: 0
aggregate_by_pair_id: true

[hit_app_html]
comparison_metadata: true
append_training_trap: false
allowed_max_hit_in_project: 1
cookie_name: mic_comparison
qual_cookie_name: mic_comparison_qualification
bw_min: NB-WB
bw_max: FB
```

Keep the other settings from the copied config. Use fresh cookie names for an independent study,
and set your payment, bonus, eligibility and screen-out settings before publishing. The bandwidth
values above must be unquoted. The no-control settings keep this example minimal; do not treat them
as a production quality-control recommendation.

```powershell
python src\master_script.py --project mic_comparison --method ccr --cfg mic_comparison.cfg `
    --clips comparisons.csv --training_clips training_clips.csv --create_local_test
```

Upload `mic_comparison\mic_comparison_ccr.html` and
`mic_comparison\mic_comparison_publish_batch.csv` to HITAppServer. The project also contains a local
preview and `mic_comparison_ccr_result_parser.cfg`. The generated batch preserves the planned membership and
playback-order metadata; the browser may shuffle question positions while keeping each comparison's
metadata attached.

### 5. Collect and analyze

Use the normal [Prolific](running_test_prolific.md) or [AMT](running_test_mturk.md) workflow. Allocate
**one completion per bundle** for the planned counts; assigning multiple raters to every bundle
multiplies the appearances. Enforce one session per participant through platform/server allocation,
or explicitly track previous comparisons if allowing more. Different session URLs and browser cookies
alone do not guarantee that a person never encounters a comparison twice.

Review the generated parser config before analysis. Set `[general] expected_votes_per_file` to the
intended per-comparison count (2 in this example); it otherwise retains the template default of 5.
This analysis target does not create assignments. Also select the correct platform and study-specific
acceptance settings.

Analyze downloaded answers with that config using the [usual result workflow](results.md).
CCR means remain B-minus-A. Compare their direction with `predicted MOS(B) - predicted MOS(A)`, not
their numeric magnitudes. Filtering, missing completions and reruns can change achieved counts and
order balance, so check the collected data rather than only the plan.

## Analysis output details

With `aggregate_by_pair_id: true`, `file_url` in aggregate output identifies the comparison rather than
one audio URL. Raw trial/control-candidate exports are available before filtering; controls are excluded
from main comparison means. The trial audit separately reconstructs second-minus-first as
`presentation_score`; canonical CCR scores are already B-minus-A, including for reversed playback.

## Controls and format details

The planner handles main comparisons only. Choose practice and hidden controls separately. If adding
controls to the saved plan, give them IDs and lookup rows, keep bundle sizes equal, and update
`number_of_clips_per_session` to include them. Set lookup `role` to `main`, `identical` or `contrast`;
contrast controls require degraded canonical A and clean canonical B. The converter does not create
or validate the acoustic quality of a control.

Optional lookup `practice_exposure` becomes `Qn_EXPOSURE`; empty means unknown, not "unexposed".
Comparison IDs and nonempty exposure labels may contain only letters, digits, `_`, `.`, `:` and `-`.
Keep each ID associated with the same pair and role. Do not assign multiple IDs to the same pair to
bypass uniqueness: the planner uses IDs and the supplied scene labels, not audio-content matching.

For hand-authored prepacked files, each row needs `Q0_R`/`Q0_P` through the configured count.
Other columns are preserved. CCR `comparison_metadata: true` additionally requires `Qn_ID`,
`Qn_ROLE`, `Qn_ORDER` and `Qn_EXPOSURE`. Prescribed orders are rejected when metadata is disabled,
rather than silently ignored. Pair-ID aggregation also requires metadata. If using
`condition_pattern` for additional grouping, it still matches B's audio URL, not the pair ID.

See [DCR/CCR preparation](prep_dcr_ccr.md#ccr-practice-and-presentation) for practice metadata,
online qualification and optional custom presentation settings.

## DCR compatibility

The converter and prepacked loader also accept DCR: use `--method dcr` in both conversion and
generation, and disable `comparison_metadata` and `aggregate_by_pair_id`. Conversion keeps the
bundle ID and audio columns but drops the plan's `order`, because DCR always presents reference
then processed. Consequently, the planner's A/B order-counterbalancing benefit applies to CCR,
not DCR. Use CCR for the symmetric device-comparison use case above.
