# Preparation of DCR/CCR test

The following steps should be performed to prepare the DCR/CCR test setup.
For all the resource files (steps 1-4) an example is provided in `src/test_inputs` using the ITU-T Sup23 Dataset.  

**Note**: make sure to first perform steps listed in the [general preparation process](preparation.md).

**Note**: Within DCR and CCR method, the quality of a speech clip is compared to a `reference` clip e.g. a same clip 
without being artificially processed.  

1. Upload your **speech clips** and the references in a cloud server and create the `rating_clips.csv` file which 
contains all URLs to speech clips in a column name `rating_clips` and URLs to the corresponding reference clips in 
`references`. (see [rating_clips_ccr.csv](../src/test_inputs/rating_clips_ccr.csv) as an example).

1. Upload your **training clips** in a cloud server and create the `training_clips.csv` file which contains all URLs in a 
column name `training_clips` and URLs to corresponding reference clips in column `training_references` 
(see [training_clips_ccr.csv](../src/test_inputs/training_clips_ccr.csv) as an example).
  
    **Hint**: Training clips are used for anchoring participants perception, and should represent the entire dataset. 
    They should approximately cover the range from worst to best quality to be expected in the test. It may contain 
    about 5 clips. 

1. Create your custom project by running the master scrip: 

    6.1. Configure the the project in your config file. See [master script configuration](conf_master.md) for more information.
    
    6.2. Run master script with all above-mentioned resources as input (following example is for ccr)
        
        ``` bash
        cd src
        python master_script.py 
            --project YOUR_PROJECT_NAME
            --method ccr
            --cfg your_configuration_file.cfg
            --clips rating_clips.csv
            --training_clips training_clips.csv
        ```
    Note: file path are expected to be relative to the current working directory.
    
    6.3. Double check the outcome of script: A folder should be create with YOUR_PROJECT_NAME in current working 
    directory which contains: 
    * `YOUR_PROJECT_NAME_ccr.html`: Customized HIT app to be used in Amazon Mechanical Turk (AMT).
    * `YOUR_PROJECT_NAME_publish_batch.csv`: List of dynamic content to be used during publishing batch in AMT.
    * `YOUR_PROJECT_NAME_ccr_result_parser.cfg`: Customized configuration file to be used by `result_parser.py` script
        
Now, you are ready for [Running the Test on Amazon Mechanical Turk](docs/running_test_mturk.md).