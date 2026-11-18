[Home](../README.md) > [Preparation](preparation.md) > Preparation of DCR/CCR test

# Preparation of DCR/CCR test

The following steps should be performed to prepare the DCR/CCR test setup.
For all the resource files (steps 1-4) an example is provided in `src/test_inputs` using the ITU-T Sup23 Dataset.  

**Note**: make sure to first perform steps listed in the [general preparation process](preparation.md).

**Note**: Within DCR and CCR method, the quality of a speech clip is compared to a `reference` clip e.g. a same clip 
without being artificially processed.  

1. Upload your **speech clips** and the references in a cloud server and create the `rating_clips.csv` file which 
contains all URLs to speech clips in a column named `rating_clips` and URLs to the corresponding reference clips in 
`references`. (see [rating_clips_ccr.csv](../src/test_inputs/rating_clips_ccr.csv) as an example).

    **Note about file names**:
    * Later in the analysis, the clip's file name will be used as a unique key and appears in the results.    
    * In case you have 'conditions' which are represented with more than one clip, you may consider using the condition's 
        name in the clip's file name e.g. xxx_c01_xxxx.wav. When you provide the corresponding pattern, the analysis script 
        will create aggregated results over conditions as well.  


1. Upload your **training clips** in a cloud server and create the `training_clips.csv` file which contains all URLs in a 
column named `training_clips` and URLs to corresponding reference clips in column `training_references` 
(see [training_clips_ccr.csv](../src/test_inputs/training_clips_ccr.csv) as an example).
  
    **Hint**: Training clips are used for anchoring participants' perception, and should represent the entire dataset. 
    They should approximately cover the range from worst to best quality to be expected in the test. It may contain 
    about 5 clips. 

1. Create your custom project by running the master script: 

    1. Configure the project in your config file. See [master script configuration](conf_master.md) for more information.
    
    1. Run master script with all above-mentioned resources as input (following example is for ccr)
        
        ```bash
        cd src
        python master_script.py ^
            --project YOUR_PROJECT_NAME ^
            --method ccr ^
            --cfg your_configuration_file.cfg ^
            --clips rating_clips.csv ^
            --training_clips training_clips.csv 
        ```
        Optionally:
         - Add `--check_urls` to validate that all links in the CSV files are accessible before creating the project. 
         - Add `--create_local_test` to generate a local preview HTML file for testing. See [preview_html](preview_html.md) for details.
         - Add `--general_assets path/to/general.csv` to use a custom general assets CSV instead of the default `assets_master_script/general.csv`.

        Note: file paths are expected to be relative to the current working directory.
    
    1. Double-check the outcome of the script. A folder should be created with YOUR_PROJECT_NAME in current working 
    directory which contains: 
    * `YOUR_PROJECT_NAME_ccr.html`: Customized HIT app to be used in Amazon Mechanical Turk (AMT).
    * `YOUR_PROJECT_NAME_publish_batch.csv`: List of dynamic content to be used during publishing batch in AMT.
    * `YOUR_PROJECT_NAME_ccr_result_parser.cfg`: Customized configuration file to be used by `result_parser.py` script
        
Now, you are ready for running the test on [Prolific](running_test_prolific.md) or [Amazon Mechanical Turk](running_test_mturk.md).

## CCR listening-device availability

Eligibility passes when any selected device meets `required_playback_device` (`headset`,
`loudspeaker` or `any`). Acoustic checks verify the active device and audibility.

## Optional: vary session bundles

In DCR/CCR a *comparison* is one A/B pair of clips that a listener hears one after the other. A *session*
is one listener's single sitting (one HIT); its *bundle* is the set of main comparisons assigned to it,
not counting training and controls.

Use `src/pack_sessions.py` when every comparison must be rated several times by different
listeners and the make-up of each session matters. The built-in `random` strategy shuffles the clip
list once and `balanced_block` balances conditions; neither controls how often a comparison is
repeated, which clip plays first, or which comparisons share a session. The script plans this offline,
before `master_script.py` runs, and guarantees:

* each comparison appears exactly `--repeats` times, half of them with A played first (`ab`) and half with B
  played first (`ba`), so a listener bias for the first or second clip cancels out for every comparison;
* no comparison appears twice in a bundle, and with `--group-column` no two comparisons from the same
  source (e.g. scene) share a bundle, so a listener does not hear the same material twice in one session;
* with `--stratum-column` and `--quota`, every bundle holds a fixed number of comparisons per stratum;
* all bundles are distinct, and a seeded local search lowers how often two comparisons are heard
  together, so a rating is not always given in the same context;
* the same input and seed give the same output, and the audit JSON records settings, hashes and balance
  statistics. Existing output files are never overwritten, and settings that would need padding are rejected.

The input is a CSV with one row per comparison: a unique ID plus optional group and stratum columns.

```powershell
python src\pack_sessions.py --input comparisons.csv --output assignments.csv --audit assignment_audit.json `
    --id-column comparison_id --group-column scene --stratum-column stratum `
    --quota representative=10 --quota supplementary=10 --session-size 20 --repeats 10 --seed 42
```

`--repeats` must be positive and even; session counts and quotas must fit exactly. The output is
an assignment plan (`bundle_id`, `position`, `item_id`, `order`), not a publish-batch CSV. Add
training and controls separately, and route participants to avoid repeated comparisons.

To use the plan, convert it to a prepacked sessions file: one row per `bundle_id`, with the bundle's
comparisons (plus any controls) as `Q0_R`/`Q0_P`, `Q1_R`/`Q1_P`, and so on. `Qn_R` is the first clip of
the canonical pair (A) and `Qn_P` the second (B). Playback order and pair IDs are honored with
`comparison_metadata: true` (below): copy each assignment's `order` to `Qn_ORDER` and its `item_id` to
`Qn_ID`; `ab` plays A first and `ba` plays B first. The script does not write this file itself.

### Prepacked assignments

For CCR/DCR, set `clip_packing_strategy: prepacked` and `prepacked_sessions` in `[create_input]`
to use such a file instead of the built-in strategies.
Each row needs `Q0_R`/`Q0_P` through the configured comparison count. Other columns are preserved;
supply the usual source-clip and training CSVs.

For CCR, `comparison_metadata: true` in `[hit_app_html]` requires prepacked `Qn_ID`, `Qn_ROLE`,
`Qn_ORDER` and `Qn_EXPOSURE` columns, which follow comparisons when screen positions are randomized.
IDs must be nonempty, each ID must always name the same audio pair and role, and roles must be
`main`, `identical` or `contrast`. IDs and nonempty exposure values may contain only letters,
digits, `_`, `.`, `:` and `-`.
When online qualification is enabled, CCR/DCR requires all five bandwidth-check answers to match
their supplied hashes; `bw_min` does not relax that client-side check, and `bw_max` must be `FB`.
Training rows may specify `order` (`ab`, `ba` or empty) and an optional `pair_id`, exported
as `Tn_ID` with each shuffled practice comparison. Use only letters, digits, `_`, `.`, `:`
or `-` in the ID. `append_training_trap: false` omits the appended training comparison.

An optional `presentation_file` loads trusted JSON fields `title`, `style`, `script`,
`instructions`, `training` and `rating`. Custom replacements must retain stock IDs, containers,
prerequisites and native qualification/device/setup/form behavior. Omitting `training` or `rating`
keeps the native panels; training order is randomized unless `randomize_training_questions: false`.

Set `aggregate_by_pair_id: true` in `[create_input]` to aggregate CCR by comparison ID. This
requires `comparison_metadata: true` and roles `main`,
`identical` or `contrast`, exports raw
trials/control candidates before filtering, and excludes controls from comparison means. Contrast
controls use degraded A and clean B. In this mode, `file_url` contains the comparison ID, while
`condition_pattern` is still matched against the processed audio URL. CCR scores
already express B-minus-A; the audit separately reconstructs second-minus-first.