# HIT App Templates
Templates for  ACR, DCR, and CCR methods to be used in Amazon Mechanical Turk platform. 
The ACR implementation is based on the ITU-T P.808 Recommendation and implementation of DCR and CCR are based on 
ITU-T P.800 Recommendation adapted to the crowdsourcing approach.

## Qualification
The qualification can be used as a separate HIT or in the integrated mode i.e. a section in the main HIT.
The qualification contains 10 questions including a hearing test.  

## ACR_Template
The implementation of Absolute Category Rating listening test as specified in the Annex A of ITU-T P.808.
The HIT has four sections: 
#### Instruction
Provides information to the workers including their task, rules and bonuses (+ terms).

#### Qualification - Just once
In case the qualification is not in a separate HIT, this section check for necessary information.
The qualification will be assigned when a user    
- reported to have English mother tongue 
- reported to have a headset
- reported to not work in the relevant area
- reported to have a normal hearing
- answered 3 or more questions of hearing tests correctly (out of 5).


#### Setup (every X minutes)
Contains 6 questions: 1) To adjust the listening level, 2) A short math exercise with digits panning between left and 
right in stereo to proove usage of two-eared headphones. 3-6) Environment Test in form of pair comparision test. Stimuli 
presented here are carefully selected, to represent finest Just Noticeable Difference in Quality recognizable by normal
participants in a laboratory session. It is expected with a proper setting, a crowd worker be able to answer  at least 
2/4 questions correctly.

You can specify how often this section show up. It is recommended to have it in every session.    

#### Listening device check
This section uses WebRTC to check if the user has a headset. 

#### Training (every X hours)
Here a small set of anchoring stimuli presented to worker in a similar GUI as the  "rating section". 
Training section is generated dynamically based on list of URLs in the `config['trainingUrls']`.
These will be added by master_script. Order of stimuli can be randomized, and retraining can be forced after X hours 
(see the Usage section).

#### Ratings
Main task of crowd worker is to provide their opinion here. 
This section is generated dynamically based on list of URLS in the `config['questionUrls']`.
Proper placeholders will be added by master_script. Order of stimuli can be randomized (recommended).
Typically, a trapping stimuli and a gold clip will be added to this section. 
 
## Usage
Check out the [preparation](../../docs/prep_acr.md) step. The master_script.py will make a customized version of 
template for your project. In case you want to change the advanced details, check out the html code and modify the 
`config` object.

## DCR_Template
The implementation of Degradation Category Rating listening test as specified in the Annex D of ITU-T P.800.
The template has same structure as ACR_Template.


## CCR_Template
The implementation of Comparison Category Rating (CCR) listening test as specified in the Annex E of ITU-T P.800.
The template has same structure as ACR_Template. 

## P835_template
The implementation of the ITU-T Rec. P.835 recommendation. An extension of it for only one time listening are given on 
P835_template_one_audio.html.
