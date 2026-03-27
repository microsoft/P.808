"""
/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

Download audio clips from URLs listed in a CSV file to a local directory.

Useful for obtaining local copies of rating clips before generating gold or trapping stimuli.

Usage:
    python utils/download_clips.py ^
        --input rating_clips.csv ^
        --column rating_clips ^
        --output_dir local_clips ^
        --sample 5
"""

import argparse
import os
import random
import urllib.request
from urllib.parse import urlparse

import pandas as pd


def download_clips(input_csv, column, output_dir, sample=None, seed=42, strategy="evenly_spaced"):
    """
    Download clips from URLs in a CSV column to a local directory.

    When sample is specified, a subset of clips is selected using the chosen
    strategy. Downloaded files keep their original filename from the URL path.

    :param input_csv: Path to the CSV file containing clip URLs.
    :param column: Name of the column containing URLs.
    :param output_dir: Local directory to save downloaded files.
    :param sample: Number of clips to download. None means download all.
    :param seed: Random seed for reproducible sampling.
    :param strategy: Sampling strategy - 'evenly_spaced' or 'random'.
    :return: List of local file paths that were downloaded.
    """
    df = pd.read_csv(input_csv)
    assert column in df.columns, f"Column '{column}' not found in {input_csv}. Available: {list(df.columns)}"

    urls = df[column].dropna().tolist()
    print(f"Found {len(urls)} URLs in column '{column}'")

    if sample is not None and sample < len(urls):
        if strategy == "evenly_spaced":
            step = len(urls) / sample
            indices = [int(i * step) for i in range(sample)]
            urls = [urls[i] for i in indices]
        elif strategy == "random":
            random.seed(seed)
            urls = random.sample(urls, sample)
        print(f"Selected {len(urls)} clips using '{strategy}' strategy")

    os.makedirs(output_dir, exist_ok=True)
    downloaded = []

    for i, url in enumerate(urls):
        filename = os.path.basename(urlparse(url).path)
        dest = os.path.join(output_dir, filename)

        if os.path.exists(dest):
            print(f"  [{i + 1}/{len(urls)}] Skipping (exists): {filename}")
            downloaded.append(dest)
            continue

        print(f"  [{i + 1}/{len(urls)}] Downloading: {filename}")
        try:
            urllib.request.urlretrieve(url, dest)
            downloaded.append(dest)
        except Exception as e:
            print(f"    Error downloading {url}: {e}")

    print(f"\nDownloaded {len(downloaded)} file(s) to {output_dir}")
    return downloaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download audio clips from URLs in a CSV file to a local directory. "
                    "Supports downloading all clips or a sampled subset."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the CSV file containing clip URLs."
    )
    parser.add_argument(
        "--column", "-c",
        default="rating_clips",
        help="Name of the column containing URLs (default: rating_clips)."
    )
    parser.add_argument(
        "--output_dir", "-o",
        required=True,
        help="Local directory to save downloaded files."
    )
    parser.add_argument(
        "--sample", "-n",
        type=int,
        default=None,
        help="Number of clips to download. Omit to download all."
    )
    parser.add_argument(
        "--strategy",
        choices=["evenly_spaced", "random"],
        default="evenly_spaced",
        help="Sampling strategy when --sample is used (default: evenly_spaced)."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42)."
    )

    args = parser.parse_args()

    assert os.path.exists(args.input), f"CSV not found: {args.input}"
    if args.sample is not None:
        assert args.sample > 0, "Sample size must be positive"

    download_clips(
        input_csv=args.input,
        column=args.column,
        output_dir=args.output_dir,
        sample=args.sample,
        seed=args.seed,
        strategy=args.strategy,
    )
