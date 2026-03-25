[Home](../README.md) > Running the Test on Prolific

# Running the Test on Prolific

Following steps explain how to conduct the Speech Quality Assessment test on the Prolific crowdsourcing platform according to the ITU-T Rec. P.808 [1]. 
It is required to perform the [preparation](preparation.md) step first. 
As a result you should have a directory named YOUR_PROJECT_NAME which contains:
 
   * `YOUR_PROJECT_NAME_METHOD.html`: Customized HIT app template to be used in AMT/Prolific.
   * `YOUR_PROJECT_NAME_publish_batch.csv`: List of dynamic content to be used during publishing batch in AMT.
   * `YOUR_PROJECT_NAME_ccr_result_parser.cfg`: Customized configuration file to be used by `result_parser.py` script    
    
You will use the first two files in this part.

In parallel you need to use a system to host your survey. One option is [HITAppServer](https://github.com/microsoft/P.910/tree/main/hitapp_server). The following procedure is customized to the HIT APP server and assumes a running server is available.


## Step 1: Create the test on HITApp Server 
1. Visit your HITApp server landing page.
2. Start by "New project"
3. Provide the required information:
    - Project name: Friendly internal name
    - Number of assignments: how many votes per file do you aim for (here it is only for statistics)
    - Crowdsourcing platform: select "Prolific"
    - Choose HTML file: Upload `YOUR_PROJECT_NAME_METHOD.html`
    - Choose CSV file with variables:  Upload `YOUR_PROJECT_NAME_publish_batch.csv`
    - Click on Submit
4. When finished download:
    - download "HIT input file"
    - download "HIT description"

## Step2: Create the test on Prolific
    - Login to your Prolific account
    - Create a Project to organize your studies.
    - Go to your project and create a New Study
    - Use "Taskflow", fill the required information including study name, study description (the above "HIT Description" with some edits can be used here)
    - Fill the rest of the information, and upload the above "HIT input file" into "upload the URL file". 
    - Set "How many total taskers do you need?" to be the number of votes you need × number of rows in "HIT input file" (one row in this file will be one task, and you need N votes per task)
    - From *recording Prolific IDs*, select "URL parameters". Keep the values as it is.
    - In "screening" select any prerequisite your participants should have.
    - From *Submissions* select *Multiple*, and use max(50, N of tasks)
## Step3: publish
    - Fill the rest of the information including a fair payment and follow the procedure on the Prolific website.


When the Batch is finished, download the answers from Prolific and HITAppServer and then you are ready to continue with [analyzing the results](results.md). 
    - "Download demographic data" from the study page in Prolific.
    - Download the answers from your study page in the HITApp server.


## References
[1]. [ITU-T Recommendation P. 808](https://www.itu.int/rec/T-REC-P.808/en): _Subjective evaluation of speech quality with a crowdsourcing approach_, International Telecommunication Union, Geneva, 2018.
   