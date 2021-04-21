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
import datetime

import pandas as pd
import requests
from azure.storage.blob import (AppendBlobService, BlockBlobService,
                                PageBlobService)
from azure.storage.file import FileService
from jinja2 import Template
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor

import create_input as ca

s = requests.Session()
retries = Retry(total=5,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504])

s.mount('https://', HTTPAdapter(max_retries=retries))

ECHO_FIELDS = [
    {
        "field_id": "rating_echo",
        "title": "How would you rate the level of acoustic echo in this file?",
        "required": True,
        "type": "category",
        "choices": [
            {"label": "Very annoying - 1", "value": "1"},
            {"label": "Annoying - 2", "value": "2"},
            {"label": "Slightly annoying - 3", "value": "3"},
            {"label": "Perceptible, but not annoying - 4", "value": "4"},
            {"label": "Imperceptible - 5", "value": "5"},
        ],
    },
    {
        "field_id": "rating_deg",
        "title": "How would you rate the level of other degradations (missing audio, distortions, cut-outs)?",
        "required": True,
        "type": "category",
        "choices": [
            {"label": "Very annoying - 1", "value": "1"},
            {"label": "Annoying - 2", "value": "2"},
            {"label": "Slightly annoying - 3", "value": "3"},
            {"label": "Perceptible, but not annoying - 4", "value": "4"},
            {"label": "Imperceptible - 5", "value": "5"},
        ]
    }
]

FIELDS = [
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
]


def parse_args():
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
    parser.add_argument('--method', default='acr', const='acr', nargs='?',
                        choices=('acr', 'echo'), help='Use regular ACR questions or echo questions')
    parser.add_argument('--replace_modelname', default=None, help="If given, replace {replace_modelname} "
        "in filenames with model name parsed from directory")
    return parser.parse_args()


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

            if not self._SAS_token:
                start = datetime.datetime.utcnow()
                end = start + datetime.timedelta(days=14)
                self._SAS_token = self.store_service.generate_container_shared_access_signature(
                    self.container, permission='r', expiry=end, start=start)
            await self.retrieve_contents(blobs)

    def make_clip_url(self, filename):
        if self._account_type == 'FileStore':
            source_url = self.store_service.make_file_url(
                self.container, self.clips_path, filename, sas_token=self._SAS_token)
        elif self._account_type == 'BlobStore':
            source_url = self.store_service.make_blob_url(
                self.container, filename, sas_token=self._SAS_token)
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


async def prepare_metadata_per_task(cfg, clips, gold, trapping, output_dir, replace_modelname):
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

        metadata = pd.DataFrame()
        for model in rating_clips_stores:
            enhancedClip = ClipsInAzureStorageAccount(cfg[model], model)
            eclips = await enhancedClip.clip_names
            eclips_urls = [enhancedClip.make_clip_url(clip) for clip in eclips]

            print('length of urls for store [{0}] is [{1}]'.format(model, len(await enhancedClip.clip_names)))
            model_df = pd.DataFrame({model: eclips_urls})
            model_df['basename'] = model_df.apply(
                lambda x: os.path.basename(remove_query_string_from_url(x[model])), axis=1)
            if replace_modelname is not None:
                model_df["basename"] = model_df["basename"].apply(lambda x: x.replace("dec", model))
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
    df_clips.to_csv(os.path.join(
        output_dir, "Batch_{0}_tasks.csv".format(datetime.datetime.now().strftime("%m%d%Y"))))
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


# TODO: some sort of structured URL parsing is more reasonable than this hack
def remove_query_string_from_url(url_series):
    filename_cutoff_index = url_series.index('.wav') + 4
    return url_series[:filename_cutoff_index]


def post_task(scale_api_key, task_obj):
    url = 'https://api.scale.com/v1/task/textcollection'
    headers = {"Content-Type": "application/json"}

    r = s.post(url, data=json.dumps(task_obj), headers=headers, auth=(
        scale_api_key, ''))
    if r.status_code != 200:
        return task_obj['unique_id'], r.content
    return None


async def main(cfg, args):
    # create output folder
    output_dir = args.project
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # prepare format
    metadata_lst = await prepare_metadata_per_task(cfg, args.clips, args.gold_clips, 
        args.trapping_clips, output_dir, args.replace_modelname)

    task_objs = list()
    for metadata in metadata_lst:
        fields = FIELDS
        if args.method == 'echo':
            fields = ECHO_FIELDS

        file_urls = metadata['file_urls'].values()
        attachments = list(
            map(lambda f: {"type": "audio", "content": f}, file_urls))
        task_obj = {
            "unique_id": args.project + "\\" + metadata['file_shortname'],
            "callback_url": "http://example.com/callback",
            "project": cfg.get("CommonAccountKeys", 'ScaleAccountName'),
            "instruction": "Please rate these audio files",
            "responses_required": args.num_responses_per_clip,
            "fields": fields,
            "attachments": attachments,
            "metadata": metadata
        }
        task_obj['metadata']["group"] = args.project

        task_objs.append(task_obj)

    assert False, json.dumps(task_objs[0])
    results = list()
    with ThreadPoolExecutor(max_workers=25) as executor:
        for res in executor.map(post_task, [cfg.get("CommonAccountKeys", 'ScaleAPIKey')] * len(task_objs), task_objs):
            results.append(res)

    failed = [x for x in results if x]
    print(failed)


if __name__ == '__main__':
    print("Welcome to the Master script for ACR test.")
    args = parse_args()
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
