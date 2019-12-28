[Home](../README.md) > Analyzing Data

# Analyzing Data

When your Batch is finished, download the answers either using the AMT website or the mturk_utils script (depending to 
the method used to create the Batch). 

1. Modify `condition_pattern` in your result parser config file i.e.`YOUR_PROJECT_NAME_ccr_result_parser.cfg` which was 
created in the first step ([preparation](preparation.md)).

    Note: The `condition_pattern` specify which part of the clip names refer to the condition name/number that they are
    representing. Clips with the same value on that position, are considered to belong to the same condition and votes 
    assigned to them will be aggregated to create the `per_condition` report.

1. Run `result_parser.py` 
        
    ``` bash
    cd src
    python result_parser.py 
        --cfg RESULT_PARSER.cfg 
        --method ccr 
        --answers DOWNLOADED_BATCH_RESULT.csv
    ```
    Note: Method could be either acr, dcr, or ccr.
    
    Beside the console outputs, following files will be generated:
    
    XXX 
    
## Approve/Reject submissions

## Assign bonises
