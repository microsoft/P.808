[Home](../README.md) > [Preparation](preparation.md) > Preparation of DCR/CCR test

# Preparation of DCR/CCR test

The following steps should be performed to prepare the DCR/CCR test setup.
For all the resource files (steps 1-4) an example is provided in `src/test_inputs` using the ITU-T Sup23 Dataset.  

**Note**: make sure to first perform steps listed in the [general preparation process](preparation.md).

**Note**: DCR compares a speech clip to a reference, for example the same clip without artificial
processing. CCR can also compare two alternatives with no clean reference, such as microphones
recording the same scene. The CSV column `references` then labels canonical A, not a known better
recording; see [Prepacked sessions](prepacked_sessions.md).

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

Use offline session planning when comparisons need repeated ratings with varied companions,
source-scene exclusion, stratum quotas or exact CCR playback-order balance. The
[Prepacked sessions guide](prepacked_sessions.md) explains the microphone-comparison use case and
provides a complete `pack_sessions.py` -> `convert_assignments.py` -> `master_script.py` walkthrough.
The usual `random` and `balanced_block` strategies remain available for simpler designs.

### Prepacked assignments

Set `clip_packing_strategy: prepacked` and `prepacked_sessions` in `[create_input]` to load a
wide-format session CSV instead of generating memberships. Supply the normal clip and training
CSVs as well. See the guide for [generation commands](prepacked_sessions.md#worked-ccr-pipeline),
[metadata and controls](prepacked_sessions.md#controls-and-format-details), and
[DCR compatibility](prepacked_sessions.md#dcr-compatibility).

## CCR practice and presentation

When online qualification is enabled, CCR/DCR requires all five bandwidth-check answers to match
their supplied hashes; `bw_min` does not relax that client-side check, and `bw_max` must be `FB`.
Training rows may specify `order` (`ab`, `ba` or empty) and an optional `pair_id`, exported
as `Tn_ID` with each shuffled practice comparison. Use only letters, digits, `_`, `.`, `:`
or `-` in the ID. `append_training_trap: false` omits the appended training comparison.
An optional `practice_example` column is passed through to custom presentation scripts for
practice-specific feedback; it has no effect in the stock template.

An optional `presentation_file` loads trusted JSON fields `title`, `style`, `script`,
`instructions`, `training` and `rating`. Custom replacements must retain stock IDs, containers,
prerequisites and native qualification/device/setup/form behavior. Omitting `training` or `rating`
keeps the native panels; training order is randomized unless `randomize_training_questions: false`.
