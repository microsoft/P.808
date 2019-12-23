# Preparation of ACR test

The following steps should be performed to prepare the ACR test setup.
For all the resource files (steps 1-4) an example is provided in `src/test_inputs`  using the ITU-T Sup23 Dataset.  

**Note**: make sure to first perform steps listed in the [general preparation process](preparation.md).


1. Upload your **speech clips** in a cloud server and create the `rating_clips.csv` file which contains all URLs in a 
column name `rating_clips` (see [rating_clips.csv](../src/test_inputs/rating_clips.csv) as an example).

1. Upload your **training clips** in a cloud server and create the `training_clips.csv` file which contains all URLs in a 
column name `training_clips` (see [training_clips.csv](../src/test_inputs/training_clips.csv) as an example).
  
    **Hint**: Training clips are used for anchoring participants perception, and should represent the entire dataset. 
    They should approximately cover the range from worst to best quality to be expected in the test. It may contain 
    about 5 clips. 

1. Upload your **gold standard clips** in a cloud server and create the `gold_clips.csv` file which contains all URLs in a 
column name `gold_clips` and expected answer to each clip in a column name `gold_clips_ans` 
(see [gold_clips.csv](../src/test_inputs/gold_clips.csv) as an example).
  
    **Hint**: Gold standard clips are used as a hidden quality control item in each session. It is expected that their 
    answers are so obvious for all participants that they all give the `gold_clips_ans` rating (+/- 1 deviation is 
    accepted). It is recommended to use clips with excellent (answer 5) or very bad (answer 1) quality.
    
1. Create trapping stimuli set for your dataset.

1. Upload your **trapping clips** in a cloud server and create the `trapping_clips.csv` file which contains all URLs in 
a column name `trapping_clips` and expected answer to each clip in a column name `trapping_ans` 
(see [trapping_clips.csv](../src/test_inputs/trapping_clips.csv) as an example).

1. Create your custom project by running the master scrip: 

    6.1. Configure the the project in your config file. See [master script configuration](conf_master.md) for more information.
    
    6.2. Run master script with all above-mentioned resources as input
        
    ``` bash
    cd src
    python master_script.py 
        --project YOUR_PROJECT_NAME
        --method acr
        --cfg your_configuration_file.cfg
        --clips rating_clips.csv
        --training_clips training_clips.csv
        --gold_clips gold_clips.csv
        --trapping_clips trapping_clips.csv
    ```
    Note: file path are expected to be relative to the current working directory.
    
    6.3. Double check the outcome of script: A folder should be create with YOUR_PROJECT_NAME in current working 
    directory which contains: 
    * `YOUR_PROJECT_NAME_acr.html`: Customized HIT app to be used in Amazon Mechanical Turk (AMT).
    * `YOUR_PROJECT_NAME_publish_batch.csv`: List of dynamic content to be used during publishing batch in AMT.
    * `YOUR_PROJECT_NAME_acr_result_parser.cfg`: Customized configuration file to be used by `result_parser.py` script
        
Now, you are ready for [Running the Test on Amazon Mechanical Turk](docs/running_test_mturk.md).