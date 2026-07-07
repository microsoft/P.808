[Home](../README.md) > [Preparation](preparation.md) > Gold Standard Clips

# Gold Standard Clips

Gold standard clips (gold clips) are hidden quality control items inserted into each listening session.
Their expected answers are known in advance and are used to verify that participants are paying attention
and rating consistently. A wrong answer to a gold clip may result in rejection of the submission.

## Overview

Gold clips should have quality so obvious that all attentive participants rate them correctly
(+/- 1 deviation is accepted). It is recommended to include clips at both extremes: excellent
quality (answer 5) and clearly degraded quality (answer 1).

## Generating Gold Clips

The `create_gold_clips.py` script automatically generates gold clips from a set of clean source
audio files. For each source file, it creates multiple degraded versions targeting different
quality dimensions.

### Usage

```bash
cd src
python create_gold_clips.py ^
    --input_dir path/to/clean_clips ^
    --output_dir path/to/gold_output ^
    --method acr
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input_dir` | Yes | — | Directory containing clean source WAV files. |
| `--output_dir` | Yes | — | Directory where gold clips and the report CSV will be saved. |
| `--method` | Yes | — | Test method: `acr`, `p835`, or `p804`. |
| `--snr_db` | No | -5.0 | Signal-to-noise ratio in dB for background noise. Lower = more noise. |
| `--clip_threshold` | No | 0.005 | Hard clipping threshold as a fraction of peak amplitude. Lower = more distortion. |
| `--no_anonymize` | No | False | Use descriptive filenames instead of random anonymous names. |

By default, output filenames are randomized so that quality cannot be inferred from the filename.
Use `--no_anonymize` for debugging and listening verification.

### Output

The script produces:
- Degraded WAV files in the output directory.
- `gold_clips_report.csv` with filenames and expected answers in the format required by `master_script.py`.

## Degradation Types by Method

### ACR

| Type | Description | Expected answer |
|------|-------------|-----------------|
| Clean | Unmodified source clip | 5 |
| Background noise | Pink noise at -5 dB SNR | 1 |
| Signal distortion | Hard clipping | 1 |
| Both | Clipping + noise | 1 |

**Output CSV columns:** `gold_clips`, `gold_clips_ans`

### P.835

For P.835, each gold clip targets specific perceptual dimensions (signal, background, overall).

| Type | Description | sig | bak | ovrl |
|------|-------------|-----|-----|------|
| Clean | Unmodified source clip | 5 | 5 | 5 |
| Background noise | Pink noise at -5 dB SNR | 5 | 1 | 1 |
| Signal distortion | Hard clipping | 1 | 4 | 1 |
| Both | Clipping + noise | 1 | 1 | 1 |

**Note:** Signal distortion introduces harmonic content that can be perceived as mild background
degradation, so `bak` is set to 4 rather than 5 for that type.

**Output CSV columns:** `gold_clips`, `gold_sig_ans`, `gold_bak_ans`, `gold_ovrl_ans`

### P.804

For P.804, gold clips target multiple quality dimensions. Only dimensions with an expected answer
of 1 are listed in the CSV; empty cells mean the dimension is not targeted (implicitly 5).

| Type | Description | col | disc | loud | noise | sig | ovrl |
|------|-------------|-----|------|------|-------|-----|------|
| Clean | Unmodified source clip | 5 | 5 | 5 | 5 | 5 | 5 |
| Background noise | Pink noise | | | | 1 | | 1 |
| Signal distortion | Hard clipping | | | | | 1 | 1 |
| Discontinuity | Random segment dropouts (choppy) | | 1 | | | 1 | 1 |
| Discontinuity + noise | Choppy + noise | | | | 1 | | 1 |
| Coloration | Resonant/muffled/telephone filter | 1 | | | | 1 | 1 |
| Coloration + noise | Coloration + noise | | | | 1 | | 1 |
| Distortion + noise | Clipping + noise | | | | 1 | | 1 |
| Loudness (too loud) | Gain raised so speech is too loud | | | 1 | | | |
| Loudness (too quiet) | Gain lowered so speech is too quiet | | | 1 | | | |
| Loudness (too loud) + distortion | Too loud + clipping | | | 1 | | 1 | 1 |
| Loudness (too quiet) + distortion | Too quiet + clipping | | | 1 | | | 1 |
| Loudness (too loud) + noise | Too loud + noise | | | 1 | 1 | | 1 |
| Loudness (too quiet) + noise | Too quiet + noise | | | 1 | 1 | | 1 |

**Note:** The `sig` dimension cannot be judged reliably when the signal is masked or hidden, so it is not
flagged for: the noise-combined types (discontinuity/coloration/distortion + noise, where noise masks the
signal) and the **too-quiet** loudness + distortion case (a very low-gain clip hides signal detail). The
**too-loud** loudness + distortion case still flags `sig`, since the distortion remains audible. In all
these cases the `ovrl` flag is retained, driven by the noise or loudness/distortion degradation.

**Note:** Loudness alone does not flag `ovrl`. A level offset by itself is not treated as an overall
quality degradation, so only the `loud` dimension is targeted. When loudness is combined with another
artifact (distortion or noise), that other artifact drives the `ovrl` flag.

**Note:** The loudness and coloration degradations keep the first few seconds of audio as a clean
reference (`GOLD_CLEAN_PREFIX_SEC`, default 3 seconds) and only apply the degradation afterwards, so a
rater can perceive the change relative to the clean start. Other artifacts (noise, distortion,
discontinuity) are applied from the beginning of the clip; when combined with loudness or coloration,
the other artifact is present throughout while the loudness/coloration change appears after the prefix.

**Output CSV columns:** `gold_clips`, `col_ans`, `disc_ans`, `loud_ans`, `noise_ans`, `reverb_ans`, `sig_ans`, `ovrl_ans`

## Source Clip Recommendations

- Use clean speech clips with no background noise or distortion.
- Include a variety of speakers (male and female).
- Clips should be representative of the duration used in the test (typically 2–5 seconds).
- A minimum of 4–6 source clips is recommended to generate a diverse gold clip set.

## Using Gold Clips with master_script.py

After generating gold clips:

1. Upload the generated WAV files to a cloud server.
2. Update the `gold_clips` column in `gold_clips_report.csv` with the hosted URLs.
3. Pass the updated CSV as `--gold_clips` to `master_script.py`.
