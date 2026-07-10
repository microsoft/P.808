"""
/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

Generate the setup-section JND ("just-noticeable-difference") clip pairs used in the
P.80x in-HIT setup/environment check.

For every clean reference speech file in an input directory this script builds one
A/B pair: the *same* clean clip mixed with white noise at two different SNR levels.
One version is cleaner (higher SNR) and one is noisier (lower SNR); the participant
is asked which sample has the better quality. The cleaner (higher-SNR) clip is the
correct answer. Because the only difference between the two clips is the noise level,
hearing it requires a good listening setup and a quiet environment - which is exactly
what the setup section checks.

This mirrors the existing hosted pairs (``sample_jnd/40S_*.wav`` vs ``50S_*.wav``)
that ``master_script`` reads from the ``pair_a`` / ``pair_b`` columns of the general
assets CSV, but with two improvements that match ``create_bandwidth_check_clips.py``:

  * Output clip names are anonymized random UUIDs, so the hosted file name does not
    reveal the SNR (and therefore the answer). The manifest CSV keeps the mapping.
  * The correct answer is written explicitly to the manifest (``ans_pair`` /
    ``ans_url``) instead of being encoded in the file name.

The noise is white and scaled with the MS-SNSD convention (speech normalized to
``-25`` dBFS, noise scaled to reach the target SNR), so the clips are consistent
with the current ``create_jnd_dataset.py`` output.

Usage:
    python utils/create_jnd_check_clips.py ^
        --input_dir C:/datasets/clean_speech ^
        --output_dir output/jnd_test ^
        --base_url https://host/container/clips/jnd-test ^
        --snr_high 50 --snr_low 40
"""

import argparse
import csv
import os
import uuid

import numpy as np
import soundfile as sf


# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

# SNR (dB) of the cleaner clip in a pair - this is the correct ("better quality")
# answer. Matches the higher-SNR side of the current sample_jnd pairs.
DEFAULT_SNR_HIGH = 50.0

# SNR (dB) of the noisier clip in a pair. A smaller gap to SNR_HIGH makes the pair
# harder to tell apart (a more demanding setup check).
DEFAULT_SNR_LOW = 40.0

# Speech is normalized to this active level before the noise is added (MS-SNSD
# convention, matching the existing create_jnd_dataset.py / audiolib output).
TARGET_LEVEL_DBFS = -25.0


# ---------------------------------------------------------------------------
# Level / mixing helpers
# ---------------------------------------------------------------------------

def rms(signal):
    """
    Compute the root-mean-square level of a signal.

    :param signal: Audio signal as a numpy array.
    :return: RMS value as a float (with a small epsilon floor).
    """
    return float(np.sqrt(np.mean(np.square(signal)) + 1e-12))


def normalize_to_dbfs(signal, target_dbfs):
    """
    Scale a signal so its overall RMS reaches a target level in dBFS.

    :param signal: Audio signal as a numpy array.
    :param target_dbfs: Target RMS level in dBFS (0 dBFS = RMS of 1.0).
    :return: Level-scaled signal as a numpy array.
    """
    target_rms = 10.0 ** (target_dbfs / 20.0)
    return signal * (target_rms / rms(signal))


def snr_mixer(clean, noise, snr, target_level_dbfs=TARGET_LEVEL_DBFS):
    """
    Mix speech and noise at a given SNR, following the MS-SNSD convention.

    The speech is normalized to ``target_level_dbfs`` and the noise is scaled so the
    resulting speech-to-noise ratio equals ``snr`` dB. The same behaviour as
    ``audiolib.snr_mixer`` used by the original ``create_jnd_dataset.py``.

    :param clean: Clean speech signal as a numpy array.
    :param noise: Noise signal as a numpy array (same length as ``clean``).
    :param snr: Target signal-to-noise ratio in dB.
    :param target_level_dbfs: Level the speech is normalized to before mixing.
    :return: The noisy speech (clean + scaled noise) as a numpy array.
    """
    clean = normalize_to_dbfs(clean, target_level_dbfs)
    noise = normalize_to_dbfs(noise, target_level_dbfs)
    rms_clean = rms(clean)
    rms_noise = rms(noise)
    noise_scalar = rms_clean / (10.0 ** (snr / 20.0)) / rms_noise
    return clean + noise * noise_scalar


def load_mono(path):
    """
    Read a WAV file as a mono float signal.

    Multi-channel files are down-mixed to mono by averaging the channels.

    :param path: Path to the WAV file.
    :return: Tuple of (mono signal as a numpy array, sample rate in Hz, subtype
        string such as ``"PCM_16"``).
    """
    signal, fs = sf.read(path)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)
    return signal.astype(np.float64), fs, sf.info(path).subtype


# ---------------------------------------------------------------------------
# Per-reference generation
# ---------------------------------------------------------------------------

def generate_for_reference(ref_path, output_dir, snr_high=DEFAULT_SNR_HIGH,
                           snr_low=DEFAULT_SNR_LOW, seed=None, anonymize=True):
    """
    Build one JND A/B pair for a single reference file.

    Both clips come from the *same* clean reference and the *same* white-noise
    realization, scaled to two SNR levels: ``snr_high`` (cleaner, the correct
    answer) and ``snr_low`` (noisier). The order of A and B is randomized so the
    correct answer is not always in the same slot.

    :param ref_path: Path to the clean reference WAV file.
    :param output_dir: Directory where the two output clips are written.
    :param snr_high: SNR in dB of the cleaner (correct) clip.
    :param snr_low: SNR in dB of the noisier clip.
    :param seed: Optional integer seed for reproducible noise and A/B order.
    :param anonymize: When True (default) use random UUID file names; when False
        use descriptive ``<stem>_snr{snr}.wav`` names for listening review.
    :return: A dict with the pair mapping: ``pair_a``, ``pair_b`` (file names),
        ``ans_pair`` (``"a"`` or ``"b"``), ``ans_name`` (the correct file name),
        ``snr_a`` and ``snr_b`` (the SNR of each slot in dB).
    """
    ref, fs, subtype = load_mono(ref_path)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(ref))

    clean_clip = np.clip(snr_mixer(ref, noise, snr_high), -1.0, 1.0)
    noisy_clip = np.clip(snr_mixer(ref, noise, snr_low), -1.0, 1.0)

    stem = os.path.splitext(os.path.basename(ref_path))[0]

    def out_name(snr):
        return f"{uuid.uuid4().hex}.wav" if anonymize else f"{stem}_snr{int(round(snr))}.wav"

    clean_name = out_name(snr_high)
    noisy_name = out_name(snr_low)
    sf.write(os.path.join(output_dir, clean_name), clean_clip, fs, subtype=subtype)
    sf.write(os.path.join(output_dir, noisy_name), noisy_clip, fs, subtype=subtype)

    # Randomize which slot (A or B) holds the cleaner (correct) clip.
    clean_is_a = rng.random() < 0.5
    if clean_is_a:
        pair_a, pair_b, ans_pair, ans_name = clean_name, noisy_name, "a", clean_name
        snr_a, snr_b = snr_high, snr_low
    else:
        pair_a, pair_b, ans_pair, ans_name = noisy_name, clean_name, "b", clean_name
        snr_a, snr_b = snr_low, snr_high

    return {"pair_a": pair_a, "pair_b": pair_b, "ans_pair": ans_pair,
            "ans_name": ans_name, "snr_a": snr_a, "snr_b": snr_b}


def generate_jnd_check_clips(input_dir, output_dir, base_url=None,
                             snr_high=DEFAULT_SNR_HIGH, snr_low=DEFAULT_SNR_LOW,
                             seed=None, limit=None, anonymize=True):
    """
    Generate one JND A/B pair for every reference WAV in a directory.

    For each reference two clips are written to ``output_dir`` and a
    ``jnd_check_clips.csv`` manifest is produced with one row per reference. The
    manifest columns are ``ref_clip``, ``pair_a`` / ``pair_b`` (output clip name,
    or full URL when ``base_url`` is given), ``ans_pair`` (``"a"``/``"b"`` - which
    slot is the correct, cleaner clip), ``ans_url`` (the correct clip name/URL) and
    ``snr_a`` / ``snr_b`` (the SNR of each slot in dB, for review).

    :param input_dir: Directory containing clean reference WAV files.
    :param output_dir: Directory for the generated clips and the manifest CSV.
    :param base_url: Optional base URL; when set the pair/ans columns hold full
        URLs (``base_url`` + file name) instead of bare file names.
    :param snr_high: SNR in dB of the cleaner (correct) clip (default: 50).
    :param snr_low: SNR in dB of the noisier clip (default: 40).
    :param seed: Optional integer seed for reproducible noise and A/B order.
    :param limit: Optional cap on the number of references processed.
    :param anonymize: When True (default) use random UUID clip names; when False
        use descriptive ``<stem>_snr{snr}.wav`` names for listening review.
    :return: Path to the generated manifest CSV.
    """
    assert snr_high > snr_low, "snr_high must be greater than snr_low (higher SNR = cleaner)."
    os.makedirs(output_dir, exist_ok=True)
    references = sorted(f for f in os.listdir(input_dir)
                        if f.lower().endswith(".wav"))
    if limit is not None:
        references = references[:limit]
    assert references, f"No .wav reference files found in {input_dir}"

    def as_url(name):
        return base_url.rstrip("/") + "/" + name if base_url else name

    manifest = []
    for idx, ref_name in enumerate(references):
        ref_path = os.path.join(input_dir, ref_name)
        print(f"[{idx + 1}/{len(references)}] {ref_name}")
        # Derive a per-reference seed so runs are reproducible yet references differ.
        ref_seed = None if seed is None else seed + idx
        pair = generate_for_reference(
            ref_path, output_dir, snr_high=snr_high, snr_low=snr_low,
            seed=ref_seed, anonymize=anonymize,
        )
        manifest.append({
            "ref_clip": ref_name,
            "pair_a": as_url(pair["pair_a"]),
            "pair_b": as_url(pair["pair_b"]),
            "ans_pair": pair["ans_pair"],
            "ans_url": as_url(pair["ans_name"]),
            "snr_a": pair["snr_a"],
            "snr_b": pair["snr_b"],
        })

    columns = ["ref_clip", "pair_a", "pair_b", "ans_pair", "ans_url", "snr_a", "snr_b"]
    manifest_path = os.path.join(output_dir, "jnd_check_clips.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(manifest)

    print(f"\nGenerated {len(manifest)} pair(s) ({len(manifest) * 2} clips) in {output_dir}")
    print(f"Manifest saved to: {manifest_path}")
    return manifest_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the setup-section JND A/B pair per reference for the "
                    "P.80x setup/environment check."
    )
    parser.add_argument(
        "--input_dir", "-i", required=True,
        help="Directory containing clean reference WAV files."
    )
    parser.add_argument(
        "--output_dir", "-o", required=True,
        help="Directory for the generated clips and manifest CSV."
    )
    parser.add_argument(
        "--base_url", default=None,
        help="Base URL where clips will be hosted. When set, the pair/ans CSV "
             "columns hold full URLs instead of file names."
    )
    parser.add_argument(
        "--snr_high", type=float, default=DEFAULT_SNR_HIGH,
        help=f"SNR in dB of the cleaner (correct) clip (default: {DEFAULT_SNR_HIGH})."
    )
    parser.add_argument(
        "--snr_low", type=float, default=DEFAULT_SNR_LOW,
        help=f"SNR in dB of the noisier clip (default: {DEFAULT_SNR_LOW}). A smaller "
             f"gap to --snr_high makes the pair harder to tell apart."
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Optional integer seed for reproducible noise and A/B order."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Optional cap on the number of references processed."
    )
    parser.add_argument(
        "--no_anonymize", action="store_true",
        help="Use descriptive <stem>_snr{snr}.wav names instead of random UUIDs "
             "(useful for listening review before hosting)."
    )
    args = parser.parse_args()

    generate_jnd_check_clips(
        args.input_dir, args.output_dir, base_url=args.base_url,
        snr_high=args.snr_high, snr_low=args.snr_low, seed=args.seed,
        limit=args.limit, anonymize=not args.no_anonymize,
    )
