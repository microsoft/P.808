---
name: create-study
description: Creates subjective speech quality tests using the P.808 toolkit — handles study setup, gold/trapping clip generation, storage upload, and project building for crowdsourcing platforms.
---

# Create subjective test instructions

Use this runbook when asked to create a new subjective speech quality test with the P.808 toolkit.

**Trigger phrases**: "create a study", "run a [method] test", "set up a [method] study", "prepare a
[method] test for these files".

## Platform and shell adaptation

The code examples below use **PowerShell on Windows** with Windows-style paths (`\`).
If you are running on a different OS or shell (e.g. bash on macOS/Linux), adapt every
command to the user's environment:

- Replace PowerShell cmdlets (`Set-Location`, `Get-ChildItem`, `Copy-Item`, `Remove-Item`,
  `Import-Csv`, `Export-Csv`, `Invoke-WebRequest`, `ForEach-Object`, `Add-Member`) with
  their shell or Python equivalents.
- Replace `REPO_ROOT` in all commands with the **actual absolute path** of this
  repository on disk (i.e. the Git root directory).
- Convert path separators as needed (`\` on Windows, `/` on macOS/Linux).
- Use `python3` instead of `python` if required by the platform.
- The Python scripts and `az` CLI commands are cross-platform — only the shell glue
  around them needs adaptation.

## Best-practice variables

These are best-practice defaults. Confirm or override them with the requester before first use.
After confirmation, save a `.cfg` file next to the input files so future runs can reuse it.
When asked to re-run a test or "go yolo", look for an existing config file first.

```text
BEST_PRACTICE_PLATFORM             = Prolific
BEST_PRACTICE_VALID_VOTE_BUFFER    = 20%
BEST_PRACTICE_CLIPS_PER_SESSION    = 10
BEST_PRACTICE_GOLD_PER_SESSION     = 1   (use 2 for P.804 — see method-specific notes)
BEST_PRACTICE_TRAPPING_PER_SESSION = 1
BEST_PRACTICE_TRAINING_CLIPS       = 5
BEST_PRACTICE_GOLD_SOURCE_COUNT    = max(3, ceil(0.05 * number_of_rating_clips))
BEST_PRACTICE_TRAPPING_SOURCE_COUNT= max(3, ceil(0.05 * number_of_rating_clips))
BEST_PRACTICE_MAX_GOLD_SOURCE_CLIPS    = 15
BEST_PRACTICE_MAX_TRAPPING_SOURCE_CLIPS= 15
BEST_PRACTICE_ALLOWED_MAX_HITS     = min(int(number_of_rating_clips / 10), 50)
BEST_PRACTICE_BASE_PAYMENT         = 0.50
BEST_PRACTICE_QUANTITY_BONUS       = 0.10
BEST_PRACTICE_QUALITY_BONUS        = 0.15
BEST_PRACTICE_BW_MIN               = FB
```

## Scope

This instruction covers:

1. Preparing inputs for all supported test methods.
2. Generating gold clips and trapping clips when needed.
3. Preparing upload commands for generated clips to public storage.
4. Running `master_script.py` to build the project.
5. Handing off the generated project for publishing on the chosen crowd platform.

Platform note: Setting up the HIT in a HITAPP server and publishing on the crowdsourcing platform
is done by the requester following the generated artifacts and platform docs.

## Mandatory pre-check

Before editing or running anything in this repository:

1. Read `AGENTS.md` and `.github\copilot-instructions.md`.
2. Confirm this is a creation task, not analysis. For analysis, use
   `.github\evaluate.instruction.md` instead.

## Environment prerequisites

Verify these once at the start so subsequent steps run without interactive prompts:

1. **`az` CLI** is logged in: run `az account show` and confirm a valid subscription.
   If expired, prompt the user to run `az login` before continuing.
2. **Python dependencies**: run `pip install -r requirements.txt --quiet` in `src\`.
3. **PowerShell execution policy**: to avoid repeated permission prompts when running
   shell commands, launch PowerShell with `powershell -ExecutionPolicy Bypass` or run
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` at the start of the
   session. Prefer running Python scripts directly (`python script.py`) over calling
   `.ps1` wrapper scripts.

Once prerequisites pass, proceed through the workflow without pausing for confirmation
at each command. The agent should only pause to ask the user for the inputs listed
in the next section and the specific decision points marked **[ASK]** in the workflow.

## Supported test methods

| Method | `--method` flag | Gold clip generation | Trapping config | Template |
|--------|-----------------|---------------------|-----------------|----------|
| ACR | `acr` | `--method acr` | `trapping.cfg` or `trapping_p835.cfg` | `ACR_template.html` |
| DCR | `dcr` | N/A (manual) | N/A (uses references) | `DCR_template.html` |
| CCR | `ccr` | N/A (manual) | N/A (uses references) | `CCR_template.html` |
| P.835 | `p835` | `--method acr` (**not** `p835`) | `trapping.cfg` or `trapping_p835.cfg` | `P835_template.html` |
| P.804 | `p804` | `--method p804` | `trapping_p804.cfg` | via `pp835_p804` path |
| Echo impairment | `echo_impairment_test` | `--method acr` | `trapping.cfg` | `echo_impairment_test_template.html` |
| Personalized P.835 | `pp835` | special (per-dimension) | `trapping.cfg` | `P835_personalized_template3.html` |

**Critical**: For plain `p835`, use `--method acr` when generating gold clips with
`create_gold_clips.py`. The `p835` method in the gold generator produces per-dimension columns
(`gold_sig_ans`, `gold_bak_ans`, `gold_ovrl_ans`) but `master_script.py` expects `gold_clips_ans`
for plain P.835.

## Inputs the agent must confirm

Do not guess these values if they are missing:

1. **Test method**: one of `acr`, `dcr`, `ccr`, `p835`, `p804`, `echo_impairment_test`, `pp835`.
2. **Crowd platform**: Prolific (recommended), AMT, or another panel.
3. **Project name**: for generated output folder and files.
4. **Input resources**:
	- `rating_clips.csv` — **required**.
	- `training_clips.csv` — **required** (can be auto-generated from rating clips, but
	  manual selection is recommended — see section 3).
	- `training_gold_clips.csv` — optional, **P.804 and pp835 only**. Contains training
	  clips with per-dimension answers, variance, and feedback messages. If not provided
	  the agent can generate one from gold clips (see section 3b).
	- `gold_clips.csv` — optional (can be generated from source clips).
	- `trapping_clips.csv` — optional (can be generated from source clips).
5. **Source clips for gold/trapping generation**:
   - **Gold clips**: if `gold_clips.csv` is not provided, the agent **must not** blindly
     download random rating clips. Gold clips require **high-quality, clean reference audio**.
     Ask the user one of:
     - Do they have a local directory of clean reference WAV files from the same dataset?
     - Can they identify clean clips by a URL pattern (e.g. `*/clean/*`, `*/reference/*`)?
     - Would they like the agent to download a small subset of rating clips for the user to
       **listen to and manually remove any clips with distortion** before gold generation?
     **Important**: never use the sample clips bundled in this repository (`src\test_inputs\`).
     Source clips must come from the same dataset as the rating clips.
   - **Trapping clips**: if `trapping_clips.csv` is not provided, the quality of source
     clips does **not** matter for trapping questions. The agent can download a random sample
     of rating clips and use them directly — no manual review needed.
6. **Storage**: the Azure storage account name and container for uploading generated clips.
   The container **must be publicly accessible** — crowd workers need unauthenticated access.
   See "Storage and public accessibility" below for the full check procedure.
7. **Contact email**: the email address to show in the HIT app for worker inquiries.
   Do **not** use a hardcoded default — always ask.
8. **Max assignments per worker** (for Prolific) or worker requirements and payment (for AMT).
9. **Target valid votes per clip**: suggest publishing `target + BEST_PRACTICE_VALID_VOTE_BUFFER`.

## Storage and public accessibility

All clip URLs (rating, gold, trapping, training) must be publicly accessible because
crowd workers access them without authentication.

**Step 1 — Check the rating clips container:**

Pick one URL from `rating_clips.csv` and test with an unauthenticated HTTP HEAD request:

```powershell
$testUrl = "<first_url_from_rating_clips>"
try {
    $response = Invoke-WebRequest -Uri $testUrl -Method Head -UseBasicParsing -ErrorAction Stop
    Write-Host "PUBLIC — HTTP $($response.StatusCode)"
} catch {
    Write-Host "NOT PUBLIC — $($_.Exception.Message)"
}
```

- **If public (HTTP 200)**: the rating clips are already accessible. Upload gold and
  trapping clips to the same account/container.
- **If not public (HTTP 403/409)**: the rating clips are on a private container.
  Upload gold and trapping clips to that same private container (using `az login`
  credentials), then ask the user which **public** container to copy **all** clips
  (rating + gold + trapping + training) to. Use `az storage blob copy` or azcopy to
  copy from private to public. Use a **random opaque subdirectory name** for the
  rating clips destination (e.g. `PROJECT_NAME/stim_x7k2m9`) — do not use predictable
  names like `rating` or `clips`.

**Step 2 — Ask the user (only if private):**

> The rating clips are on a private container (`ACCOUNT/CONTAINER`). Crowd workers
> will not be able to access them. Which public storage account and container should
> I copy all clips to?

After copying, update all CSV files to use the new public URLs.

## CSV column names by method

These are the **actual column names** expected by the code in `src\create_input.py` and
`src\master_script.py`.

### Single-stimulus methods (ACR, P.835, echo_impairment_test)

| CSV file | Columns |
|----------|---------|
| `rating_clips.csv` | `rating_clips` |
| `training_clips.csv` | `training_clips` |
| `gold_clips.csv` | `gold_clips`, `gold_clips_ans` |
| `trapping_clips.csv` | `trapping_clips`, `trapping_ans` |

### P.804

P.804 gold clips use **per-dimension answer columns** and a **`ver` column** to assign
clips to gold slots. The `master_script.py` internally renames columns via
`update_gold_clips_for_p804()`.

| CSV file | Columns |
|----------|---------|
| `rating_clips.csv` | `rating_clips` |
| `training_clips.csv` | `training_clips` (not needed if `training_gold_clips.csv` is used) |
| `training_gold_clips.csv` | `training_clips`, `noise_ans`, `noise_var`, `noise_msg`, `disc_ans`, `disc_var`, `disc_msg`, `col_ans`, `col_var`, `col_msg`, `loud_ans`, `loud_var`, `loud_msg`, `reverb_ans`, `reverb_var`, `reverb_msg`, `sig_ans`, `sig_var`, `sig_msg`, `ovrl_ans`, `ovrl_var`, `ovrl_msg` |
| `gold_clips.csv` | `gold_url`, `col_ans`, `disc_ans`, `loud_ans`, `noise_ans`, `reverb_ans`, `sig_ans`, `ovrl_ans`, `ver` |
| `trapping_clips.csv` | `trapping_clips`, `trapping_ans` |

**Column mapping note**: `create_gold_clips.py --method p804` outputs a column named
`gold_clips`. You **must** rename it to `gold_url` before passing it to `master_script.py`.
The answer columns (`col_ans`, `disc_ans`, etc.) are output without the `gold_` prefix
and should be kept as-is — the master script adds the prefix internally.

The `ver` column is **required** and must contain an integer (1 or 2) indicating which
gold slot the clip belongs to. See section 4 for how to generate two sets.

### Double-stimulus methods (DCR, CCR)

| CSV file | Columns |
|----------|---------|
| `rating_clips.csv` | `rating_clips`, `references` |
| `training_clips.csv` | `training_clips`, `training_references` |
| `trapping_clips.csv` | `trapping_clips` (uses references as trapping) |

### Personalized P.835 (`pp835`)

| CSV file | Columns |
|----------|---------|
| `gold_clips.csv` | `gold_url`, `gold_sig_ans`, `gold_bak_ans`, `gold_ovrl_ans` |
| `training_gold_clips.csv` | `training_clips`, `sig_ans`, `sig_var`, `sig_msg`, `bak_ans`, `bak_var`, `bak_msg`, `ovrl_ans`, `ovrl_var`, `ovrl_msg` |

See `src\test_inputs\` for example CSV files.

## Execution workflow

### 1. Prepare the environment

Environment setup is covered in "Environment prerequisites" above. Verify `az` login
and install dependencies before entering the workflow.

### 2. Check for existing project config

Look for a `.cfg` file next to the `rating_clips.csv` in the requester's data directory.
If one exists, offer to reuse it. If this is a re-run or "go yolo" request, use it directly.

### 3. Prepare training clips

Training clips anchor participants' perception and should represent the quality
distribution within the dataset — from worst to best.

**[ASK]** Ask the user: "Can you provide a `training_clips.csv` file with manually
selected clips that represent the quality distribution in your dataset? For multi-scale
tests (P.804, P.835), training clips should also show variations across all dimensions.
If not, I can randomly select some samples, but manual selection is recommended."

If the user provides a file, use it directly. Otherwise, auto-generate:

```powershell
Set-Location REPO_ROOT\src
python utils\select_training_clips.py `
	--input RATING_CLIPS_PATH\rating_clips.csv `
	--output RATING_CLIPS_PATH\training_clips.csv `
	--count 5
```

Note: `select_training_clips.py` selects clips purely by list position without knowledge
of actual quality. Manual selection is always preferred.

#### 3b. Prepare training gold clips (P.804 and pp835 only)

For P.804 and personalized P.835, you can provide `training_gold_clips.csv` which adds
per-dimension answers, accepted variance, and feedback messages to training clips. This
enables the HIT app to show participants feedback if their training answers deviate too
far from the expected score.

**[ASK]** Ask the user: "For P.804/pp835, do you have a `training_gold_clips.csv` with
per-dimension answers and feedback messages? If not, I can generate one from the gold
clips by selecting those with the highest deviation across dimensions (up to 5 clips)."

**CSV format for P.804 `training_gold_clips.csv`:**

| Column | Description |
|--------|-------------|
| `training_clips` | URL of the training clip |
| `noise_ans` | Expected noise score (1–5) |
| `noise_var` | Accepted deviation (e.g. 1); use 0 to skip feedback for this dimension |
| `noise_msg` | Feedback message shown if the answer deviates |
| `disc_ans`, `disc_var`, `disc_msg` | Same for discontinuity |
| `col_ans`, `col_var`, `col_msg` | Same for coloration |
| `loud_ans`, `loud_var`, `loud_msg` | Same for loudness |
| `reverb_ans`, `reverb_var`, `reverb_msg` | Same for reverberation |
| `sig_ans`, `sig_var`, `sig_msg` | Same for signal distortion |
| `ovrl_ans`, `ovrl_var`, `ovrl_msg` | Same for overall quality |

For pp835, use columns: `sig_ans/var/msg`, `bak_ans/var/msg`, `ovrl_ans/var/msg`.

See `src\test_inputs\training_gold_clips_p804.csv` for an example.

**Rules for the `_var` and `_msg` columns:**
- `_var`: set to `1` for most dimensions (accept ±1 deviation). Set to `0` to skip
  feedback for that dimension — any answer will be accepted.
- `_msg`: a short feedback message explaining why the given answer is expected. Use
  clear, instructive language.
- If no answer is provided for a dimension (empty cell), any answer is accepted.
- Typically 1 point of deviation is accepted.

**Auto-generating from gold clips:**

If the user does not provide training gold clips, generate them from the gold clips:
1. Select up to 5 gold clips with the most distinctive quality characteristics
   (prefer clips with extreme or opposite dimension values).
2. Assign `_var = 1` for all dimensions that have an answer.
3. Write brief feedback messages for each dimension describing the expected quality.
4. Upload these clips to public storage (they may already be uploaded as gold clips).

### 4. Generate gold clips (if not provided)

Gold clips require **high-quality, clean reference WAV files** — not arbitrary rating clips.

**[ASK] Source clips**: ask the user how to obtain clean source audio (see "Inputs the
agent must confirm", item 5). Options:
- The user provides a directory of clean WAV files from the same dataset.
- The user identifies clean clips by a URL pattern (e.g. `*/clean/*`).
- Download a subset and let the user review them to remove any with distortion.

If downloading clips from Azure private storage, use `az storage blob download` with
`--auth-mode login` instead of the HTTP-based `download_clips.py`.

**How many source clips?** Use `BEST_PRACTICE_GOLD_SOURCE_COUNT` capped at
`BEST_PRACTICE_MAX_GOLD_SOURCE_CLIPS`.

Generate gold clips (filenames are **anonymized** by default — do **not** use
`--no_anonymize`):

```powershell
python create_gold_clips.py `
	--input_dir RATING_CLIPS_PATH\gold_source `
	--output_dir RATING_CLIPS_PATH\gold_output `
	--method GOLD_METHOD
```

**Method mapping for `create_gold_clips.py`:**

| Study method | Use `--method` | Output columns |
|--------------|---------------|----------------|
| `acr` | `acr` | `gold_clips`, `gold_clips_ans` |
| `p835` | `acr` | `gold_clips`, `gold_clips_ans` |
| `echo_impairment_test` | `acr` | `gold_clips`, `gold_clips_ans` |
| `p804` | `p804` | `gold_clips`, `col_ans`, `disc_ans`, `loud_ans`, `noise_ans`, `reverb_ans`, `sig_ans`, `ovrl_ans` |
| `pp835` | `p835` | `gold_clips`, `gold_sig_ans`, `gold_bak_ans`, `gold_ovrl_ans` |

**Note**: Each source clip produces multiple gold clips (clean, noisy, distorted, etc.).
With 3 source clips you get approximately 12 gold clips for ACR, more for P.804
(~11 variants per source clip).

#### P.804-specific: assigning `ver` column from a single gold set

For P.804, always use `number_of_gold_clips_per_session = 2`. You do **not** need two
independent sets of source clips. Instead, generate one set and assign `ver` based on the
`ovrl_ans` value:

- Clips with `ovrl_ans = 5` (clean/high-quality) → `ver = 1`
- Clips with `ovrl_ans = 1` (degraded) → `ver = 2`

1. Run `create_gold_clips.py --method p804` once with all source clips.
2. Rename `gold_clips` → `gold_url` in the output CSV.
3. Add a `ver` column based on `ovrl_ans`: `ver=1` when `ovrl_ans=5`, `ver=2` when `ovrl_ans=1`.

Example post-processing:

```powershell
$gold = Import-Csv "RATING_CLIPS_PATH\gold_output\gold_clips_report.csv"

# Rename gold_clips -> gold_url, assign ver based on ovrl_ans
$gold | ForEach-Object {
    $_ | Add-Member -NotePropertyName gold_url -NotePropertyValue $_.gold_clips -Force
    $ver = if ([int]$_.ovrl_ans -eq 5) { 1 } else { 2 }
    $_ | Add-Member -NotePropertyName ver -NotePropertyValue $ver -Force
    $_.PSObject.Properties.Remove('gold_clips')
    $_
}

$gold | Export-Csv "RATING_CLIPS_PATH\gold_clips.csv" -NoTypeInformation
```

After generation, upload to public storage and create the gold_clips.csv:

```powershell
python utils\copy_to_pub_storage.py upload `
	--input RATING_CLIPS_PATH\gold_output\gold_clips_report.csv `
	--columns gold_clips `
	--local-dir RATING_CLIPS_PATH\gold_output `
	--account-name STORAGE_ACCOUNT_NAME `
	--target-container TARGET_CONTAINER `
	--dest-path PROJECT_NAME/RANDOM_SUBDIR
```

**Important**: do **not** use predictable directory names like `gold` or `trapping` for the
upload `--dest-path`. Generate a short random or opaque subdirectory name (e.g.
`PROJECT_NAME/stim_a3x9k2`) so crowd workers cannot guess the purpose of the clips
from the URL.

This directly uploads via `az login` credentials (no SAS tokens needed) and produces
`gold_clips_report_public.csv` with public URLs.

If `az` CLI is not available or login has expired, fall back to `upload-local` mode which
generates an azcopy command for manual upload instead.

Copy the public CSV as `gold_clips.csv` next to the rating clips. For P.804, remember to
apply the column renaming (`gold_clips` → `gold_url`) and add the `ver` column **after**
the URLs have been updated to public paths.

### 5. Generate trapping clips (if not provided)

Trapping clips can be generated from any rating clips — they do not need to be
high-quality references (unlike gold clips). Download a sample of rating clips:

```powershell
python utils\download_clips.py `
	--input RATING_CLIPS_PATH\rating_clips.csv `
	--column rating_clips `
	--output_dir RATING_CLIPS_PATH\trapping_source `
	--sample BEST_PRACTICE_TRAPPING_SOURCE_COUNT `
	--strategy random `
	--seed 99
```

If the rating clips are on private storage, use `az storage blob download` with
`--auth-mode login` instead.

Use a different seed or strategy than gold to avoid overlap with gold source clips.

Clear the toolkit's trapping source directory and copy source clips there:

```powershell
$trapSrc = "REPO_ROOT\src\trapping_clips_assets\source"
$trapOut = "REPO_ROOT\src\trapping_clips_assets\output"
Get-ChildItem $trapSrc -File | Remove-Item -Force
if (Test-Path $trapOut) { Get-ChildItem $trapOut -File | Remove-Item -Force }
Copy-Item "RATING_CLIPS_PATH\trapping_source\*.wav" $trapSrc -Force
```

Select the correct trapping config:

| Study method | Config file |
|-------------|-------------|
| `acr` | `configurations\trapping.cfg` or `configurations\trapping_p835.cfg` |
| `p835` | `configurations\trapping.cfg` or `configurations\trapping_p835.cfg` |
| `echo_impairment_test` | `configurations\trapping.cfg` |
| `p804` | `configurations\trapping_p804.cfg` |

Run the trapping clip generator:

```powershell
Set-Location REPO_ROOT\src
python create_trapping_stimuli.py `
	--cfg configurations\TRAPPING_CONFIG
```

Output goes to `trapping_clips_assets\output\`. The report is at
`trapping_clips_assets\output\output_report.csv` with columns `trapping_ans`, `trapping_clips`.

Prepare for upload — use a **random subdirectory name** (not `trapping`):

```powershell
python utils\copy_to_pub_storage.py upload `
	--input "trapping_clips_assets\output\output_report.csv" `
	--columns trapping_clips `
	--local-dir "trapping_clips_assets\output" `
	--account-name STORAGE_ACCOUNT_NAME `
	--target-container TARGET_CONTAINER `
	--dest-path PROJECT_NAME/RANDOM_SUBDIR
```

Copy the public CSV as `trapping_clips.csv` next to the rating clips.

### 5b. Review generated clips

**[ASK]** After generating gold, trapping, and training clips (and uploading them to
storage), pause and ask the user:

> "Gold, trapping, and training clips have been generated and uploaded. Before running
> the master script, I recommend reviewing a few clips to verify quality:
> - Gold clips: `STORAGE_ACCOUNT/CONTAINER/GOLD_SUBDIR/`
> - Trapping clips: `STORAGE_ACCOUNT/CONTAINER/TRAP_SUBDIR/`
> - Training clips: included in the rating clips
>
> Would you like to review them before proceeding, or should I continue?"

Wait for the user's response. If they want to review, pause. If they want to continue,
proceed to the next step.

### 6. Create the project config

Create a `.cfg` file next to the input CSVs. Save it with the project name so future
runs can reuse it.

Template (all values **unquoted**, no extra spaces around `:`):

```ini
[create_input]
number_of_clips_per_session:10
number_of_trapping_per_session:1
number_of_gold_clips_per_session:GOLD_PER_SESSION
clip_packing_strategy: random

[hit_app_html]
allowed_max_hit_in_project:COMPUTED_VALUE
bw_min: FB
bw_max: FB
hit_base_payment:0.5
quantity_hits_more_than: COMPUTED_VALUE
quantity_bonus: 0.1
quality_top_percentage: 20
quality_bonus: 0.15
contact_email:USER_PROVIDED_EMAIL
```

**Important config rules:**

- Do **not** quote values. `bw_min: FB` is correct. `bw_min: "FB"` will fail.
- `number_of_gold_clips_per_session` = **2 for P.804**, 1 for all other methods.
- `bw_min` defaults to `FB` unless the user explicitly requests a different value.
  Valid options: `NB-WB`, `SWB`, `FB`.
- `contact_email` = always use the email address provided by the user. Never hardcode
  a default.
- `allowed_max_hit_in_project` = the max number of HITs a single worker can complete.
  Use the requester's value or `BEST_PRACTICE_ALLOWED_MAX_HITS`.
- `quantity_hits_more_than` = threshold for quantity bonus. Should be approximately
  `floor(total_sessions / 2)` but at least 2. `total_sessions` is printed by the master
  script ("There are N clips and M sessions").
  If unsure, set to 2 and adjust after seeing the session count.

### 7. Run the master script

Always include `--check_urls` and `--create_local_test` flags. URL checking validates
that all clip URLs are accessible and catches broken links before publishing. The local
test generates a preview HTML file for visual inspection.

`--check_urls` may be skipped **only** if this is a re-run and the URLs were already
validated in a previous run (e.g. when re-running due to a config change).

```powershell
Set-Location RATING_CLIPS_PATH
python REPO_ROOT\src\master_script.py `
	--project PROJECT_NAME `
	--method METHOD `
	--cfg PROJECT_CONFIG.cfg `
	--clips rating_clips.csv `
	--training_clips training_clips.csv `
	--gold_clips gold_clips.csv `
	--trapping_clips trapping_clips.csv `
	--check_urls `
	--create_local_test
```

For **P.804** and **pp835**, also pass `--training_gold_clips` if a training gold clips
CSV was provided or generated in step 3b:

```powershell
python REPO_ROOT\src\master_script.py `
	--project PROJECT_NAME `
	--method p804 `
	--cfg PROJECT_CONFIG.cfg `
	--clips rating_clips.csv `
	--training_gold_clips training_gold_clips.csv `
	--gold_clips gold_clips.csv `
	--trapping_clips trapping_clips.csv `
	--check_urls `
	--create_local_test
```

Note: when `--training_gold_clips` is used, the `--training_clips` flag is **not**
needed — training clips are embedded in the training gold CSV.

**Notes:**

- Use **full absolute paths** for all arguments to avoid path resolution issues.
- The working directory should be the folder containing the input CSVs so that the
  project output directory is created there.
- Supported `--method` values: `acr`, `dcr`, `ccr`, `p835`, `echo_impairment_test`,
  `pp835`, `p804`.
- If `quantity_hits_more_than` triggers a warning, update the config file with the
  suggested value and re-run.

### 8. Verify the generated project artifacts

The output project directory (`PROJECT_NAME\`) should contain:

| File | Purpose |
|------|---------|
| `PROJECT_NAME_METHOD.html` | HIT app (HTML) for the crowd platform |
| `PROJECT_NAME_publish_batch.csv` | Session data with clip URLs for publishing |
| `PROJECT_NAME_METHOD_result_parser.cfg` | Config for `result_parser.py` when analyzing results |

Verify:

1. All three files exist.
2. The publish batch CSV has the expected number of rows (sessions).
3. The HTML file is non-empty.

### 9. Clean up temporary files

After the project is verified, clean up intermediate files generated during the workflow:

**Always remove:**
- `tmp_gold.csv` in the working directory (debug artifact from `master_script.py` for
  P.804 / personalized P.835 — written by `update_gold_clips_for_p804()`).
- Downloaded source clips directories (`gold_source\`, `trapping_source\`).
- The toolkit's trapping working directories (`src\trapping_clips_assets\source\*.wav`,
  `src\trapping_clips_assets\output\*`). Always clean these up — generated clips and
  reports must not be left in the repository tree.

**[ASK]** After cleanup, ask: "Would you like me to also remove the local `gold_output\`
directory? The gold clips are already uploaded to Azure at
`STORAGE_ACCOUNT/CONTAINER/RANDOM_SUBDIR/`."

If the user agrees, remove `gold_output\`. Regardless of the user's choice, only refer
to the **online location** of the clips in subsequent messages — do not mention local
directories that have been deleted.

### 10. Handoff

**Upload status**: If the `upload` mode was used, gold and trapping clips are already
uploaded and publicly accessible. If `upload-local` was used as a fallback (no `az` CLI),
remind the requester to run the azcopy commands before publishing the study.

**Handoff checklist:**

1. The project directory with all three artifacts.
2. The config file used (saved next to input CSVs for future re-runs).
3. The azcopy commands for uploading generated clips (if applicable).
4. The method and scale used.
5. Any warnings or deviations from the documented flow.
6. Instructions for the requester to publish on their chosen platform:
	- **Prolific**: follow the team's Prolific workflow or `docs\running_test_prolific.md`.
	- **AMT**: follow `docs\running_test_mturk.md`.

## Utility scripts reference

| Script | Purpose |
|--------|---------|
| `src\utils\download_clips.py` | Download clips from URLs in a CSV to local directory |
| `src\utils\select_training_clips.py` | Select N evenly-spaced training clips from rating clips |
| `src\utils\copy_to_pub_storage.py` | Upload clips to Azure Blob Storage (direct via `az login`) or prepare azcopy commands |
| `src\utils\preview_html.py` | Generate local preview HTML from master script output |
| `src\create_gold_clips.py` | Generate gold standard clips from clean source WAVs |
| `src\create_trapping_stimuli.py` | Generate trapping stimuli by overlaying messages on source clips |
