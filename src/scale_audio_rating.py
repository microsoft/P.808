"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Vishak Gopal
"""

import argparse
import asyncio
import json
import os
import requests
import datetime

import configparser as CP
import pandas as pd

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from azure_clip_storage import AzureClipStorage, TrappingSamplesInStore, GoldSamplesInStore

s = requests.Session()
retries = Retry(total=5,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504])

s.mount('https://', HTTPAdapter(max_retries=retries))


async def prepare_metadata_per_task(cfg, clips, gold, trapping, output_dir):
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
        testclipsstore = AzureClipStorage(cfg['noisy'], 'noisy')
        testclipsbasenames = [os.path.basename(clip) for clip in await testclipsstore.clip_names]
        metadata = pd.DataFrame({'basename': testclipsbasenames})
        metadata = metadata.set_index('basename')
        for model in rating_clips_stores:
            enhancedClip = AzureClipStorage(cfg[model], model)
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
    df_clips.to_csv(os.path.join(
        output_dir, "Batch_{0}_tasks.csv".format(datetime.datetime.utcnow().strftime("%m%d%Y"))))
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


async def create_batch(scale_api_key, project_name, batch_name):
    url = 'https://api.scale.com/v1/batches'
    headers = {"Content-Type": "application/json"}
    payload = {
        "project": project_name,
        "name": batch_name,
        "callback_url": "http://example.com/callback",
    }
    r = s.post(url, data=payload, headers=headers, auth=(
        scale_api_key, ''))
    if r.status_code == 200:
        return r.content.name


async def finalize_batch(scale_api_key, batch_name):
    url = f'https://api.scale.com/v1/batches/{batch_name}/finalize'
    headers = {"Accept": "application/json"}
    r = s.post(url, headers=headers, auth=(scale_api_key, ''))
    if r.status_code == 200:
        return print(f'batch {r.content.name} finalized')
    

async def post_task(scale_api_key, task_obj):
    url = 'https://api.scale.com/v1/task/textcollection'
    headers = {"Content-Type": "application/json"}
    r = s.post(url, data=json.dumps(task_obj), headers=headers, auth=(
        scale_api_key, ''))
    if r.status_code != 200:
        print(r.content)


async def main(cfg, args):
    # create output folder
    output_dir = args.project
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # create batch
    batch = await create_batch(cfg.get("CommonAccountKeys", 'ScaleAPIKey'),cfg.get("CommonAccountKeys", 'ScaleAccountName'),args.project)

    # prepare format
    metadata_lst = await prepare_metadata_per_task(cfg, args.clips, args.gold_clips, args.trapping_clips, output_dir)

    for metadata in metadata_lst:
        file_urls = metadata['file_urls'].values()
        attachments = list(map(lambda f: {"type": "audio", "content": f}, file_urls))
        task_obj = {
            "unique_id": args.project + "\\" + metadata['file_shortname'],
            "callback_url": "http://example.com/callback",
            "project": cfg.get("CommonAccountKeys", 'ScaleAccountName'),
            "batch": batch,
            "instruction": "Please rate these audio files",
            "responses_required": args.num_responses_per_clip,
            "attachments": attachments,
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

    await finalize_batch(cfg.get("CommonAccountKeys", 'ScaleAPIKey'), batch)


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
