[Home](../README.md) > [Preparation](preparation.md) > Preparation for the P.835]
# Preparation of P.835 test

The following steps should be performed to prepare the P.835 test setup.

**Note**: make sure to first perform steps listed in the [general preparation process](preparation.md).


1. Upload your **speech clips** in a cloud server and create `rating_clips.csv` file which contains all URLs in a 
column named `rating_clips` (see [rating_clips.csv](../src/test_inputs/rating_clips.csv) as an example).

    **Note about file names**:
    * Later in the analyzes, clip's file name will be used as a unique key and appears in the results.    
    * In case you have 'conditions' which are represented with more than one clip, you may consider to use the condition's 
        name in the clip's file name or in the URL e.g. xxx_c01_xxxx.wav. Latter you can use regex pattern to extract the 
        condition identifier from the URLs.

1. Upload your **training clips** in a cloud server and create `training_clips.csv` file which contains all URLs in a 
column named `training_clips` (see [training_clips.csv](../src/test_inputs/training_clips.csv) as an example).
  
    **Hint**: Training clips are used for anchoring participants perception, and should represent the entire dataset. 
    They should approximately cover the range from worst to best quality to be expected in the test. It may contain 
    about 5 clips. 

1. Upload your **gold standard clips** in a cloud server and create `gold_clips.csv` file which contains all URLs in a 
column named `gold_clips` and expected answer to each clip in a column named `gold_clips_ans` 
(see [gold_clips.csv](../src/test_inputs/gold_clips.csv) as an example).
  
    **Hint**: Gold standard clips are used as a hidden quality control item in each session. It is expected that their 
    answers are so obvious for all participants that they all give the `gold_clips_ans` rating (+/- 1 deviation is 
    accepted) to the "overall quality" question. It is recommended to use clips with excellent (answer 5) or very bad 
    (answer 1) quality.
    
1. Create trapping stimuli set for your dataset.

    1. Configure the `create_trapping_stimuli.py` in your config file. See [configuration of create_trapping_stimuli script ](conf-trapping.md)
     for more information. An example is provided in `configurations\trapping_p835.cfg`.
     
    2. Delete all files from `trapping clips\source` directory
    ``` bash
    cd "src\trapping clips\source"
    del *.* 
    ```  
    3. Add some clips from your dataset to `trapping clips\source` directory. Select clips in a way that
		1. Covers fair distributions of speakers (best couple of clips per each speaker)
		1. Covers entire range of quality (some good, fair and bad ones)
    
    4. Run `create_trapping_stimuli.py`
    ``` bash
    cd src
    python create_trapping_stimuli.py ^
        --cfg your_config_file.cfg
    ```
    5. Trapping clips are stored in `trapping clips\output` directory. List of clips and their correct answer can 
    be found in `trapping clips\source\output_report.csv`. You can replace file names (appears in column named `trapping_clips`)
    with the URLs pointing to those files to create the `trapping_clips.csv` file (see below).
        
1. Upload your **trapping clips** in a cloud server and create `trapping_clips.csv` file which contains all URLs in 
a column named `trapping_clips` and expected answer to each clip in a column named `trapping_ans` 
(see [trapping_clips.csv](../src/test_inputs/trapping_clips.csv) as an example).

1. Create your custom project by running the master script: 
	
    1. Configure the project in your config file. See [master script configuration](conf_master.md) for more information.
    
    1. Run `master_script.py` with all above-mentioned resources as input
        
        ``` bash
        cd src
        python master_script.py ^
            --project YOUR_PROJECT_NAME ^
            --method p835 ^
            --cfg your_configuration_file.cfg ^
            --clips rating_clips.csv ^
            --training_clips training_clips.csv ^
            --gold_clips gold_clips.csv ^
            --trapping_clips trapping_clips.csv 
        ```
        Note: file paths are expected to be relative to the current working directory.
    
    1. Double check the outcome of the script. A folder should be created with YOUR_PROJECT_NAME in current working 
    directory which contains: 
    * `YOUR_PROJECT_NAME_p835.html`: Customized HIT app to be used in Amazon Mechanical Turk (AMT).
    * `YOUR_PROJECT_NAME_publish_batch.csv`: List of dynamic content to be used during publishing batch in AMT.
    * `YOUR_PROJECT_NAME_acr_result_parser.cfg`: Customized configuration file to be used by `result_parser.py` script
        
Now, you are ready for [Running the Test on Amazon Mechanical Turk](running_test_mturk.md).