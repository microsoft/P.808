"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Vishak Gopal
"""

import argparse
import asyncio
import configparser as CP
import json
import os
import random

import pandas as pd
import requests
from azure.storage.blob import (AppendBlobService, BlockBlobService,
                                PageBlobService)
from azure.storage.file import FileService
from jinja2 import Template
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import create_input as ca

s = requests.Session()
retries = Retry(total=5,
            backoff_factor=0.1,
            status_forcelist=[ 500, 502, 503, 504 ])

s.mount('https://', HTTPAdapter(max_retries=retries))

class ClipsInAzureStorageAccount(object):
    def __init__(self, config, alg):
        self._account_name = os.path.basename(
            config['StorageUrl']).split('.')[0]
        if '.file.core.windows.net' in config['StorageUrl']:
            self._account_type = 'FileStore'
        elif '.blob.core.windows.net' in config['StorageUrl']:
            self._account_type = 'BlobStore'
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
        if self._account_type == 'FileStore':
            return FileService(account_name=self._account_name, account_key=self._account_key)
        elif self._account_type == 'BlobStore':
            return BlockBlobService(account_name=self._account_name, account_key=self._account_key)

    @property
    def modified_clip_names(self):
        self._modified_clip_names = [
            os.path.basename(clip) for clip in self._clip_names]
        return self._modified_clip_names

    async def traverse_down_filestore(self, dirname):
        files = self.store_service.list_directories_and_files(
            self.container, os.path.join(self.clips_path, dirname))
        await self.retrieve_contents(files, dirname)

    async def retrieve_contents(self, list_generator, dirname=''):
        for e in list_generator:
            if '.wav' in e.name:
                if not dirname:
                    self._clip_names.append(e.name)
                else:
                    self._clip_names.append(
                        posixpath.join(dirname.lstrip('/'), e.name))
            else:
                await self.traverse_down_filestore(e.name)

    async def get_clips(self):
        if self._account_type == 'FileStore':
            files = self.store_service.list_directories_and_files(
                self.container, self.clips_path)
            if not self._SAS_token:
                self._SAS_token = self.store_service.generate_share_shared_access_signature(
                    self.container, permission='read', expiry=datetime.datetime(2019, 10, 30, 12, 30), start=datetime.datetime.now())
            await self.retrieve_contents(files)
        elif self._account_type == 'BlobStore':
            blobs = self.store_service.list_blobs(
                self.container, self.clips_path)
            await self.retrieve_contents(blobs)

    def make_clip_url(self, filename):
        if self._account_type == 'FileStore':
            source_url = self.store_service.make_file_url(
                self.container, self.clips_path, filename, sas_token=self._SAS_token)
        elif self._account_type == 'BlobStore':
            source_url = self.store_service.make_blob_url(
                self.container, filename)
        return source_url


class GoldSamplesInStore(ClipsInAzureStorageAccount):
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


class TrappingSamplesInStore(ClipsInAzureStorageAccount):
    async def get_dataframe(self):
        clips = await self.clip_names
        df = pd.DataFrame(columns=['trapping_clips', 'trapping_ans'])
        clipsList = []
        for clip in clips:
            clipUrl = self.make_clip_url(clip)
            rating = 0
            if '_bad_' in clip.lower():
                rating = 1
            elif '_poor_' in clip.lower():
                rating = 2
            elif '_fair_' in clip.lower():
                rating = 3
            elif '_good_' in clip.lower():
                rating = 4
            elif '_excellent_' in clip.lower():
                rating = 5

            clipsList.append(
                {'trapping_clips': clipUrl, 'trapping_ans': rating})

        df = df.append(clipsList)
        return df


async def prepare_metadata_per_task(cfg, clips, gold, trapping):
    """
    Merge different input files into one dataframe
    :param test_method
    :param clips:
    :param trainings:
    :param gold:
    :param trapping:
    :param general:
    :return:
    """
    df_clips = pd.DataFrame()
    df_gold = pd.DataFrame()
    df_trap = pd.DataFrame()
    metadata_lst = []
    if clips and os.path.exists(clips):
        df_clips = pd.read_csv(clips)
    else:
        rating_clips_stores = cfg.get(
            'RatingClips', 'RatingClipsConfigurations').split(',')
        testclipsstore = ClipsInAzureStorageAccount(cfg['noisy'], 'noisy')
        testclipsbasenames = [os.path.basename(clip) for clip in await testclipsstore.clip_names]
        metadata = pd.DataFrame({'basename': testclipsbasenames})
        metadata = metadata.set_index('basename')
        for model in rating_clips_stores:
            enhancedClip = ClipsInAzureStorageAccount(cfg[model], model)
            eclips = await enhancedClip.clip_names
            eclips_urls = [enhancedClip.make_clip_url(clip) for clip in eclips]

            print('length of urls for store [{0}] is [{1}]'.format(model, len(await enhancedClip.clip_names)))
            model_df = pd.DataFrame({model: eclips_urls})
            model_df['basename'] = model_df.apply(
                lambda x: os.path.basename(x[model]), axis=1)
            model_df = model_df.set_index('basename')
            metadata = pd.concat([metadata, model_df], axis=1)

        df_clips = metadata

    if gold and os.path.exists(gold):
        df_gold = pd.read_csv(gold)
    else:
        goldclipsstore = GoldSamplesInStore(
            cfg['GoldenSample'], 'GoldenSample')
        df_gold = await goldclipsstore.get_dataframe()
        print('total gold clips from store [{0}]'.format(len(await goldclipsstore.clip_names)))

    if trapping and os.path.exists(trapping):
        df_trap = pd.read_csv(trapping)
    else:
        trapclipsstore = TrappingSamplesInStore(
            cfg['TrappingQuestions'], 'TrappingQuestions')
        df_trap = await trapclipsstore.get_dataframe()
        print('total trapping clips from store [{0}]'.format(len(await trapclipsstore.clip_names)))

    df_clips = df_clips.fillna('')
    print('iterating through [{0}] clips'.format(len(df_clips)))
    for i in range(len(df_clips)):
        metadata = {'file_shortname': df_clips.index[i]}
        metadata['file_urls'] = {}
        for col in df_clips.columns:
            if df_clips.loc[df_clips.index[i], col] != '':
                metadata['file_urls'][col] = df_clips.loc[df_clips.index[i], col]
        metadata['ground_truth'] = []
        random_gold_sample = df_gold.sample()
        random_trap_sample = df_trap.sample()
        gold_clip_dict = {
            "type": "golden_clip",
            "attachment": random_gold_sample.iloc[0, 0],
            "response": {"rating": "{0}".format(random_gold_sample.iloc[0, 1])},
        }
        trap_clip_dict = {
            "type": "trapping_clip",
            "attachment": random_trap_sample.iloc[0, 0],
            "response": {"rating": "{0}".format(random_trap_sample.iloc[0, 1])},
        }
        metadata['ground_truth'].append(gold_clip_dict)
        metadata['ground_truth'].append(trap_clip_dict)

        metadata_lst.append(metadata)

    return metadata_lst


async def post_task(scale_api_key, task_obj):
    url = 'https://api.scale.com/v1/task/textcollection'
    headers = {"Content-Type": "application/json"}
    r = s.post(url, data=json.dumps(task_obj), headers=headers, auth=(
        scale_api_key, ''))
    if r.status_code != 200:
        print(r.content)


async def main(cfg, args):

    # prepare format
    metadata_lst = await prepare_metadata_per_task(cfg, args.clips, args.gold_clips, args.trapping_clips)

    for metadata in metadata_lst:
        task_obj = {
            "unique_id": args.project + "\\" + metadata['file_shortname'],
            "callback_url": "http://example.com/callback",
            "project": cfg.get("CommonAccountKeys", 'ScaleAccountName'),
            "instruction": "Please rate these audio files",
            "responses_required": args.num_responses_per_clip,
            "attachments": [
                {
                    "type": "text",
                    "content": "Please rate these audio files",
                },
            ],
            "fields": [
                {
                    "field_id": "rating",
                    "title": "Please rate the audio file",
                    "required": True,
                    "type": "category",
                    "choices": [
                        {"label": "Bad - 1", "value": "1"},
                        {"label": "Poor - 2", "value": "2"},
                        {"label": "Fair - 3", "value": "3"},
                        {"label": "Good - 4", "value": "4"},
                        {"label": "Excellent - 5", "value": "5"},
                    ],
                },
            ],
            "metadata": metadata
        }
        task_obj['metadata']["group"] = args.project

        await post_task(cfg.get("CommonAccountKeys", 'ScaleAPIKey'), task_obj)


if __name__ == '__main__':
    print("Welcome to the Master script for ACR test.")
    parser = argparse.ArgumentParser(
        description='Master script to prepare the ACR test')
    parser.add_argument("--project", help="Name of the project", required=True)
    parser.add_argument(
        "--cfg", help="Configuration file, see master.cfg", required=True)
    parser.add_argument("--clips", help="A csv containing urls of all clips to be rated in column 'rating_clips', in "
                                        "case of ccr/dcr it should also contain a column for 'references'")
    parser.add_argument("--gold_clips", help="A csv containing urls of all gold clips in column 'gold_clips' and their "
                                             "answer in column 'gold_clips_ans'")
    parser.add_argument("--trapping_clips", help="A csv containing urls of all trapping clips. Columns 'trapping_clips'"
                                                 "and 'trapping_ans'")
    parser.add_argument('--num_responses_per_clip',
                        help='Number of response per clip required', default=5, type=int)
    # check input arguments
    args = parser.parse_args()

    assert os.path.exists(args.cfg), f"No config file in {args.cfg}"

    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(args.cfg)

    if args.clips:
        assert os.path.exists(
            args.clips), f"No csv file containing clips in {args.clips}"
    elif cfg.has_option('RatingClips', 'RatingClipsConfigurations'):
        assert len(cfg['RatingClips']['RatingClipsConfigurations']
                   ) > 0, f"No cloud store for clips specified in config"
    else:
        assert True, "Neither clips file not cloud store provided for rating clips"

    if args.gold_clips:
        assert os.path.exists(
            args.gold_clips), f"No csv file containing gold clips in {args.gold_clips}"
    elif cfg.has_option('GoldenSample', 'Path'):
        assert len(cfg['GoldenSample']['Path']
                   ) > 0, "No golden clips store found"
    else:
        assert True, "Neither gold clips file nor store configuration provided"

    if args.trapping_clips:
        assert os.path.exists(
            args.trapping_clips), f"No csv file containing trapping  clips in {args.trapping_clips}"
    elif cfg.has_option('TrappingQuestions', 'Path'):
        assert len(cfg['TrappingQuestions']['Path']
                   ) > 0, "No golden clips store found"
    else:
        assert True, "Neither Trapping clips file nor store configuration provided"

    asyncio.run(main(cfg, args))
