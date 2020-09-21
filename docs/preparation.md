[Home](../README.md) > Preparation
# Preparation

The following steps should be performed to prepare the test setup.

1. Install `python` and `pip`, if they are not already installed. Follow the platform specific installation instructions.

1. Clone or download the P.808 Toolkit repository from Github: https://github.com/microsoft/P.808.git, e.g.

    ```bash
    git clone https://github.com/microsoft/P.808.git
    cd P.808
    ```

1. Install the python module dependencies in `requirements.txt` using `pip`

    ```bash
    cd src
    pip install -r requirements.txt
    ```
    
1. (optional) Upload the general resources (found in `src\P809Template\assets`) in a cloud server and change the 
URLs associated to them as described in [General Resources](general_res.md)

1.  Follow the rest of preparation process based on the test methodology you want to apply:

    - [Preparation for Absolute Category Rating (ACR)](prep_acr.md)
    - [Preparation for Degradation Category Rating (DCR)](prep_dcr_ccr.md)
    - [Preparation for Comparison Category Rating (CCR)](prep_dcr_ccr.md)
    - [Preparation for the P.835](prep_p835.md)