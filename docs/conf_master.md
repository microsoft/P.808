[Home](../README.md) > [Preparation](preparation.md) > [Preparation for Absolute Category Rating (ACR)](prep_acr.md)

# Configure for `master_script.py`
 
This describes the configuration for the `master_script.py`. A sample configuration file can be found in [`configurations\master.cfg`](.\src\configurations\master.cfg).

## Command-line arguments

* `--project`: Name of the project (required).
* `--cfg`: Configuration file path (required). See sections below.
* `--method`: Test method — `acr`, `dcr`, `ccr`, `p835`, `pp835`, `p804`, or `echo_impairment_test` (required).
* `--clips`: CSV with rating clip URLs in column `rating_clips`.
* `--gold_clips`: CSV with gold clip URLs and answers.
* `--training_clips`: CSV with training clip URLs.
* `--trapping_clips`: CSV with trapping clip URLs and answers.
* `--training_gold_clips`: CSV with gold training question details (P.804).
* `--general_assets`: Path to the general assets CSV. Defaults to `assets_master_script/general.csv`.
  Use `assets_master_script/general_assets_internal.csv` for projects with internally generated
  math clips (see `utils/generate_math_questions.py`).
* `--check_urls`: Validate that all links in the CSV files are accessible.
* `--create_local_test`: Generate a local preview HTML file after the project is created.
* `--p831_fest`: Use the question set of P.831 for FEST.
 
## `[create_input]`

* `number_of_clips_per_session:10`: Number of clips from "rating_clips" to be included in the "Rating section" of each HIT/listening session. 
* `number_of_trapping_per_session:1`: Number of trapping questions to be included in the "Rating section".
* `number_of_gold_clips_per_session:1`: Number of gold clips to be included in the "Rating section".
* (optional)  `condition_pattern:`: Specifies a regex to extract the condition name from the clip URL. example: 
Assuming the URL is `http://test.com/D501_C03_M2_S02.wav` is the clip URL, and "03" is the condition name. 
The pattern will be `.*_c(?P<condition_num>\d{1,2})_.*.wav`, you should also use condition_keys with `condition_num`.
* (optional)  `condition_keys:` comma separated list of keys appearing in the `condition_pattern`:
* (optional)  `clip_packing_strategy:random`: Either `random` or `balanced_block`. It specifies how to select clips 
which will be assessed in a same HIT. For the `balanced_block` design, `condition_pattern`, `condition_pattern`, and
 `condition_pattern` should be specified.  `number_of_clips_per_session` should be a multiple of the unique values of the 
 key specified in the `block_keys`. 
* (optional)  `block_keys:`:  The key(s) to be used for creating the blocks should be specified here. Up to two keys. 
A comma separated list. For multiple keys, all values of the first key should appear in one block.


## `[hit_app_html]` 
* `cookie_name:itu_p808_sup23_exp3`: A cookie with this name will be used to store the current state of a worker in this project.
 Key attributes like number of assignments answered by the worker, if the training or setup sections are needed. 
 It is a project specific value. 
* `qual_cookie_name:ACR_LISTENER_19_12_2019`: A cookie with this name will show if the user passed the Qualification section.
The cookie expires after 1 month. If a worker could not successfully pass the Qualification section, they will see the 
following message next time they want to perform a HIT from this group:
    ````text
    There is no assignments that match to your profile now. Please try it again in two-weeks time.
    We thank you for your participation.
    ````
* `allowed_max_hit_in_project:60`: Number of assignments that one worker can perform from this project.
* `hit_base_payment:0.5`: Base payment for an accepted assignment from this HIT. This value will be used as information.
* `quantity_hits_more_than: 30`: Defines the necessary hits required for quantity bonus.
* `quantity_bonus: 0.1`: The amount of the quantity bonus to be paid for each accepted assignment.
* `quality_top_percentage: 20`: Defines when quality bonus should be applied (in addition, participant should be 
eligible for quantity bonus).
* `quality_bonus: 0.15`: The amount of the quality bonus per accepted assignment.
* `bw_min: FB `: minimum bandwidth that participants playback should support, can be "NB-WB", "SWB", "FB"
* `bw_max: FB `: maximum bandwidth that participants playback should support, can be "NB-WB", "SWB", "FB"
* (optional) `show_qualification: true`: Whether the in-HIT qualification section is shown (`true`/`false`).
Set to `false` when the qualification is run as a separate study (e.g. a Prolific screener). Default: `true`.
* (optional) `screenout_code_qualification:`: Study-level completion code shown to a participant who fails the
in-HIT **qualification** (bandwidth/hearing) check on their final attempt. They enter it on the crowdsourcing
platform (e.g. Prolific) to be paid for their screening effort.
* (optional) `screenout_code_setup:`: Same as `screenout_code_qualification`, but shown when a participant fails
the **setup** (listening environment/attention) check after the allowed number of attempts.

If a screen-out code is not set, `master_script.py` prints a warning at generation time and leaves the
`${screenout_code_qualification}` / `${screenout_code_setup}` placeholder in the generated HIT so the HIT App
Server can fill it at run time. When neither the configuration nor the server provides a code, the participant is
asked to **return the task** instead of being paid for the screening.


## `[acr_html]` or `[p835_html]` _deprecated_ 
* `cookie_name:itu_p808_sup23_exp3`: A cookie with this name will be used to store the current state of a worker in this project.
 Key attributes like number of assignments answered by the worker, if the training or setup sections are needed. 
 It is a project specific value. 
* `qual_cookie_name:ACR_LISTENER_19_12_2019`: A cookie with this name will show if the user passed the Qualification section.
The cookie expires after 1 month. If a worker could not successfully pass the Qualification section, they will see the 
following message next time they want to perform a HIT from this group:
    ````text
    There is no assignments that match to your profile now. Please try it again in two-weeks time.
    We thank you for your participation.
    ````
* `allowed_max_hit_in_project:60`: Number of assignments that one worker can perform from this project.
* `hit_base_payment:0.5`: Base payment for an accepted assignment from this HIT. This value will be used as information.
* `quantity_hits_more_than: 30`: Defines the necessary hits required for quantity bonus.
* `quantity_bonus: 0.1`: The amount of the quantity bonus to be paid for each accepted assignment.
* `quality_top_percentage: 20`: Defines when quality bonus should be applied (in addition, participant should be 
eligible for quantity bonus).
* `quality_bonus: 0.15`: The amount of the quality bonus per accepted assignment.

## `[dcr_ccr_html]` _deprecated_ 
* `cookie_name:itu_p808_sup23_exp3`: A cookie with this name will be used to store current state of a worker in this project.
 Key attributes like number of assignments answered by the worker, if the training or setup sections are needed. 
 It is a project specific value. 
* `qual_cookie_name:ACR_LISTENER_19_12_2019`: A cookie with this name will show if the user passed the Qualification section.
The cookie expires after 1 month. If a worker could not successfully pass the Qualification section, they will see the 
following message next time they want to perform a HIT from this group:
    ````text
    There is no assignments that match to your profile now. Please try it again in two-weeks time.
    We thank you for your participation.
    ````
* `allowed_max_hit_in_project:60`: Number of assignments that one worker can perform from this project.
* `hit_base_payment:0.5`: Base payment for an accepted assignment from this HIT. This value will be used as information.
* `quantity_hits_more_than: 30`: Defines the quantity bonus requirement.
* `quantity_bonus: 0.1`: The amount of the quantity bonus to be paid for each accepted assignment.
* `quality_top_percentage: 20`: Defines when quality bonus should be applied (in addition, participant should be 
eligible for quantity bonus).
* `quality_bonus: 0.15`: The amount of the quality bonus per accepted assignment.
