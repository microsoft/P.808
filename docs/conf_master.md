[Home](../README.md) > [Preparation](preparation.md) > [Preparation for Absolute Category Rating (ACR)](prep_acr.md)

# Configure for `master_script.py`
 
This describe the configuration for the `master_scripz.py`. A sample configuration file can be found in `configurations\master.cfg`.
 
## `[create_input]`

* `number_of_clips_per_session:10`: Number of clips from "rating_clips" to be included in the "Rating section" of each HIT/listening session. 
* `number_of_trapping_per_session:1`: Number of trapping questions to be included in the "Rating section".
* `number_of_gold_clips_per_session:1`:Number of gold clips to be included in the "Rating section".



## `[acr_html]`
* `cookie_name:itu_p808_sup23_exp3`: A cookie with this name will be used to store current state of a worker in this project.
 key attributes like number of assignments answered by the worker, if the training or setup sections are needed. 
 It is a project specific value. 
* `qual_cookie_name:ACR_LISTENER_19_12_2019`: A cookie with this name will show if the user passed the Qualification section.
The cookies expires after 1 month. If a worker could not successfully pass the Qualification section, they will see a 
following message next time they want to perform a HIT from this group:
    ````text
    There is no assignments that match to your profile now. Please try it again in two-weeks time.
    We thank you for your participation.
    ````
* `allowed_max_hit_in_project:60`: Number of assignments that one worker can perform from this project.
* `hit_base_payment:0.5`: Base payment for an accepted assignment from this HIT. This value will be used as information.
* `quantity_hits_more_than: 30`: Defines when quantity bonus requirement.
* `quantity_bonus: 0.1`: the amount of the quantity bonus to be payed for each accepted assignment.
* `quality_top_percentage: 20`: Defines when quality bonus should be applied (in addition, participant should be 
eligible for quantity bonus).
* `quality_bonus: 0.15`: the amount of the quality bonus per accepted assignment.

## `[dcr_ccr_html]`
* `cookie_name:itu_p808_sup23_exp3`: A cookie with this name will be used to store current state of a worker in this project.
 key attributes like number of assignments answered by the worker, if the training or setup sections are needed. 
 It is a project specific value. 
* `qual_cookie_name:ACR_LISTENER_19_12_2019`: A cookie with this name will show if the user passed the Qualification section.
The cookies expires after 1 month. If a worker could not successfully pass the Qualification section, they will see a 
following message next time they want to perform a HIT from this group:
    ````text
    There is no assignments that match to your profile now. Please try it again in two-weeks time.
    We thank you for your participation.
    ````
* `allowed_max_hit_in_project:60`: Number of assignments that one worker can perform from this project.
* `hit_base_payment:0.5`: Base payment for an accepted assignment from this HIT. This value will be used as information.
* `quantity_hits_more_than: 30`: Defines when quantity bonus requirement.
* `quantity_bonus: 0.1`: the amount of the quantity bonus to be payed for each accepted assignment.
* `quality_top_percentage: 20`: Defines when quality bonus should be applied (in addition, participant should be 
eligible for quantity bonus).
* `quality_bonus: 0.15`: the amount of the quality bonus per accepted assignment.
