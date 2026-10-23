import os
import datetime
import posixpath

import pandas as pd

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas


class AzureClipStorage:
    def __init__(self, config, alg, credential=None):
        """
        Configure Microsoft Entra-authenticated access to Azure Blob Storage.

        :param config: Storage account and clip-path configuration.
        :param alg: Algorithm name associated with the stored clips.
        :param credential: Optional Azure token credential for dependency injection.
        """
        self._storage_url = config['StorageUrl'].rstrip('/')
        self._account_name = os.path.basename(
            self._storage_url).split('.')[0]

        self._credential = credential if credential is not None else DefaultAzureCredential()
        self._blob_service = None
        self._container = config['Container']
        self._alg = alg
        path = config['Path'].lstrip('/')
        if path and not path.endswith('/'):
            path += '/'
        self._clips_path = path
        self._clip_names = []
        self._modified_clip_names = []
        self._user_delegation_key = None
        self._sas_start_time = None
        self._sas_expiry_time = None

    @property
    def container(self):
        return self._container

    @property
    def alg(self):
        return self._alg

    @property
    def clips_path(self):
        return self._clips_path

    @property
    def blob_service(self):
        """
        Return a Blob service client authenticated with Microsoft Entra ID.

        :return: Authenticated Azure Blob service client.
        """
        if self._blob_service is None:
            self._blob_service = BlobServiceClient(
                account_url=self._storage_url,
                credential=self._credential,
            )
        return self._blob_service

    @property
    async def clip_names(self):
        if len(self._clip_names) <= 0:
            await self.get_clips()
        return self._clip_names

    @property
    def store_service(self):
        """
        Return the configured Azure Blob container client.

        :return: Authenticated Azure Blob container client.
        """
        return self.blob_service.get_container_client(container=self._container)

    @property
    def modified_clip_names(self):
        self._modified_clip_names = [
            os.path.basename(clip) for clip in self._clip_names]
        return self._modified_clip_names

    async def retrieve_contents(self, list_generator, dirname=''):
        for e in list_generator:
            if not '.wav' in e.name:
                continue

            if dirname:
                self._clip_names.append(e.name)
            else:
                clip_path = posixpath.join(dirname.lstrip('/'), e.name)
                self._clip_names.append(clip_path)

    async def get_clips(self):
        """
        Retrieve clip names and create a seven-day user delegation key.

        :return: None.
        """
        blobs = self.store_service.list_blobs(name_starts_with=self.clips_path)

        if self._user_delegation_key is None:
            self._sas_start_time = datetime.datetime.now(datetime.timezone.utc)
            self._sas_expiry_time = self._sas_start_time + datetime.timedelta(days=7)
            self._user_delegation_key = self.blob_service.get_user_delegation_key(
                key_start_time=self._sas_start_time,
                key_expiry_time=self._sas_expiry_time,
            )

        await self.retrieve_contents(blobs)

    def make_clip_url(self, filename):
        """
        Create a URL containing a read-only SAS scoped to one exact clip blob.

        :param filename: Blob name of the clip.
        :return: HTTPS URL containing a blob-scoped user delegation SAS.
        """
        if self._user_delegation_key is None:
            raise RuntimeError("Clip names must be retrieved before generating clip URLs.")

        sas_token = generate_blob_sas(
            account_name=self._account_name,
            container_name=self._container,
            blob_name=filename,
            user_delegation_key=self._user_delegation_key,
            permission=BlobSasPermissions(read=True),
            start=self._sas_start_time,
            expiry=self._sas_expiry_time,
            protocol='https',
        )
        return f"{self._storage_url}/{self._container}/{filename}?{sas_token}"


class GoldSamplesInStore(AzureClipStorage):
    async def get_dataframe(self):
        clips = await self.clip_names
        df = pd.DataFrame(columns=['gold_clips', 'gold_clips_ans'])
        clipsList = []
        for clip in clips:
            clipUrl = self.make_clip_url(clip)
            rating = 5
            if 'noisy' in clipUrl.lower():
                rating = 1

            clipsList.append({'gold_clips': clipUrl, 'gold_clips_ans': rating})

        df = df.append(clipsList)
        return df


class TrappingSamplesInStore(AzureClipStorage):
    async def get_dataframe(self):
        clips = await self.clip_names
        df = pd.DataFrame(columns=['trapping_clips', 'trapping_ans'])
        clipsList = []
        for clip in clips:
            clipUrl = self.make_clip_url(clip)
            rating = 0
            if '_bad_' in clip.lower() or '_1_short' in clip.lower():
                rating = 1
            elif '_poor_' in clip.lower() or '_2_short' in clip.lower():
                rating = 2
            elif '_fair_' in clip.lower() or '_3_short' in clip.lower():
                rating = 3
            elif '_good_' in clip.lower() or '_4_short' in clip.lower():
                rating = 4
            elif '_excellent_' in clip.lower() or '_5_short' in clip.lower():
                rating = 5
            if rating == 0:
                print(
                    f"  TrappingSamplesInStore: could not extract correct rating for this trapping clip: {clip.lower()}")
            else:
                clipsList.append(
                    {'trapping_clips': clipUrl, 'trapping_ans': rating})

        df = df.append(clipsList)
        return df


class PairComparisonSamplesInStore(AzureClipStorage):
    async def get_dataframe(self):
        clips = await self.clip_names
        pair_a_names = [clip for clip in clips if '40S_' in clip]
        pair_b_names = [clip.replace('40S_', '50S_') for clip in pair_a_names]
        pair_a_clips = [self.make_clip_url(clip) for clip in pair_a_names]
        pair_b_clips = [self.make_clip_url(clip) for clip in pair_b_names]

        df = pd.DataFrame({'pair_a': pair_a_clips, 'pair_b': pair_b_clips})
        return df
