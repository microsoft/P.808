# Hearing Test

This is an implementation of digit-triplet test [1].
It estimates an SNR level that the user in the current environmental setting can recognize three spoken digits in the presence of background noise.
Subject should listen to several audio clips and each time type in which number is spoken. To estimate the
It is an implementation of the Adaptive Staircase Psychoacoustics method (3AFC, 2 down- 1 up) as proposed by Levitt [2].

## Setup

Currently numbers for English and German languages are provided. 
Audio clips are stored in `\assets\[lang]_num_snr` where `[lang]` can be `en` or `de`.
You can change the language and others settings by editing the config object in the `\assets\js\hearing_test.js`.


## Results
It should be used by your target group in a laboratory settings to find out what is a good SNR level (as cutting point
 for  recognizing normal hearing participants) to be included in your crowdsourcing test. 
Result shows the SNR level that the subject can successfully recognize the three spoken digits in presence of background noise and in 
70.7% (or more) of times.
  

## References

[1]. Smits, Cas, Theo S. Kapteyn, and Tammo Houtgast. "Development and validation of an automatic speech-in-noise screening test by telephone." International journal of audiology 43.1 (2004): 15-28.
[2]. Levitt, H. (1992). Adaptive procedures for hearing aid prescription and other audiologic applications. Journal of
the American Academy of Audiology, 3, 119-131.


