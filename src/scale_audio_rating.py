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
import create_input as ca

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from azure_clip_storage import AzureClipStorage, TrappingSamplesInStore, GoldSamplesInStore
from concurrent.futures import ThreadPoolExecutor


s = requests.Session()
retries = Retry(total=5,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504])

s.mount('https://', HTTPAdapter(max_retries=retries))

P835_FIELDS = [
    {
        "field_id": "distortion",
        "title": "Distortion",
        "description": "Referring to the previous file, how would you judge the SPEECH SIGNAL/DISTORTION of the speaker?",
        "required": True,
        "type": "category",
        "choices": [
            { "label": "5 - Not distorted", "value": "5" },
            { "label": "4 - Slightly distorted", "value": "4" },
            { "label": "3 - Somewhat distorted", "value": "3" },
            { "label": "2 - Fairly distorted", "value": "2" },
            { "label": "1 - Very distorted", "value": "1" },
        ],
    },
    {
        "field_id": "background",
        "title": "Background Noise",
        "description": "Referring to the previous file, how would you judge the BACKGROUND NOISE of the file?",
        "required": True,
        "type": "category",
        "choices": [
            { "label": "5 - Not noticeable", "value": "5" },
            { "label": "4 - Slightly noticeable", "value": "4" },
            { "label": "3 - Noticeable but not intrusive", "value": "3" },
            { "label": "2 - Somewhat intrusive", "value": "2" },
            { "label": "1 - Very intrusive", "value": "1" },
        ],
    },
    {
        "field_id": "overall",
        "title": "Overall",
        "description": "Referring to the previous file, how would you judge the OVERALL quality of the file?",
        "required": True,
        "type": "category",
        "choices": [
            { "label": "5 - Excellent", "value": "5" },
            { "label": "4 - Good", "value": "4" },
            { "label": "3 - Fair", "value": "3" },
            { "label": "2 - Poor", "value": "2" },
            { "label": "1 - Bad", "value": "1" },
        ],
    },
]

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
        description='Script for submitting clips to Scale for ratings')
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
                        choices=('acr', 'echo', 'p835'), help='Use regular ACR questions or echo questions')
    return parser.parse_args()


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

        metadata = pd.DataFrame()
        for model in rating_clips_stores:
            enhancedClip = AzureClipStorage(cfg[model], model)
            eclips = await enhancedClip.clip_names
            eclips_urls = [enhancedClip.make_clip_url(clip) for clip in eclips]

            print('length of urls for store [{0}] is [{1}]'.format(model, len(await enhancedClip.clip_names)))
            model_df = pd.DataFrame({model: eclips_urls})
            model_df['basename'] = model_df.apply(
                lambda x: os.path.basename(remove_query_string_from_url(x[model])), axis=1)
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
                if col == 'reference':
                    metadata['reference_url'] = df_clips.loc[df_clips.index[i], col]
                else:
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


async def create_batch(scale_api_key, project_name, batch_name, callback_url=''):
    url = 'https://api.scale.com/v1/batches'
    headers = {"Content-Type": "application/json"}
    payload = {
        "project": project_name,
        "name": batch_name,
        "callback_url": callback_url,
    }
    r = s.post(url, json=payload, headers=headers, auth=(
        scale_api_key, ''))

    response_body = r.json()
    
    if r.status_code == 200:
        return response_body["name"]
    
    if r.status_code == 409:
        # Already exists, no idea if it's finalized or not, but we'll assume it's not
        return batch_name


async def finalize_batch(scale_api_key, batch_name):
    url = f'https://api.scale.com/v1/batches/{batch_name}/finalize'
    headers = {"Accept": "application/json"}
    r = s.post(url, headers=headers, auth=(scale_api_key, ''))
    if r.status_code == 200:
        return print(f'batch {r.json()["name"]} finalized')


def post_task(scale_api_key, task_obj):
    url = 'https://api.scale.com/v1/task/textcollection'
    headers = {"Content-Type": "application/json"}

    r = s.post(url, data=json.dumps(task_obj), headers=headers, auth=(
        scale_api_key, ''))
    if r.status_code != 200:
        return task_obj['unique_id'], r.content
    return None


async def main(cfg, args):
    api_key = cfg.get("CommonAccountKeys", 'ScaleAPIKey')
    scale_project_name = cfg.get("CommonAccountKeys", 'ScaleAccountName')
    scale_batch_name =  args.project
    callback_url = (
        cfg.get("CommonAccountKeys", "CallbackURL")
        if cfg.has_option("CommonAccountKeys", "CallbackURL")
        else 'http://example.com/callback'
    )

    # create output folder
    output_dir = scale_batch_name
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # prepare format
    metadata_lst = await prepare_metadata_per_task(cfg, args.clips, args.gold_clips,
                                                   args.trapping_clips, output_dir)

    # create batch
    batch = await create_batch(api_key, scale_project_name, scale_batch_name,callback_url)

    task_objs = list()
    for metadata in metadata_lst:
        fields = FIELDS
        if args.method == 'echo':
            fields = ECHO_FIELDS
        elif args.method == 'p835':
            fields = P835_FIELDS

        file_urls = metadata['file_urls'].values()
        for file in file_urls:
            attachments = [{"type": "audio", "content": file}]
            task_obj = {
                "unique_id": scale_batch_name + "\\" + metadata['file_shortname'],
                "callback_url": "http://example.com/callback",
                "project": scale_project_name,
                "batch": batch,
                "instruction": "Please rate these audio files",
                "responses_required": args.num_responses_per_clip,
                "fields": fields,
                "attachments": attachments,
                "metadata": metadata
            }
            task_obj['metadata']["group"] = scale_batch_name

            task_objs.append(task_obj)

    executor = ThreadPoolExecutor(max_workers=25)
    results = executor.map(post_task, [cfg.get(
        "CommonAccountKeys", 'ScaleAPIKey')] * len(task_objs), task_objs)
    failed = [result for result in results if result]
    print("Failed to submit: ", failed)

    # Don't finalize batch if there are files that failed to submit
    if len(failed) == 0:
        await finalize_batch(api_key, batch)


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
