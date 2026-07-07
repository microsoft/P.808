"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

import argparse
import csv
import hashlib
import os
import random
import string
from os.path import basename, isfile, join, splitext

import librosa as lr
import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter


AUDIO_EXTENSION = '.wav'

# Gold clip types and their expected answers per method.
# For ACR: single overall answer (gold_clips_ans).
# For P835: per-dimension answers (sig, bak, ovrl).
# For P804: per-dimension answers; only dimensions rated 1 are listed (others omitted = 5).
#   P804 has 6 degradation types (3 distortion kinds × with/without noise) plus clean.

_P804_ALL_5 = {
    'col_ans': 5, 'disc_ans': 5, 'loud_ans': 5,
    'noise_ans': 5, 'reverb_ans': 5, 'sig_ans': 5, 'ovrl_ans': 5,
}

# Target active-speech levels (dBov) for the loudness degradation. The "too loud"
# case is scaled so the active speech sits at about -10 dBov, the "too quiet"
# case at about -45 dBov.
LOUDNESS_TOO_LOUD_DBOV = -10.0
LOUDNESS_TOO_QUIET_DBOV = -45.0

# Every gold source clip is normalized to this active speech level (dBov) before
# any degradation (or none, for the clean/score-5 case) is applied.
GOLD_SOURCE_TARGET_DBOV = -26.0

# Loudness and coloration degradations keep the first this-many seconds free of the
# degradation (a clean reference), then apply it. Other artifacts (noise, distortion,
# discontinuity) are applied from the beginning of the clip.
GOLD_CLEAN_PREFIX_SEC = 2.0

GOLD_TYPES = {
    'clean': {
        'suffix': 'clean',
        'acr': {'gold_clips_ans': 5},
        'p835': {'gold_sig_ans': 5, 'gold_bak_ans': 5, 'gold_ovrl_ans': 5},
        'p804': {**_P804_ALL_5},
    },
    'background_noise': {
        'suffix': 'noisy',
        'acr': {'gold_clips_ans': 1},
        'p835': {'gold_sig_ans': 5, 'gold_bak_ans': 1, 'gold_ovrl_ans': 1},
        'p804': {'noise_ans': 1, 'ovrl_ans': 1},
    },
    'signal_distortion': {
        'suffix': 'distorted',
        'acr': {'gold_clips_ans': 1},
        'p835': {'gold_sig_ans': 1, 'gold_bak_ans': 4, 'gold_ovrl_ans': 1},
        'p804': {'sig_ans': 1, 'ovrl_ans': 1},
    },
    'both': {
        'suffix': 'noisy_distorted',
        'acr': {'gold_clips_ans': 1},
        'p835': {'gold_sig_ans': 1, 'gold_bak_ans': 1, 'gold_ovrl_ans': 1},
    },
    'discontinuity': {
        'suffix': 'choppy',
        'p804': {'disc_ans': 1, 'sig_ans': 1, 'ovrl_ans': 1},
    },
    'discontinuity_noise': {
        'suffix': 'choppy_noisy',
        'p804': {'noise_ans': 1, 'ovrl_ans': 1},
    },
    'coloration': {
        'suffix': 'colored',
        'p804': {'col_ans': 1, 'sig_ans': 1, 'ovrl_ans': 1},
    },
    'coloration_noise': {
        'suffix': 'colored_noisy',
        'p804': {'noise_ans': 1, 'ovrl_ans': 1},
    },
    'distortion_noise': {
        'suffix': 'distorted_noisy',
        'p804': {'noise_ans': 1, 'ovrl_ans': 1},
    },
    'loudness_high': {
        'suffix': 'too_loud',
        'p804': {'loud_ans': 1},
    },
    'loudness_low': {
        'suffix': 'too_quiet',
        'p804': {'loud_ans': 1},
    },
    'loudness_high_distortion': {
        'suffix': 'too_loud_distorted',
        'p804': {'loud_ans': 1, 'sig_ans': 1, 'ovrl_ans': 1},
    },
    'loudness_low_distortion': {
        # too quiet (low gain): signal detail is hidden, so sig is not judged
        'suffix': 'too_quiet_distorted',
        'p804': {'loud_ans': 1, 'ovrl_ans': 1},
    },
    'loudness_high_noise': {
        'suffix': 'too_loud_noisy',
        'p804': {'loud_ans': 1, 'noise_ans': 1, 'ovrl_ans': 1},
    },
    'loudness_low_noise': {
        'suffix': 'too_quiet_noisy',
        'p804': {'loud_ans': 1, 'noise_ans': 1, 'ovrl_ans': 1},
    },
}

SUPPORTED_METHODS = ['acr', 'p835', 'p804']


def generate_pink_noise(n_samples, sr):
    """
    Generate pink noise (1/f spectrum) with the given number of samples.

    :param n_samples: Number of audio samples to generate.
    :param sr: Sample rate (used for filter design).
    :return: Numpy array of pink noise with unit variance.
    """
    white = np.random.randn(n_samples)
    b, a = butter(1, 200.0 / (sr / 2.0), btype='low')
    pink = lfilter(b, a, white)
    pink = pink / (np.std(pink) + 1e-10)
    return pink


def add_background_noise(signal, sr, snr_db=-5.0):
    """
    Add pink noise to the signal at the specified SNR level.

    :param signal: Clean audio signal as a numpy array.
    :param sr: Sample rate of the signal.
    :param snr_db: Target signal-to-noise ratio in dB (lower = more noise).
    :return: Noisy signal as a numpy array.
    """
    original_rms = np.sqrt(np.mean(signal ** 2)) + 1e-10
    noise = generate_pink_noise(len(signal), sr)
    sig_power = np.mean(signal ** 2) + 1e-10
    noise_power = np.mean(noise ** 2) + 1e-10
    target_noise_power = sig_power / (10.0 ** (snr_db / 10.0))
    noise = noise * np.sqrt(target_noise_power / noise_power)
    noisy = signal + noise
    # Match the original RMS level to preserve perceived loudness
    noisy_rms = np.sqrt(np.mean(noisy ** 2)) + 1e-10
    noisy = noisy * (original_rms / noisy_rms)
    # Prevent clipping
    peak = np.max(np.abs(noisy))
    if peak > 1.0:
        noisy = noisy / peak
    return noisy


def apply_signal_distortion(signal, clip_threshold=0.005):
    """
    Apply hard clipping distortion to the signal.

    The signal is clipped to a fraction of its peak amplitude, creating
    severe distortion that degrades the speech signal while leaving
    the background clean.

    :param signal: Audio signal as a numpy array.
    :param clip_threshold: Fraction of peak amplitude to clip to (0.0–1.0).
    :return: Distorted signal as a numpy array.
    """
    original_rms = np.sqrt(np.mean(signal ** 2)) + 1e-10
    peak = np.max(np.abs(signal)) + 1e-10
    threshold = clip_threshold * peak
    distorted = np.clip(signal, -threshold, threshold)
    # Match the original RMS level to preserve perceived loudness
    distorted_rms = np.sqrt(np.mean(distorted ** 2)) + 1e-10
    distorted = distorted * (original_rms / distorted_rms)
    return distorted


def apply_discontinuity(signal, sr, drop_duration_ms=15):
    """
    Simulate choppy/discontinuous audio by randomly zeroing out segments.

    :param signal: Audio signal as a numpy array.
    :param sr: Sample rate.
    :param drop_duration_ms: Duration of each dropout in milliseconds.
    :return: Choppy signal as a numpy array.
    """
    original_rms = np.sqrt(np.mean(signal ** 2)) + 1e-10
    result = signal.copy()
    drop_rate = np.random.choice([0.30, 0.40])
    drop_samples = int(drop_duration_ms / 1000.0 * sr)
    n_drops = max(1, int(len(signal) * drop_rate / drop_samples))

    for _ in range(n_drops):
        start = np.random.randint(0, max(1, len(signal) - drop_samples))
        end = min(start + drop_samples, len(signal))
        # Apply a short fade to avoid clicks at drop boundaries
        fade_len = min(8, (end - start) // 2)
        result[start:end] = 0.0
        if fade_len > 0 and start >= fade_len:
            result[start - fade_len:start] *= np.linspace(1.0, 0.0, fade_len)
        if fade_len > 0 and end + fade_len <= len(result):
            result[end:end + fade_len] *= np.linspace(0.0, 1.0, fade_len)

    # Restore RMS
    result_rms = np.sqrt(np.mean(result ** 2)) + 1e-10
    result = result * (original_rms / result_rms)
    return result


def apply_coloration(signal, sr):
    """
    Simulate coloration (voice timbre change) by randomly applying one of three
    heavy coloration styles: muffled, resonant, or telephone effect.

    Cut-offs are specified in Hz and converted with the sample rate so the effect is
    consistent across sample rates (16/24/48 kHz). The styles are deliberately strong,
    with no clean passthrough, so the timbre change is clearly audible.

    :param signal: Audio signal as a numpy array.
    :param sr: Sample rate.
    :return: Colored signal as a numpy array.
    """
    original_rms = np.sqrt(np.mean(signal ** 2)) + 1e-10

    style = np.random.choice(['muffled_heavy', 'resonant_heavy', 'telephone'])

    if style == 'muffled_heavy':
        # very muffled / "underwater": aggressive low-pass, no clean passthrough
        center_freq_hz, bandwidth_hz, lp_cutoff_hz = 900, 180, 800
        mix_orig, mix_resonant, mix_muffled = 0.0, 0.2, 0.8
    elif style == 'resonant_heavy':
        # strong narrow-band resonance (hollow / tinny)
        center_freq_hz, bandwidth_hz, lp_cutoff_hz = 1000, 120, 2200
        mix_orig, mix_resonant, mix_muffled = 0.0, 0.85, 0.15
    else:  # telephone
        # band-limited "old telephone" timbre
        center_freq_hz, bandwidth_hz, lp_cutoff_hz = 750, 180, 1600
        mix_orig, mix_resonant, mix_muffled = 0.0, 0.7, 0.3

    nyquist = sr / 2.0
    low = max(0.001, (center_freq_hz - bandwidth_hz / 2.0) / nyquist)
    high = min(0.999, (center_freq_hz + bandwidth_hz / 2.0) / nyquist)
    high = max(low + 0.001, high)
    b_bp, a_bp = butter(4, [low, high], btype='band')
    resonant = lfilter(b_bp, a_bp, signal)

    lp_norm = min(0.999, lp_cutoff_hz / nyquist)
    b_lp, a_lp = butter(4, lp_norm, btype='low')
    muffled = lfilter(b_lp, a_lp, signal)

    colored = mix_orig * signal + mix_resonant * resonant + mix_muffled * muffled

    # Restore RMS
    colored_rms = np.sqrt(np.mean(colored ** 2)) + 1e-10
    colored = colored * (original_rms / colored_rms)
    return colored


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
    full_scale_sine_rms = 1.0 / np.sqrt(2.0)
    frame_len = max(1, int(sr * frame_ms / 1000.0))
    n_frames = len(signal) // frame_len
    if n_frames == 0:
        active_rms = np.sqrt(np.mean(signal ** 2) + eps)
        return 20.0 * np.log10(active_rms / full_scale_sine_rms + eps)
    frames = signal[:n_frames * frame_len].reshape(n_frames, frame_len)
    frame_rms = np.sqrt(np.mean(frames ** 2, axis=1) + eps)
    peak_rms = frame_rms.max()
    threshold = peak_rms / (10.0 ** (threshold_db / 20.0))
    active = frame_rms >= threshold
    if not np.any(active):
        active = np.ones(n_frames, dtype=bool)
    active_rms = np.sqrt(np.mean(frames[active] ** 2) + eps)
    return 20.0 * np.log10(active_rms / full_scale_sine_rms + eps)


def normalize_active_speech_level(signal, sr, target_dbov):
    """
    Scale a signal so its active speech level matches a target level in dBov.

    :param signal: Audio signal as a numpy array.
    :param sr: Sample rate in Hz.
    :param target_dbov: Target active speech level in dBov.
    :return: Level-normalized signal, hard-clipped to [-1, 1].
    """
    current_dbov = active_speech_level_dbov(signal, sr)
    gain_db = target_dbov - current_dbov
    factor = 10.0 ** (gain_db / 20.0)
    return np.clip(signal * factor, -1.0, 1.0)


def apply_loudness(signal, sr, target_dbov=None):
    """
    Apply an extreme loudness change by scaling the active speech level to a target.

    The clip is randomly made too loud or too quiet by scaling so that the active
    speech part reaches ``LOUDNESS_TOO_LOUD_DBOV`` or ``LOUDNESS_TOO_QUIET_DBOV``.
    For the too-loud case peaks may exceed full scale, so the result is hard-clipped
    to [-1, 1] (this preserves the loud level instead of rescaling it back down).

    :param signal: Audio signal as a numpy array.
    :param sr: Sample rate in Hz.
    :param target_dbov: Target active speech level in dBov. If None, randomly picks
        the too-loud or too-quiet target.
    :return: Loudness-adjusted signal as a numpy array.
    """
    if target_dbov is None:
        target_dbov = np.random.choice([LOUDNESS_TOO_LOUD_DBOV, LOUDNESS_TOO_QUIET_DBOV])
    current_dbov = active_speech_level_dbov(signal, sr)
    gain_db = target_dbov - current_dbov
    factor = 10.0 ** (gain_db / 20.0)
    adjusted = signal * factor
    # Preserve the target level (especially for the too-loud case) by hard-clipping
    # rather than rescaling the peak back down.
    return np.clip(adjusted, -1.0, 1.0)


def _apply_random_post_processing(signal, sr, gold_type):
    """
    Apply subtle random post-processing to blur spectral and statistical fingerprints
    across degradation types, making it harder to identify quality from audio analysis.

    Applies type-aware randomization: sparse transient peaks for clipped signals
    (raises crest factor), mild dynamic compression for clean signals (lowers crest
    factor), plus random filtering and micro-noise for all types.

    :param signal: Audio signal as a numpy array.
    :param sr: Sample rate.
    :param gold_type: The degradation type, used to select appropriate blurring.
    :return: Post-processed signal with preserved RMS level.
    """
    original_rms = np.sqrt(np.mean(signal ** 2)) + 1e-10

    # Random subtle low-pass filter (cutoff between 60–95% of Nyquist)
    cutoff_ratio = np.random.uniform(0.60, 0.95)
    b, a = butter(2, cutoff_ratio, btype='low')
    signal = lfilter(b, a, signal)

    # Types where background must stay clean (no noise addition)
    _clean_background_types = ('signal_distortion', 'discontinuity', 'coloration')

    if gold_type in ('signal_distortion', 'both', 'distortion_noise',
                      'discontinuity', 'discontinuity_noise',
                      'coloration', 'coloration_noise'):
        # Add smooth Gaussian-windowed bumps to subtly raise crest factor and kurtosis
        # without creating audible clicks or masking the intended degradation. The
        # amplitude is a small fraction of the signal peak; larger values (previously
        # several times the peak) dominated the audio and hid the real degradation.
        n_bumps = np.random.randint(8, 25)
        peak_val = np.max(np.abs(signal))
        for _ in range(n_bumps):
            center = np.random.randint(0, len(signal))
            amp = np.random.uniform(0.05, 0.2) * peak_val
            sign = np.random.choice([-1, 1])
            # Gaussian window width: 20–80 samples (~2.5–10 ms at 8kHz)
            width = np.random.randint(20, 80)
            half = width // 2
            start = max(0, center - half)
            end = min(len(signal), center + half)
            window = np.exp(-0.5 * ((np.arange(start, end) - center) / (width / 6.0)) ** 2)
            signal[start:end] += sign * amp * window

    if gold_type == 'clean':
        # Apply mild soft-knee compression to reduce crest factor
        threshold = np.random.uniform(0.3, 0.6) * np.max(np.abs(signal))
        ratio = np.random.uniform(2.0, 4.0)
        abs_signal = np.abs(signal)
        mask = abs_signal > threshold
        compressed = signal.copy()
        compressed[mask] = np.sign(signal[mask]) * (
            threshold + (abs_signal[mask] - threshold) / ratio
        )
        signal = compressed

    # Add a small amount of shaped noise (skip for types that must keep background clean)
    if gold_type not in _clean_background_types:
        noise_level = np.random.uniform(0.002, 0.01) * original_rms
        micro_noise = np.random.randn(len(signal)) * noise_level
        signal = signal + micro_noise

    # Restore original RMS
    processed_rms = np.sqrt(np.mean(signal ** 2)) + 1e-10
    signal = signal * (original_rms / processed_rms)

    # Prevent clipping
    peak = np.max(np.abs(signal))
    if peak > 1.0:
        signal = signal / peak

    return signal


def _apply_delayed(base, degraded_full, sr, delay_sec=GOLD_CLEAN_PREFIX_SEC, fade_ms=30.0):
    """
    Keep the first ``delay_sec`` seconds of ``base`` and switch to ``degraded_full``
    afterwards, with a short crossfade to avoid a click at the boundary.

    Used so that loudness/coloration degradations only appear after an initial
    clean-reference portion, while any other artifact already present in ``base``
    (e.g. noise or distortion) continues throughout.

    :param base: The signal without the delayed degradation (may already contain
        other artifacts). Used for the clean prefix.
    :param degraded_full: The full-length signal with the delayed degradation applied.
    :param sr: Sample rate in Hz.
    :param delay_sec: Length of the clean prefix in seconds.
    :param fade_ms: Crossfade length in milliseconds at the switch point.
    :return: The combined signal as a numpy array.
    """
    n = int(delay_sec * sr)
    # clip too short to hold the clean prefix -> apply the degradation to all of it
    if n >= len(base):
        return degraded_full
    result = np.concatenate([base[:n], degraded_full[n:]]).astype(float)
    fade = min(int(fade_ms / 1000.0 * sr), len(base) - n)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade)
        result[n:n + fade] = base[n:n + fade] * (1.0 - ramp) + degraded_full[n:n + fade] * ramp
    return result


def process_clip(signal, sr, gold_type, snr_db=-5.0, clip_threshold=0.005):
    """
    Apply the specified degradation type to an audio signal, followed by
    subtle random post-processing to blur statistical fingerprints.

    :param signal: Clean audio signal as a numpy array.
    :param sr: Sample rate.
    :param gold_type: Degradation type name from GOLD_TYPES.
    :param snr_db: SNR in dB for noise addition.
    :param clip_threshold: Clipping threshold for signal distortion.
    :return: Processed audio signal as a numpy array.
    """
    if gold_type == 'clean':
        result = signal.copy()
    elif gold_type == 'background_noise':
        result = add_background_noise(signal, sr, snr_db)
    elif gold_type == 'signal_distortion':
        result = apply_signal_distortion(signal, clip_threshold)
    elif gold_type == 'both':
        distorted = apply_signal_distortion(signal, clip_threshold)
        result = add_background_noise(distorted, sr, snr_db)
    elif gold_type == 'discontinuity':
        result = apply_discontinuity(signal, sr)
    elif gold_type == 'discontinuity_noise':
        result = apply_discontinuity(signal, sr)
        result = add_background_noise(result, sr, snr_db)
    elif gold_type == 'coloration':
        # coloration starts after the clean-reference prefix
        result = _apply_delayed(signal, apply_coloration(signal, sr), sr)
    elif gold_type == 'coloration_noise':
        # colour the speech first (delayed after the clean prefix), then add broadband
        # noise on top, so the noise itself is not coloured (more realistic than
        # colouring an already-noisy signal)
        colored = _apply_delayed(signal, apply_coloration(signal, sr), sr)
        result = add_background_noise(colored, sr, snr_db)
    elif gold_type == 'distortion_noise':
        result = apply_signal_distortion(signal, clip_threshold)
        result = add_background_noise(result, sr, snr_db)
    elif gold_type == 'loudness_high':
        # too loud, applied after the clean-reference prefix
        result = _apply_delayed(signal, apply_loudness(signal, sr, LOUDNESS_TOO_LOUD_DBOV), sr)
    elif gold_type == 'loudness_low':
        # too quiet (low gain), applied after the clean-reference prefix
        result = _apply_delayed(signal, apply_loudness(signal, sr, LOUDNESS_TOO_QUIET_DBOV), sr)
    elif gold_type == 'loudness_high_distortion':
        # distortion from the beginning; too-loud gain delayed after the clean prefix
        base = apply_signal_distortion(signal, clip_threshold)
        result = _apply_delayed(base, apply_loudness(base, sr, LOUDNESS_TOO_LOUD_DBOV), sr)
    elif gold_type == 'loudness_low_distortion':
        # distortion from the beginning; too-quiet gain delayed after the clean prefix
        base = apply_signal_distortion(signal, clip_threshold)
        result = _apply_delayed(base, apply_loudness(base, sr, LOUDNESS_TOO_QUIET_DBOV), sr)
    elif gold_type == 'loudness_high_noise':
        # noise from the beginning; too-loud gain delayed after the clean prefix
        base = add_background_noise(signal, sr, snr_db)
        result = _apply_delayed(base, apply_loudness(base, sr, LOUDNESS_TOO_LOUD_DBOV), sr)
    elif gold_type == 'loudness_low_noise':
        # noise from the beginning; too-quiet gain delayed after the clean prefix
        base = add_background_noise(signal, sr, snr_db)
        result = _apply_delayed(base, apply_loudness(base, sr, LOUDNESS_TOO_QUIET_DBOV), sr)
    else:
        raise ValueError(f"Unknown gold type: {gold_type}")

    # Skip post-processing for loudness types to preserve the gain change
    if gold_type.startswith('loudness'):
        return result

    return _apply_random_post_processing(result, sr, gold_type)


def get_csv_columns(method):
    """
    Return the list of CSV column names for the given test method.

    :param method: Test method ('acr', 'p835', or 'p804').
    :return: List of column name strings.
    """
    if method == 'acr':
        return ['gold_clips', 'gold_clips_ans']
    elif method == 'p835':
        return ['gold_clips', 'gold_sig_ans', 'gold_bak_ans', 'gold_ovrl_ans']
    elif method == 'p804':
        return ['gold_clips', 'col_ans', 'disc_ans', 'loud_ans',
                'noise_ans', 'reverb_ans', 'sig_ans', 'ovrl_ans']
    else:
        raise ValueError(f"Unsupported method: {method}")


def _generate_anonymous_name():
    """
    Generate a random anonymous filename that reveals nothing about the clip's quality.

    :return: A random 12-character alphanumeric string.
    """
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))


def create_gold_clips(input_dir, output_dir, method, snr_db=-5.0, clip_threshold=0.005, anonymize=True):
    """
    Generate gold clips from clean source audio files.

    For each source file, degraded versions are created based on the method.
    Each source clip is first normalized to a fixed active speech level
    (``GOLD_SOURCE_TARGET_DBOV``) before any degradation is applied.
    A CSV report mapping filenames to expected answers is written to output_dir.
    For P804, only dimensions with answer 1 are written; others are left empty.

    :param input_dir: Directory containing clean source WAV files.
    :param output_dir: Directory where gold clips and the report CSV will be saved.
    :param method: Test method ('acr', 'p835', or 'p804').
    :param snr_db: SNR in dB for background noise addition.
    :param clip_threshold: Clipping threshold for signal distortion (0.0–1.0).
    :param anonymize: If True, use random filenames; if False, use descriptive names.
    :return: Number of gold clips created.
    """
    assert method in SUPPORTED_METHODS, f"Method '{method}' not supported. Choose from {SUPPORTED_METHODS}"

    os.makedirs(output_dir, exist_ok=True)

    source_files = sorted([
        join(input_dir, f)
        for f in os.listdir(input_dir)
        if isfile(join(input_dir, f)) and f.lower().endswith(AUDIO_EXTENSION)
    ])

    if not source_files:
        raise FileNotFoundError(f"No {AUDIO_EXTENSION} files found in {input_dir}")

    print(f"Found {len(source_files)} source file(s) in {input_dir}")
    print(f"Method: {method}, SNR: {snr_db} dB, Clip threshold: {clip_threshold}")

    csv_columns = get_csv_columns(method)
    used_names = set()
    rows = []
    count = 0

    # Only use gold types that have answers defined for this method
    applicable_types = {k: v for k, v in GOLD_TYPES.items() if method in v}

    for src_path in source_files:
        src_name = splitext(basename(src_path))[0]
        signal, sr = lr.load(src_path, sr=None)
        # Normalize every source clip to a fixed active speech level before degrading,
        # so degradations (or none, for the clean/score-5 case) start from -26 dBov.
        signal = normalize_active_speech_level(signal, sr, GOLD_SOURCE_TARGET_DBOV)
        print(f"  Processing: {basename(src_path)} ({len(signal)} samples, {sr} Hz)")

        for gold_type, type_info in applicable_types.items():
            answers = type_info[method]

            if anonymize:
                while True:
                    anon_name = _generate_anonymous_name()
                    if anon_name not in used_names:
                        used_names.add(anon_name)
                        break
                out_name = f"{anon_name}{AUDIO_EXTENSION}"
            else:
                suffix = type_info['suffix']
                out_name = f"{src_name}_gold_{suffix}{AUDIO_EXTENSION}"
            out_path = join(output_dir, out_name)

            processed = process_clip(signal, sr, gold_type, snr_db, clip_threshold)
            sf.write(out_path, processed, sr, subtype='PCM_16')

            row = {'gold_clips': out_name}
            if method == 'p804' and gold_type != 'clean':
                # Sparse format: only include dimensions with answer 1
                for col in csv_columns[1:]:
                    row[col] = answers.get(col, '')
            else:
                row.update(answers)
            rows.append(row)
            count += 1

    report_path = join(output_dir, 'gold_clips_report.csv')
    with open(report_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\n{count} gold clip(s) created in {output_dir}")
    print(f"Report saved to {report_path}")
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate gold standard clips from clean source audio files. '
                    'Creates four degradation types per source clip: clean, background noise, '
                    'signal distortion, and both. Outputs degraded audio files and a CSV report '
                    'with expected answers for use with master_script.py.'
    )
    parser.add_argument(
        '--input_dir',
        required=True,
        help='Directory containing clean source WAV files.'
    )
    parser.add_argument(
        '--output_dir',
        required=True,
        help='Directory where gold clips and the report CSV will be saved.'
    )
    parser.add_argument(
        '--method',
        required=True,
        choices=SUPPORTED_METHODS,
        help='Test method. Determines the expected answer format in the output CSV.'
    )
    parser.add_argument(
        '--snr_db',
        type=float,
        default=-5.0,
        help='Signal-to-noise ratio in dB for background noise (default: -5.0). '
             'Lower values mean more noise.'
    )
    parser.add_argument(
        '--clip_threshold',
        type=float,
        default=0.005,
        help='Hard clipping threshold as a fraction of peak amplitude (default: 0.005). '
             'Lower values mean more distortion.'
    )
    parser.add_argument(
        '--no_anonymize',
        action='store_true',
        help='Use descriptive filenames instead of anonymous random names. '
             'Default is to anonymize filenames.'
    )

    args = parser.parse_args()

    assert os.path.isdir(args.input_dir), f"Input directory not found: {args.input_dir}"
    assert 0.0 < args.clip_threshold <= 1.0, "clip_threshold must be between 0.0 (exclusive) and 1.0"

    create_gold_clips(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        method=args.method,
        snr_db=args.snr_db,
        clip_threshold=args.clip_threshold,
        anonymize=not args.no_anonymize,
    )
