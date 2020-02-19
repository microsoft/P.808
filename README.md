# P.808 Toolkit
The P.808 Toolkit is a software package that enables users to run subjective speech quality assessment test
in Amazon Mechanical Turk (AMT) crowdsourcing platform, according to the ITU-T Recommendation P.808.

For more information about the ITU-T Rec. P.808 please read:

[ITU-T Recommandation P.808, _Subjective evaluation of speech quality with a crowdsourcing approach._](https://www.itu.int/rec/T-REC-P.808/en) 
Geneva: International Telecommunication Union, 2018.

## Getting Started
* [Preparation](docs/preparation.md)
* [Running the Test on Amazon Mechanical Turk](docs/running_test_mturk.md)
* [Analyzing Data](docs/results.md)


## Troubleshooting
For bug reports and issues with this code, please see the 
[_github issues page_](https://github.com/babaknaderi/hitapp_p808/issues). Please review this page before contacting the authors.


## Contact

Contact [dns_challenge@microsoft.com](dns_challenge@microsoft.com) or [Vishak Gopal](vishak.gopal@microsoft.com), [Ross Cutler] (rcutler@microsoft.com) with any questions.

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
* Following clips are created by adding noise to above-mentioned clips; License [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode) ?
    * `src/environment test/script/clips_snr/*`
    * `src/environment test/assets/jnd_noise/*`
    * `src/P808Template/assets/clips/environment_test/*`
    * `src/trapping/source/*`

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
