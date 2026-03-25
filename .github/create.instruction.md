# Create subjective test instructions

Use this runbook when an agent is asked to create and publish a new subjective video quality test with the P.910 toolkit.

## Best-practice variables

These are best-practice defaults, not hard requirements. Confirm or override them with the requester before execution.

```text
BEST_PRACTICE_PLATFORM=Prolific
BEST_PRACTICE_DEFAULT_SCALE_ACR_DCR=5
BEST_PRACTICE_DEFAULT_SCALE_CCR=7
BEST_PRACTICE_VALID_VOTE_BUFFER=20%
BEST_PRACTICE_GOLD_SOURCE_SAMPLE_RATE=5%
BEST_PRACTICE_TRAPPING_SOURCE_SAMPLE_RATE=5%
BEST_PRACTICE_MAX_GOLD_SOURCE_CLIPS=20
BEST_PRACTICE_MAX_TRAPPING_SOURCE_CLIPS=20
BEST_PRACTICE_MIN_DEVICE_RESOLUTION=1920x1080
BEST_PRACTICE_ALLOWED_MAX_HITS=min(int(number_of_rating_clips / 10), 50)
BEST_PRACTICE_VIDEO_PLAYBACK=no-scale
```

## Scope

This instruction covers:

1. Preparing inputs for `acr`, `acr-hr`, `dcr`, or `ccr`.
2. Generating gold clips and trapping clips when needed.
3. Running `master_script.py` to build the project.
4. Publishing the generated test through the HITAPP Server.
5. Handing off the generated project for publishing on the chosen crowd platform.

Platform note:

1. Prolific is the recommended crowd platform for this guide.
2. The repository README links to an external Prolific wiki, but does not contain a full in-repo Prolific publishing tutorial.
3. The repository does contain an in-repo AMT guide at `docs\running_test_mturk.md`.
4. Setting up the HIT in HITApp server and publishing it on crowdsourcing platform should be done by the user, following the instrudction.

## Mandatory pre-check

Before editing or running anything in this repository:

1. Read `AGENTS.md`.
2. Read `.github\copilot-instructions.md`.
3. Confirm that the task is a creation or publishing task, not a result-analysis task. If it is an analysis task, use `.github\evaluate.instruction.md` instead.

## Inputs the agent must confirm

Do not guess these values if they are missing:

1. Test method: `acr`, `acr-hr`, `dcr`, or `ccr`.
2. Crowd platform: Prolific, AMT, or another panel.
3. Whether a HITAPP Server already exists, and if so, its URL.
4. The project name to use for generated outputs.
5. Where the rating, training, gold, and trapping media are stored or should be uploaded.
6. The rating scale to use.
	- `acr`, `acr-hr`, `dcr`: usually `5` or `9`; if unspecified, suggest `BEST_PRACTICE_DEFAULT_SCALE_ACR_DCR`.
	- `ccr`: usually `4` or `7`; if unspecified, suggest `BEST_PRACTICE_DEFAULT_SCALE_CCR`.
7. Worker requirements, payment, target countries, and maximum assignments per worker in case of AMT. For Prolific, only maximum assignments per worker.
8. The target number of valid votes per clip.
	- If the requester specifies `X` valid votes per clip and asks for a planning heuristic, suggest publishing about `X` plus `BEST_PRACTICE_VALID_VOTE_BUFFER` to absorb rejects and unusable sessions.
9. Whether condition-level aggregation is needed later, because that affects `condition_pattern` and clip naming.

## Execution workflow

### 1. Prepare the environment

1. Work from the repository root.
2. Install Python dependencies for the main toolkit:

```powershell
Set-Location C:\my\repos\internal_p910\src
pip install -r requirements.txt
```

3. If trapping clips must be generated, also install the extra trapping dependency set:

```powershell
Set-Location C:\my\repos\internal_p910\src\trapping_clips
pip install -r requirements.txt
```

4. If the requester needs a new HITAPP Server, first ask whether the team already has a managed installation. If not, point them to `hitapp_server\README.md`. Do not deploy infrastructure on your own unless the requester explicitly wants that and the required security review is already approved.

### 2. Prepare public media and static assets

1. Upload the PVS clips and any required source clips to publicly reachable storage.
2. Make sure the public storage allows CORS with `Access-Control-Allow-Origin: *`.
3. Prefer a CDN for video delivery when available.
4. If the user currently has private blob URLs or blob-relative paths, confirm how those should be converted into public URLs before editing CSVs.
5. A helper script exists at `src\utility\copy_to_pub_storage.py`. Review and adapt it before using it.
6. If general UI assets are not already hosted, upload the files from `src\template\assets\imgs` and update the links described in `docs\general_res.md`.

### 3. Build the required CSV inputs

Use the files in `sample_inputs\` as concrete examples.

Required CSV shapes by method:

1. `rating_clips.csv`
	- `acr`: column `pvs`
	- `acr-hr`: columns `pvs`, `src`
	- `dcr` or `ccr`: columns `pvs`, `src`
2. `training_clips.csv`
	- `acr`: column `training_pvs`
	- `acr-hr`, `dcr`, `ccr`: columns `training_pvs`, `training_src`
3. `gold_clips.csv`
	- `acr`: columns `gold_clips_pvs`, `gold_clips_ans`
	- `acr-hr`: same shape as `acr`
	- `dcr` or `ccr`: columns `gold_clips_pvs`, `gold_clips_src`, `gold_clips_ans`
4. `trapping_clips.csv`
	- `acr`: columns `trapping_pvs`, `trapping_ans`
	- `acr-hr`: same shape as `acr`
	- `dcr` or `ccr`: columns `trapping_pvs`, `trapping_src`, `trapping_ans`

Clip naming guidance:

1. Use stable file names, because the parser later uses the clip file name as a key.
2. If one condition spans multiple clips, encode the condition in the file name and carry that through into `condition_pattern`.

### 4. Generate gold clips if they do not already exist

`src\gold_clips\create_gold_clips.py` only supports `acr` and `ccr` as `--test_method` values.

Use:

1. `acr` for both `acr` and `acr-hr` projects.
2. `ccr` for both `dcr` and `ccr` projects.

Input guidance:

1. `input_csv` should list source clips from the same dataset as the one being studied.
2. Those source clips should be available locally before running the script.
3. For `dcr` or `ccr`, a reasonable source of candidate references is the `src` column from `rating_clips.csv`.
4. If the requester asks for a heuristic and no project rule exists, suggest selecting about `BEST_PRACTICE_GOLD_SOURCE_SAMPLE_RATE` of the source clips, capped at `BEST_PRACTICE_MAX_GOLD_SOURCE_CLIPS`.
5. Given any error, stop and provide the message to requester. 
6. Check the number of generated clips, it depends to the number of source clips and the test method.

Example:

```powershell
Set-Location C:\my\repos\internal_p910\src\gold_clips
python create_gold_clips.py `
	--input_csv YOUR_INPUT.csv `
	--test_method acr `
	--output_dir YOUR_OUT_DIR
```

After generation:

1. Upload the produced gold clips to public storage.
2. The generated clip list and answers are saved to `{output_dir}\{test_method}_gold_clips.csv`.
3. Save a copy of that file as `gold_clips.csv` next to `rating_clips.csv`.
4. Update `gold_clips.csv` so it uses the method-specific column names and the final hosted clip URLs.

### 5. Generate trapping clips if they do not already exist

1. Copy `src\configurations\trappings.cfg` and edit the copy.
2. Note that the actual sample file on disk is `trappings.cfg` with an `s`, even though some docs refer to `trapping.cfg`.
3. Put representative source clips into a staging folder such as `tp_src`.
	- Use clips from the same dataset the user wants to evaluate.
	- Avoid using same set of clips as gold clips.
	- For `dcr` or `ccr`, you can use reference clips from the `src` column of `rating_clips.csv` if needed.
	- If the requester asks for a heuristic and no project rule exists, suggest selecting about `BEST_PRACTICE_TRAPPING_SOURCE_SAMPLE_RATE` of the evaluated clips, capped at `BEST_PRACTICE_MAX_TRAPPING_SOURCE_CLIPS`.
4. Update `scale_min` and `scale_max` in `trappings.cfg` so they match the selected test method and rating scale.

Example:

```powershell
Set-Location C:\my\repos\internal_p910\src\trapping_clips
python create_trapping_clips.py `
	--source tp_src `
	--des tp_out `
	--cfg YOUR_TRAPPINGS_CFG
```

Then:

1. Upload the generated trapping clips to public storage.
2. The clip list and expected answers will be saved in `tp_out\output_report.csv`.
3. Use `tp_out\output_report.csv` to build `trapping_clips.csv` with the correct method-specific columns and the final hosted clip URLs.
4. Save a copy of `trapping_clips.csv` next to `rating_clips.csv`.

### 6. Configure `master_script.py`

1. Copy `src\configurations\master.cfg` or `sample_inputs\master.cfg` to a project-specific config file.
2. Review at minimum:
	- `condition_pattern` and `condition_keys` if condition-level analysis will be needed
	- `scale`
	- `video_player`
	- `allowed_max_hit_in_project`
	- `min_device_resolution`
3. `video_player` supports values such as `no-scale`, `max-height`, or a percentage like `80%`. These control scaling, not browser full-screen mode. Use `BEST_PRACTICE_VIDEO_PLAYBACK` if nothing specified.
4. If the requester wants heuristics and does not provide values:
	- suggest `BEST_PRACTICE_ALLOWED_MAX_HITS` for `allowed_max_hit_in_project`
	- suggest `BEST_PRACTICE_MIN_DEVICE_RESOLUTION` for `min_device_resolution`

### 7. Run the master script

Example:

```powershell
Set-Location C:\my\repos\internal_p910\src
python master_script.py `
	--project YOUR_PROJECT_NAME `
	--method acr `
	--cfg YOUR_MASTER_CFG `
	--clips rating_clips.csv `
	--training_clips training_clips.csv `
	--gold_clips gold_clips.csv `
	--trapping_clips trapping_clips.csv `
	--check_urls
```

Validation notes:

1. Keep paths relative to the current working directory when following the documented flow.
2. Keep `--method` aligned with the actual study type: `acr`, `acr-hr`, `dcr`, or `ccr`.
3. Review console warnings carefully. If the warning is only about `quantity_hits_more_than` and the study will not use the AMT bonus workflow, confirm with the requester whether it can be ignored.

### 8. Verify the generated project artifacts

The output project directory should contain:

1. `YOUR_PROJECT_NAME\YOUR_PROJECT_NAME_METHOD.html`
2. `YOUR_PROJECT_NAME\YOUR_PROJECT_NAME_publish_batch.csv`
3. `YOUR_PROJECT_NAME\YOUR_PROJECT_NAME_METHOD_result_parser.cfg`

Do not hardcode a `_dcr` suffix when validating outputs. The actual file names are method-based in code, for example `myproj_acr.html` and `myproj_acr_result_parser.cfg`.

### 9. Publish through the HITAPP Server

Ask requester to follow instruction to publish the HITs in HITAPP server.

### 10. Publish through the crowd platform

For Prolific:

1. Prolific is the recommended platform for this guide.
2. The README points to an external Prolific wiki rather than a full in-repo guide.
3. If the requester has an approved team workflow for Prolific study creation, follow it.
4. Otherwise, hand off the generated project files and ask the requester to provide the exact Prolific publishing process they want the agent to follow.

For AMT:

1. Follow `docs\running_test_mturk.md`.
2. Use the HITAPP-generated `AMT HIT` and `AMT Input File` artifacts.

### 11. Handoff checklist

Before considering creation complete, make sure you can point to:

1. The project directory generated by `master_script.py`.
2. The exact config files used.
3. The hosted media locations.
4. The HITAPP Server project entry.
5. The platform-specific handoff artifacts that were generated.
6. The method and scale used.
7. Any warnings or deviations from the documented flow.

## Questions that must be answered when missing

If any of the following is unknown, ask the requester before execution or leave the task blocked:

1. Which test method should be used: `acr`, `acr-hr`, `dcr`, or `ccr`?
2. Is the study going to Prolific, AMT, or another platform?
3. Is there an existing HITAPP Server?
4. Where should the media be hosted publicly?
5. Are the source assets currently in private storage, and if so, what is the approved copy or publishing path?
6. Should the agent generate gold clips and trapping clips, or are ready-made CSVs already available?
7. What rating scale should be used?
8. What is the target number of valid votes per clip?
9. Should videos be kept at original resolution, scaled with `max-height`, or set to a fixed percentage?
10. Is condition-level aggregation required later?
11. If Prolific is being used, what exact study-creation workflow should replace the missing in-repo publishing guide?
