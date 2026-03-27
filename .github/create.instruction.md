# Create subjective test instructions

Use this runbook when asked to create a new subjective speech quality test with the P.808 toolkit.

**Trigger phrases**: "create a study", "run a [method] test", "set up a [method] study", "prepare a
[method] test for these files".

## Best-practice variables

These are best-practice defaults. Confirm or override them with the requester before first use.
After confirmation, save a `.cfg` file next to the input files so future runs can reuse it.
When asked to re-run a test or "go yolo", look for an existing config file first.

```text
BEST_PRACTICE_PLATFORM             = Prolific
BEST_PRACTICE_VALID_VOTE_BUFFER    = 20%
BEST_PRACTICE_CLIPS_PER_SESSION    = 10
BEST_PRACTICE_GOLD_PER_SESSION     = 1
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
	- `training_clips.csv` — **required** (can be auto-generated from rating clips).
	- `gold_clips.csv` — optional (can be generated from source clips).
	- `trapping_clips.csv` — optional (can be generated from source clips).
5. **Source clips** for gold/trapping generation: if gold and trapping CSVs are not provided,
   ask whether the requester has clean reference clips or whether to download a sample of rating
   clips for generation.
6. **Storage**: the Azure storage account name and container for uploading generated clips
   (e.g. account `crowdsourcedatapub`, container `crowdsource-data`). The `upload` mode in
   `copy_to_pub_storage.py` uses `az login` credentials — no SAS tokens needed. If the
   rating clips are already on a known storage account, reuse the same one.
7. **Max assignments per worker** (for Prolific) or worker requirements and payment (for AMT).
8. **Target valid votes per clip**: suggest publishing `target + BEST_PRACTICE_VALID_VOTE_BUFFER`.

## CSV column names by method

These are the **actual column names** expected by the code in `src\create_input.py` and
`src\master_script.py`.

### Single-stimulus methods (ACR, P.835, echo_impairment_test, P.804)

| CSV file | Columns |
|----------|---------|
| `rating_clips.csv` | `rating_clips` |
| `training_clips.csv` | `training_clips` |
| `gold_clips.csv` | `gold_clips`, `gold_clips_ans` |
| `trapping_clips.csv` | `trapping_clips`, `trapping_ans` |

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

See `src\test_inputs\` for example CSV files.

## Execution workflow

### 1. Prepare the environment

```powershell
Set-Location C:\my\repos\P.808\src
pip install -r requirements.txt --quiet
```

No extra dependency installs are needed for trapping clip generation — it uses the same
`requirements.txt`.

### 2. Check for existing project config

Look for a `.cfg` file next to the `rating_clips.csv` in the requester's data directory.
If one exists, offer to reuse it. If this is a re-run or "go yolo" request, use it directly.

### 3. Generate training clips (if not provided)

If the requester did not provide `training_clips.csv`, generate one from rating clips:

```powershell
Set-Location C:\my\repos\P.808\src
python utils\select_training_clips.py `
	--input RATING_CLIPS_PATH\rating_clips.csv `
	--output RATING_CLIPS_PATH\training_clips.csv `
	--count 5
```

The script selects evenly spaced clips from the rating set to cover the quality range.

### 4. Generate gold clips (if not provided)

Gold clips require local source WAV files. If the requester does not have clean reference
clips, download a sample of rating clips:

```powershell
Set-Location C:\my\repos\P.808\src
python utils\download_clips.py `
	--input RATING_CLIPS_PATH\rating_clips.csv `
	--column rating_clips `
	--output_dir RATING_CLIPS_PATH\gold_source `
	--sample BEST_PRACTICE_GOLD_SOURCE_COUNT
```

Then generate gold clips:

```powershell
python create_gold_clips.py `
	--input_dir RATING_CLIPS_PATH\gold_source `
	--output_dir RATING_CLIPS_PATH\gold_output `
	--method GOLD_METHOD `
	--no_anonymize
```

**Method mapping for `create_gold_clips.py`:**

| Study method | Use `--method` | Output columns |
|--------------|---------------|----------------|
| `acr` | `acr` | `gold_clips`, `gold_clips_ans` |
| `p835` | `acr` | `gold_clips`, `gold_clips_ans` |
| `echo_impairment_test` | `acr` | `gold_clips`, `gold_clips_ans` |
| `p804` | `p804` | `gold_clips` + per-dimension answers |
| `pp835` | `p835` | `gold_clips`, `gold_sig_ans`, `gold_bak_ans`, `gold_ovrl_ans` |

**Note**: Each source clip produces 4 gold clips (clean, noisy, distorted, both).
With 3 source clips you get 12 gold clips.

After generation, upload to public storage and create the gold_clips.csv:

```powershell
python utils\copy_to_pub_storage.py upload `
	--input RATING_CLIPS_PATH\gold_output\gold_clips_report.csv `
	--columns gold_clips `
	--local-dir RATING_CLIPS_PATH\gold_output `
	--account-name STORAGE_ACCOUNT_NAME `
	--target-container TARGET_CONTAINER `
	--dest-path PROJECT_NAME/gold
```

This directly uploads via `az login` credentials (no SAS tokens needed) and produces
`gold_clips_report_public.csv` with public URLs.

If `az` CLI is not available or login has expired, fall back to `upload-local` mode which
generates an azcopy command for manual upload instead.

Copy the public CSV as `gold_clips.csv` next to the rating clips.

### 5. Generate trapping clips (if not provided)

Download a **different** sample of rating clips than used for gold (no overlap):

```powershell
python utils\download_clips.py `
	--input RATING_CLIPS_PATH\rating_clips.csv `
	--column rating_clips `
	--output_dir RATING_CLIPS_PATH\trapping_source `
	--sample BEST_PRACTICE_TRAPPING_SOURCE_COUNT `
	--strategy random `
	--seed 99
```

Use a different seed or strategy than gold to avoid overlap.

Clear the toolkit's trapping source directory and copy source clips there:

```powershell
$trapSrc = "C:\my\repos\P.808\src\trapping clips\source"
$trapOut = "C:\my\repos\P.808\src\trapping clips\output"
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
Set-Location C:\my\repos\P.808\src
python create_trapping_stimuli.py `
	--cfg configurations\TRAPPING_CONFIG
```

Output goes to `trapping clips\output\`. The report is at
`trapping clips\output\output_report.csv` with columns `trapping_ans`, `trapping_clips`.

Prepare for upload:

```powershell
python utils\copy_to_pub_storage.py upload `
	--input "trapping clips\output\output_report.csv" `
	--columns trapping_clips `
	--local-dir "trapping clips\output" `
	--account-name STORAGE_ACCOUNT_NAME `
	--target-container TARGET_CONTAINER `
	--dest-path PROJECT_NAME/trapping
```

Copy the public CSV as `trapping_clips.csv` next to the rating clips.

### 6. Create the project config

Create a `.cfg` file next to the input CSVs. Save it with the project name so future
runs can reuse it.

Template (all values **unquoted**, no extra spaces around `:`):

```ini
[create_input]
number_of_clips_per_session:10
number_of_trapping_per_session:1
number_of_gold_clips_per_session:1
clip_packing_strategy: random

[hit_app_html]
allowed_max_hit_in_project:COMPUTED_VALUE
bw_min: NB-WB
bw_max: FB
hit_base_payment:0.5
quantity_hits_more_than: COMPUTED_VALUE
quantity_bonus: 0.1
quality_top_percentage: 20
quality_bonus: 0.15
contact_email:ic3ai@outlook.com
```

**Important config rules:**

- Do **not** quote values. `bw_min: NB-WB` is correct. `bw_min: "NB-WB"` will fail.
- `allowed_max_hit_in_project` = the max number of HITs a single worker can complete.
  Use the requester's value or `BEST_PRACTICE_ALLOWED_MAX_HITS`.
- `quantity_hits_more_than` = threshold for quantity bonus. Should be approximately
  `floor(total_sessions / 2)` but at least 2. `total_sessions` is printed by the master
  script ("There are N clips and M sessions").
  If unsure, set to 2 and adjust after seeing the session count.
- `bw_min` and `bw_max` must be one of: `NB-WB`, `SWB`, `FB`.

### 7. Run the master script

```powershell
Set-Location RATING_CLIPS_PATH
python C:\my\repos\P.808\src\master_script.py `
	--project PROJECT_NAME `
	--method METHOD `
	--cfg PROJECT_CONFIG.cfg `
	--clips rating_clips.csv `
	--training_clips training_clips.csv `
	--gold_clips gold_clips.csv `
	--trapping_clips trapping_clips.csv
```

**Notes:**

- Use **full absolute paths** for all arguments to avoid path resolution issues.
- Add `--check_urls` only when clips are already uploaded to public storage.
- The working directory should be the folder containing the input CSVs so that the
  project output directory is created there.
- Supported `--method` values: `acr`, `dcr`, `ccr`, `p835`, `echo_impairment_test`,
  `pp835`, `p804`.

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

### 9. Generate local preview (optional)

```powershell
Set-Location C:\my\repos\P.808\src
python utils\preview_html.py `
	--dir RATING_CLIPS_PATH\PROJECT_NAME `
	--samples 1
```

This generates a `_row-1.html` file that can be opened in a browser for a quick visual check.

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

## Quick-reference: end-to-end for single-stimulus methods

This is the condensed version for ACR / P.835 / echo_impairment_test studies when starting
from only a `rating_clips.csv`. Replace placeholders in CAPS.

```powershell
Set-Location C:\my\repos\P.808\src

# 1. Training clips
python utils\select_training_clips.py -i DATA_DIR\rating_clips.csv -o DATA_DIR\training_clips.csv -n 5

# 2. Download source clips for gold generation
python utils\download_clips.py -i DATA_DIR\rating_clips.csv -o DATA_DIR\gold_source -n GOLD_SRC_COUNT

# 3. Generate gold clips (use --method acr for both ACR and P.835)
python create_gold_clips.py --input_dir DATA_DIR\gold_source --output_dir DATA_DIR\gold_output --method acr --no_anonymize

# 4. Upload gold clips + create gold_clips.csv with public URLs
python utils\copy_to_pub_storage.py upload -i DATA_DIR\gold_output\gold_clips_report.csv -c gold_clips -l DATA_DIR\gold_output -a STORAGE_ACCOUNT -t CONTAINER -d PROJECT/gold
Copy-Item DATA_DIR\gold_output\gold_clips_report_public.csv DATA_DIR\gold_clips.csv

# 5. Download source clips for trapping (different set than gold)
python utils\download_clips.py -i DATA_DIR\rating_clips.csv -o DATA_DIR\trapping_source -n TRAP_SRC_COUNT --strategy random --seed 99

# 6. Generate trapping clips
$trapSrc = "C:\my\repos\P.808\src\trapping clips\source"
$trapOut = "C:\my\repos\P.808\src\trapping clips\output"
Get-ChildItem $trapSrc -File | Remove-Item -Force
if (Test-Path $trapOut) { Get-ChildItem $trapOut -File | Remove-Item -Force }
Copy-Item "DATA_DIR\trapping_source\*.wav" $trapSrc -Force
python create_trapping_stimuli.py --cfg configurations\TRAPPING_CFG

# 7. Upload trapping clips + create trapping_clips.csv
python utils\copy_to_pub_storage.py upload -i "$trapOut\output_report.csv" -c trapping_clips -l $trapOut -a STORAGE_ACCOUNT -t CONTAINER -d PROJECT/trapping
Copy-Item "$trapOut\output_report_public.csv" DATA_DIR\trapping_clips.csv

# 8. Create project config (see section 6 template)
# 9. Run master script
Set-Location DATA_DIR
python C:\my\repos\P.808\src\master_script.py --project PROJECT --method METHOD --cfg CONFIG.cfg --clips rating_clips.csv --training_clips training_clips.csv --gold_clips gold_clips.csv --trapping_clips trapping_clips.csv
```

## Known issues

1. **Config values must not be quoted.** `bw_min: NB-WB` works; `bw_min: "NB-WB"` causes an
   assertion error in `extend_general_cfg_bw()`.
2. **`quantity_hits_more_than` warning.** If the computed session count is small, the script
   warns about this value. Set it to approximately `floor(sessions / 2)`, minimum 2.
3. **Gold clips method mismatch for P.835.** `create_gold_clips.py --method p835` produces
   per-dimension columns but `create_input.py` expects `gold_clips_ans`. Use `--method acr`
   for plain P.835 studies.

## Utility scripts reference

| Script | Purpose |
|--------|---------|
| `src\utils\download_clips.py` | Download clips from URLs in a CSV to local directory |
| `src\utils\select_training_clips.py` | Select N evenly-spaced training clips from rating clips |
| `src\utils\copy_to_pub_storage.py` | Upload clips to Azure Blob Storage (direct via `az login`) or prepare azcopy commands |
| `src\utils\preview_html.py` | Generate local preview HTML from master script output |
| `src\create_gold_clips.py` | Generate gold standard clips from clean source WAVs |
| `src\create_trapping_stimuli.py` | Generate trapping stimuli by overlaying messages on source clips |
