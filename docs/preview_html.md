# Preview HTML

`preview_html.py` generates a local preview of the HIT by substituting one row from the
`_publish_batch.csv` into the generated `.html` template.

Non-public asset URLs (`.js`, `.css`) are replaced with publicly accessible CDN equivalents
so the preview works without downloading external resources.

## Usage

```bash
cd src
python utils/preview_html.py --dir YOUR_PROJECT_NAME --samples 1
```

| Argument | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--dir` | Yes | — | Directory containing the `.html`, `_publish_batch.csv`, and `.cfg` files produced by `master_script.py`. |
| `--samples` | No | 1 | Number of CSV rows to generate preview files for. |

The output is saved in the same directory as `<original_name>_row-1.html`.

## Automatic generation

Pass `--create_local_test` to `master_script.py` to automatically generate one preview file
after the project is created:

```bash
python master_script.py ^
	--project YOUR_PROJECT_NAME ^
	--method acr ^
	--cfg your_configuration_file.cfg ^
	--clips rating_clips.csv ^
	--training_clips training_clips.csv ^
	--gold_clips gold_clips.csv ^
	--trapping_clips trapping_clips.csv ^
	--check_urls ^
	--create_local_test
```
