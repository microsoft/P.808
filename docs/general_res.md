[Home](../README.md) > [Preparation](preparation.md) > General Resources
# General Resources

There are general resources required for the HIT APP to function properly.

1. Upload files you find here `src/P808Template/assets/*` into a cloud server and change URLs you find in the following HTML 
files:
     - `src/P808Template/ACR_template.html`
     - `src/P808Template/DCR_template.html`
     - `src/P808Template/CCR_template.html`
     - `src/P808Template/Qualification.html`
     
1. Upload the links in the `src/assets_master_script/general.csv`:
    - Column `math` should contain URLs of files you find here `src/P808Template/assets/clips/math/*`.
    - Columns `pair_a`, `pair_b` should contain URLs of files you find here `src/P808Template/assets/clips/environment_test/*`.
    Use files starting by `40` in `pair_a`, and corresponding file starting by `50` in `pair_b`.
    