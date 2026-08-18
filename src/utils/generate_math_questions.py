"""
/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

Generate math audio questions for P.808 headphone verification.

Creates stereo WAV files where a spoken prompt ("Please add up the following
numbers") plays in both channels, followed by individual numbers panned to
either the left or right speaker.  Each question uses at least one number in
each channel so participants must hear both sides to compute the correct sum.

The script pre-renders TTS segments for the prompt and all required number
words, then assembles each question from these cached segments.  A manifest
CSV is written alongside the WAV files with the correct answer for each
question.

Requires the Azure Cognitive Services Speech SDK and Azure Identity:

    pip install azure-cognitiveservices-speech azure-identity

See also ``trapping_clips_assets/messages/azure_tts_create_msgs.py`` for the
original Azure TTS example this script is based on.

Usage:
    python utils/generate_math_questions.py ^
        --output_dir output/math ^
        --count 10 ^
        --region eastus ^
        --resource_id <your-resource-id>
"""

import argparse
import csv
import hashlib
import os
import random
import tempfile
import uuid
import wave

import numpy as np


# ---------------------------------------------------------------------------
# Number-to-word conversion (1–99)
# ---------------------------------------------------------------------------

_ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety",
]

PROMPT_TEXT = "Please add up the following numbers"


def number_to_words(n):
    """
    Convert an integer in the range 1–99 to its English word form.

    :param n: Integer between 1 and 99 inclusive.
    :return: English word string (e.g., 1 → "one", 42 → "forty two").
    :raises ValueError: If *n* is outside the supported range.
    """
    if not 1 <= n <= 99:
        raise ValueError(f"Number {n} is outside the supported range (1-99).")
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + ("" if ones == 0 else " " + _ONES[ones])


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def compute_math_hash(audio_url, answer):
    """
    Compute a SHA-256 hash for client-side math answer verification.

    The hash is derived from the audio URL and the correct answer so that
    the raw answer is never exposed in the HTML source.  The client can
    verify a user's input by computing the same hash and comparing.

    :param audio_url: Full URL of the math audio clip.
    :param answer: Correct numeric answer (int or str).
    :return: Hex-encoded SHA-256 digest string.
    """
    payload = f"{audio_url}:{answer}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Azure TTS helpers
# ---------------------------------------------------------------------------

def configure_speech(region, resource_id):
    """
    Create an Azure SpeechConfig authenticated via DefaultAzureCredential.

    The output format is set to 16 kHz 16-bit mono PCM to match the sample
    rate of the existing math question clips shipped with the P.808 toolkit.

    :param region: Azure Speech service region (e.g. ``"eastus"``).
    :param resource_id: Full Azure resource ID of the Speech resource.
    :return: Configured ``speechsdk.SpeechConfig`` instance.
    """
    import azure.cognitiveservices.speech as speechsdk
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")

    speech_config = speechsdk.SpeechConfig(subscription="unused", region=region)
    speech_config.authorization_token = "aad#" + resource_id + "#" + token.token
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
    )
    return speech_config


def synthesize_to_wav(speech_config, text, output_path, voice="en-US-AriaNeural"):
    """
    Synthesize a text phrase to a WAV file using Azure Neural TTS.

    Uses SSML to select the voice and wraps the text in a ``<s>`` element
    for natural sentence-level prosody.

    :param speech_config: Azure ``SpeechConfig`` instance.
    :param text: Plain text to synthesize.
    :param output_path: Destination path for the output WAV file.
    :param voice: Azure TTS voice name (default: ``en-US-AriaNeural``).
    :return: ``True`` on success, ``False`` on failure.
    """
    import azure.cognitiveservices.speech as speechsdk

    audio_output = speechsdk.audio.AudioOutputConfig(filename=output_path)
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_output
    )

    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="en-US"><voice name="{voice}">'
        f"<s>{text}</s></voice></speak>"
    )
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return True

    cancellation = result.cancellation_details
    print(f"  TTS failed for '{text}': {cancellation.reason}")
    if cancellation.error_details:
        print(f"  Error: {cancellation.error_details}")
    return False


# ---------------------------------------------------------------------------
# ASL measurement and normalization (ITU-T P.56 Method B)
# ---------------------------------------------------------------------------

def measure_asl(samples, sample_rate):
    """
    Measure Active Speech Level per ITU-T P.56 Method B.

    Uses an iterative threshold refinement to distinguish active speech
    frames from silence and returns the RMS level of active regions in
    dBov (decibels relative to digital full-scale).

    :param samples: Audio samples as a float ndarray, values in [-1, 1].
    :param sample_rate: Sample rate in Hz.
    :return: Active speech level in dBov, or ``-inf`` for silent input.
    """
    x = samples.astype(np.float64)
    sq = x ** 2

    long_term_sq = np.mean(sq)
    if long_term_sq < 1e-20:
        return -np.inf

    # 30 ms frames for activity detection
    frame_len = max(1, int(0.03 * sample_rate))
    n_frames = len(x) // frame_len
    if n_frames == 0:
        return 10 * np.log10(long_term_sq)

    frame_energies = np.mean(
        sq[:n_frames * frame_len].reshape(n_frames, frame_len), axis=1
    )

    # Iterative refinement: threshold at active_level - 15.9 dB
    active_level_sq = long_term_sq
    for _ in range(20):
        threshold = active_level_sq * 10 ** (-15.9 / 10)
        active_mask = frame_energies > threshold

        if not np.any(active_mask):
            break

        new_active_level_sq = np.mean(frame_energies[active_mask])

        if abs(10 * np.log10(new_active_level_sq / (active_level_sq + 1e-30))) < 0.05:
            active_level_sq = new_active_level_sq
            break

        active_level_sq = new_active_level_sq

    return 10 * np.log10(active_level_sq + 1e-30)


def normalize_segments_to_asl(segments, sample_rate, target_dbov=-26.0):
    """
    Scale all pre-rendered TTS segments so their combined ASL matches the target.

    The prompt and every number word are concatenated into a single mono
    signal for measurement.  The resulting gain is applied uniformly to
    every segment so relative levels are preserved.

    :param segments: Dict mapping ``"prompt"`` and integers to mono float32
        arrays (as returned by :func:`prerender_tts_segments`).
    :param sample_rate: Sample rate in Hz.
    :param target_dbov: Desired active speech level in dBov (default: -26).
    :return: New segments dict with scaled arrays.
    """
    all_audio = [segments["prompt"]]
    for key in sorted(k for k in segments if isinstance(k, int)):
        all_audio.append(segments[key])
    combined = np.concatenate(all_audio)

    current_asl = measure_asl(combined, sample_rate)
    if np.isinf(current_asl):
        print(f"  Warning: could not measure ASL (silent input), skipping normalization.")
        return segments

    gain_db = target_dbov - current_asl
    gain = 10 ** (gain_db / 20)

    print(f"  Current ASL: {current_asl:.1f} dBov -> target: {target_dbov:.1f} dBov "
          f"(gain: {gain_db:+.1f} dB)")

    return {k: (v * gain).astype(np.float32) for k, v in segments.items()}


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def load_wav_mono(path):
    """
    Load a WAV file and return its samples as a mono float32 array.

    Multi-channel files are down-mixed by averaging all channels.  Supports
    16-bit and 32-bit integer PCM formats.

    :param path: Path to the WAV file.
    :return: Tuple of (*samples* as float32 ndarray, *sample_rate* as int).
    """
    with wave.open(path, "rb") as w:
        sample_rate = w.getframerate()
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        raw = w.readframes(w.getnframes())

    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).mean(axis=1)

    return samples, sample_rate


def pan_to_stereo(mono, channel):
    """
    Pan a mono audio signal to the left, right, or both stereo channels.

    :param mono: Mono audio samples as a float32 ndarray.
    :param channel: Target channel — ``"left"``, ``"right"``, or ``"both"``.
    :return: Stereo array with shape ``(N, 2)``.
    """
    stereo = np.zeros((len(mono), 2), dtype=np.float32)
    if channel == "left":
        stereo[:, 0] = mono
    elif channel == "right":
        stereo[:, 1] = mono
    else:
        stereo[:, 0] = mono
        stereo[:, 1] = mono
    return stereo


def save_stereo_wav(path, stereo, sample_rate=16000):
    """
    Save a stereo float32 array as a 16-bit PCM WAV file.

    Samples are clipped to [-1, 1] before conversion to 16-bit integers.

    :param path: Output file path.
    :param stereo: Stereo audio array with shape ``(N, 2)``, values in [-1, 1].
    :param sample_rate: Sample rate in Hz (default: 16000).
    """
    stereo = np.clip(stereo, -1.0, 1.0)
    int_data = (stereo * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(int_data.tobytes())


# ---------------------------------------------------------------------------
# Generation pipeline
# ---------------------------------------------------------------------------

def prerender_tts_segments(speech_config, tmp_dir, min_number, max_number,
                           voice="en-US-AriaNeural"):
    """
    Pre-render TTS audio for the prompt phrase and all required number words.

    Each segment is synthesized once and cached as a mono float32 array so
    that multiple questions can be assembled without repeated TTS calls.

    :param speech_config: Azure ``SpeechConfig`` instance.
    :param tmp_dir: Temporary directory for intermediate WAV files.
    :param min_number: Smallest number to render.
    :param max_number: Largest number to render.
    :param voice: Azure TTS voice name.
    :return: Dict mapping ``"prompt"`` and integers to mono float32 arrays.
    :raises RuntimeError: If any TTS call fails.
    """
    segments = {}

    prompt_path = os.path.join(tmp_dir, "prompt.wav")
    print("  Rendering TTS: prompt")
    if not synthesize_to_wav(speech_config, PROMPT_TEXT, prompt_path, voice):
        raise RuntimeError("Failed to render TTS for the prompt.")
    segments["prompt"], _ = load_wav_mono(prompt_path)

    for n in range(min_number, max_number + 1):
        word = number_to_words(n)
        num_path = os.path.join(tmp_dir, f"{n}.wav")
        print(f"  Rendering TTS: {word}")
        if not synthesize_to_wav(speech_config, word, num_path, voice):
            raise RuntimeError(f"Failed to render TTS for '{word}'.")
        segments[n], _ = load_wav_mono(num_path)

    return segments


def build_stereo_clip(prompt, number_audios, channels, sample_rate, gap_sec=0.5):
    """
    Assemble a stereo math question clip from pre-rendered segments.

    The prompt plays in both channels, followed by each number panned to its
    assigned channel.  A silence gap separates consecutive segments.

    :param prompt: Mono float32 array for the prompt phrase.
    :param number_audios: List of mono float32 arrays, one per number.
    :param channels: List of channel assignments (``"left"`` or ``"right"``).
    :param sample_rate: Sample rate in Hz.
    :param gap_sec: Silence gap between segments in seconds (default: 0.5).
    :return: Stereo array with shape ``(N, 2)``.
    """
    gap = np.zeros(int(gap_sec * sample_rate), dtype=np.float32)

    parts = [pan_to_stereo(prompt, "both"), pan_to_stereo(gap, "both")]
    for audio, ch in zip(number_audios, channels):
        parts.append(pan_to_stereo(audio, ch))
        parts.append(pan_to_stereo(gap, "both"))

    return np.concatenate(parts, axis=0)


def generate_math_questions(output_dir, count, speech_config, seed=42,
                            sample_rate=16000, numbers_per_question=3,
                            min_number=1, max_number=9,
                            voice="en-US-AriaNeural", start_index=1,
                            target_asl=-26.0, base_url=None):
    """
    Generate N math question audio files with a manifest CSV.

    Each question is a stereo WAV containing a spoken prompt followed by
    randomly chosen numbers panned to left or right channels.  At least one
    number is placed in each channel so the listener must hear both sides to
    compute the correct answer.

    All TTS segments are normalized to the target active speech level (ASL)
    per ITU-T P.56 Method B *before* stereo panning, so the per-ear level
    matches the target regardless of channel assignment.

    Each clip is saved with a random UUID filename.  When *base_url* is
    provided, a ``general_assets_internal.csv`` is also written with
    ``math``, ``math_ans``, and ``math_hash`` columns ready for use with
    the P.808 master script.

    A ``math_questions.csv`` manifest is always written alongside the WAV
    files with columns ``filename``, ``numbers``, ``channels``, ``answer``,
    and ``math_hash``.

    :param output_dir: Directory for output WAV files and manifest CSV.
    :param count: Number of questions to generate.
    :param speech_config: Azure ``SpeechConfig`` instance.
    :param seed: Random seed for reproducibility (default: 42).
    :param sample_rate: Output sample rate in Hz (default: 16000).
    :param numbers_per_question: How many numbers per question (default: 3).
    :param min_number: Minimum number value (default: 1).
    :param max_number: Maximum number value (default: 9).
    :param voice: Azure TTS voice name (default: ``en-US-AriaNeural``).
    :param start_index: Starting index for output filenames (default: 1).
    :param target_asl: Target active speech level in dBov (default: -26).
    :param base_url: Base URL where clips will be uploaded (e.g.
        ``"https://host/container/clips/internal_assets/"``).  When set,
        a ``general_assets_internal.csv`` is generated with full URLs.
    :return: List of dicts with ``filename``, ``numbers``, ``channels``,
        ``answer``, and ``math_hash`` keys.
    """
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        print("Pre-rendering TTS segments...")
        segments = prerender_tts_segments(speech_config, tmp_dir, min_number,
                                          max_number, voice)

    print("Normalizing ASL...")
    segments = normalize_segments_to_asl(segments, sample_rate, target_asl)

    print(f"\nGenerating {count} math question(s)...")
    manifest = []
    general_rows = []

    for i in range(count):
        numbers = [random.randint(min_number, max_number)
                   for _ in range(numbers_per_question)]

        # Assign random channels, ensuring both L and R are used
        channels = [random.choice(["left", "right"])
                    for _ in range(numbers_per_question)]
        if all(c == "left" for c in channels):
            channels[random.randint(0, len(channels) - 1)] = "right"
        elif all(c == "right" for c in channels):
            channels[random.randint(0, len(channels) - 1)] = "left"

        answer = sum(numbers)

        # Random UUID filename
        filename = f"{uuid.uuid4().hex}.wav"
        filepath = os.path.join(output_dir, filename)

        number_audios = [segments[n] for n in numbers]
        stereo = build_stereo_clip(segments["prompt"], number_audios, channels,
                                   sample_rate)
        save_stereo_wav(filepath, stereo, sample_rate)

        # Compute hash only when base_url is known
        math_hash = ""
        if base_url:
            url = base_url.rstrip("/") + "/" + filename
            math_hash = compute_math_hash(url, answer)

        label = " + ".join(
            f"{n}({c[0].upper()})" for n, c in zip(numbers, channels)
        )
        print(f"  [{i + 1}/{count}] {filename}: {label} = {answer}")

        entry = {
            "filename": filename,
            "numbers": "+".join(str(n) for n in numbers),
            "channels": ",".join(channels),
            "answer": answer,
        }
        if base_url:
            entry["math_hash"] = math_hash
        manifest.append(entry)

        if base_url:
            general_rows.append({
                "math": url, "math_ans": answer, "math_hash": math_hash,
            })

    # Write detailed manifest
    fieldnames = ["filename", "numbers", "channels", "answer"]
    if base_url:
        fieldnames.append("math_hash")
    manifest_path = os.path.join(output_dir, "math_questions.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest)
    print(f"\nManifest saved to: {manifest_path}")

    # Write general_assets_internal.csv
    if base_url:
        general_path = os.path.join(output_dir, "general_assets_internal.csv")
        with open(general_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["math", "math_ans", "math_hash"]
            )
            writer.writeheader()
            writer.writerows(general_rows)
        print(f"General assets CSV saved to: {general_path}")

    print(f"Generated {count} question(s) ({count} WAV files) in {output_dir}")
    return manifest


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate math audio questions for P.808 headphone "
                    "verification.  Creates stereo WAV files with numbers "
                    "panned to left/right speakers."
    )
    parser.add_argument(
        "--output_dir", "-o", required=True,
        help="Directory for output WAV files and manifest CSV."
    )
    parser.add_argument(
        "--count", "-n", type=int, required=True,
        help="Number of math questions to generate."
    )
    parser.add_argument(
        "--region", required=True,
        help="Azure Speech service region (e.g. eastus)."
    )
    parser.add_argument(
        "--resource_id", required=True,
        help="Azure Speech resource ID for AAD-based authentication. "
             "Find it in Azure Portal > Speech resource > Properties."
    )
    parser.add_argument(
        "--voice", default="en-US-AriaNeural",
        help="Azure TTS voice name (default: en-US-AriaNeural)."
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)."
    )
    parser.add_argument(
        "--numbers_per_question", type=int, default=3,
        help="How many numbers per question (default: 3)."
    )
    parser.add_argument(
        "--min_number", type=int, default=1,
        help="Minimum number value (default: 1)."
    )
    parser.add_argument(
        "--max_number", type=int, default=9,
        help="Maximum number value (default: 9)."
    )
    parser.add_argument(
        "--target_asl", type=float, default=-26.0,
        help="Target active speech level in dBov per ITU-T P.56 (default: -26)."
    )
    parser.add_argument(
        "--base_url",
        default=None,
        help="Base URL where clips will be uploaded. When provided, "
             "general_assets_internal.csv and math_hash values are generated. "
             "When omitted, math_hash is not computed."
    )

    args = parser.parse_args()

    assert args.count > 0, "Count must be positive"
    assert 1 <= args.min_number <= args.max_number <= 99, (
        "Number range must satisfy 1 <= min_number <= max_number <= 99"
    )
    assert args.numbers_per_question >= 2, (
        "At least 2 numbers per question are required to use both channels"
    )

    config = configure_speech(args.region, args.resource_id)

    generate_math_questions(
        output_dir=args.output_dir,
        count=args.count,
        speech_config=config,
        seed=args.seed,
        numbers_per_question=args.numbers_per_question,
        min_number=args.min_number,
        max_number=args.max_number,
        voice=args.voice,
        target_asl=args.target_asl,
        base_url=args.base_url,
    )
