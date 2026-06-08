"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

import argparse
import glob
import os
import re

import pandas as pd


# Mapping of known non-public asset filenames to publicly accessible CDN URLs.
PUBLIC_CDN_MAP = {
    'bootstrap.min.css': 'https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/3.3.7/css/bootstrap.min.css',
    'jquery.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js',
    'bootstrap.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/3.3.7/js/bootstrap.min.js',
}


def find_files(directory):
    """
    Find the .html, .csv, and .cfg files in the given directory.

    :param directory: Path to the directory containing master script output.
    :return: Tuple of (html_path, csv_path, cfg_path).
    """
    html_files = [f for f in glob.glob(os.path.join(directory, "*.html")) if "_row-" not in f]
    csv_files = glob.glob(os.path.join(directory, "*_publish_batch.csv"))
    cfg_files = glob.glob(os.path.join(directory, "*.cfg"))

    if len(html_files) != 1:
        raise FileNotFoundError(
            f"Expected exactly 1 .html file in '{directory}', found {len(html_files)}"
        )
    if len(csv_files) != 1:
        raise FileNotFoundError(
            f"Expected exactly 1 _publish_batch.csv file in '{directory}', found {len(csv_files)}"
        )
    if len(cfg_files) != 1:
        raise FileNotFoundError(
            f"Expected exactly 1 .cfg file in '{directory}', found {len(cfg_files)}"
        )

    return html_files[0], csv_files[0], cfg_files[0]


def replace_placeholders(template, row):
    """
    Replace all ${column_name} placeholders in the template with the row values.

    :param template: The HTML template string.
    :param row: A pandas Series representing one row of the CSV.
    :return: The HTML string with placeholders replaced.
    """
    result = template
    for col_name, value in row.items():
        placeholder = "${" + str(col_name) + "}"
        result = result.replace(placeholder, str(value))
    return result


def replace_with_public_urls(html_content):
    """
    Replace known non-public asset URLs with publicly accessible CDN equivalents.
    URLs that are already publicly accessible or not in the known map are left unchanged.

    :param html_content: The HTML string to scan.
    :return: The HTML string with non-public URLs replaced by public CDN equivalents.
    """
    for filename, cdn_url in PUBLIC_CDN_MAP.items():
        pattern = re.compile(
            r'https?://p910\.planetstat\.net/api/static/assets/' + re.escape(filename),
            re.IGNORECASE,
        )
        if pattern.search(html_content):
            print(f"  Replacing with public CDN: {filename} -> {cdn_url}")
            html_content = pattern.sub(cdn_url, html_content)

    return html_content


def _disable_fetch_for_local(html_content):
    """
    Replace the checkScripts() function body with a no-op so that the preview
    works with the file:// protocol. fetch() does not support file:// URLs.

    :param html_content: The HTML string.
    :return: The HTML string with checkScripts() neutralized.
    """
    pattern = re.compile(
        r'(async\s+function\s+checkScripts\s*\(\s*\)\s*\{).*?(\n\t\})',
        re.DOTALL,
    )
    replacement = (
        r'\1\n\t\t// Disabled in local preview — fetch() does not work with file:// protocol\n'
        r'\t\treturn;\2'
    )
    return pattern.sub(replacement, html_content)


def generate_previews(directory, samples):
    """
    Generate preview HTML files by substituting CSV row values into the HTML template
    and replacing non-public asset URLs with publicly accessible CDN equivalents.

    :param directory: Path to the directory containing master script output.
    :param samples: Number of rows from the CSV to generate previews for.
    :return: List of generated file paths.
    """
    html_path, csv_path, _ = find_files(directory)
    df = pd.read_csv(csv_path)

    if samples > len(df):
        print(f"Warning: requested {samples} samples but CSV only has {len(df)} rows. Using all rows.")
        samples = len(df)

    with open(html_path, "r", encoding="utf-8") as f:
        template = f.read()

    template = replace_with_public_urls(template)

    base_name = os.path.splitext(os.path.basename(html_path))[0]
    generated_files = []

    for i in range(samples):
        row = df.iloc[i]
        html_content = replace_placeholders(template, row)
        html_content = _disable_fetch_for_local(html_content)
        output_path = os.path.join(directory, f"{base_name}_row-{i + 1}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        generated_files.append(output_path)
        print(f"  [{output_path}] is created")

    print(f"Generated {samples} preview file(s).")

    return generated_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate preview HTML files from master script output by substituting CSV values "
                    "into the HTML template. Non-public asset URLs (js, css) are replaced with "
                    "publicly accessible CDN equivalents so the preview works without downloading."
    )
    parser.add_argument(
        "--dir",
        required=True,
        help="Path to the directory containing the .html, .csv, and .cfg output files from master_script.py",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=1,
        help="Number of CSV rows to generate preview HTML files for (default: 1)",
    )
    args = parser.parse_args()

    assert os.path.isdir(args.dir), f"Directory not found: {args.dir}"
    assert args.samples > 0, "Number of samples must be at least 1"

    generate_previews(args.dir, args.samples)
