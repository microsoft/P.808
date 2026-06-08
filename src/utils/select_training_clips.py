"""
/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

Select a subset of clips from a rating clips CSV to use as training clips.

Training clips anchor participants' perception and should cover the quality range
from worst to best. This script selects evenly spaced clips from the input CSV
to maximize diversity.

.. note::
    This script selects clips purely by their position in the list, without any
    knowledge of their actual quality. For best results it is recommended to select
    training clips manually so they represent the quality distribution within the
    dataset. In multi-scale tests (e.g. P.804, P.835) the training set should also
    show variations across all dimensions.

Usage:
    python utils/select_training_clips.py ^
        --input rating_clips.csv ^
        --output training_clips.csv ^
        --count 5
"""

import argparse
import os

import pandas as pd


def select_training_clips(input_csv, output_csv, count, input_column="rating_clips",
                          output_column="training_clips"):
    """
    Select evenly spaced clips from a rating clips CSV for use as training clips.

    Reads URLs from the input column, selects a subset by evenly spacing through
    the list, and writes them to a new CSV with the output column name.

    Note: selection is based solely on list position — the script has no knowledge
    of actual clip quality. For best results, select training clips manually to
    represent the quality distribution. In multi-scale tests (e.g. P.804, P.835),
    ensure the training set shows variations across all dimensions.

    :param input_csv: Path to the rating clips CSV.
    :param output_csv: Path for the output training clips CSV.
    :param count: Number of training clips to select.
    :param input_column: Column name in the input CSV (default: rating_clips).
    :param output_column: Column name in the output CSV (default: training_clips).
    :return: The output DataFrame.
    """
    df = pd.read_csv(input_csv)
    assert input_column in df.columns, (
        f"Column '{input_column}' not found in {input_csv}. Available: {list(df.columns)}"
    )

    urls = df[input_column].dropna().tolist()
    total = len(urls)

    if count >= total:
        print(f"Warning: requested {count} clips but only {total} available. Using all.")
        selected = urls
    else:
        step = total / count
        indices = [int(i * step) for i in range(count)]
        selected = [urls[i] for i in indices]

    out_df = pd.DataFrame({output_column: selected})
    out_df.to_csv(output_csv, index=False)

    print(f"Selected {len(selected)} training clips from {total} rating clips")
    print(f"Output saved to: {output_csv}")
    return out_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Select a subset of rating clips to use as training clips. "
                    "Clips are evenly spaced through the list to maximize quality range coverage."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the rating clips CSV."
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path for the output training clips CSV."
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=5,
        help="Number of training clips to select (default: 5)."
    )
    parser.add_argument(
        "--input_column",
        default="rating_clips",
        help="Column name in the input CSV (default: rating_clips)."
    )
    parser.add_argument(
        "--output_column",
        default="training_clips",
        help="Column name in the output CSV (default: training_clips)."
    )

    args = parser.parse_args()

    assert os.path.exists(args.input), f"CSV not found: {args.input}"
    assert args.count > 0, "Count must be positive"

    select_training_clips(
        input_csv=args.input,
        output_csv=args.output,
        count=args.count,
        input_column=args.input_column,
        output_column=args.output_column,
    )
