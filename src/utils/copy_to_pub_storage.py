"""
/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

Upload or copy audio clips to Azure Blob Storage for use in crowdsourcing studies.

Supports two workflows:
  1. upload-local: Upload locally generated clips (e.g. from create_gold_clips.py or
     create_trapping_stimuli.py) to a target Azure Blob Storage container and update the
     CSV report with public URLs.
  2. copy-remote: Copy clips from a private Azure storage container to a public one and
     update the CSV with the new public URLs.

Both modes produce:
  - A list-of-files text file for use with azcopy.
  - An updated CSV (*_public.csv) where clip path columns contain public URLs.
  - A ready-to-use azcopy command (with placeholder SAS tokens).

Usage:
  # Upload local gold clips
  python utils/copy_to_pub_storage.py upload-local ^
      --input gold_clips_report.csv ^
      --columns gold_clips ^
      --local-dir C:\\datasets\\gold_p808\\acr ^
      --dest-storage-url https://ACCOUNT.blob.core.windows.net ^
      --target-container my-study-clips

  # Copy from private to public storage
  python utils/copy_to_pub_storage.py copy-remote ^
      --input rating_clips.csv ^
      --columns rating_clips ^
      --src-url https://private.blob.core.windows.net/container ^
      --dest-storage-url https://public.blob.core.windows.net ^
      --target-container my-study-clips
"""

import argparse
import os

import pandas as pd


def upload_local(input_csv, columns, local_dir, dest_storage_url, target_container,
                 cdn_base_url):
    """
    Prepare a local clip upload to Azure Blob Storage.

    Reads the input CSV, resolves local file paths, writes a file list for azcopy,
    and creates an updated CSV with public URLs.

    :param input_csv: Path to the input CSV file.
    :param columns: List of column names containing clip filenames.
    :param local_dir: Local directory containing the clip files to upload.
    :param dest_storage_url: Base URL of the destination storage account.
    :param target_container: Name of the target blob container.
    :param cdn_base_url: Base URL for public access (CDN or storage URL).
    """
    df = pd.read_csv(input_csv)
    final_url = f'{cdn_base_url}/{target_container}/'
    local_dir = os.path.abspath(local_dir)

    files_to_upload = []
    for col in columns:
        for filename in df[col].dropna().unique():
            local_path = os.path.join(local_dir, str(filename))
            if not os.path.exists(local_path):
                print(f"  Warning: file not found: {local_path}")
            files_to_upload.append(str(filename))

    files_to_upload = sorted(set(files_to_upload))

    # Write the file list for azcopy
    out_file = input_csv.replace('.csv', '_to_upload.txt')
    with open(out_file, 'w') as f:
        for item in files_to_upload:
            f.write(f"{item}\n")

    # Update CSV with public URLs
    for col in columns:
        df[col] = final_url + df[col].astype(str)

    output_csv = input_csv.replace('.csv', '_public.csv')
    df.to_csv(output_csv, index=False)

    print(f"File list written to: {out_file}")
    print(f"Updated CSV written to: {output_csv}")
    print(f"Files to upload: {len(files_to_upload)}")
    print()
    print("Use the following azcopy command to upload the clips:")
    print("  Replace [SAS_TOKEN_WITH_WRITE_CREATE] with a SAS token that has write/create permissions.")
    print()

    azcopy_cmd = (
        f'azcopy copy "{local_dir}/*" '
        f'"{dest_storage_url}/{target_container}/[SAS_TOKEN_WITH_WRITE_CREATE]" '
        f'--list-of-files="{os.path.abspath(out_file)}"'
    )
    print(azcopy_cmd)
    print()
    print("Note: azcopy may take several minutes without output. Consider running it on a VM.")


def copy_remote(input_csv, columns, src_url, dest_storage_url, target_container,
                cdn_base_url):
    """
    Prepare a remote copy from private to public Azure Blob Storage.

    Reads the input CSV, strips source URLs and SAS tokens to get relative blob paths,
    writes a file list for azcopy, and creates an updated CSV with public URLs.

    :param input_csv: Path to the input CSV file.
    :param columns: List of column names containing clip URLs.
    :param src_url: URL of the source blob storage container.
    :param dest_storage_url: Base URL of the destination storage account.
    :param target_container: Name of the target blob container.
    :param cdn_base_url: Base URL for public access (CDN or storage URL).
    """
    df = pd.read_csv(input_csv)
    final_url = f'{cdn_base_url}/{target_container}/'

    relative_paths = []
    for col in columns:
        tmp = df[col].str.replace(src_url, '', regex=False)
        # Strip SAS tokens
        tmp = tmp.str.split('?').str[0]
        # Strip leading slash
        tmp = tmp.str.lstrip('/')
        relative_paths.extend(tmp.tolist())

    relative_paths = sorted(set(relative_paths))

    # Write the file list for azcopy
    out_file = input_csv.replace('.csv', '_to_copy.txt')
    with open(out_file, 'w') as f:
        for item in relative_paths:
            f.write(f"{item}\n")

    # Update CSV with public URLs
    for col in columns:
        tmp = df[col].str.replace(src_url, '', regex=False)
        tmp = tmp.str.split('?').str[0]
        tmp = tmp.str.lstrip('/')
        df[col] = final_url + tmp

    output_csv = input_csv.replace('.csv', '_public.csv')
    df.to_csv(output_csv, index=False)

    print(f"File list written to: {out_file}")
    print(f"Updated CSV written to: {output_csv}")
    print(f"Files to copy: {len(relative_paths)}")
    print()
    print("Use the following azcopy command to copy the clips:")
    print("  Replace [SAS_TOKEN_WITH_READ] with a read SAS token for the source container.")
    print("  Replace [SAS_TOKEN_WITH_WRITE_CREATE] with a write/create SAS token for the target.")
    print()

    azcopy_cmd = (
        f'azcopy copy "{src_url}/[SAS_TOKEN_WITH_READ]" '
        f'"{dest_storage_url}/{target_container}/[SAS_TOKEN_WITH_WRITE_CREATE]" '
        f'--list-of-files="{os.path.abspath(out_file)}"'
    )
    print(azcopy_cmd)
    print()
    print("Note: azcopy may take several minutes without output. Consider running it on a VM.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upload or copy audio clips to Azure Blob Storage for crowdsourcing studies."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # --- upload-local ---
    p_local = subparsers.add_parser(
        "upload-local",
        help="Upload locally generated clips to Azure Blob Storage."
    )
    p_local.add_argument("--input", "-i", required=True,
                         help="Path to the input CSV file (e.g. gold_clips_report.csv).")
    p_local.add_argument("--columns", "-c", nargs="+", required=True,
                         help="Column names in the CSV that contain clip filenames.")
    p_local.add_argument("--local-dir", "-l", required=True,
                         help="Local directory containing the clip files to upload.")
    p_local.add_argument("--dest-storage-url", required=True,
                         help="Base URL of the destination storage account "
                              "(e.g. https://ACCOUNT.blob.core.windows.net).")
    p_local.add_argument("--target-container", "-t", required=True,
                         help="Name of the target blob container.")
    p_local.add_argument("--cdn-base-url", default=None,
                         help="Base URL for public access. Defaults to --dest-storage-url.")

    # --- copy-remote ---
    p_remote = subparsers.add_parser(
        "copy-remote",
        help="Copy clips from a private storage container to a public one."
    )
    p_remote.add_argument("--input", "-i", required=True,
                          help="Path to the input CSV file containing clip URLs.")
    p_remote.add_argument("--columns", "-c", nargs="+", required=True,
                          help="Column names in the CSV that contain clip URLs.")
    p_remote.add_argument("--src-url", "-s", required=True,
                          help="URL of the source blob storage container "
                               "(e.g. https://private.blob.core.windows.net/container).")
    p_remote.add_argument("--dest-storage-url", required=True,
                          help="Base URL of the destination storage account "
                               "(e.g. https://public.blob.core.windows.net).")
    p_remote.add_argument("--target-container", "-t", required=True,
                          help="Name of the target blob container.")
    p_remote.add_argument("--cdn-base-url", default=None,
                          help="Base URL for public access. Defaults to --dest-storage-url.")

    args = parser.parse_args()

    cdn = args.cdn_base_url or args.dest_storage_url

    if args.mode == "upload-local":
        assert os.path.isdir(args.local_dir), f"Directory not found: {args.local_dir}"
        assert os.path.exists(args.input), f"CSV not found: {args.input}"
        upload_local(
            input_csv=args.input,
            columns=args.columns,
            local_dir=args.local_dir,
            dest_storage_url=args.dest_storage_url,
            target_container=args.target_container,
            cdn_base_url=cdn,
        )
    elif args.mode == "copy-remote":
        assert os.path.exists(args.input), f"CSV not found: {args.input}"
        copy_remote(
            input_csv=args.input,
            columns=args.columns,
            src_url=args.src_url,
            dest_storage_url=args.dest_storage_url,
            target_container=args.target_container,
            cdn_base_url=cdn,
        )
