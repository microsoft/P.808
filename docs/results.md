[Home](../README.md) > Analyzing Data

# Analyzing Data

When your Batch is finished, download the answers either using the AMT website or the mturk_utils script (depending on 
the method used to create the Batch). 

1. Modify `condition_pattern` in your result parser config file i.e.`YOUR_PROJECT_NAME_ccr_result_parser.cfg` which was 
created in the first step ([preparation](preparation.md)).

    **Note**: In case there is possible to have a condition level aggregation in your dataset, uncomment the `condition_pattern`.
    
    **Note**: The `condition_pattern` specifies which part of the clip file name refers to the condition name/number that they are
    representing. Clips with the same value on that position, are considered to belong to the same condition and votes 
    assigned to them will be aggregated to create the `per_condition` report.
     
    

1. Run `result_parser.py` 
        
    ``` bash
    cd src
    python result_parser.py ^
        --cfg your_configuration_file.cfg ^ 
        --method ccr  ^
        --answers downloaded_batch_result.csv ^
        --quantity_bonus all ^
        --quality_bonus
    ```
    * `--cfg` use the configuration file generated for your project in the [preparation](preparation.md) step here (i.e.`YOUR_PROJECT_NAME_ccr_result_parser.cfg`).
    * `--method` could be either `acr`, `dcr`, or `ccr`.
    * `--quantity_bonus` could be `all`, or `submitted`. It specify which assignments should be considered when calculating
    the amount of quantity bonus (everything i.e. `all` or just the assignments with status submitted i.e. `submitted`).
    
    Beside the console outputs, following files will be generated in the same directory as the `--answers` file is located in.
    All file names will start with the `--answers` file name.   
    * `[downloaded_batch_result]_data_cleaning_report`: Data cleansing report. Each line refers to one line in answer file. 
    * `[downloaded_batch_result]_accept_reject_gui.csv`: A report to be used for approving and rejecting assignments. One line
    for each assignment which has a status of "submitted". 
    * `[downloaded_batch_result]_votes_per_clip.csv`: Aggregated result per clip, including MOS, standard deviations, and 95% Confidence Intervals.  
    * `[downloaded_batch_result]_votes_per_cond.csv`: Aggregated result per condition.
    * `[downloaded_batch_result]_quantity_bonus_report.csv`: List of workers who are eligible for quantity bonus with the amount of bonus (to be used with the mturk_utils.py).
    * `[downloaded_batch_result]_quality_bonus_report.csv`: List of workers who are eligible for quality bonus with the amount of bonus (to be used with the mturk_utils.py).     
    
## Approve/Reject submissions

Depending to how you create the HITs (using the AMT website or script) you should use the same method for approving/rejecting
submission.

### Approve/Reject submissions - using website.
 
 1. Go to “**Manage**”> “**Results**”> find your *Batch* and select “**Review Results**”.
   
 1. Click on "**Upload CSV**" and upload the `[downloaded_batch_result]_accept_reject_gui.csv` file.
 
### Approve/Reject submissions - using script/API.

 1. Run the following script:
 
    ```bash
    cd src
    python mturk_utils.py ^
        --cfg mturk.cfg ^
        --approve_reject [downloaded_batch_result]_accept_reject_gui.csv  
    ```
    

## Assign bonuses

 1. Run the following script with both `[downloaded_batch_result]_quantity_bonus_report.csv` and 
 `[downloaded_batch_result]_quality_bonus_report.csv`:
 
    ```bash
    cd src
    python mturk_utils.py ^
        --cfg mturk.cfg ^
        --send_bonus [downloaded_batch_result]_*_bonus_report.csv
    ```
   