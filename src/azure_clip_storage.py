import os
import datetime
import posixpath

import pandas as pd

from azure.storage.blob import BlobServiceClient, generate_container_sas, ContainerSasPermissions


class AzureClipStorage:
    def __init__(self, config, alg):
        self._account_name = os.path.basename(
            config['StorageUrl']).split('.')[0]

        self._account_key = config['StorageAccountKey']
        self._container = config['Container']
        self._alg = alg
        self._clips_path = config['Path'].lstrip('/')
        self._clip_names = []
        self._modified_clip_names = []
        self._SAS_token = ''

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
    async def clip_names(self):
        if len(self._clip_names) <= 0:
            await self.get_clips()
        return self._clip_names

    @property
    def store_service(self):
        blob_service = BlobServiceClient(
            account_url=f"https://{self._account_name}.blob.core.windows.net/", credential=self._account_key)
        return blob_service.get_container_client(container=self._container)

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
        blobs = self.store_service.list_blobs(
            name_starts_with=self.clips_path)

        if not self._SAS_token:
            self._SAS_token = generate_container_sas(
                account_name=self._account_name,
                container_name=self._container,
                account_key=self._account_key,
                permission=ContainerSasPermissions(read=True),
                expiry=datetime.datetime.utcnow() + datetime.timedelta(days=14)
            )

        await self.retrieve_contents(blobs)

    def make_clip_url(self, filename):
        return f"https://{self._account_name}.blob.core.windows.net/{self._container}/{filename}?{self._SAS_token}"


class GoldSamplesInStore(AzureClipStorage):
    def __init__(self, config, alg):
        super().__init__(config, alg)
        self._SAS_token = ''

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
        pair_a_clips = [self.make_clip_url(clip)
                        for clip in clips if '40S_' in clip]
        pair_b_clips = [clip.replace('40S_', '50S_') for clip in pair_a_clips]

        df = pd.DataFrame({'pair_a': pair_a_clips, 'pair_b': pair_b_clips})
        return df
