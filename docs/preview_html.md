# Preview HTML

`preview_html.py` generates a local preview of the HIT by substituting one row from the
`_publish_batch.csv` into the generated `.html` template.

External resources (`.js`, `.css`, `.woff`, `.woff2`) are downloaded into a local `assets/`
directory and URLs in the HTML are rewritten to point there, so the preview works offline
without CORS issues.

## Usage

```bash
cd src
python utils/preview_html.py --dir YOUR_PROJECT_NAME --samples 1
```

| Argument | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--dir` | Yes | — | Directory containing the `.html`, `_publish_batch.csv`, and `.cfg` files produced by `master_script.py`. |
| `--samples` | No | 1 | Number of CSV rows to generate preview files for. |

The output is saved in the same directory as `<original_name>_row-1.html`, and downloaded
assets are placed in `<dir>/assets/`.

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
	--create_local_test
```
