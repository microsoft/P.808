"""
/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

Upload or copy audio clips to Azure Blob Storage for use in crowdsourcing studies.

Supports three workflows:
  1. upload: Upload locally generated clips directly to Azure Blob Storage using
     ``az storage blob upload-batch`` (requires ``az login``). Updates the CSV report
     with public URLs. No SAS tokens or manual steps required.
  2. upload-local: Prepare a file list and azcopy command for manual upload. Updates
     the CSV report with public URLs but does NOT perform the actual upload.
  3. copy-remote: Copy clips from a private Azure storage container to a public one and
     update the CSV with the new public URLs (azcopy command only).

Usage:
  # Direct upload (recommended — requires az login)
  python utils/copy_to_pub_storage.py upload ^
      --input gold_clips_report.csv ^
      --columns gold_clips ^
      --local-dir C:\\datasets\\gold_output ^
      --account-name crowdsourcedatapub ^
      --target-container crowdsource-data ^
      --dest-path study01/gold

  # Prepare azcopy command (manual upload)
  python utils/copy_to_pub_storage.py upload-local ^
      --input gold_clips_report.csv ^
      --columns gold_clips ^
      --local-dir C:\\datasets\\gold_output ^
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
import shutil
import subprocess
import sys

import pandas as pd


def upload(input_csv, columns, local_dir, account_name, target_container, dest_path,
           cdn_base_url):
    """
    Upload local clips to Azure Blob Storage and update the CSV with public URLs.

    Uses ``az storage blob upload-batch`` with ``--auth-mode login``, so the caller
    must be signed in via ``az login`` with write access to the target container.
    Falls back to ``upload_local`` (azcopy command) if ``az`` is not available.

    :param input_csv: Path to the input CSV file.
    :param columns: List of column names containing clip filenames.
    :param local_dir: Local directory containing the clip files to upload.
    :param account_name: Azure storage account name.
    :param target_container: Name of the target blob container.
    :param dest_path: Blob path prefix inside the container (e.g. 'study01/gold').
    :param cdn_base_url: Base URL for public access. Defaults to storage account URL.
    """
    az_path = shutil.which("az")
    if az_path is None:
        print("Warning: 'az' CLI not found. Falling back to upload-local (azcopy command).")
        dest_storage_url = f"https://{account_name}.blob.core.windows.net"
        upload_local(input_csv, columns, local_dir, dest_storage_url, target_container,
                     cdn_base_url or dest_storage_url)
        return

    df = pd.read_csv(input_csv)
    local_dir = os.path.abspath(local_dir)
    storage_url = f"https://{account_name}.blob.core.windows.net"
    final_base = cdn_base_url or storage_url

    # Collect files to upload
    files_to_upload = []
    for col in columns:
        for filename in df[col].dropna().unique():
            local_path = os.path.join(local_dir, str(filename))
            if not os.path.exists(local_path):
                print(f"  Warning: file not found: {local_path}")
            else:
                files_to_upload.append(str(filename))
    files_to_upload = sorted(set(files_to_upload))

    if not files_to_upload:
        print("No files to upload.")
        return

    print(f"Uploading {len(files_to_upload)} file(s) to "
          f"{storage_url}/{target_container}/{dest_path or ''}")

    # Create a temporary directory with only the files we need to upload
    import tempfile
    with tempfile.TemporaryDirectory() as staging_dir:
        for filename in files_to_upload:
            src = os.path.join(local_dir, filename)
            dst = os.path.join(staging_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)

        cmd = [
            az_path, "storage", "blob", "upload-batch",
            "--account-name", account_name,
            "--destination", target_container,
            "--source", staging_dir,
            "--auth-mode", "login",
            "--overwrite",
        ]
        if dest_path:
            cmd.extend(["--destination-path", dest_path])

        result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Upload failed (exit code {result.returncode}):")
        print(result.stderr)
        sys.exit(1)

    print(f"Upload complete. {len(files_to_upload)} file(s) uploaded.")

    # Build public URLs and update CSV
    if dest_path:
        url_prefix = f"{final_base}/{target_container}/{dest_path.rstrip('/')}/"
    else:
        url_prefix = f"{final_base}/{target_container}/"

    for col in columns:
        df[col] = url_prefix + df[col].astype(str)

    output_csv = input_csv.replace('.csv', '_public.csv')
    df.to_csv(output_csv, index=False)

    print(f"Updated CSV written to: {output_csv}")
    print(f"Public URL prefix: {url_prefix}")


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

    # --- upload (direct, recommended) ---
    p_upload = subparsers.add_parser(
        "upload",
        help="Upload local clips directly to Azure Blob Storage using az CLI (requires az login)."
    )
    p_upload.add_argument("--input", "-i", required=True,
                          help="Path to the input CSV file (e.g. gold_clips_report.csv).")
    p_upload.add_argument("--columns", "-c", nargs="+", required=True,
                          help="Column names in the CSV that contain clip filenames.")
    p_upload.add_argument("--local-dir", "-l", required=True,
                          help="Local directory containing the clip files to upload.")
    p_upload.add_argument("--account-name", "-a", required=True,
                          help="Azure storage account name (e.g. crowdsourcedatapub).")
    p_upload.add_argument("--target-container", "-t", required=True,
                          help="Name of the target blob container.")
    p_upload.add_argument("--dest-path", "-d", default="",
                          help="Blob path prefix inside the container (e.g. 'study01/gold').")
    p_upload.add_argument("--cdn-base-url", default=None,
                          help="Base URL for public access. Defaults to storage account URL.")

    # --- upload-local (azcopy command) ---
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

    if args.mode == "upload":
        cdn = args.cdn_base_url
        assert os.path.isdir(args.local_dir), f"Directory not found: {args.local_dir}"
        assert os.path.exists(args.input), f"CSV not found: {args.input}"
        upload(
            input_csv=args.input,
            columns=args.columns,
            local_dir=args.local_dir,
            account_name=args.account_name,
            target_container=args.target_container,
            dest_path=args.dest_path,
            cdn_base_url=cdn,
        )
    elif args.mode == "upload-local":
        cdn = args.cdn_base_url or args.dest_storage_url
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
        cdn = args.cdn_base_url or args.dest_storage_url
        assert os.path.exists(args.input), f"CSV not found: {args.input}"
        copy_remote(
            input_csv=args.input,
            columns=args.columns,
            src_url=args.src_url,
            dest_storage_url=args.dest_storage_url,
            target_container=args.target_container,
            cdn_base_url=cdn,
        )
