import asyncio
import datetime
from unittest.mock import Mock, PropertyMock

import pytest

from src import azure_clip_storage
from src.azure_clip_storage import AzureClipStorage, PairComparisonSamplesInStore


def _storage_config(path):
    """
    Create minimal Azure storage configuration for path tests.

    :param path: Configured blob-directory path.
    :return: Azure storage configuration dictionary.
    """
    return {
        "StorageUrl": "https://example.blob.core.windows.net",
        "Container": "clips",
        "Path": path,
    }


@pytest.mark.parametrize(
    ("configured_path", "expected_prefix"),
    [
        ("something/xyz", "something/xyz/"),
        ("/something/xyz", "something/xyz/"),
        ("something/xyz/", "something/xyz/"),
        ("", ""),
        ("/", ""),
    ],
)
def test_azure_clip_storage_normalizes_directory_prefix(configured_path, expected_prefix):
    """
    Verify that nonempty blob-directory prefixes end at a path boundary.

    :param configured_path: Path supplied through storage configuration.
    :param expected_prefix: Prefix expected for Azure blob enumeration.
    :return: None.
    """
    storage = AzureClipStorage(
        _storage_config(configured_path),
        "test",
        credential=Mock(),
    )

    assert storage.clips_path == expected_prefix


def test_blob_service_uses_token_credential(monkeypatch):
    """
    Verify that Azure Blob Storage receives a token credential instead of an account key.

    :param monkeypatch: Pytest fixture used to replace the Azure SDK client.
    :return: None.
    """
    credential = Mock()
    blob_service = Mock()
    blob_service_factory = Mock(return_value=blob_service)
    monkeypatch.setattr(
        azure_clip_storage,
        "BlobServiceClient",
        blob_service_factory,
    )
    storage = AzureClipStorage(
        _storage_config("something/xyz"),
        "test",
        credential=credential,
    )

    assert storage.blob_service is blob_service
    blob_service_factory.assert_called_once_with(
        account_url="https://example.blob.core.windows.net",
        credential=credential,
    )


def test_get_clips_uses_normalized_directory_prefix(monkeypatch):
    """
    Verify directory-prefix handling and seven-day user delegation key creation.

    :param monkeypatch: Pytest fixture used to replace Azure SDK calls.
    :return: None.
    """
    container_service = Mock()
    container_service.list_blobs.return_value = []
    blob_service = Mock()
    blob_service.get_container_client.return_value = container_service
    user_delegation_key = Mock()
    blob_service.get_user_delegation_key.return_value = user_delegation_key
    monkeypatch.setattr(
        AzureClipStorage,
        "blob_service",
        PropertyMock(return_value=blob_service),
    )
    storage = AzureClipStorage(
        _storage_config("something/xyz"),
        "test",
        credential=Mock(),
    )

    asyncio.run(storage.get_clips())

    blob_service.get_container_client.assert_called_once_with(container="clips")
    container_service.list_blobs.assert_called_once_with(name_starts_with="something/xyz/")

    delegation_key_arguments = blob_service.get_user_delegation_key.call_args.kwargs
    assert (
        delegation_key_arguments["key_expiry_time"] - delegation_key_arguments["key_start_time"]
        == datetime.timedelta(days=7)
    )
    assert delegation_key_arguments["key_start_time"].utcoffset() is not None
    assert storage._user_delegation_key is user_delegation_key


def test_make_clip_url_generates_a_separate_blob_sas_for_each_clip(monkeypatch):
    """
    Verify that each clip URL receives a read-only SAS scoped to its exact blob name.

    :param monkeypatch: Pytest fixture used to replace Azure SDK calls.
    :return: None.
    """
    generate_sas = Mock(side_effect=["token-a", "token-b"])
    monkeypatch.setattr(
        azure_clip_storage,
        "generate_blob_sas",
        generate_sas,
    )
    storage = AzureClipStorage(
        _storage_config("something/xyz"),
        "test",
        credential=Mock(),
    )
    storage._user_delegation_key = Mock()
    storage._sas_start_time = datetime.datetime.now(datetime.timezone.utc)
    storage._sas_expiry_time = storage._sas_start_time + datetime.timedelta(days=7)

    first_url = storage.make_clip_url("something/xyz/clip-a.wav")
    second_url = storage.make_clip_url("something/xyz/clip-b.wav")

    assert first_url.endswith("something/xyz/clip-a.wav?token-a")
    assert second_url.endswith("something/xyz/clip-b.wav?token-b")
    assert generate_sas.call_count == 2

    first_arguments = generate_sas.call_args_list[0].kwargs
    second_arguments = generate_sas.call_args_list[1].kwargs
    assert first_arguments["blob_name"] == "something/xyz/clip-a.wav"
    assert second_arguments["blob_name"] == "something/xyz/clip-b.wav"
    assert first_arguments["user_delegation_key"] is storage._user_delegation_key
    assert first_arguments["permission"].read is True
    assert first_arguments["expiry"] - first_arguments["start"] == datetime.timedelta(days=7)
    assert first_arguments["protocol"] == "https"
    assert "account_key" not in first_arguments


def test_make_clip_url_requires_a_user_delegation_key():
    """
    Verify that clip URLs are never generated without a signed blob SAS.

    :return: None.
    """
    storage = AzureClipStorage(
        _storage_config("something/xyz"),
        "test",
        credential=Mock(),
    )

    with pytest.raises(RuntimeError, match="retrieved"):
        storage.make_clip_url("something/xyz/clip.wav")


def test_pair_comparison_signs_each_raw_blob_name(monkeypatch):
    """
    Verify that paired clips receive signatures generated for their respective blob names.

    :param monkeypatch: Pytest fixture used to replace Azure SDK calls.
    :return: None.
    """
    generate_sas = Mock(side_effect=["token-a", "token-b"])
    monkeypatch.setattr(
        azure_clip_storage,
        "generate_blob_sas",
        generate_sas,
    )
    storage = PairComparisonSamplesInStore(
        _storage_config("pairs"),
        "pairs",
        credential=Mock(),
    )
    storage._clip_names = ["pairs/40S_sample.wav"]
    storage._user_delegation_key = Mock()
    storage._sas_start_time = datetime.datetime.now(datetime.timezone.utc)
    storage._sas_expiry_time = storage._sas_start_time + datetime.timedelta(days=7)

    pairs = asyncio.run(storage.get_dataframe())

    assert pairs.loc[0, "pair_a"].endswith("pairs/40S_sample.wav?token-a")
    assert pairs.loc[0, "pair_b"].endswith("pairs/50S_sample.wav?token-b")
    assert [
        call.kwargs["blob_name"] for call in generate_sas.call_args_list
    ] == [
        "pairs/40S_sample.wav",
        "pairs/50S_sample.wav",
    ]
