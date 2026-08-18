[Home](../README.md) > [Preparation](preparation.md) > General Resources
# General Resources

There are general resources required for the HIT APP to function properly.

1. Upload files you find here `src/P808Template/assets/*` into a cloud server and change URLs you find in the following HTML 
files:
     - `src/P808Template/ACR_template.html`
     - `src/P808Template/DCR_template.html`
     - `src/P808Template/CCR_template.html`
     - `src/P808Template/P835_template.html`
     - `src/P808Template/Qualification.html`
     
1. Upload the links in the `src/assets_master_script/general.csv` (or `general_assets_internal.csv`
   for internal assets):
    - Column `math` should contain URLs of files you find here `src/P808Template/assets/clips/math/*`.
	  You can generate additional math clips with `src/utils/generate_math_questions.py`.
    - Column `math_ans` should contain the correct answer (sum) for each math clip.
    - Column `math_hash` should contain a SHA-256 hash of the clip URL and answer for client-side
	  verification. The `generate_math_questions.py` script computes these automatically.
    - Columns `pair_a`, `pair_b` should contain URLs of files you find here `src/P808Template/assets/clips/environment_test/*`.
    Use files starting by `40` in `pair_a`, and corresponding file starting by `50` in `pair_b`.
    