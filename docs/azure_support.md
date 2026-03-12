[Home](../README.md) > Azure Blob Storage Support
# Azure Blob Storage Support

The toolkit normally expects CSV files that list the URLs to all audio clips used in a test.  When a CSV file is supplied via the command line, it will be used as the data source.

Alternatively, the toolkit can read audio clips directly from an Azure Blob Storage container.  To enable this, provide the storage details in the configuration file and omit the CSV arguments.

## Configuration example
```ini
[CommonAccountKeys]
# Storage account access key
mystorageaccount:

[DefaultStorage]
StorageUrl:https://mystorageaccount.blob.core.windows.net
StorageAccountKey:${CommonAccountKeys:mystorageaccount}
Container:p808-assets
Path:/clips/rating/

[RatingClips]
RatingClipsConfigurations:store1

[store1]
StorageUrl:${DefaultStorage:StorageUrl}
StorageAccountKey:${DefaultStorage:StorageAccountKey}
Container:${DefaultStorage:Container}
Path:${DefaultStorage:Path}
```

When the above sections are present and `--clips`, `--gold_clips` and `--trapping_clips` are not supplied, the scripts will query Azure to obtain the list of clips.  Using CSV files remains the default approach and requires no Azure configuration.

