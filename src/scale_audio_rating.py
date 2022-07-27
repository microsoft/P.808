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
import copy

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

P835_INSTRUCTIONS = '''
  ### Instructions for Melon Audio Rating - Advanced
  In each task, you will **first** listen to a **clean reference audio file** to give you a context of what a baseline clean audio should sound like and allow you to identify who the **main speaker** of the audio file is (as distinct from any background speakers), and **then** you will rate the audio quality of several files in comparison to that reference file based on background noise and speech signal distortion. You will provide the following ratings for each audio sample:
  * **Distortion**: focus on the speech signal and rate how distorted the speech signal sounds to you. This can include garbled voices and audio cutouts, and is unrelated to background noise. 
  * **Background Noise**: Focus on the background and rate how noticeable or intrusive the background noise sounds to you. Be sure to **distinguish** between the speech of the **main speaker** you heard in the reference audio file and any other speakers that might be talking in the background. Speech from **other speakers** should be considered background noise and evaluated accordingly
  * **Overall**: attend to the entire sample (both the speech signal and the background) and rate your opinion of the OVERALL QUALITY of the sample for purposes of everyday speech communication. Most importantly, rate based on how well you're able to understand the speaker. There may be situations where there is little or no background noise, but the distortions result in lower scores.

  ### Conditions 
  * You must perform the task in a **quiet environment** like at home.
  * You must use **headphones**.
  * Note that **loudspeakers** are **not acceptable**.

  Feel free to refer back to the courses for examples!
  [Overall course](https://www.remotasks.com/course?id=melon-audio-rating_alternate_intro)
  [Distortion course](https://www.remotasks.com/course?id=melon-audio-rating-distortion)
  '''

ECHO_INSTRUCTIONS = '''
  ### Instructions for Melon Audio Rating - Echo (Mono - Singletalk)
  In each clip, you will hear a single person speaking. In some cases, you may hear an echo of the person in the background. In some cases, you may hear the person’s voice degraded or missing.
  
  Please do the following as you rate each audio sample:
  * listen for any **acoustic echo** (and distortions *from* Echo)
  * listen for any **other degradations** (missing/fading audio, cut-outs, background noise, non-Echo distortions). Their source *must not be from Echo*.
  
  ### Important Tips
  * As echoes or degradations present may be subtle, so be sure to rate 3 or lower when appropriate!
  * **Note that the Echo and Degradation ratings should be evaluated independently!**
---
  * If there is audible **full-blown echo** (even if soft in volume) throughout the clip, Echo rating should be **at most 1**.
  * If there is a **short burst** of echo in the clip, Echo rating should be **at most 3**.
  * If there is a **short burst** of echo-related distortion, Echo rating should be **at most 3**.

  Please refer to the [course](https://www.remotasks.com/course?id=melon-audio-rating-echo-stereo) for additional/updated examples!

  ### Examples to help you calibrate 
  Here are a few examples:
  ![](https://deepechoblob.blob.core.windows.net/p808-runs/improved_accuracy_experiments_20201210/vqe_lync_seeded3/icassp-2021-aec-challenge-blind-test-set/farend-singletalk/clean/JT6MoCMn9kmXsieQZCPMmA_farend_singletalk_--_vqe_lync_seeded3_--_mixed.wav)
  **Rating:** Imperceptible echo (5), no degradation (5)

  ![](https://deepechoblob.blob.core.windows.net/p808-runs/improved_accuracy_experiments_20201210/vqe_lync_seeded3/icassp-2021-aec-challenge-blind-test-set/farend-singletalk/noisy/a9DUm7Qvb0m7C7jtOGh9oA_farend_singletalk_with_movement_--_vqe_lync_seeded3_--_mixed.wav)
  **Rating:** Barely perceptible echo (4), severe degradation (1)

  ![](https://deepechoblob.blob.core.windows.net/p808-runs/improved_accuracy_experiments_20201210/vqe_lync_seeded3/icassp-2021-aec-challenge-blind-test-set/farend-singletalk/clean/eBFafcGQ40WeuETghasPmw_farend_singletalk_with_movement_--_vqe_lync_seeded3_--_mixed.wav)
  **Rating:** Slight echo (3), no degradation (5)

  ![](https://deepechoblob.blob.core.windows.net/p808-runs/accuracy_test_20201110/farend-singletalk/clean/VlTD-2fGSU6RL2eDvwzxOA_farend_singletalk_with_movement_--_vqe_lync_seeded3_--_mixed.wav)
  **Rating:** Moderate echo (2), slight degradation (4)

  ![](https://deepechoblob.blob.core.windows.net/p808-runs/improved_accuracy_experiments_20201210/vqe_lync_seeded3/icassp-2021-aec-challenge-blind-test-set/farend-singletalk/noisy/DNb0qIMRg0iwJqiYFx6RbA_farend_singletalk_with_movement_--_vqe_lync_seeded3_--_mixed.wav)
  **Rating:** Severe echo (1), high degradation (2)

  ### Low echo ratings here!
  <audio controls="controls"><source type="audio/wav" src="https://attachments.labeling-data.net/6032ba2e5bc91300118aafb3%2F%2F505cb61f-7799-4be4-877c-caab7378456b?Expires=2207520000&Key-Pair-Id=APKAIGOZDNNPITVQK2FQ&Signature=PRkehgLMRGo8QGkiZ1GR3VoclYJZXCF0FEGHNRXB5rsgVk4RWKwzJYsoHxpfF3QBeqiGUmfUT4zHxSw1XXt7LMbzzeIsRvTnadZJxSQHMAknnbOG~yYyUQnqRbORbg6eWCC29pr0VjeQZnwcRynmWAzX4PvDg1PeoqnvtdzOTBhTQH5gs2LsfSRtE9bv5n2lZ4CL98UPVQBVVoTL9Wi21jUqPf4~r69lRiEav6anN1Qlb1h1C~y5OfJogIVVvQljTFDg28DfulPh101rX4hH2Ye4q62jH5RIV~bJJIIYKNM0cAcX0Qq201XrZkaci2juXO6Vuj40Qh9Xok~Yd8iIjA__"></source></audio>
  There is **persistent, full-blown echo**, so rate 1

  <audio controls="controls"><source type="audio/wav" src="https://attachments.labeling-data.net/6032ba2e5bc91300118aafb3%2F%2F759ffa97-da53-43bd-b3a1-d20a9597b3bc?Expires=2207520000&Key-Pair-Id=APKAIGOZDNNPITVQK2FQ&Signature=aHkANj5GQDln1aeaQ4sqCtaCJJ7rB-1w1Pf8Zts-K~DL~uWss4GNXEpT98Ghd0fi3hK~BmSZ45jMFoW3wgl02QybQVwK-Y27S0xNd094Ikraqa8M3U1vi2Fi-GYTlSyRUHnD7tvigaiIDa3kFWsfery~5USxY0pIyUDbALbqe4wgOWSUXyzNKpFvGalCtEymRzeJv5nPHy9wJwysmjDHTe0Rki8Z1ntlFDAzGS-b4d-iX2yHl-O5P5dcFJ-EprV0NSnzwN8gX8UOdTfcnC-3oHsEEQidsLA~QhTLZjsyHuwGOJI4ZZ8QtczWg9IwKjfvawgCkBjH6Ss5HySMx1bzcw__"></source></audio>
  There is a **short burst of echo**, so rate 3 or 2

  <audio controls="controls"><source type="audio/wav" src="https://attachments.labeling-data.net/6032ba2e5bc91300118aafb3%2F%2F79e4c6ca-8cc5-4df3-9742-3270d03b13e4?Expires=2207520000&Key-Pair-Id=APKAIGOZDNNPITVQK2FQ&Signature=cGMmwWV8uAZx7i-XoybreHXuJPsATfzW-gvGunXk3Y5dXk58PfJUTiXt3l8eAWk40R~UjhbNFYEFyDhGID3YYTtjVwSgzy4DjWJ-lhgxSszR6vxucv5GYDfE-5dT1mGfcH3RxHGjGexiJk8FLuyhDRonRAuRtwkOwrvJDNyzLZlObYApgmZMEuxPvTd8ICnEQXINzOumARVPUKp9Et8yImaPw~rAj5unpt-YbJH8atNkQBSVvJKgPFaNZjPkgpSWBg9B9No~y8LUvrKnxpHK5tWsqoBA6hL-Bse7rOCbFPqf95~ZCVT5~O94mEDE88TqcsA73jtC3bPPN327BwivcA__"></source></audio>
  There is a **short burst of echo-rated distortion**, so rate 3 or 2
  '''

ACR_INSTRUCTIONS = '''
  ### Instructions for Melon Audio Rating - Alternate
  In this experiment, you will be rating the quality of speech samples. Each trial will include 6-8 audio samples containing one or more sentences. In each task, you will be rating the overall audio quality of several files, based on background noise and speech distortion. Most importantly, rate based on how well you’re able to understand the speaker. There may be situations where there is little or no background noise, but the distortions result in lower scores.

  ### Conditions
  * You must perform the task in a **quiet environment** like at home.
  * You must use **headphones**.
  * Note that **loudspeakers** are **not acceptable**.
  
  ### Examples
  Excellent (5) examples
  ![](https://noisesuppeastusblobstore.blob.core.windows.net/aml-inference/sensitivity-study-v3/600_testclips_validated_plus_100_stationary_enhanced_PHASENv134_4_55_24000/noreverb_clnsp176_chair_154380_0_snr19_tl-32_fileid_35.wav)
  ![](https://noisesuppeastusblobstore.blob.core.windows.net/jbc-share/new_samples/FiveStar/test_sample_1535.wav)
  ![](https://noisesuppeastusblobstore.blob.core.windows.net/jbc-share/new_samples/FiveStar/test_sample_121.wav)
 
  Bad (1) Examples
  ![](https://noisesuppeastusblobstore.blob.core.windows.net/jbc-share/new_samples/OneStarCompress/test_sample_1567.wav)
  ![](https://noisesuppeastusblobstore.blob.core.windows.net/aml-inference/nsnet-sensitivity-study-Feb_25/noisy_700_testclips_validated_adsp_filtered/noreverb_clnsp156_water_320289_2_snr3_tl-19_fileid_125.wav)
  ![](https://noisesuppeastusblobstore.blob.core.windows.net/jbc-share/new_samples/OneStarHeal/test_sample_4877.wav)

  Feel free to refer back to the courses for more examples!
  [Intro course](https://www.remotasks.com/course?id=melon-audio-rating_alternate_intro)
  [Packet loss course](https://www.remotasks.com/course?id=melon-audio-rating-packet-loss)
  '''

P835_FIELDS = [
    {
        "field_id": "distortion",
        "title": "Distortion",
        "description": "Referring to the previous file, how would you judge the SPEECH SIGNAL/DISTORTION of the speaker?",
        "required": True,
        "type": "category",
        "choices": [
            {"label": "5 - Not distorted", "value": "5"},
            {"label": "4 - Slightly distorted", "value": "4"},
            {"label": "3 - Somewhat distorted", "value": "3"},
            {"label": "2 - Fairly distorted", "value": "2"},
            {"label": "1 - Very distorted", "value": "1"},
        ],
    },
    {
        "field_id": "background",
        "title": "Background Noise",
        "description": "Referring to the previous file, how would you judge the BACKGROUND NOISE of the file?",
        "required": True,
        "type": "category",
        "choices": [
            {"label": "5 - Not noticeable", "value": "5"},
            {"label": "4 - Slightly noticeable", "value": "4"},
            {"label": "3 - Noticeable but not intrusive", "value": "3"},
            {"label": "2 - Somewhat intrusive", "value": "2"},
            {"label": "1 - Very intrusive", "value": "1"},
        ],
    },
    {
        "field_id": "overall",
        "title": "Overall",
        "description": "Referring to the previous file, how would you judge the OVERALL quality of the file?",
        "required": True,
        "type": "category",
        "choices": [
            {"label": "5 - Excellent", "value": "5"},
            {"label": "4 - Good", "value": "4"},
            {"label": "3 - Fair", "value": "3"},
            {"label": "2 - Poor", "value": "2"},
            {"label": "1 - Bad", "value": "1"},
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
        ],
    },
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
    parser.add_argument('--batch',
                        help='Name of batch for inputted tasks')
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
    scale_batch_name = args.batch
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
    batch = await create_batch(api_key, scale_project_name, scale_batch_name, callback_url)

    task_objs = list()
    for metadata in metadata_lst:
        instructions = ACR_INSTRUCTIONS
        fields = FIELDS
        if args.method == 'echo':
            instructions = ECHO_INSTRUCTIONS
            fields = ECHO_FIELDS
        elif args.method == 'p835':
            instructions = P835_INSTRUCTIONS
            fields = P835_FIELDS

        for key, file in metadata['file_urls'].items():
            attachments = [{"type": "audio", "content": file},
                           {"type": "text", "content": instructions}]
            task_obj = {
                "unique_id": scale_batch_name + "\\" + str(metadata['file_shortname']) + "\\" + key,
                "callback_url": "http://example.com/callback",
                "project": scale_project_name,
                "batch": batch,
                "instruction": "Please rate these audio files",
                "responses_required": args.num_responses_per_clip,
                "fields": fields,
                "attachments": attachments,
                "metadata": copy.deepcopy(metadata),
                "force_stacked": True,
            }
            task_obj['metadata']["file_urls"] = {key: file}
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
