# Scripts
Here you find scripts that might be useful during the process of conducting an experiment based on P.808 using MTurk.

## mturk_utils
Set of utility commands based on MTurk python package ([Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/mturk.html#MTurk.Client.reject_assignment))

To use the utilities first you need to provide your 'AWS Access Key and AWS Secret Key', [see here](https://requester.mturk.com/developer)
Put them in the corresponding field of configuration file.
Note, the script looks into mturk.cfg if no other path is provided as argument.
Install required packages using following command:

```
pip install -r mturk_utilis_requirements.txt
```

#### assign_bonus
usage
```
python mturk_utils.py --send_bonus cfgs_and_inputs/bonus.csv 
```
the bonus.csv should have following columns: workerId, assignmentId, bonusAmount, reason

#### approve
usage
```
python mturk_utils.py --approve cfgs_and_inputs/approve.csv 
```
the approve.csv should have following columns: assignmentId

#### reject
usage
```
python mturk_utils.py --reject cfgs_and_inputs/reject.csv 
```
the reject.csv should have following columns: assignmentId,feedback

#### send_emails
usage
```
python mturk_utils.py send_emails 
```
script reads the configuration from the section `[send_emails]` in config file.

#### create_hit
usage 

```
python mturk_utils.py --create_hit ../P808Template/create_acr_hit.cfg --create_hit_input ../P808Template/input.csv  
```

Crate one or more HITs in MTurk. The AssignmentReviewPolicy is just applicable when HITs are created using API.
This command create one HIT per a row in the input.csv file. See `--create_hit_input ../P808Template/input.csv` 
 for details. It generates a report as well to be used with 
`--answers` command later to download the worker's answers. Note that HITs created using API are not visible
in the GUI.


#### answers
usage 

```
python mturk_utils.py --answers [REPORT_FILE]   
```

Check the status of HITs listed in the [REPORT_FILE] (i.e. outcome of '--create_hit' e.f. Batch_fdhdgede_123.csv)) 
file, and download alla answers available for them. As HITs created using API are not visible in the GUI, this 
command should be used to get the results.

#### create_qualification_type
usage

```
python mturk_utils.py --create_qualification_type cfgs_and_inputs/qualification_type.cfg

```

Create a new Qualification Type Without Test given the configuration. A name and description are needed.
See `cfgs_and_inputs/qualification_type.cfg` for more details.


#### assign_qualification_type

usage
```
python mturk_utils.py --assign_qualification_type cfgs_and_inputs/assign_qualification.csv
```
for each row of `assign_qualification.csv` assign the given qualification and its value to the worker.
The csv file should have following columns: `workerId`, `qualification_name` ,`value`


## create_trapping_stimuli
Script to create set of trapping stimuli(Gold standard question) based on the ITU-T Rec. P.808 (section 6.3.8) and 
tailored to the test dataset.
Install required packages using following command:

```
pip install -r create_trapping_stimuli_requirements.txt
```

How to use is?

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
  