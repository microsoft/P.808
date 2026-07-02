"""
/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

Generate the bandwidth-check ("same vs. different quality") clips used in the
P.80x qualification test.

For every clean reference speech file in an input directory this script builds
five combined clips.  Each combined clip is two speech segments joined by a
short beep tone (``segment A | beep | segment B``); the listener is asked
whether the audio *after* the beep sounds different from the audio *before* it.

The five cases per reference are (both halves always come from the *same*
source clip):

    q1  reference | beep | reference + noise(3.5-22 kHz)   -> different (dq)
    q2  reference | beep | reference + noise(8.5-22 kHz)   -> different (dq)
    q3  reference | beep | reference + noise(15-22 kHz)    -> different (dq)
    q4  reference | beep | reference                       -> same      (sq)
    q5  reference | beep | reference                       -> same      (sq)

The added noise is band-limited to a high-frequency band and made clearly
audible *within that band*.  A participant only hears the difference if their
playback chain and hearing reproduce that band, so q1 (widest band) is the
obvious/attention case while q3 (15-22 kHz) discriminates full-band capable
equipment.  q4 and q5 carry no audible change and are the obvious "same"
(trapping) cases.  These design answers match the hosted production clips
(``d_g1_cmb.wav`` .. ``d_g5_cmb.wav``) referenced by ``master_script`` and
``P808Template/Qualification.html`` (dq, dq, dq, sq, sq).

Every segment additionally receives an independent *inaudible* dither (far
below the speech, but above the 16-bit LSB).  This keeps the two halves - and
the two "same" clips - from ever being bit-identical, so exact-match / dedup
detection cannot flag them, while humans still perceive them as identical.

Output clip names are anonymized random UUIDs so the hosted file names do not
reveal the source reference; the manifest CSV keeps the source-to-clip mapping.

The references must be full-band (48 kHz recommended); a reference sampled below
twice the lowest band edge cannot carry the high-frequency noise and is
skipped.

Usage:
    python utils/create_bandwidth_check_clips.py ^
        --input_dir C:/datasets/p501 ^
        --output_dir output/bw_test ^
        --base_url https://host/container/clips/bw-test
"""

import argparse
import csv
import os
import uuid

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt


# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

# Low edge of the band-limited noise for q1/q2/q3 (high edge is the reference
# bandwidth, clamped below Nyquist). Lower edges are progressively higher so the
# added noise sits in an ever-higher band that needs better equipment to hear.
NOISE_BANDS_HZ = [
    (3500, 22000),   # q1: WB+ band, audible on most decent equipment
    (8500, 22000),   # q2: SWB band
    (15000, 22000),  # q3: FB band, only high-end equipment reproduces it
]

# Correct answer for each of the five cases ("dq" = different, "sq" = same).
CASE_ANSWERS = ["dq", "dq", "dq", "sq", "sq"]

# Band-limited noise level, in dB relative to the reference active speech level.
# The production clips use roughly +13 dB, which keeps the noise clearly audible
# within its band while the reference stays undistorted.
DEFAULT_NOISE_GAIN_DB = 13.0

# Level of the inaudible dither added to every segment, in dBov. It is well below
# the speech (so humans cannot hear it) yet several 16-bit LSBs high, so it
# survives quantization and keeps the two halves - and the two "same" clips -
# from ever being bit-identical (defeating exact-match / dedup detection).
INAUDIBLE_DITHER_DBOV = -75.0

FULL_SCALE_SINE_RMS = 1.0 / np.sqrt(2.0)


# ---------------------------------------------------------------------------
# Level helpers
# ---------------------------------------------------------------------------

def rms(signal):
    """
    Compute the root-mean-square level of a signal.

    :param signal: Audio signal as a numpy array.
    :return: RMS value as a float (with a small epsilon floor).
    """
    return float(np.sqrt(np.mean(np.square(signal)) + 1e-12))


def active_speech_level_dbov(signal, sr, frame_ms=20.0, threshold_db=25.0):
    """
    Estimate the active speech level of a signal in dBov.

    The level is measured over the active speech part only: the signal is split
    into short frames and frames whose RMS is within ``threshold_db`` of the
    loudest frame are treated as active (speech) frames. ``0 dBov`` corresponds
    to a full-scale sine wave (RMS = 1/sqrt(2)).

    :param signal: Audio signal as a numpy array in the range [-1, 1].
    :param sr: Sample rate in Hz.
    :param frame_ms: Frame length in milliseconds.
    :param threshold_db: Frames within this many dB below the loudest frame count as active.
    :return: Active speech level in dBov.
    """
    eps = 1e-12
    frame_len = max(1, int(sr * frame_ms / 1000.0))
    n_frames = len(signal) // frame_len
    if n_frames == 0:
        active_rms = np.sqrt(np.mean(signal ** 2) + eps)
        return 20.0 * np.log10(active_rms / FULL_SCALE_SINE_RMS + eps)
    frames = signal[:n_frames * frame_len].reshape(n_frames, frame_len)
    frame_rms = np.sqrt(np.mean(frames ** 2, axis=1) + eps)
    peak_rms = frame_rms.max()
    threshold = peak_rms / (10.0 ** (threshold_db / 20.0))
    active = frame_rms >= threshold
    if not np.any(active):
        active = np.ones(n_frames, dtype=bool)
    active_rms = np.sqrt(np.mean(frames[active] ** 2) + eps)
    return 20.0 * np.log10(active_rms / FULL_SCALE_SINE_RMS + eps)


def scale_to_dbov(signal, target_dbov):
    """
    Scale a stationary signal so its overall RMS reaches a target level in dBov.

    :param signal: Audio signal as a numpy array.
    :param target_dbov: Target RMS level in dBov (0 dBov = full-scale sine).
    :return: Level-scaled signal as a numpy array.
    """
    target_rms = FULL_SCALE_SINE_RMS * (10.0 ** (target_dbov / 20.0))
    return signal * (target_rms / rms(signal))


# ---------------------------------------------------------------------------
# Signal building blocks
# ---------------------------------------------------------------------------

def bandpass(signal, low_hz, high_hz, fs, order=5):
    """
    Band-pass filter a signal, clamping the band edges to the valid range.

    The high edge is clamped just below Nyquist and the low edge is kept above
    zero so the filter stays stable for any input sample rate.

    :param signal: Audio signal as a numpy array.
    :param low_hz: Lower cut-off frequency in Hz.
    :param high_hz: Upper cut-off frequency in Hz.
    :param fs: Sample rate in Hz.
    :param order: Butterworth filter order (default: 5).
    :return: Band-pass filtered signal as a numpy array.
    """
    nyq = 0.5 * fs
    low = max(1.0, low_hz) / nyq
    high = min(high_hz, 0.99 * nyq) / nyq
    sos = butter(order, [low, high], btype="bandpass", output="sos")
    return sosfilt(sos, signal)


def band_limited_noise(num_samples, low_hz, high_hz, fs, target_dbov,
                       order=5, rng=None):
    """
    Create band-limited white noise scaled to a target level.

    White Gaussian noise is band-pass filtered to ``[low_hz, high_hz]`` and then
    scaled so its RMS reaches ``target_dbov``.

    :param num_samples: Length of the noise in samples.
    :param low_hz: Lower cut-off frequency in Hz.
    :param high_hz: Upper cut-off frequency in Hz.
    :param fs: Sample rate in Hz.
    :param target_dbov: Target RMS level of the band-limited noise in dBov.
    :param order: Butterworth filter order (default: 5).
    :param rng: Optional numpy random generator for reproducibility.
    :return: Band-limited noise as a numpy array.
    """
    if rng is None:
        rng = np.random.default_rng()
    noise = rng.standard_normal(num_samples)
    noise = bandpass(noise, low_hz, high_hz, fs, order=order)
    return scale_to_dbov(noise, target_dbov)


def add_inaudible_dither(signal, rng, level_dbov=INAUDIBLE_DITHER_DBOV):
    """
    Add inaudible low-level white noise to a segment.

    The noise sits far below the speech so it cannot be heard, but it is high
    enough to survive 16-bit quantization. A fresh realization is drawn on every
    call so no two segments end up bit-identical, which defeats exact-match and
    dedup detection of the "same" trapping clips without affecting how the audio
    sounds.

    :param signal: Audio signal as a numpy array.
    :param rng: Numpy random generator used to draw the noise.
    :param level_dbov: Noise RMS level in dBov (default: ``INAUDIBLE_DITHER_DBOV``).
    :return: Signal with the inaudible dither added.
    """
    noise = scale_to_dbov(rng.standard_normal(len(signal)), level_dbov)
    return signal + noise


def make_beep(fs, freq_hz=440.0, duration_sec=1.0, amplitude=0.2, fade_ms=10.0):
    """
    Create a short beep tone with fade-in/out to avoid clicks.

    :param fs: Sample rate in Hz.
    :param freq_hz: Tone frequency in Hz (default: 440).
    :param duration_sec: Tone duration in seconds (default: 1.0).
    :param amplitude: Peak amplitude in [0, 1] (default: 0.2).
    :param fade_ms: Fade-in/out length in milliseconds (default: 10).
    :return: Beep tone as a numpy array.
    """
    n = int(duration_sec * fs)
    t = np.arange(n) / fs
    tone = amplitude * np.sin(2.0 * np.pi * freq_hz * t)
    fade = min(int(fade_ms / 1000.0 * fs), n // 2)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade)
        tone[:fade] *= ramp
        tone[-fade:] *= ramp[::-1]
    return tone


def assemble_pair(part_a, part_b, beep, gap):
    """
    Join two speech segments with a beep separator and silence gaps.

    The result is ``part_a | gap | beep | gap | part_b``.

    :param part_a: First speech segment as a numpy array.
    :param part_b: Second speech segment as a numpy array.
    :param beep: Beep tone as a numpy array.
    :param gap: Silence gap as a numpy array (placed on both sides of the beep).
    :return: Concatenated clip as a numpy array, hard-clipped to [-1, 1].
    """
    clip = np.concatenate([part_a, gap, beep, gap, part_b])
    return np.clip(clip, -1.0, 1.0)


# ---------------------------------------------------------------------------
# Per-reference generation
# ---------------------------------------------------------------------------

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


def generate_for_reference(ref_path, output_dir, noise_gain_db=DEFAULT_NOISE_GAIN_DB,
                           beep_freq=440.0, beep_sec=1.0, gap_sec=0.2, seed=None,
                           anonymize=True):
    """
    Build the five bandwidth-check clips for a single reference file.

    Both halves of every clip come from the *same* reference source. q1-q3 add
    audible band-limited noise to the second half (answer "different"); q4 and q5
    add no audible change and are the "same" trapping cases. To keep the two
    halves - and the two "same" clips - from being bit-identical, every segment
    also receives an independent inaudible dither, so exact-match / dedup
    detection cannot flag them while humans still hear "same".

    Output file names are anonymized random UUIDs so the hosted clip names do not
    reveal the source reference; the manifest CSV keeps the mapping. Set
    ``anonymize`` to False to use descriptive ``<stem>_q{n}.wav`` names for
    listening review.

    :param ref_path: Path to the clean reference WAV file.
    :param output_dir: Directory where the five output clips are written.
    :param noise_gain_db: Band-noise level relative to the reference active
        speech level, in dB (default: +13).
    :param beep_freq: Beep tone frequency in Hz (default: 440).
    :param beep_sec: Beep tone duration in seconds (default: 1.0).
    :param gap_sec: Silence gap on each side of the beep, in seconds (default: 0.2).
    :param seed: Optional integer seed for reproducible noise.
    :param anonymize: When True (default) use random UUID file names; when False
        use descriptive ``<stem>_q{n}.wav`` names.
    :return: List of the five output clip file names (basenames), ordered q1..q5,
        or ``None`` if the reference sample rate is too low for the noise bands.
    """
    ref, fs, subtype = load_mono(ref_path)
    nyq = 0.5 * fs
    if nyq <= min(low for low, _ in NOISE_BANDS_HZ):
        print(f"  Skipping {os.path.basename(ref_path)}: sample rate {fs} Hz too "
              f"low for the bandwidth bands.")
        return None

    rng = np.random.default_rng(seed)
    ref_asl = active_speech_level_dbov(ref, fs)
    noise_dbov = ref_asl + noise_gain_db

    beep = make_beep(fs, freq_hz=beep_freq, duration_sec=beep_sec)
    gap = np.zeros(int(gap_sec * fs))

    stem = os.path.splitext(os.path.basename(ref_path))[0]
    filenames = []

    for i in range(5):
        # First half: the reference with only inaudible dither.
        part_a = add_inaudible_dither(ref, rng)
        if i < len(NOISE_BANDS_HZ):
            # q1-q3: high-frequency band-limited noise on the second half.
            low_hz, high_hz = NOISE_BANDS_HZ[i]
            noise = band_limited_noise(len(ref), low_hz, high_hz, fs,
                                       noise_dbov, rng=rng)
            part_b = add_inaudible_dither(ref + noise, rng)
        else:
            # q4/q5: same source, no audible change (only inaudible dither).
            part_b = add_inaudible_dither(ref, rng)

        clip = assemble_pair(part_a, part_b, beep, gap)
        out_name = f"{uuid.uuid4().hex}.wav" if anonymize else f"{stem}_q{i + 1}.wav"
        sf.write(os.path.join(output_dir, out_name), clip, fs, subtype=subtype)
        filenames.append(out_name)

    return filenames


def generate_bandwidth_check_clips(input_dir, output_dir, base_url=None,
                                   noise_gain_db=DEFAULT_NOISE_GAIN_DB,
                                   beep_freq=440.0, beep_sec=1.0, gap_sec=0.2,
                                   seed=None, limit=None, anonymize=True):
    """
    Generate bandwidth-check clips for every reference WAV in a directory.

    For each reference, five clips (q1..q5) are written to ``output_dir`` and a
    ``bandwidth_check_clips.csv`` manifest is produced with one row per
    reference. The manifest columns are ``ref_clip``, ``q1``..``q5`` (output
    clip name, or full URL when ``base_url`` is given) and ``ans_q1``..``ans_q5``
    (the correct answer ``dq``/``sq`` for each case).

    :param input_dir: Directory containing clean reference WAV files.
    :param output_dir: Directory for the generated clips and the manifest CSV.
    :param base_url: Optional base URL; when set the q1..q5 columns hold full
        URLs (``base_url`` + file name) instead of bare file names.
    :param noise_gain_db: Band-noise level relative to the reference active
        speech level, in dB (default: +13).
    :param beep_freq: Beep tone frequency in Hz (default: 440).
    :param beep_sec: Beep tone duration in seconds (default: 1.0).
    :param gap_sec: Silence gap on each side of the beep, in seconds (default: 0.2).
    :param seed: Optional integer seed for reproducible noise.
    :param limit: Optional cap on the number of references processed.
    :param anonymize: When True (default) use random UUID clip names; when False
        use descriptive ``<stem>_q{n}.wav`` names for listening review.
    :return: Path to the generated manifest CSV.
    """
    os.makedirs(output_dir, exist_ok=True)
    references = sorted(f for f in os.listdir(input_dir)
                        if f.lower().endswith(".wav"))
    if limit is not None:
        references = references[:limit]
    assert references, f"No .wav reference files found in {input_dir}"

    manifest = []
    for idx, ref_name in enumerate(references):
        ref_path = os.path.join(input_dir, ref_name)
        print(f"[{idx + 1}/{len(references)}] {ref_name}")
        # Derive a per-reference seed so runs are reproducible yet references differ.
        ref_seed = None if seed is None else seed + idx
        filenames = generate_for_reference(
            ref_path, output_dir, noise_gain_db=noise_gain_db,
            beep_freq=beep_freq, beep_sec=beep_sec, gap_sec=gap_sec, seed=ref_seed,
            anonymize=anonymize,
        )
        if filenames is None:
            continue

        row = {"ref_clip": ref_name}
        for i, name in enumerate(filenames):
            value = base_url.rstrip("/") + "/" + name if base_url else name
            row[f"q{i + 1}"] = value
            row[f"ans_q{i + 1}"] = CASE_ANSWERS[i]
        manifest.append(row)

    columns = ["ref_clip"]
    for i in range(1, 6):
        columns.append(f"q{i}")
    for i in range(1, 6):
        columns.append(f"ans_q{i}")

    manifest_path = os.path.join(output_dir, "bandwidth_check_clips.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(manifest)

    print(f"\nGenerated {len(manifest)} reference set(s) "
          f"({len(manifest) * 5} clips) in {output_dir}")
    print(f"Manifest saved to: {manifest_path}")
    return manifest_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the five bandwidth-check clips per reference for "
                    "the P.80x qualification test."
    )
    parser.add_argument(
        "--input_dir", "-i", required=True,
        help="Directory containing clean, full-band reference WAV files."
    )
    parser.add_argument(
        "--output_dir", "-o", required=True,
        help="Directory for the generated clips and manifest CSV."
    )
    parser.add_argument(
        "--base_url", default=None,
        help="Base URL where clips will be hosted. When set, the q1..q5 CSV "
             "columns hold full URLs instead of file names."
    )
    parser.add_argument(
        "--noise_gain_db", type=float, default=DEFAULT_NOISE_GAIN_DB,
        help="Band-noise level relative to the reference active speech level, "
             f"in dB (default: {DEFAULT_NOISE_GAIN_DB})."
    )
    parser.add_argument(
        "--beep_freq", type=float, default=440.0,
        help="Beep tone frequency in Hz (default: 440)."
    )
    parser.add_argument(
        "--beep_sec", type=float, default=1.0,
        help="Beep tone duration in seconds (default: 1.0)."
    )
    parser.add_argument(
        "--gap_sec", type=float, default=0.2,
        help="Silence gap on each side of the beep, in seconds (default: 0.2)."
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Optional integer seed for reproducible noise."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Optional cap on the number of references processed."
    )
    parser.add_argument(
        "--no_anonymize", action="store_true",
        help="Use descriptive <stem>_q{n}.wav names instead of random UUIDs "
             "(useful for listening review)."
    )

    args = parser.parse_args()

    generate_bandwidth_check_clips(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        base_url=args.base_url,
        noise_gain_db=args.noise_gain_db,
        beep_freq=args.beep_freq,
        beep_sec=args.beep_sec,
        gap_sec=args.gap_sec,
        seed=args.seed,
        limit=args.limit,
        anonymize=not args.no_anonymize,
    )
