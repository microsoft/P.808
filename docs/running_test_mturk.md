[Home](../README.md) > Running the Test on Amazon Mechanical Turk

# Running the Test on Amazon Mechanical Turk

Following steps explains how to conduct the Speech Quality Assessment test on Amazon Mechanical Turk (AMT) according to
the ITU-T Rec. P.808 [1]. 
It is required to perform the [preparation](preparation.md) step first. 
As a result you should have a directory name YOUR_PROJECT_NAME which contains:
 
    * `YOUR_PROJECT_NAME_ccr.html`: Customized HIT app to be used in AMT.
    * `YOUR_PROJECT_NAME_publish_batch.csv`: List of dynamic content to be used during publishing batch in AMT.
    * `YOUR_PROJECT_NAME_ccr_result_parser.cfg`: Customized configuration file to be used by `result_parser.py` script    
    
You will use the first two files in this part.


## Create the test
1. Create [an account on AMT](https://requester.mturk.com/create/projects/new)

1. Prepare the development setup as explained [here](https://requester.mturk.com/developer) and get your AWS Access Key

1. Update the general configuration file (hereafter mturk.cfg) with your AWS Access Key (see [mturk.cfg](../src/configurations/mturk.cfg) as an example).

1. Create a New Project for your test
  
    4.1. Go to “**Create**” > “**New Project**” > “**Survey Link**” > “**Create project**”

    4.2. Fill information in “**1 – Enter Properties**”, important ones:

    * **Setting up your survey**
       * **Reward per response**: It is recommended to pay more than the minimum wage of target country per hour. 
        * **Number of respondents**: It is the number of votes that you want to collect per clip.
        * **Time allotted per Worker**: 1 Hour
    * **Worker requirements**
        * **Add another criterion**: **HIT Approval Rate(%)** greater than 98
         * **Add another criterion**: **Number of HITs Approved** greater than 500
         * **Location**: It is required that workers are native speakers of language under study

    4.3. Save and go to “**2 – Design Layout**”:

        4.3.1. Click on **Source**
        
        4.3.2. Copy and paste the content of `YOUR_PROJECT_NAME_acr.html` here.
        
        4.3.3. Click on **Source**, then **Save**
     
Next, you should create a New Batch with Existing Project. 
That can be done using either the AMT website or API. 
Using the API makes it possible to apply the [Assignment Review Policy](https://docs.aws.amazon.com/AWSMechTurk/latest/AWSMturkAPI/ApiReference_AssignmentReviewPolicies.html).
However when the HITs are created using the API, they will not be visible in the website (stand Dec.2019). Therefore 
all actions (like download results, approve/reject assignments, etc.) should be done using the API.

### Create a _New Batch with Existing Project_ - using website.

1. Go to “**Create**” > “**New Batch with an Existing Project**”, find your project and click on "**Publish Batch**" 

1. Upload your csv file that contains list of dynamic content (`YOUR_PROJECT_NAME_publish_batch.csv`).

1. Check the HITs and publish them.

1. Later, download the results from “**Manage**” > “**YOUR_BATCH_NAME**” > “**Review Results**” > “**Download CSV**”. 

### Create a _New Batch with Existing Project_ - using API.

1. Update [create_hit.cfg](../src/configurations/create_hit.cfg) configuration file with hit_layout_id, [hit_type], and [create_hit].

1. Create a batch using following command

    ```bash
    cd src
    python mturk_utils.py 
        --cfg mturk.cfg
        --create_hit create_hit.cfg
        --create_hit_input YOUR_PROJECT_NAME_publish_batch.csv
    ```
    
The script will creates a csv file containing HITIds,HITTypeIds,HITGroupIds of created HITs (call it Batch_123_456.csv).
This file is required for downloading the results.
        
3. Later, download the results
    ```bash
    cd src
    python mturk_utils.py 
        --cfg mturk.cfg
        --answers Batch_123_456.csv
    ```
 
## References
[1]. [ITU-T Recommendation P. 808](https://www.itu.int/rec/T-REC-P.808/en): _Subjective evaluation of speech quality with a crowdsourcing approach_, International Telecommunication Union, Geneva, 2018.
   