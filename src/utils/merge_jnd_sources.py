"""
/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

Build setup-section JND source clips by merging two split speech segments with added
pre / mid / post silence.

Each source clip was split into 2-3 segments (``<source>_p1.wav`` ...). This tool
joins two of those segments into one clip with a silent lead-in, a silent gap between
the two sentences, and a silent tail:

    [pre silence] segment_i [mid silence] segment_j [post silence]

The mid-silence gap is the important one: once white noise is added (by
``create_jnd_check_clips.py``) the listener hears the noise floor in that quiet gap,
which makes the small SNR difference between the two clips of a JND pair much easier
to notice on a good setup.

By default every ordered pair of distinct segments is produced (1+2, 2+1, 1+3, ...),
so a source with three segments yields six merged clips.

Usage:
    python utils/merge_jnd_sources.py ^
        --input_dir C:/datasets/clean_speech/split ^
        --output_dir C:/datasets/clean_speech/jnd_sources ^
        --pre_sec 0.5 --mid_sec 1.5 --post_sec 0.5
"""

import argparse
import os
import re
from collections import defaultdict

import numpy as np
import soundfile as sf


PART_RE = re.compile(r"^(?P<source>.+)_p(?P<idx>\d+)\.wav$", re.IGNORECASE)


def load_mono(path):
    """
    Read a WAV file as a mono float signal.

    Multi-channel files are down-mixed to mono by averaging the channels.

    :param path: Path to the WAV file.
    :return: Tuple of (mono signal as a numpy array, sample rate in Hz, subtype string).
    """
    signal, fs = sf.read(path)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)
    return signal.astype(np.float64), fs, sf.info(path).subtype


def merge_parts(part_a, part_b, fs, pre_sec, mid_sec, post_sec):
    """
    Join two speech segments with pre, mid and post silence.

    :param part_a: First speech segment as a numpy array.
    :param part_b: Second speech segment as a numpy array.
    :param fs: Sample rate in Hz (used to size the silence gaps).
    :param pre_sec: Silence before the first segment, in seconds.
    :param mid_sec: Silence between the two segments, in seconds.
    :param post_sec: Silence after the second segment, in seconds.
    :return: The concatenated clip as a numpy array.
    """
    pre = np.zeros(int(round(pre_sec * fs)))
    mid = np.zeros(int(round(mid_sec * fs)))
    post = np.zeros(int(round(post_sec * fs)))
    return np.concatenate([pre, part_a, mid, part_b, post])


def group_parts(input_dir):
    """
    Group the split part files in a directory by their source name.

    :param input_dir: Directory containing ``<source>_p<n>.wav`` files.
    :return: Dict mapping source name -> dict of {part index (int): file name},
        sorted by part index.
    """
    groups = defaultdict(dict)
    for name in os.listdir(input_dir):
        m = PART_RE.match(name)
        if m:
            groups[m.group("source")][int(m.group("idx"))] = name
    return groups


def build_jnd_sources(input_dir, output_dir, pre_sec=0.5, mid_sec=1.5, post_sec=0.5,
                      sources=None, combos=None, limit=None):
    """
    Merge every ordered pair of segments for each source into a JND source clip.

    For each source, all ordered pairs of distinct segments are merged (unless
    ``combos`` restricts them) and written as ``<source>_p<i><j>.wav``.

    :param input_dir: Directory with ``<source>_p<n>.wav`` split files.
    :param output_dir: Directory for the merged clips.
    :param pre_sec: Silence before the first segment, in seconds (default: 0.5).
    :param mid_sec: Silence between the two segments, in seconds (default: 1.5).
    :param post_sec: Silence after the second segment, in seconds (default: 0.5).
    :param sources: Optional iterable of source names to restrict processing to.
    :param combos: Optional iterable of ``(i, j)`` part-index pairs to build; when
        None, all ordered pairs of distinct parts are built.
    :param limit: Optional cap on the number of sources processed.
    :return: List of the written file names.
    """
    os.makedirs(output_dir, exist_ok=True)
    groups = group_parts(input_dir)
    names = sorted(groups)
    if sources is not None:
        wanted = set(sources)
        names = [n for n in names if n in wanted]
    if limit is not None:
        names = names[:limit]
    assert names, f"No <source>_p<n>.wav files found in {input_dir}"

    written = []
    for source in names:
        parts = groups[source]
        idxs = sorted(parts)
        pairs = combos if combos is not None else [(i, j) for i in idxs for j in idxs if i != j]
        for i, j in pairs:
            if i not in parts or j not in parts:
                print(f"  Skipping {source} {i}+{j}: missing part.")
                continue
            a, fs_a, subtype = load_mono(os.path.join(input_dir, parts[i]))
            b, fs_b, _ = load_mono(os.path.join(input_dir, parts[j]))
            assert fs_a == fs_b, f"{source}: part sample rates differ ({fs_a} vs {fs_b})."
            clip = merge_parts(a, b, fs_a, pre_sec, mid_sec, post_sec)
            out_name = f"{source}_p{i}{j}.wav"
            sf.write(os.path.join(output_dir, out_name), clip, fs_a, subtype=subtype)
            written.append(out_name)

    print(f"\nMerged {len(written)} clip(s) from {len(names)} source(s) into {output_dir}")
    return written


def _parse_combos(value):
    """
    Parse a ``--combos`` string such as ``"12,21,13"`` into ``(i, j)`` index pairs.

    :param value: Comma-separated list of two-digit part-index pairs.
    :return: List of ``(int, int)`` pairs, or None when the value is empty.
    """
    if not value:
        return None
    combos = []
    for token in value.split(","):
        token = token.strip()
        assert len(token) == 2 and token.isdigit(), f"Invalid combo '{token}', expected two digits like '12'."
        combos.append((int(token[0]), int(token[1])))
    return combos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge split speech segments into JND source clips with pre/mid/post silence."
    )
    parser.add_argument("--input_dir", "-i", required=True,
                        help="Directory with <source>_p<n>.wav split files.")
    parser.add_argument("--output_dir", "-o", required=True,
                        help="Directory for the merged clips.")
    parser.add_argument("--pre_sec", type=float, default=0.5,
                        help="Silence before the first segment, in seconds (default: 0.5).")
    parser.add_argument("--mid_sec", type=float, default=1.5,
                        help="Silence between the two segments, in seconds (default: 1.5).")
    parser.add_argument("--post_sec", type=float, default=0.5,
                        help="Silence after the second segment, in seconds (default: 0.5).")
    parser.add_argument("--sources", default=None,
                        help="Optional comma-separated source names to restrict to.")
    parser.add_argument("--combos", default=None,
                        help="Optional comma-separated part-index pairs to build (e.g. '12,21,13'). "
                             "Default builds all ordered pairs of distinct parts.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Optional cap on the number of sources processed.")
    args = parser.parse_args()

    build_jnd_sources(
        args.input_dir, args.output_dir,
        pre_sec=args.pre_sec, mid_sec=args.mid_sec, post_sec=args.post_sec,
        sources=args.sources.split(",") if args.sources else None,
        combos=_parse_combos(args.combos), limit=args.limit,
    )
