# P.808 Toolkit
The P.808 Toolkit is a software package that enables users to run subjective speech quality assessment test
in crowdsourcing platforms like Amazon Mechanical Turk (AMT), Prolific, or conduct remote testing with a dedicated panel of workers, according to the ITU-T Recommendation P.808. 
It includes following test methods:
* Absolute Category Rating (ACR) -- Annex A, P.808
* Degradation Category Ratings (DCR) -- Annex B, P.808
* Comparison Category Ratings (CCR) -- Annex C, P.808
* Evaluating the subjective quality of speech in noise (i.e. implementation of ITU-T Rec. P.835 approach in crowdsourcing) -- Annex D, P.808
 
 
It also extends P.808 in the following ways:

* Includes implementation of the ITU-T Rec. P.831 for the crowdsourcing approach is also provided based on the recommendations given in the ITU-T Rec. P.808.

* Multi-dimensional Speech Quality Assessment - Following the ITU-T Rec. P.804 and extending it with reverberation, signal and overall quality.

* Extending P.835 test to evaluate personalized noise suppression


Relevant ITU-T Recommendations are :
* [ITU-T Recommendation P.808, _Subjective evaluation of speech quality with a crowdsourcing approach._](https://www.itu.int/rec/T-REC-P.808/en) Geneva: International Telecommunication Union, 2021.

* [ITU-T Recommendation P.835, _Subjective test methodology for evaluating speech communication systems that include noise suppression algorithm._](https://www.itu.int/rec/T-REC-P.835/en) Geneva: International Telecommunication Union, 2003.

* [ITU-T Recommendation P.831 _Subjective performance evaluation of network echo cancellers._](https://www.itu.int/rec/T-REC-P.831/en) Geneva: International Telecommunication Union, 1998.

* [ITU-T Recommendation P.804 _Subjective diagnostic test method for conversational speech quality analysis_](https://www.itu.int/rec/T-REC-P.804/en) Geneva: International Telecommunication Union, 2017.

Technical description of the implementation and validation are given in these papers:

* [An Open Source Implementation of ITU-T Recommendation P.808 with Validation.](https://arxiv.org/pdf/2005.08138.pdf)
Babak Naderi, Ross Cutler, INTERSPEECH 2020.

* [Crowdsourcing approach for subjective evaluation of echo impairment.](https://arxiv.org/pdf/2010.13063.pdf)
Ross Cutler, Babak Naderi, Markus Loide, Sten Sootla, Ando Saabas, ICASSP 2021.

* [Subjective Evaluation of Noise Suppression Algorithms in Crowdsourcing](https://arxiv.org/pdf/2010.13200.pdf)
Babak Naderi, Ross Cutler, INTERSPEECH 2021.

* [Multi-dimensional Speech Quality Assessment in Crowdsourcing.](https://arxiv.org/pdf/2309.07385.pdf)
Babak Naderi, Ross Cutler, Nicolae-Catalin Ristea.

## Citation
If you use this tool in your research please cite it with the following references:

```BibTex
@inproceedings{naderi2020,
  title={An Open source Implementation of ITU-T Recommendation P.808 with Validation},
  author={Naderi, Babak and Cutler, Ross},
  booktitle={Proc. INTERSPEECH},
  year={2020}
}
```

```BibTex
@inproceedings{cutler2021crowdsourcing,
  title={Crowdsourcing approach for subjective evaluation of echo impairment},
  author={Cutler, Ross and Naderi, Babak and Loide, Markus and Sootla, Sten and Saabas, Ando},
  booktitle={ICASSP 2021-2021 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)},
  pages={406--410},
  year={2021},
  organization={IEEE}
}
```

```BibTex
@inproceedings{naderi2021,
  title={Subjective Evaluation of Noise Suppression Algorithms in Crowdsourcing},
  author={Naderi, Babak and Cutler, Ross},
  booktitle={Proc. INTERSPEECH},
  year={2021}
}
```

```BibTex
@inproceedings{naderi2024multi,
  title={Multi-dimensional speech quality assessment in crowdsourcing},
  author={Naderi, Babak and Cutler, Ross and Ristea, Nicolae-C{\u{a}}t{\u{a}}lin},
  booktitle={ICASSP 2024-2024 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)},
  pages={696--700},
  year={2024},
  organization={IEEE}
}
```

## Getting Started
* [Preparation](docs/preparation.md)
* Running the Test on crowdsourcing platform
  * [Using Amazon Mechanical Turk](docs/running_test_mturk.md)
  * [Using Prolific](docs/running_test_prolific.md)
* [Analyzing Data](docs/results.md)

## Using an AI Agent

You can use an AI coding agent (e.g. GitHub Copilot, Claude) to create and run studies
automatically. The agent will generate gold clips, trapping clips, training clips, upload
them to Azure storage, and build the complete project — all from a single prompt.

**Setup**: This experince is trilored to use Azure Storage, if you use any other cloud provider for serving your clips, adapt the code accordingly.Otherwise, make sure you have `az login` configured with write access to your Azure Blob
Storage account.

**Usage**: Open the repository in your IDE with an AI agent and ask it to create a study:

> _"Run a P.835 test for the files in C:\path\to\my\rating_clips"_

The agent uses the `create-study` custom agent defined in [`.github/agents/create-study.agent.md`](.github/agents/create-study.agent.md).
Select it via `/agent` in Copilot CLI, or just describe your task — the model will auto-infer the
right agent. See [`AGENTS.md`](AGENTS.md) for the full list of available agents.

**Supported methods**: `acr`, `dcr`, `ccr`, `p835`, `p804`, `echo_impairment_test`, `pp835`.



## Troubleshooting
For bug reports and issues with this code, please see the 
[_github issues page_](https://github.com/babaknaderi/hitapp_p808/issues). Please review this page before contacting the authors.


## Contact

Contact [Babak Naderi](babaknaderi@microsoft.com), [Vishak Gopal](vishak.gopal@microsoft.com) or [Ross Cutler](rcutler@microsoft.com) with any questions.

## License
### Code License
MIT License

Copyright 2019 (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### Audio clips License
The datasets are provided under the original terms that Microsoft received such datasets. See below for more information about each dataset.

The datasets used in this project are licensed as follows:

* Following clips are created under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode) license:
    *  `src/P808Template/assets/clips/math/*`
    *  `src/P808Template/assets/clips/hearing_test/*`
    *  `src/trapping/messages/*`
* Following clips are taken from [PTDB-TUG: Pitch Tracking Database from Graz University of Technology](https://www.spsc.tugraz.at/databases-and-tools/ptdb-tug-pitch-tracking-database-from-graz-university-of-technology.html); License: http://opendatacommons.org/licenses/odbl/1.0/ 
    * `src/environment test/script/clips/*`
    * `src/P808Template/assets/clips/signal_level.wav`
* Following clips are taken from [Noisy speech database for training speech enhancement algorithms and TTS models](http://hdl.handle.net/10283/2791)
    * `p835_reference_conditions/source/NSD/*`
* Following clips are taken from [NOIZEUS](https://ecs.utdallas.edu/loizou/speech/noizeus/)
    * `p835_reference_conditions/source/noizeus_ref/*`    
* Following clips are created by adding noise (or other degradation) to above-mentioned clips; License [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode)
    * `src/environment test/script/clips_snr/*`
    * `src/environment test/assets/jnd_noise/*`
    * `src/P808Template/assets/clips/environment_test/*`
    * `src/trapping/source/*`
    * `p835_reference_conditions/trapping clips/*`
    * `p835_reference_conditions/degraded_*/*`
* Following clips are created by degrading the source signals from ITU-T Rec. P.501; License of [source signals](p835_reference_conditions/3gpp_p501_FB/itu_license_text_from_P501.txt)
    * `p835_reference_conditions/3gpp_p501_FB/*`
    
# Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
