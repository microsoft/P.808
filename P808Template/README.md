# HIT App
Implementation of the ITU-T P.808 Recommendation to be used in Amazon Mechanical Turk platform.

## Qualification
[tba]

## ACR
The implementation of Absolute Category Rating listening test as specified in the Annex A of ITU-T P.808.
The HIT has four sections: 
#### Instruction
Provides information to the workers including their task, rules and bonuses (+ terms).

#### Setup
Contains 6 questions: 1) to adjust the listening level, 2) A short math exercises with digits panning between left and 
right in stereo to proof usage of two-eared headphones. 3-6) Environment Test in form of pair comparision test. Stimuli 
presented here are carefully selected, to represent finest Just Noticeable Difference in Quality recognizable by normal
participants in a laboratory session. It is expected with a proper setting, a crowd worker be able to answer  at least 
2/4 questions correctly.

You can specify how often this section show up. It is recommended to have it in every session.    

#### Training
Here small set of anchoring stimuli presented to worker in a similar GUI as the  "rating section". 
Training section is generated dynamically based on list of URLS in the `config['trainingUrls']`.
Hardcode the urls in the  `config['trainingUrls']` or use placeholders like `"${T1}"` so the values will be set from 
input.csv file.
Order of stimuli can be randomized, and retraining can be forced after X hours (see the Usage section).

#### Ratings
Main task of crowd worker is to provide their opinion here. 
This section is generated dynamically based on list of URLS in the `config['questionUrls']`.
It is expected to use placeholders here, so the values will be picked and replaced during HIT generation process from
the input.csv.
Order of stimuli can be randomized (recommended).
 
## Usage

Note: It is recommended to invite group of workers who satisfy pre-requisites to this job. Workers should first perform 
the `Qualification`job.

Steps:
1. Modify the config  variable in ACR.html

    ```
    var config ={
        // cookie name which will be used to specify training and setup ncessity. 
        cookieName:"itu_p808_test", 
        // how often should the Training section will be presented. Recommended: 1
        forceRetrainingInHours:1,   
        debug:true,
        // list of URLS (or placehodlers) refering to audio clips. One question per URL will be created in Ratings section.
        // placeholders will be replaced by URLS from input.csv file in the HIT creation process.
        questionUrls: ["${Q1}","${Q2}","${Q3}","${Q4}","${Q5}","${Q6}","${Q7}","${Q8}","${Q9}","${Q10}","${TP}"],
         // list of URLS (or placehodlers) refering to audio clips. One question per URL will be created in Training section.
        // placeholders will be replaced by URLS from input.csv file in the HIT creation process.
        trainingUrls: ["${T1}","${T2}","${T3}","${T4}","${T5}"],
        // should the order of audio clips be randomized in training section? Recommended: True
        randomizeTrainingQuestions:"true",
        // should the order of audio clips be randomized in Ratings section? Recommended: True
        randomizeRatingQuestions:"false",
        // how often should the "Setup" section be presented to worker? Recommended: 3min --> everytime
        showSetupEveryMinutes:3,
        // In case you want to use Assignment Review Policies, what is the URL of file with known correct answer
        // the same URL should appear in the "questionUrls".
        knownQuestionUrl:"${TP}",
        // What is the correct answer?
        knownQuestionAns:"${TP_ANS}"
    } 
    ```
2. In case you do not want to use Assignment Review Policies, just simply use the MTurk website to
create a New Project using the ACR.html and follow the steps there.
In case you want to use  use Assignment Review Policies:

NOTE: the Assignment Review Policies is only available when you create HITs using API. The drawback is that those HITs 
will not be visible in MTurk website, and all management process should be done using scripts/api.

1. create a "project" in MTurk website using the ACR.html
2. obtain the Layout ID (see: https://docs.aws.amazon.com/AWSMechTurk/latest/AWSMturkAPI/ApiReference_HITLayoutArticle.html)
3. add the Layout ID to the `create_acr_hit.cfg` and update other settings there.
4. create input.csv: it is expected to have one column per placeholders used in `ACR.html`.  Here is a list for current
version:
    ```
    CMP1_A, CMP1_B, CMP2_A, CMP2_B, CMP3_A, CMP3_B, CMP4_A, CMP4_B, Q1, Q10, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q9, T1, T2, 
    T3, T4, T5, TP, TP_ANS, math
    ```
5. use `Scripts\mturk_utils.py`  to create HITs (see `create_hit` the [Readme](../Scripts/README.md) file there)
6. use  `Scripts\mturk_utils.py`  to download the answers (see `answers` the [Readme](../Scripts/README.md) file there)


 

