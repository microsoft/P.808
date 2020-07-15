# Materials to generate Gold standard stimuli database


## Generate
use `azure_tts_create_msgs.py` to create the audio clip given your customized test. Information on how to setup your 
system can be found in [3].

## For ACR test
All files start with `ACR_*`. They are created based on description in section 6.3.8 of the ITU-T P.808 [1] and [2].
The audio clips were created using Bing Speech API. 

Text: 
```
This is an interruption. Please select the answer X to confirm your attention now.
```
## For P.835
As there is 3 different scales for each stimuli, here specify which "Score" user should select:
Text: 
```
This is an interruption. Please select the score X to confirm your attention now.
```


## References
[1]. [ITU-T Recommendation P. 808](https://www.itu.int/rec/T-REC-P.808/en): Subjective evaluation of speech quality with a crowdsourcing approach, International Telecommunication Union, Geneva, 2018.

[2]. Naderi B, Polzehl T, Wechsung I, Köster F, Möller S. [Effect of Trapping Questions on the Reliability of Speech Quality Judgments in a Crowdsourcing Paradigm.](https://www.isca-speech.org/archive/interspeech_2015/papers/i15_2799.pdf) 16th Ann. Conf. of the Int. Speech Comm. Assoc. (Interspeech 2015). ISCA, 2799–2803.

[3].[Quickstart: Synthesize speech into an audio file](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/quickstarts/text-to-speech-audio-file)
 


