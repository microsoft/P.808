# Scripts
Here you find scripts that might be useful during the process of conducting an experiment based on P.808 using MTurk.

## mturk_utils
Set of utility commands based on MTurk python package ([Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/mturk.html#MTurk.Client.reject_assignment))

To use the utilities first you need to provide your 'AWS Access Key' and 'AWS Secret Key' ([see here](https://requester.mturk.com/developer)) .
Put them in the corresponding field of configuration file. `[CONFIG_FILE]` refers to the path to configuration file and
needs to be provided to the script (`--cfg [CONFIG_FILE]`).
Note, the script looks into mturk.cfg if no other path is provided as argument.
Install required packages using following command:

```
pip install -r mturk_utilis_requirements.txt
```

#### assign_bonus
usage
```
python mturk_utils.py --cfg [CONFIG_FILE] --send_bonus cfgs_and_inputs/bonus.csv 
```
`[CONFIG_FILE]` path to the configuration file.

The bonus.csv should have following columns: workerId, assignmentId, bonusAmount, reason.

#### approve
usage
```
python mturk_utils.py --cfg [CONFIG_FILE] --approve cfgs_and_inputs/approve.csv 
```
`[CONFIG_FILE]` path to the configuration file.

The approve.csv should have following columns: assignmentId


#### reject
usage
```
python mturk_utils.py --cfg [CONFIG_FILE] --reject cfgs_and_inputs/reject.csv 
```

`[CONFIG_FILE]` path to the configuration file.

The reject.csv should have following columns: assignmentId,feedback

#### send_emails
usage
```
python mturk_utils.py --cfg [CONFIG_FILE] send_emails 
```

`[CONFIG_FILE]` path to the configuration file.

Script reads the settings from the section `[send_emails]` in configuration file.
From that section, edit `subject`,`message`(subject and body of message to be sent) and `worker_ids` 
(comma separated list of workerIds whom the message will be sent to). 
Add your MTurk_id in `requester_client_id` to include a link to your 
currently running HITs in the message. 


#### create_hit
usage 

```
python mturk_utils.py --cfg [CONFIG_FILE] --create_hit ../P808Template/create_acr_hit.cfg 
--create_hit_input ../P808Template/input.csv  
```

`[CONFIG_FILE]` path to the configuration file.

Create one or more HITs in MTurk. The AssignmentReviewPolicy is just applicable when HITs are created using API.
This command creates one HIT per row in the input.csv file. See `--create_hit_input ../P808Template/input.csv` 
 for details. It generates a report as well to be used with 
`--answers` command later to download the worker's answers. Note that HITs created using API are not visible
in the GUI.


#### answers
usage 

```
python mturk_utils.py --cfg [CONFIG_FILE] --answers [REPORT_FILE]   
```

`[CONFIG_FILE]` path to the configuration file.

Check the status of HITs listed in the [REPORT_FILE] (i.e. outcome of '--create_hit' e.f. Batch_fdhdgede_123.csv)) 
file, and download all answers available for them. As HITs created using API are not visible in the GUI, this 
command should be used to get the results.

#### create_qualification_type
usage

```
python mturk_utils.py --cfg [CONFIG_FILE] --create_qualification_type cfgs_and_inputs/qualification_type.cfg

```

`[CONFIG_FILE]` path to the configuration file.

Create a new Qualification Type Without Test given the configuration. A name and description are needed.
See `cfgs_and_inputs/qualification_type.cfg` for more details.


#### assign_qualification_type

usage
```
python mturk_utils.py --cfg [CONFIG_FILE] --assign_qualification_type cfgs_and_inputs/assign_qualification.csv
```
`[CONFIG_FILE]` path to the configuration file.

For each row of `assign_qualification.csv` assign the given qualification and its value to the worker.
The csv file should have following columns: `workerId`, `qualification_name` ,`value`


## create_trapping_stimuli
Script to create set of trapping stimuli (Gold standard questions) based on the ITU-T Rec. P.808 (section 6.3.8) and 
tailored to the test dataset.
Install required packages using following command:

```
pip install -r create_trapping_stimuli_requirements.txt
```

How to use it?

```
python create_trapping_stimuli.py --cfg trapping.cfg 
```
The `input_directory` should have the following structure:

`[input_directory]\messages\`: Directory containing all recorded messages. To create a trapping stimulus, one message
 will be appended to the first seconds of a source stimulus.

`[input_directory]\source\`: Directory containing all source recordings which will be used to create trapping stimuli 
dataset.

 It is recommended to:
  > Five stimuli per each speaker from the dataset should be randomly selected, reflecting different degradation conditions. 
 
`[input_directory]\output\`: Directory which will contain the generated trapping stimuli.
  
  
## process_qualification_ans
Script can be used to select workers given their answers to the qualification job.
Install required packages using following command:
 
 ```
pip install -r process_qualification_ans_requirments.txt
```

How to use it?

```
python process_qualification_ans.py --check [ANSWER_FILE]
```
The `ANSWER_FILE` is a csv file you download from MTurk. A sample is given in 
`cfgs_and_inputs/Batch_256535_batch_results.csv`. 
The configuration that script uses to make the decisions can also be edited.
Open the script code, on top you find the `config` object:

```
config= {
    # criteria to accept/reject one workers
    'acceptance_criteria': {
        # which questions to include
        'consider_fileds': ['3_mother_tongue', '4_ld', '7_working_area', '8_hearing'],
        # how many of answers to hearing test should be correct
        'correct_hearing_test_bigger_equal': 3
    },
    # correct answers to each question
    '3_mother_tongue': ['english','en'],
    '4_ld':['in-ear','over-ear'],
    '5_last_subjective':['7d','30d','nn'],
    '6_audio_test':['7d','30d','nn'],
    '7_working_area':['N'],
    '8_hearing':['normal'],
    'hearing_test':{
        'num1':'289',
        'num2':'246',
        'num3':'626',
        'num4':'802',
        'num5':'913'
    }
}

````

## create_input_acr

Script can be used to create the input.csv for the ACR hitapp. 
Install required packages using following command:
 
 ```
pip install -r create_input_acr_requirments.txt
```

How to use it?

```
python create_input_acr.py --cfg [CONFIG_FILE] --row_input [ROW_INPUT]
```
Check `cfgs_and_inputs/create_input.cfg` as a sample for `[CONFIG_FILE]` and 
`cfgs_and_inputs/row_input_librivox.csv` for `[ROW_INPUT]`.


## acr_result_parser

Script to evaluate result of acr test. 
Install required packages using following command:
 
 ```
pip install -r acr_result_parser_requirments.txt
```

How to use it?

```
python acr_result_parser.py --answers [ANSWERS_CSV] --cfg [CONFIG_FILE] --quantity_bonus [submitted|all]  \--quality_bonus
```

* `[ANSWERS_CSV]`: The `Batch_XYZ_batch_results.csv` file you download from MTurk
* `[CONFIG_FILE]`: Configuration file which contain criteria for acceptance/rejection, bonus assignments, correct answers, and etc (project specific).
* `--quantity_bonus [submitted|all]`: Calculate the bonus report based on the quantity of work (how many accepted answers are submitted by
particular worker). "Submitted" just consider answers with status of submitted for calculating the amount of bonus. 
* `--quality_bonus`: Call it when you have the final result of your project. It calculates the quality bonus (top 20% of people who got the 
quantity bonus).

Correct answers to the math, environment test and trapping questions are given in the `config` file. 

 