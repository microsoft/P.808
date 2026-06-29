"""
Detect silent / no-speech clips with a Voice Activity Detector (Silero VAD).

This utility computes the amount of voiced speech in each clip and flags clips
that contain little or no speech. It supports two workflows:

* ``prescreen``  - run VAD over a clip list (e.g. ``rating_clips.csv``) before
  publishing a study and write a report flagging silent clips. The same logic is
  reused by ``master_script.py`` via the optional ``--check_silence`` flag.
* ``crosscheck`` - compare the VAD result against the crowd ``is_silent_percentage``
  column produced by ``result_parser.py`` to validate silent votes and spot
  broken clips or rater abuse.

Audio is read with ``soundfile``/``librosa`` (already required by the toolkit), so
``torchaudio`` is not needed. ``torch`` and the ``silero-vad`` package are imported
lazily and are only required when VAD is actually run.
"""

import argparse
import os
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import librosa as lr
import numpy as np
import pandas as pd
import soundfile as sf

VAD_SAMPLE_RATE = 16000
DEFAULT_MIN_SPEECH_SEC = 0.30
DEFAULT_MIN_SPEECH_RATIO = 0.02
DEFAULT_CROWD_SILENT_THRESHOLD = 50.0

_VAD_MODEL = None
_GET_SPEECH_TS = None


def load_vad_model():
    """
    Load the Silero VAD model and the speech-timestamp helper (lazily, once).

    :return: Tuple of (model, get_speech_timestamps callable).
    """
    global _VAD_MODEL, _GET_SPEECH_TS
    if _VAD_MODEL is None:
        try:
            from silero_vad import load_silero_vad, get_speech_timestamps
        except ImportError as err:
            raise ImportError(
                "Silero VAD is required for silence detection. Install it with "
                "'pip install silero-vad torch' (see src/requirements.txt)."
            ) from err
        _VAD_MODEL = load_silero_vad()
        _GET_SPEECH_TS = get_speech_timestamps
    return _VAD_MODEL, _GET_SPEECH_TS


def load_audio_mono_16k(path):
    """
    Read an audio file as a mono waveform resampled to 16 kHz.

    :param path: Path to a local audio file.
    :return: 1-D float32 numpy array at 16 kHz.
    """
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != VAD_SAMPLE_RATE:
        audio = lr.resample(audio.astype("float32"), orig_sr=sr, target_sr=VAD_SAMPLE_RATE)
    return audio.astype("float32")


def speech_stats_for_audio(audio):
    """
    Compute speech statistics for a 16 kHz mono waveform using Silero VAD.

    :param audio: 1-D float32 numpy array sampled at 16 kHz.
    :return: Dict with total_sec, speech_sec, and speech_ratio.
    """
    import torch

    model, get_speech_timestamps = load_vad_model()
    total_sec = len(audio) / VAD_SAMPLE_RATE
    if total_sec == 0:
        return {"total_sec": 0.0, "speech_sec": 0.0, "speech_ratio": 0.0}
    wav = torch.from_numpy(audio)
    segments = get_speech_timestamps(
        wav, model, sampling_rate=VAD_SAMPLE_RATE, return_seconds=True
    )
    speech_sec = float(sum(seg["end"] - seg["start"] for seg in segments))
    return {
        "total_sec": round(total_sec, 3),
        "speech_sec": round(speech_sec, 3),
        "speech_ratio": round(speech_sec / total_sec, 4) if total_sec else 0.0,
    }


def _download_to_temp(url, sas_token=None):
    """
    Download a remote clip to a temporary file.

    :param url: HTTP(S) URL of the clip.
    :param sas_token: Optional Azure SAS token (without leading '?') for private storage.
    :return: Path to the downloaded temporary file.
    """
    full_url = url
    if sas_token:
        sep = "&" if "?" in url else "?"
        full_url = f"{url}{sep}{sas_token.lstrip('?')}"
    suffix = os.path.splitext(url.split("?")[0])[1] or ".wav"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    urllib.request.urlretrieve(full_url, tmp_path)
    return tmp_path


def _prepare_local(url, sas_token=None):
    """
    Resolve a clip URL to a local path, downloading it if it is remote.

    :param url: Clip URL or local file path.
    :param sas_token: Optional Azure SAS token for private storage.
    :return: Tuple of (local_path or None, is_remote, error_string).
    """
    is_remote = url.lower().startswith("http")
    try:
        path = _download_to_temp(url, sas_token) if is_remote else url
        return path, is_remote, ""
    except Exception as err:  # noqa: BLE001
        return None, is_remote, str(err)


def analyze_clip(url, sas_token=None, min_speech_sec=DEFAULT_MIN_SPEECH_SEC,
                 min_speech_ratio=DEFAULT_MIN_SPEECH_RATIO):
    """
    Download (if remote) and analyze a single clip for speech presence.

    Note: VAD inference is not thread-safe, so callers must invoke this
    sequentially (see ``prescreen_clips`` for the parallel-download pattern).

    :param url: Clip URL or local file path.
    :param sas_token: Optional Azure SAS token for private storage.
    :param min_speech_sec: Minimum voiced seconds to count the clip as non-silent.
    :param min_speech_ratio: Minimum voiced ratio to count the clip as non-silent.
    :return: Dict with the clip URL, speech stats, is_silent flag, and any error.
    """
    path, is_remote, error = _prepare_local(url, sas_token)
    result = {"file_url": url, "total_sec": None, "speech_sec": None,
              "speech_ratio": None, "vad_is_silent": None, "error": error}
    if error:
        return result
    try:
        stats = speech_stats_for_audio(load_audio_mono_16k(path))
        result.update(stats)
        result["vad_is_silent"] = bool(
            stats["speech_sec"] < min_speech_sec or stats["speech_ratio"] < min_speech_ratio
        )
    except Exception as err:  # noqa: BLE001
        result["error"] = str(err)
    finally:
        if is_remote and path and os.path.exists(path):
            os.remove(path)
    return result


def prescreen_clips(csv_path, column="rating_clips", sas_token=None,
                    min_speech_sec=DEFAULT_MIN_SPEECH_SEC,
                    min_speech_ratio=DEFAULT_MIN_SPEECH_RATIO,
                    download_workers=8, report_path=None):
    """
    Run VAD over every clip in a CSV column and report silent clips.

    Downloads run in parallel, but VAD inference runs sequentially in the calling
    thread because the Silero model is not thread-safe.

    :param csv_path: Path to a CSV containing clip URLs.
    :param column: Name of the column holding the clip URLs.
    :param sas_token: Optional Azure SAS token for private storage.
    :param min_speech_sec: Minimum voiced seconds to count the clip as non-silent.
    :param min_speech_ratio: Minimum voiced ratio to count the clip as non-silent.
    :param download_workers: Number of parallel download threads.
    :param report_path: Where to write the report CSV (defaults next to the input).
    :return: Tuple of (report DataFrame, path to the written report CSV).
    """
    df = pd.read_csv(csv_path)
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in {csv_path}")
    urls = [u for u in df[column].tolist() if isinstance(u, str) and u.strip()]
    urls = list(dict.fromkeys(urls))
    print(f" Checking speech presence (VAD) in {len(urls)} clips from {csv_path}")

    # warm up the model once before processing
    load_vad_model()

    rows = []
    done = 0
    with ThreadPoolExecutor(max_workers=download_workers) as ex:
        future_to_url = {ex.submit(_prepare_local, url, sas_token): url for url in urls}
        for fut in as_completed(future_to_url):
            url = future_to_url[fut]
            path, is_remote, error = fut.result()
            row = {"file_url": url, "total_sec": None, "speech_sec": None,
                   "speech_ratio": None, "vad_is_silent": None, "error": error}
            if not error:
                try:
                    stats = speech_stats_for_audio(load_audio_mono_16k(path))
                    row.update(stats)
                    row["vad_is_silent"] = bool(
                        stats["speech_sec"] < min_speech_sec
                        or stats["speech_ratio"] < min_speech_ratio
                    )
                except Exception as err:  # noqa: BLE001
                    row["error"] = str(err)
                finally:
                    if is_remote and path and os.path.exists(path):
                        os.remove(path)
            rows.append(row)
            done += 1
            if done % 100 == 0:
                print(f"      Analyzed: {done}/{len(urls)} clips")

    report = pd.DataFrame(rows)
    n_silent = int(report["vad_is_silent"].fillna(False).sum())
    n_error = int((report["error"].astype(str).str.len() > 0).sum())
    if n_silent > 0:
        print("\033[91m" + f"  VAD flagged {n_silent}/{len(urls)} clips as silent "
              f"(< {min_speech_sec}s speech). {n_error} clip(s) could not be read." + "\033[0m")
    else:
        print(f"  VAD found speech in all {len(urls)} clips. {n_error} clip(s) could not be read.")

    if report_path is None:
        report_path = os.path.splitext(csv_path)[0] + "_vad_silence_report.csv"
    report.to_csv(report_path, index=False)
    print(f"  VAD silence report saved to: {report_path}")
    return report, report_path


def crosscheck(vad_report_path, votes_per_clip_path, crowd_threshold=DEFAULT_CROWD_SILENT_THRESHOLD,
               output_path=None):
    """
    Compare VAD silence flags against the crowd is_silent_percentage column.

    :param vad_report_path: CSV produced by ``prescreen`` (has file_url, vad_is_silent).
    :param votes_per_clip_path: A result_parser ``*_votes_per_clip*`` CSV with is_silent_percentage.
    :param crowd_threshold: Percentage above which crowd votes mark a clip as silent.
    :param output_path: Where to write the comparison CSV (defaults next to the VAD report).
    :return: Path to the written comparison CSV.
    """
    vad = pd.read_csv(vad_report_path)
    votes = pd.read_csv(votes_per_clip_path)
    if "is_silent_percentage" not in votes.columns:
        raise ValueError(
            f"'is_silent_percentage' not found in {votes_per_clip_path}. "
            "Re-run result_parser.py with the updated version."
        )
    merged = pd.merge(
        vad[["file_url", "speech_sec", "speech_ratio", "vad_is_silent"]],
        votes[["file_url", "is_silent_percentage"]],
        on="file_url", how="inner",
    )
    merged["crowd_is_silent"] = merged["is_silent_percentage"] >= crowd_threshold
    merged["agreement"] = merged["vad_is_silent"] == merged["crowd_is_silent"]
    merged["disagreement_type"] = ""
    merged.loc[merged["vad_is_silent"] & ~merged["crowd_is_silent"], "disagreement_type"] = \
        "vad_silent_crowd_rated"
    merged.loc[~merged["vad_is_silent"] & merged["crowd_is_silent"], "disagreement_type"] = \
        "crowd_silent_vad_speech"

    n = len(merged)
    n_disagree = int((~merged["agreement"]).sum())
    print(f" Cross-checked {n} clips; {n_disagree} disagreement(s) between VAD and crowd.")
    if output_path is None:
        output_path = os.path.splitext(vad_report_path)[0] + "_vs_crowd.csv"
    merged.to_csv(output_path, index=False)
    print(f"  Cross-check report saved to: {output_path}")
    return output_path


def _build_arg_parser():
    """
    Build the command-line argument parser.

    :return: Configured argparse.ArgumentParser.
    """
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("prescreen", help="Flag silent clips in a clip-list CSV using VAD.")
    pre.add_argument("--input", "-i", required=True, help="CSV file containing clip URLs.")
    pre.add_argument("--column", "-c", default="rating_clips", help="Column with clip URLs.")
    pre.add_argument("--sas_token", default=None, help="Azure SAS token for private storage.")
    pre.add_argument("--min_speech_sec", type=float, default=DEFAULT_MIN_SPEECH_SEC,
                     help="Minimum voiced seconds to consider a clip non-silent.")
    pre.add_argument("--min_speech_ratio", type=float, default=DEFAULT_MIN_SPEECH_RATIO,
                     help="Minimum voiced ratio to consider a clip non-silent.")
    pre.add_argument("--workers", type=int, default=8, help="Parallel download workers.")
    pre.add_argument("--report", default=None, help="Path to the output report CSV.")

    cc = sub.add_parser("crosscheck", help="Compare VAD report against crowd is_silent_percentage.")
    cc.add_argument("--vad_report", required=True, help="VAD report CSV from 'prescreen'.")
    cc.add_argument("--votes_per_clip", required=True,
                    help="result_parser *_votes_per_clip*.csv with is_silent_percentage.")
    cc.add_argument("--crowd_threshold", type=float, default=DEFAULT_CROWD_SILENT_THRESHOLD,
                    help="Percentage above which crowd votes mark a clip as silent.")
    cc.add_argument("--output", default=None, help="Path to the comparison CSV.")
    return parser


def main():
    """
    Command-line entry point for VAD-based silence detection.

    :return: None.
    """
    args = _build_arg_parser().parse_args()
    if args.command == "prescreen":
        prescreen_clips(
            args.input, column=args.column, sas_token=args.sas_token,
            min_speech_sec=args.min_speech_sec, min_speech_ratio=args.min_speech_ratio,
            download_workers=args.workers, report_path=args.report,
        )
    elif args.command == "crosscheck":
        crosscheck(args.vad_report, args.votes_per_clip,
                   crowd_threshold=args.crowd_threshold, output_path=args.output)


if __name__ == "__main__":
    sys.exit(main())
