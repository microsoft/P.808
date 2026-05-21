---
name: create-study
description: Creates subjective speech quality tests using the P.808 toolkit — handles study setup, gold/trapping clip generation, storage upload, and project building for crowdsourcing platforms.
---

# Create subjective test instructions

Use this runbook when asked to create a new subjective speech quality test with the P.808 toolkit.

**Trigger phrases**: "create a study", "run a [method] test", "set up a [method] study", "prepare a
[method] test for these files".

## Platform and shell adaptation

Code examples use **PowerShell on Windows** (`\` paths). Adapt for other OS/shells:
replace PowerShell cmdlets with equivalents, use `python3` if needed, convert paths.
Replace `REPO_ROOT` with the actual absolute path of this repository.

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

This instruction covers preparing inputs, generating gold/trapping clips, uploading to
storage, running `master_script.py`, and handing off for publishing. Setting up the HIT
in a HITAPP server and publishing is done by the requester.

## Mandatory pre-check

Before editing or running anything in this repository:

1. Read `AGENTS.md` and `.github\copilot-instructions.md`.
2. Confirm this is a creation task, not analysis. For analysis, use
   `.github\evaluate.instruction.md` instead.

## Environment prerequisites

Verify once at the start:

1. **`az` CLI** logged in: `az account show`. If expired, prompt `az login`.
2. **Python deps**: `pip install -r requirements.txt --quiet` in `src\`.
3. **PowerShell**: use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
   Prefer running Python scripts directly over `.ps1` wrappers.

Once prerequisites pass, proceed without pausing except at **[ASK]** decision points.

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
	- `training_clips.csv` — **required for most methods** (can be auto-generated from
	  rating clips, but manual selection is recommended — see section 4).
	  **Not needed for P.804 or pp835 when `training_gold_clips.csv` is provided or
	  generated** — the two are mutually exclusive (see section 4).
	- `training_gold_clips.csv` — **P.804 and pp835 only**. Contains training
	  clips with per-dimension answers, variance, and feedback messages. **When available
	  (provided or auto-generated), this takes priority over `training_clips.csv`** —
	  do not ask for or generate plain training clips. If not provided the agent can
	  generate one from gold clips (see section 4b).
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

All clip URLs must be publicly accessible for crowd workers.

**Check accessibility**: pick one URL from the clip list and test with HTTP HEAD:

```powershell
$testUrl = "<first_url_from_rating_clips>"
try {
    $r = Invoke-WebRequest -Uri $testUrl -Method Head -UseBasicParsing -ErrorAction Stop
    Write-Host "PUBLIC — HTTP $($r.StatusCode)"
} catch { Write-Host "NOT PUBLIC — $($_.Exception.Message)" }
```

- **If public (HTTP 200)**: upload gold/trapping clips to the same account/container.
- **If not public (HTTP 403/409)**: ask the user which **public** container to copy all
  clips to. Use a **random opaque subdirectory** (e.g. `PROJECT_NAME/stim_x7k2m9`).

#### Preserving directory structure when copying

Rating clips often share filenames across subdirectories (each representing a different
condition). **Never copy to a flat directory** — preserve the parent directory name:

```text
Source:  .../condition_A/clip1.wav  →  Dest: .../<random_subdir>/condition_A/clip1.wav
Source:  .../condition_B/clip1.wav  →  Dest: .../<random_subdir>/condition_B/clip1.wav
```

#### Copy method: `azcopy` with SAS tokens (preferred)

For private-to-public transfers, use `azcopy` with **user-delegation SAS tokens on
both source and destination URLs**. **Never use `azcopy login`** — its token cache is
separate from `az login`, expires after 90 days of inactivity (`AADSTS700082`), and
cannot be refreshed via `az login`. Always generate SAS tokens with `az` instead.

**Generate SAS tokens for both containers and copy:**

```powershell
$expiry = (Get-Date).AddHours(2).ToUniversalTime().ToString("yyyy-MM-ddTHH:mmZ")

$srcSas = az storage container generate-sas `
    --account-name SOURCE_ACCOUNT --name SOURCE_CONTAINER `
    --permissions rl --expiry $expiry `
    --auth-mode login --as-user -o tsv

$destSas = az storage container generate-sas `
    --account-name DEST_ACCOUNT --name DEST_CONTAINER `
    --permissions rwl --expiry $expiry `
    --auth-mode login --as-user -o tsv

azcopy copy `
    "https://SOURCE_ACCOUNT.blob.core.windows.net/SOURCE_CONTAINER/path?$srcSas" `
    "https://DEST_ACCOUNT.blob.core.windows.net/DEST_CONTAINER/dest_path?$destSas" `
    --recursive
```

This uses your `az login` session to generate the tokens — no `azcopy login` needed.
Requires the **Storage Blob Delegator** role (included in **Storage Blob Data
Contributor**) on both storage accounts.

**Important**: `azcopy` with `--recursive` preserves the source directory tree. The
copied paths will include intermediate directories from the source prefix. After
copying, update the rating clips CSV to reflect the **actual** destination paths
(verify with `az storage blob list`).

**Common failures:**

| Symptom | Fix |
|---------|-----|
| `AADSTS700082: refresh token expired` | You used `azcopy login` — switch to the SAS token approach above |
| `AuthorizationPermissionMismatch` | Assign **Storage Blob Data Contributor** role on both accounts |
| `azcopy: command not found` | Install from https://aka.ms/azcopy or use the `az` fallback below |

**Fallback**: if `azcopy` is not installed, use `az storage blob copy start` with
SAS-authenticated source URIs:

```powershell
$clips | ForEach-Object -Parallel {
    $url = $_.rating_clips
    $sasToken = $using:srcSas
    if ($url -match 'https?:/+([^.]+)\.blob\.core\.windows\.net/([^/]+)/(.+)/([^/]+)$') {
        $parentDir = ($Matches[3] -split '/')[-1]; $fileName = $Matches[4]
        az storage blob copy start `
            --account-name DEST_ACCOUNT --destination-container DEST_CONTAINER `
            --destination-blob "DEST_PREFIX/$parentDir/$fileName" `
            --source-uri "$url`?$sasToken" `
            --auth-mode login 2>&1 | Out-Null
    }
} -ThrottleLimit 20
```

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
gold slot the clip belongs to. See section 5 for how to generate two sets.

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

### 2. Validate the input clip list

Before proceeding, validate **every URL** to catch typos, broken links, or inaccessible
files early.

1. Parse the CSV and fix common URL formatting issues (e.g. `https:/host` → `https://host`).
2. Validate URLs using one of the approaches below.
3. If **any URLs are invalid**, **stop** and report the full list to the user.
4. Check for **duplicate URLs** — report them and ask the user to clarify before continuing.

#### Validation approaches

**For public storage**: use `check_urls_in_files_exist` from `master_script.py` for fast
multicore validation:

```python
import sys, os
sys.path.insert(0, os.path.join("REPO_ROOT", "src"))
from master_script import check_urls_in_files_exist
check_urls_in_files_exist("CLIP_LIST_PATH", ["COLUMN_NAME"])
```

**For private storage**: `check_urls_in_files_exist` uses plain HTTP HEAD and will fail
with HTTP 409. Generate a SAS token using `az`, append it to every URL temporarily, then
validate:

```powershell
$expiry = (Get-Date).AddHours(2).ToUniversalTime().ToString("yyyy-MM-ddTHH:mmZ")
$sasToken = az storage container generate-sas `
    --account-name SOURCE_ACCOUNT --name SOURCE_CONTAINER `
    --permissions rl --expiry $expiry `
    --auth-mode login --as-user -o tsv
```

Then temporarily append `?$sasToken` to every URL in the CSV, call
`check_urls_in_files_exist`, and strip the token afterwards. Store the SAS token for
reuse in later steps (downloading clips, azcopy transfers).

**[ASK]** If clips are on private storage: "Your clips are on private storage. I can
generate a SAS token using your `az login` session to validate and download clips.
Should I go ahead?"

### 3. Check for existing project config

Look for a `.cfg` file next to the `rating_clips.csv` in the requester's data directory.
If one exists, offer to reuse it. If this is a re-run or "go yolo" request, use it directly.

### 4. Prepare training clips

Training clips anchor participants' perception and should represent the quality
distribution within the dataset — from worst to best.

**P.804 and pp835 — training gold clips take priority:**

For P.804 and pp835, `training_gold_clips.csv` and `training_clips.csv` are **mutually
exclusive** — the master script accepts one or the other, not both. Because training gold
clips provide richer per-dimension feedback, they are **always preferred**:

1. If the user provides `training_gold_clips.csv` → use it, **skip** plain training clips.
2. If neither is provided → generate `training_gold_clips.csv` from gold clips (see
   section 4b), **skip** plain training clips.
3. Only generate or ask for `training_clips.csv` when the method is **not** P.804/pp835,
   or when the user explicitly opts out of training gold clips.

**For all other methods (ACR, DCR, CCR, P.835, echo impairment):**

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

#### 4b. Prepare training gold clips (P.804 and pp835 only)

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

**Rules**: `_var = 1` accepts ±1 deviation; `_var = 0` skips feedback. `_msg` is a
short feedback message. Empty `_ans` cells accept any answer.

**Auto-generating from gold clips:**

If the user does not provide training gold clips, generate them from the gold clips:
1. Select up to 5 gold clips with the most distinctive quality characteristics
   (prefer clips with extreme or opposite dimension values).
2. Assign `_var = 1` for all dimensions that have an answer.
3. Write brief feedback messages for each dimension describing the expected quality.
4. Upload these clips to public storage (they may already be uploaded as gold clips).

### 5. Generate gold clips (if not provided)

Gold clips require **high-quality, clean reference WAV files** — not arbitrary rating clips.

**[ASK] Source clips**: ask the user how to obtain clean source audio (see "Inputs the
agent must confirm", item 5). Options:
- The user provides a directory of clean WAV files from the same dataset.
- The user identifies clean clips by a URL pattern (e.g. `*/clean/*`).
- Download a subset and let the user review them to remove any with distortion.

If downloading clips from Azure private storage, either:
- Use `download_clips.py` with `--sas_token` to authenticate, or
- Use `az storage blob download` with `--auth-mode login` for each clip individually.

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
3. Add a `ver` column: `ver=1` when `ovrl_ans=5` (clean), `ver=2` when `ovrl_ans=1` (degraded).
4. Export as `gold_clips.csv`.

After generation, upload to public storage:

```powershell
python utils\copy_to_pub_storage.py upload `
	--input RATING_CLIPS_PATH\gold_output\gold_clips_report.csv `
	--columns gold_clips --local-dir RATING_CLIPS_PATH\gold_output `
	--account-name STORAGE_ACCOUNT_NAME `
	--target-container TARGET_CONTAINER `
	--dest-path PROJECT_NAME/RANDOM_SUBDIR
```

Use a **random subdirectory name** (not `gold` or `trapping`). This uploads via
`az login` credentials and produces `gold_clips_report_public.csv` with public URLs.
If `az` CLI is unavailable, fall back to `upload-local` mode.

For P.804, apply column renaming (`gold_clips` → `gold_url`) and add `ver` **after**
URLs have been updated to public paths.

### 6. Generate trapping clips (if not provided)

Trapping clips can be generated from any rating clips — they do not need to be
high-quality references (unlike gold clips). Download a sample of rating clips:

```powershell
python utils\download_clips.py `
	--input RATING_CLIPS_PATH\rating_clips.csv `
	--column rating_clips `
	--output_dir RATING_CLIPS_PATH\trapping_source `
	--sample BEST_PRACTICE_TRAPPING_SOURCE_COUNT `
	--strategy random --seed 99 `
	--sas_token "SAS_TOKEN_VALUE"
```

Omit `--sas_token` for public storage. If no SAS token is available for private storage,
fall back to `az storage blob download --auth-mode login` for each clip.

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

### 6b. Review generated clips

**[ASK]** After generating and uploading gold, trapping, and training clips, ask:
"Gold, trapping, and training clips are generated and uploaded. Would you like to
review them before I run the master script, or should I continue?"

### 7. Create the project config

Create a `.cfg` file next to the input CSVs with the project name.

Template (values **unquoted**):

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

**Key rules:**
- `number_of_gold_clips_per_session` = **2 for P.804**, 1 for others.
- `bw_min` defaults to `FB`. Valid: `NB-WB`, `SWB`, `FB`.
- `contact_email` = user-provided. Never hardcode.
- `allowed_max_hit_in_project` = `BEST_PRACTICE_ALLOWED_MAX_HITS`.
- `quantity_hits_more_than` ≈ `floor(total_sessions / 2)`, at least 2.

### 8. Run the master script

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
CSV was provided or generated in step 4b:

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

### 9. Verify the generated project artifacts

The output project directory (`PROJECT_NAME\`) should contain:

| File | Purpose |
|------|---------|
| `PROJECT_NAME_METHOD.html` | HIT app (HTML) for the crowd platform |
| `PROJECT_NAME_publish_batch.csv` | Session data with clip URLs for publishing |
| `PROJECT_NAME_METHOD_result_parser.cfg` | Config for `result_parser.py` when analyzing results |
| `url_mapping.csv` | Mapping of original (private/local) URLs to final public URLs |

Verify:

1. All three files exist.
2. The publish batch CSV has the expected number of rows (sessions).
3. The HTML file is non-empty.

### 9b. Generate URL mapping CSV

If clips were copied from private to public storage, generate `url_mapping.csv` in the
project output directory mapping every original URL to its public URL.

Columns: `original_url`, `public_url`, `clip_type` (one of: `rating`, `gold`,
`trapping`, `training`, `training_gold`).

Include all clip types that were uploaded or copied. For clips already public (e.g.
training gold clips), set `original_url = public_url`.

Save as `PROJECT_NAME\url_mapping.csv`.

### 10. Clean up temporary files

**Always remove:**
- `tmp_gold.csv` (debug artifact from `master_script.py`).
- Downloaded source clips directories (`gold_source\`, `trapping_source\`).
- Toolkit trapping directories (`src\trapping_clips_assets\source\*.wav`,
  `src\trapping_clips_assets\output\*`).

**[ASK]** Ask whether to also remove local `gold_output\` (clips are already uploaded).

### 11. Handoff

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
