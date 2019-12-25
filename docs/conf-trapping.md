 # Configure for `create_trapping_stimuli.py`
 
 This describe the configuration for the `create_trapping_stimuli` script. A sample configuration file can be found in `configurations\trapping.cfg`.
 The `create_trapping_stimuli` script creates the trapping clips based on the section 6.3.8 of the ITU-T P.808 [1] and [2].
  
 ## `[trappings]`
 `input_directory = trapping clips`: path pointing to the `trapping clips` directory. It is relative to the current working directory. 
 The directory should contain following subdirectories:
 * `source`: it should contains fair distributions of clips from your dataset under study. First couple of seconds from
 each clip in this directory will be used to generate the trapping clips.
 * `messages`: message clips found in this directory will be appended to first couple of seconds from each clip in the 
 `source` directory to create the trapping clips.
 * `output`: generated trapping clips will be stored here.
 
 `message_file_prefix:ACR_`: specify prefix of audio clips available in `source` directory which should be used.
  
 **One** of the following options should be used:
 
 * `include_from_source_stimuli_in_second = 2`: use first 2 seconds from the `source` clips to generate the trapping clips.
 It may lead to a clip duration that is different from the rest of clips which should be rated. 
 
 * `keep_original_duration = true`: As a result each generated clips will be as long as the corresponding original clip.
 It is the recommended setting.    
 
 
 
 ## References
[1]. [ITU-T Recommendation P. 808](https://www.itu.int/rec/T-REC-P.808/en): Subjective evaluation of speech quality with a crowdsourcing approach, International Telecommunication Union, Geneva, 2018.

[2]. Naderi B, Polzehl T, Wechsung I, Köster F, Möller S. [Effect of Trapping Questions on the Reliability of Speech Quality Judgments in a Crowdsourcing Paradigm.](https://www.isca-speech.org/archive/interspeech_2015/papers/i15_2799.pdf) 16th Ann. Conf. of the Int. Speech Comm. Assoc. (Interspeech 2015). ISCA, 2799–2803.


 
 