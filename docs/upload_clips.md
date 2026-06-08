[Home](../README.md) > [Preparation](preparation.md) > Upload Clips to Storage

# Upload Clips to Storage

The `copy_to_pub_storage.py` utility prepares audio clips for crowdsourcing studies by uploading
or copying them to a publicly accessible Azure Blob Storage container. It updates the CSV report
with public URLs ready for use with `master_script.py`.

## Prerequisites

- [azcopy](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10) must be installed and available in your PATH.
- A destination Azure Blob Storage account with a container created.
- SAS tokens with appropriate permissions (see below).

## Use Case 1: Upload Local Clips

After generating gold clips or trapping clips locally (e.g. with `create_gold_clips.py` or
`create_trapping_stimuli.py`), upload them to Azure Blob Storage.

### Step 1: Prepare the upload

```bash
cd src
python utils/copy_to_pub_storage.py upload-local ^
	--input path/to/gold_clips_report.csv ^
	--columns gold_clips ^
	--local-dir path/to/gold_clips_directory ^
	--dest-storage-url https://ACCOUNT.blob.core.windows.net ^
	--target-container my-study-clips
```

This produces:
- `gold_clips_report_to_upload.txt` — file list for azcopy.
- `gold_clips_report_public.csv` — updated CSV with public URLs.

### Step 2: Run the azcopy command

The script prints an azcopy command. Replace `[SAS_TOKEN_WITH_WRITE_CREATE]` with a SAS token
that has **write** and **create** permissions on the target container, then run it.

### Step 3: Use the updated CSV

Pass `gold_clips_report_public.csv` as `--gold_clips` to `master_script.py`.

## Use Case 2: Copy from Private to Public Storage

When clips are stored in a private Azure storage account and need to be moved to a public
container for the study.

### Step 1: Prepare the copy

```bash
cd src
python utils/copy_to_pub_storage.py copy-remote ^
	--input rating_clips.csv ^
	--columns rating_clips ^
	--src-url https://private.blob.core.windows.net/container ^
	--dest-storage-url https://public.blob.core.windows.net ^
	--target-container my-study-clips
```

This produces:
- `rating_clips_to_copy.txt` — file list for azcopy.
- `rating_clips_public.csv` — updated CSV with public URLs.

### Step 2: Run the azcopy command

Replace both SAS token placeholders:
- `[SAS_TOKEN_WITH_READ]` — read permission on the source container.
- `[SAS_TOKEN_WITH_WRITE_CREATE]` — write/create permission on the target container.

## Arguments

### upload-local

| Argument | Required | Description |
|----------|----------|-------------|
| `--input` | Yes | Path to the input CSV file. |
| `--columns` | Yes | Column names containing clip filenames (space-separated). |
| `--local-dir` | Yes | Local directory containing the clip files. |
| `--dest-storage-url` | Yes | Base URL of the destination storage account. |
| `--target-container` | Yes | Name of the target blob container. |
| `--cdn-base-url` | No | Base URL for public access. Defaults to `--dest-storage-url`. |

### copy-remote

| Argument | Required | Description |
|----------|----------|-------------|
| `--input` | Yes | Path to the input CSV file. |
| `--columns` | Yes | Column names containing clip URLs (space-separated). |
| `--src-url` | Yes | URL of the source blob storage container. |
| `--dest-storage-url` | Yes | Base URL of the destination storage account. |
| `--target-container` | Yes | Name of the target blob container. |
| `--cdn-base-url` | No | Base URL for public access. Defaults to `--dest-storage-url`. |

## Multiple Columns

Both modes support multiple columns. For example, to upload gold and trapping clips in one pass:

```bash
python utils/copy_to_pub_storage.py upload-local ^
	--input combined_report.csv ^
	--columns gold_clips trapping_clips ^
	--local-dir path/to/clips ^
	--dest-storage-url https://ACCOUNT.blob.core.windows.net ^
	--target-container my-study-clips
```

## SAS Token Tips

- Generate SAS tokens from the Azure Portal: Storage Account > Shared access signature.
- For the **source** (read): select "Read" and "List" permissions, Container scope.
- For the **target** (write): select "Write" and "Create" permissions, Container scope.
- Set an appropriate expiry date (e.g. 24 hours for a one-time copy).
