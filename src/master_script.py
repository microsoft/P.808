"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

import argparse
import os
import asyncio
import base64
import hashlib
import random
import re
import string

import configparser as CP
import pandas as pd
import create_input as ca
import math
from jinja2 import Template
from azure_clip_storage import (
    AzureClipStorage,
    TrappingSamplesInStore,
    GoldSamplesInStore,
    PairComparisonSamplesInStore,
)

import requests
from multiprocessing import Pool
from utils.preview_html import generate_previews

#p835_personalized = "p835_personalized"
p835_personalized = "pp835"


def _strip_author_lines(text):
    """
    Remove any line containing an ``@author`` tag from a template's text.

    Generated HIT-app HTML files are published to crowd workers, so personal author
    attribution carried over from the templates is stripped out during generation.

    :param text: The template file content.
    :return: The content with any line containing ``@author`` removed.
    """
    return re.sub(r'(?m)^.*@author.*\r?\n?', '', text)


def _get_cookie_value(cfg, key):
    """
    Return the cookie value from cfg if available, otherwise generate a random string.

    :param cfg: Configuration section (dict-like).
    :param key: The key to look up (e.g. 'cookie_name' or 'qual_cookie_name').
    :return: The value from cfg or a randomly generated 10-character string.
    """
    if key in cfg and cfg[key]:
        return cfg[key]
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

"""
def create_analyzer_cfg_acr(cfg, template_path, out_path):

    create cfg file to be used by analyzer script (acr method)
    :param cfg:
    :param template_path:
    :param out_path:
    :return:

    print("Start creating config file for result_parser")
    config = {}

    config['q_num'] = int(cfg['create_input']['number_of_clips_per_session']) + \
                      int(cfg['create_input']['number_of_trapping_per_session']) + \
                      int(cfg['create_input']['number_of_gold_clips_per_session'])

    config['max_allowed_hits'] = cfg['acr_html']['allowed_max_hit_in_project']

    config['quantity_hits_more_than'] = cfg['acr_html']['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['acr_html']['quantity_bonus']
    config['quality_top_percentage'] = cfg['acr_html']['quality_top_percentage']
    config['quality_bonus'] = cfg['acr_html']['quality_bonus']

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    content = _strip_author_lines(content)
    t = Template(content)
    cfg_file = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(cfg_file)
        file.close()
    print(f"  [{out_path}] is created")
"""


def create_analyzer_cfg_general(cfg, cfg_section, template_path, out_path, general_cfg, n_HITs):
    """
    create cfg file to be used by analyzer script (acr, p835, and echo_impairment_test method)
    :param cfg:
    :param cfg_section_name: 'acr_html', 'p835_html', 'echo_impairment_test_html'
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating config file for result_parser")
    config = {}

    config['q_num'] = int(cfg['create_input']['number_of_clips_per_session']) + \
                      int(cfg['create_input']['number_of_trapping_per_session']) + \
                      int(cfg['create_input']['number_of_gold_clips_per_session'])

    config["max_allowed_hits"] = cfg_section["allowed_max_hit_in_project"] if "allowed_max_hit_in_project" in cfg_section else min(50, n_HITs)

    config['quantity_hits_more_than'] = cfg_section['quantity_hits_more_than']
    config['quantity_bonus'] = cfg_section['quantity_bonus']
    config['quality_top_percentage'] = cfg_section['quality_top_percentage']
    config['quality_bonus'] = cfg_section['quality_bonus']
    default_condition = r'.*_c(?P<condition_num>\d{1,2})_.*.wav'
    default_keys = 'condition_num'
    config['condition_pattern'] = cfg['create_input'].get("condition_pattern", default_condition)
    config['condition_keys'] = cfg['create_input'].get("condition_keys", default_keys)
    # target crowdsourcing platform (mturk or prolific); Prolific skips bonus reports
    config['platform'] = cfg['create_input'].get("platform", "prolific")

    # BW check
    config['bw_min'] = general_cfg['bw_min']
    config['bw_max'] = general_cfg['bw_max']

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    content = _strip_author_lines(content)
    t = Template(content)
    cfg_file = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(cfg_file)
        file.close()
    print(f"  [{out_path}] is created")


def create_analyzer_cfg_dcr_ccr(cfg, template_path, out_path, general_cfg, n_HITs):
    """
    create cfg file to be used by analyzer script (ccr/dcr method)
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating config file for result_parser")
    config = {}

    config['q_num'] = int(cfg['create_input']['number_of_clips_per_session']) + \
                      int(cfg['create_input']['number_of_trapping_per_session'])

    config['max_allowed_hits'] = cfg["allowed_max_hit_in_project"] if "allowed_max_hit_in_project" in cfg else min(50, n_HITs)

    config['quantity_hits_more_than'] = cfg['hit_app_html']['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['hit_app_html']['quantity_bonus']
    config['quality_top_percentage'] = cfg['hit_app_html']['quality_top_percentage']
    config['quality_bonus'] = cfg['hit_app_html']['quality_bonus']
    default_condition = r'.*_c(?P<condition_num>\d{1,2})_.*.wav'
    default_keys = 'condition_num'
    config['condition_pattern'] = cfg['create_input'].get("condition_pattern", default_condition)
    config['condition_keys'] = cfg['create_input'].get("condition_keys", default_keys)
    # target crowdsourcing platform (mturk or prolific); Prolific skips bonus reports
    config['platform'] = cfg['create_input'].get("platform", "prolific")

    # BW check
    config['bw_min'] = general_cfg['bw_min']
    config['bw_max'] = general_cfg['bw_max']
    
    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    content = _strip_author_lines(content)
    t = Template(content)
    cfg_file = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(cfg_file)
        file.close()
    print(f"  [{out_path}] is created")


async def create_hit_app_ccr_dcr(cfg, template_path, out_path, training_path, cfg_g, general_cfg):
    """
    Create the hit_app (html file) corresponding to this project for ccr and dcr
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating custom hit_app (html)")

    config = {}
    config['cookie_name'] = _get_cookie_value(cfg, 'cookie_name')
    config['qual_cookie_name'] = _get_cookie_value(cfg, 'qual_cookie_name')
    config['allowed_max_hit_in_project'] = cfg['allowed_max_hit_in_project']
    config['contact_email'] = cfg["contact_email"] if "contact_email" in cfg else ""

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = float(cfg['quality_bonus']) + float(cfg['quantity_bonus'])
    config['sum_quantity'] = float(cfg['quantity_bonus']) + float(cfg['hit_base_payment'])
    config['sum_quality'] = config['quality_bonus'] + float(cfg['hit_base_payment'])

    config = {**config, **general_cfg}
    # rating urls
    rating_urls = []
    n_clips = int(cfg_g['number_of_clips_per_session'])
    n_traps = int(cfg_g['number_of_trapping_per_session'])
    # 'dummy':'dummy' is added because of current bug in AMT for replacing variable names. See issue #6
    for i in range(0, n_clips):
        rating_urls.append({"ref": f"${{Q{i}_R}}", "processed": f"${{Q{i}_P}}", 'dummy': 'dummy'})

    if n_traps > 1:
        print("more than 1 trapping clips question is not supported. Proceed with 1 trap")
    rating_urls.append({"ref": "${TP}", "processed": "${TP}", 'dummy': 'dummy'})
    if 'number_of_gold_clips_per_session' in cfg_g:
        print("Gold clips are not supported for CCR and DCR method. Proceed without them")
    config['rating_urls'] = rating_urls

    # training urls
    df_train = pd.read_csv(training_path)
    train_urls = []
    train_ref = None
    for _, row in df_train.iterrows():
        if train_ref is None:
            train_ref = row['training_references']
        train_urls.append({"ref": f"{row['training_references']}", "processed": f"{row['training_clips']}"})
    # add a trapping clips to the training section
    train_urls.append({"ref": f"{train_ref}", "processed": f"{train_ref}"})
    config['training_urls'] = train_urls
    config['training_trap_urls'] = train_ref

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    content = _strip_author_lines(content)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(html)
    print(f"  [{out_path}] is created")


async def create_hit_app_acr(cfg, template_path, out_path, training_path, trap_path, cfg_g, cfg_trapping_store,
                             general_cfg, nHITs):
    """
    Create the ACR.html file corresponding to this project
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating custom acr.html")
    df_trap = pd.DataFrame()
    if trap_path and os.path.exists(trap_path):
        df_trap = pd.read_csv(trap_path, nrows=1)
    else:
        if cfg_trapping_store  is None:
            raise Exception("cfg_trapping_store is required when trap_path is not provided or invalid.")
        trapclipsstore = TrappingSamplesInStore(cfg_trapping_store, 'TrappingQuestions')
        df_trap = await trapclipsstore.get_dataframe()
    # trapping clips are required, at list 1 clip should be available here
    if len(df_trap.index) < 1 and int(cfg_g['number_of_clips_per_session']) > 0:
        raise ("At least one trapping clip is required")
    for _, row in df_trap.head(n=1).iterrows():
        trap_url = row['trapping_clips']
        trap_ans = row['trapping_ans']

    config = {}
    config['cookie_name'] = _get_cookie_value(cfg, 'cookie_name')
    config['qual_cookie_name'] = _get_cookie_value(cfg, 'qual_cookie_name')
    config['allowed_max_hit_in_project'] = cfg["allowed_max_hit_in_project"] if "allowed_max_hit_in_project" in cfg else nHITs
    config['training_trap_urls'] = trap_url
    config['training_trap_ans'] = trap_ans
    config['contact_email'] = cfg["contact_email"] if "contact_email" in cfg else "ic3ai@outlook.com"

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = float(cfg['quality_bonus']) + float(cfg['quantity_bonus'])
    config['sum_quantity'] = float(cfg['quantity_bonus']) + float(cfg['hit_base_payment'])
    config['sum_quality'] = config['quality_bonus'] + float(cfg['hit_base_payment'])
    config = {**config, **general_cfg}

    df_train = pd.read_csv(training_path)
    train = []
    for _, row in df_train.iterrows():
        train.append(row['training_clips'])
    train.append(trap_url)
    config['training_urls'] = train

    # rating urls
    rating_urls = []
    n_clips = int(cfg_g['number_of_clips_per_session'])
    n_traps = int(cfg_g['number_of_trapping_per_session'])
    n_gold_clips = int(cfg_g['number_of_gold_clips_per_session'])

    for i in range(0, n_clips):
        rating_urls.append('${Q'+str(i)+'}')
    if n_traps > 1:
        raise Exception("more than 1 trapping clips question is not supported.")
    if n_traps == 1:
        rating_urls.append('${TP}')

    if n_gold_clips > 1:
        raise Exception("more than 1 gold question is not supported.")
    if n_gold_clips == 1:
        rating_urls.append('${gold_clips}')

    config['rating_urls'] = rating_urls

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    content = _strip_author_lines(content)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(html)
    print(f"  [{out_path}] is created")


def get_encoded_gold_ans(url, ans):
    ans = f"{url}_{round(ans)}"
    return base64.b64encode(ans.encode("ascii")).decode("ascii")


async def create_hit_app_p835(cfg, template_path, out_path, training_path, trap_path, cfg_g, cfg_trapping_store, general_cfg,
    nHITs):
    """
    Create the p835.html/echo_impairment_test file corresponding to this project
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating custom p835.html")
    df_trap = pd.DataFrame()
    if trap_path and os.path.exists(trap_path):
        df_trap = pd.read_csv(trap_path, nrows=1)
    else:
        if cfg_trapping_store  is None:
            raise Exception("cfg_trapping_store is required when trap_path is not provided or invalid.")
        trapclipsstore = TrappingSamplesInStore(cfg_trapping_store, 'TrappingQuestions')
        df_trap = await trapclipsstore.get_dataframe()
    # trapping clips are required, at list 1 clip should be available here
    if len(df_trap.index) < 1 and int(cfg_g['number_of_clips_per_session']) > 0:
        raise (f"At least one trapping clip is required")
    for _, row in df_trap.head(n=1).iterrows():
        trap_url = row['trapping_clips']
        trap_ans = row['trapping_ans']

    config = {}
    config['cookie_name'] = _get_cookie_value(cfg, 'cookie_name')
    config['qual_cookie_name'] = _get_cookie_value(cfg, 'qual_cookie_name')
    config['allowed_max_hit_in_project'] = cfg["allowed_max_hit_in_project"] if "allowed_max_hit_in_project" in cfg else  min(50, nHITs) 
    config['training_trap_urls'] = trap_url
    config['training_trap_ans'] = trap_ans
    config['contact_email'] = cfg["contact_email"] if "contact_email" in cfg else "ic3ai@outlook.com"

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = round(float(cfg['quality_bonus']) + float(cfg['quantity_bonus']),2)
    config['sum_quantity'] = round(float(cfg['quantity_bonus']) + float(cfg['hit_base_payment']),2)
    config['sum_quality'] = round(config['quality_bonus'] + float(cfg['hit_base_payment']),2)
    config = {**config, **general_cfg}

    df_train = pd.read_csv(training_path)
    train = []
    for _, row in df_train.iterrows():
        train.append(row['training_clips'])
    train.append(trap_url)
    config['training_urls'] = train

    # rating urls
    rating_urls = []
    n_clips = int(cfg_g['number_of_clips_per_session'])
    n_traps = int(cfg_g['number_of_trapping_per_session'])
    n_gold_clips = int(cfg_g['number_of_gold_clips_per_session'])

    for i in range(0, n_clips):
        rating_urls.append('${Q'+str(i)+'}')
    if n_traps > 1:
        raise Exception("more than 1 trapping clips question is not supported.")
    if n_traps == 1:
        rating_urls.append('${TP}')

    if n_gold_clips > 1:
        raise Exception("more than 1 gold question is not supported.")
    if n_gold_clips == 1:
        rating_urls.append('${gold_clips}')

    config['rating_urls'] = rating_urls

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    content = _strip_author_lines(content)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(html)
    print(f"  [{out_path}] is created")


async def create_hit_app_pp835_p804(
    cfg,
    template_path,
    out_path,
    training_path,
    trap_path,
    cfg_g,
    cfg_trapping_store,
    general_cfg,
    nHITs
):
    """
    Create the p835.html/echo_impairment_test file corresponding to this project
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating custom p835.html")
    df_trap = pd.DataFrame()
    if trap_path and os.path.exists(trap_path):
        df_trap = pd.read_csv(trap_path, nrows=1)
    else:
        if cfg_trapping_store is None:
            raise Exception("cfg_trapping_store is required when trap_path is not provided or invalid.")
        trapclipsstore = TrappingSamplesInStore(cfg_trapping_store, "TrappingQuestions")
        df_trap = await trapclipsstore.get_dataframe()
    # trapping clips are required, at list 1 clip should be available here
    if len(df_trap.index) < 1 and int(cfg_g["number_of_clips_per_session"]) > 0:
        raise (f"At least one trapping clip is required")
    for _, row in df_trap.head(n=1).iterrows():
        trap_url = row["trapping_clips"]
        trap_ans = row["trapping_ans"]

    config = {}
    config["cookie_name"] = _get_cookie_value(cfg, "cookie_name")
    config["qual_cookie_name"] = _get_cookie_value(cfg, "qual_cookie_name")
    config["allowed_max_hit_in_project"] = cfg["allowed_max_hit_in_project"] if "allowed_max_hit_in_project" in cfg else  min(50, nHITs) 
    config["training_trap_urls"] = trap_url
    config["training_trap_ans"] = trap_ans
    config["test_instructions_flavor"] = cfg.get("test_instructions_flavor") or "default"
    config["contact_email"] = (
        cfg["contact_email"] if "contact_email" in cfg else "ic3ai@outlook.com"
    )
    # whether the in-HIT qualification section is shown. Default: shown.
    config["show_qualification"] = (
        "false"
        if str(cfg.get("show_qualification", "true")).strip().lower()
        in ("false", "0", "no", "off")
        else "true"
    )

    config["hit_base_payment"] = cfg["hit_base_payment"]
    config["quantity_hits_more_than"] = cfg["quantity_hits_more_than"]
    config["quantity_bonus"] = cfg["quantity_bonus"]
    config["quality_top_percentage"] = cfg["quality_top_percentage"]
    config["quality_bonus"] = round(float(cfg["quality_bonus"]) + float(cfg["quantity_bonus"]), 2)
    config["sum_quantity"] = round(float(cfg["quantity_bonus"]) + float(cfg["hit_base_payment"]), 2)
    config["sum_quality"] = round(float(config["quality_bonus"]) + float(cfg["hit_base_payment"]), 2)
    config = {**config, **general_cfg}

    
    train = []
    
    if not args.training_gold_clips:
        df_train = pd.read_csv(training_path)
        for _, row in df_train.iterrows():
            train.append(row["training_clips"])
        train.append(trap_url)

    if args.training_gold_clips:        
        df_train = pd.read_csv(args.training_gold_clips)
        gold_in_train = []
        cols = ['sig_ans','bak_ans','ovrl_ans']
        if test_method == 'p804':
            cols = ['sig_ans','noise_ans','ovrl_ans', 'disc_ans', 'col_ans', 'loud_ans', 'reverb_ans' ]

        for _, row in df_train.iterrows():
            train.append(row["training_clips"])
            data = {
                'url': row["training_clips"],
            }
            for col in cols:
                if not math.isnan(row[col]):
                    coded_ans = get_encoded_gold_ans(row["training_clips"], row[col])
                    prfx = col.split('_')[0]
                    data[prfx] = {'ans': coded_ans,'msg': row[f"{prfx}_msg"],'var': round(row[f"{prfx}_var"])}
            gold_in_train.append(data.copy())
        config["training_gold_clips"] = gold_in_train
        
    config["training_urls"] = train
    
    # rating urls
    rating_urls = []
    n_clips = int(cfg_g["number_of_clips_per_session"])
    n_traps = int(cfg_g["number_of_trapping_per_session"])
    n_gold_clips = int(cfg_g["number_of_gold_clips_per_session"])

    for i in range(0, n_clips):
        rating_urls.append("${Q" + str(i) + "}")
    if n_traps > 1:
        raise Exception("more than 1 trapping clips question is not supported.")
    if n_traps == 1:
        rating_urls.append("${TP}")

    #TODO move to personalized
    if n_gold_clips >=1:
        rating_urls.append("${gold_url}")
    if n_gold_clips >=2:
        rating_urls.append("${gold_url_2}")
    if n_gold_clips > 2:
        raise Exception("more than 2 gold question is not supported.")

    config["rating_urls"] = rating_urls

    print(template_path)

    with open(template_path, "r", encoding="utf-8") as file:
        content = file.read()
        file.seek(0)
    content = _strip_author_lines(content)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, "w", encoding="utf-8") as file:
        file.write(html)
    print(f"  [{out_path}] is created")


def update_gold_clips_for_personalized(df_gold):
    # expected columns: gold_url,sig_ans,bak_ans,ovrl_ans. If any of scale are not relevant add the column but let the value be empty
    columns = ['gold_url','sig_ans','bak_ans','ovrl_ans']
    for col in columns:
        if col not in df_gold.columns:
            df_gold[col] = math.nan
    df_gold['gold_sig_ans'] = ''
    df_gold['gold_bak_ans'] = ''
    df_gold['gold_ovrl_ans'] = ''
    new_data = []
    # iterate through the rows of df_gold
    for index, row in df_gold.iterrows():
        data  = {'gold_url': row['gold_url']}
        if 'ver' in row:
            data['ver']= row['ver']
        data['gold_sig_ans'] = get_encoded_gold_ans(row['gold_url'], row['sig_ans']) if not math.isnan(row["sig_ans"]) else ''
        data['gold_bak_ans'] = get_encoded_gold_ans(row['gold_url'], row['bak_ans']) if not math.isnan(row["bak_ans"]) else ''
        data['gold_ovrl_ans'] = get_encoded_gold_ans(row['gold_url'], row['ovrl_ans']) if not math.isnan(row["ovrl_ans"]) else ''
        new_data.append(data)
    
    df_gold = pd.DataFrame(new_data)
    # df_gold.to_csv('tmp_gold.csv', index=False)
    return df_gold

def update_gold_clips_for_p804(df_gold):
    # expected columns: gold_url,sig_ans,bak_ans,ovrl_ans. If any of scale are not relevant add the column but let the value be empty
    columns = ['sig_ans','noise_ans','ovrl_ans', 'disc_ans', 'col_ans', 'loud_ans', 'reverb_ans' ]
    columns_list = columns.copy()
    columns_list.append('gold_url')
    for col in columns_list:
        if col not in df_gold.columns:
            df_gold[col] = math.nan

    for col in columns:
        df_gold[f'gold_{col}'] = ''
    
    new_data = []
    # iterate through the rows of df_gold
    for index, row in df_gold.iterrows():
        data  = {'gold_url': row['gold_url']}
        if 'ver' in row:
            data['ver']= row['ver']
        for col in columns:
            data[f'gold_{col}'] = get_encoded_gold_ans(row['gold_url'], row[col]) if not math.isnan(row[col]) else ''
        
        new_data.append(data)
    
    df_gold = pd.DataFrame(new_data)
    df_gold = df_gold.sample(frac =1)
    df_gold.to_csv('tmp_gold.csv', index=False)
    return df_gold


async def prepare_csv_for_create_input(cfg, test_method, clips, gold, trapping, general):
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
    df_general = pd.read_csv(general)
    df_clips = pd.DataFrame()
    df_gold = pd.DataFrame()
    df_trap = pd.DataFrame()

    # prepare the rating clips
    rating_clips = []
    if clips and os.path.exists(clips):
        df_clips = pd.read_csv(clips)
    elif test_method == p835_personalized:
        raise Exception("CSV describing the raiting clips is not provided")
    else:
        rating_clips_stores = cfg.get('RatingClips', 'RatingClipsConfigurations').split(',')
        for model in rating_clips_stores:
            enhancedClip = AzureClipStorage(cfg[model], model)
            eclips = await enhancedClip.clip_names
            eclips_urls = [enhancedClip.make_clip_url(clip) for clip in eclips]

            print('length of urls for store [{0}] is [{1}]'.format(model, len(await enhancedClip.clip_names)))
            rating_clips = rating_clips + eclips_urls

        df_clips = pd.DataFrame({'rating_clips': rating_clips})

    sec_gold_question = False
    if test_method in ["acr", "p835", "echo_impairment_test", p835_personalized,'p804']:
        # prepare the golden clips
        if gold and os.path.exists(gold):
            df_gold = pd.read_csv(gold)
            # TODO change it with p835_personalized
            if test_method in [p835_personalized, 'p804']:
                df_gold = update_gold_clips_for_p804(df_gold) if test_method == 'p804' else update_gold_clips_for_personalized(df_gold)
            
            #if 'gold_clips2' in args and args.gold_clips2 and os.path.exists(args.gold_clips2):
            #    df_gold2 = pd.read_csv(args.gold_clips2)
            #    df_gold2 = update_gold_clips_for_p804(df_gold2) if test_method == 'p804' else update_gold_clips_for_personalized(df_gold2)
                #df_gold2.to_csv('tmp_gold2.csv', index=False)
            #    sec_gold_question = True
        elif test_method == p835_personalized:
            raise Exception("CSV describing the golden clips is not provided")
        else:
            goldclipsstore = GoldSamplesInStore(cfg['GoldenSample'], 'GoldenSample')
            df_gold = await goldclipsstore.get_dataframe()
            print(
                "total gold clips from store [{0}]".format(
                    len(await goldclipsstore.clip_names)
                )
            )

        # prepare the trapping clips
        if not sec_gold_question:
            if  trapping and os.path.exists(trapping):
                df_trap = pd.read_csv(trapping)
            elif test_method == p835_personalized:
                raise Exception("CSV describing the trapping clips is not provided")
            else:
                trapclipsstore = TrappingSamplesInStore(
                    cfg["TrappingQuestions"], "TrappingQuestions"
                )
                df_trap = await trapclipsstore.get_dataframe()
                print(
                    "total trapping clips from store [{0}]".format(
                        len(await trapclipsstore.clip_names)
                    )
                )
    else:
        df_gold = None
        if not os.path.exists(clips):
            testclipsstore = AzureClipStorage(cfg['noisy'], 'noisy')
            testclipsurls = [testclipsstore.make_clip_url(clip) for clip in await testclipsstore.clip_names]
            print('The total test clips for our study is [{0}]'.format(len(testclipsurls)))

            clipdictList = []
            for eclip in rating_clips:
                for i, c in enumerate(testclipsurls):
                    if os.path.basename(c) in eclip:
                        clipdictList.append({'rating_clips':eclip, 'references':testclipsurls[i]})
                        break

            df_clips = pd.DataFrame(clipdictList)
        df_trap = df_clips[['references']].copy()
        df_trap.rename(columns={'references': 'trapping_clips'}, inplace=True)

    if sec_gold_question:
        result = pd.concat([df_clips, df_gold, df_gold2, df_general], axis=1, sort=False)
    else:
        result = pd.concat([df_clips, df_gold, df_trap, df_general], axis=1, sort=False)
    return result


def _correct_pair_url(row):
    """
    Return the correct (better-quality) clip URL of a JND setup pair.

    Prefer the explicit ``pair_ans`` answer (the URL of the correct/cleaner clip) when
    it is present; this is required for anonymized clips whose file names do not encode
    the SNR. Otherwise fall back to the legacy convention where the higher-SNR clip -
    the one whose file name starts with the larger 2-digit SNR prefix - is correct.

    :param row: A dataframe row (Series) with ``pair_a`` / ``pair_b`` and optionally
        ``pair_ans``.
    :return: The correct clip URL as a string.
    """
    ans = row.get("pair_ans") if "pair_ans" in row.index else None
    if isinstance(ans, str) and ans.strip():
        return ans.strip()
    a = int((row["pair_a"].rsplit("/", 1)[-1])[:2])
    b = int((row["pair_b"].rsplit("/", 1)[-1])[:2])
    return row["pair_a"] if a > b else row["pair_b"]


def prepare_basic_cfg(df):
    config = {}
    pair_cols = ["pair_a", "pair_b"] + (["pair_ans"] if "pair_ans" in df.columns else [])
    only_cfgs = df[pair_cols].copy()
    only_cfgs.dropna(subset=["pair_a"], inplace=True)
    cmp_correct_hashes = []
    for index, row in only_cfgs.iterrows():
        # SHA-256 hex of the correct clip URL, so the plain answer is not exposed in the
        # page (mirrors the bandwidth-check hashing). The client verifies a selected clip
        # by hashing its URL and matching against this list.
        url = _correct_pair_url(row)
        cmp_correct_hashes.append(hashlib.sha256(url.encode("utf-8")).hexdigest())

    # randomly select numbers for hearing test
    clear_sample_url = "https://audiosamplesp808.blob.core.windows.net/p808-assets/clips/sample_hearing_test/s0.wav"
    clear_sample_ans = "289"

    only_hearing_test = df[['hearing_test_url', 'hearing_test_ans']].copy()
    only_hearing_test.dropna(subset=["hearing_test_url"], inplace=True)
    sample = only_hearing_test.sample(n=4)
    tmp_sample = pd.DataFrame([{"hearing_test_url": clear_sample_url, "hearing_test_ans": clear_sample_ans}])
    sample = pd.concat([sample, tmp_sample])    
    sample["hearing_test_ans"] = sample["hearing_test_ans"].apply(lambda x: str(int(x)))
    i = 2
    for _, row in sample.iterrows():
        ans = row["hearing_test_ans"]
        if ans == clear_sample_ans:
            index = 1
        else:
            index = i
            i += 1
        config[f"num{index}_url"] = row["hearing_test_url"]
        config[f"num{index}_ans"] = base64.b64encode(ans.encode("ascii")).decode(
            "ascii"
        )

    # set environment test
    config["cmp_correct_answers"] = cmp_correct_hashes
    config["cmp_max_n_feedback"] = 4
    config["cmp_pass_threshold"] = 2
    return config


def create_qualification_only(args):
    """
    Generate the standalone qualification page (Qualification.html) for a project.

    Writes the qualification HTML (the hearing-test number clips are ${q_numN}
    placeholders, filled per row by the HIT app server) plus an answers CSV with
    one row per qualification instance (args.n_samples rows). Each row holds the
    question audio URLs (q_*) and correct answers (ans_*) for server-side
    validation; no answers are embedded in the HTML. Optionally generates a local
    preview from the first row when args.create_local_test is set.

    :param args: Parsed command-line arguments (project, general_assets, n_samples,
        create_local_test).
    :return: Path to the generated qualification HTML file.
    """
    # Static bandwidth/quality-discrimination clips and their correct answers.
    # These must match the comb_bw* clips in P808Template/Qualification.html.
    bw_base = "https://audiosamplesp808.blob.core.windows.net/p808-assets/clips/bw-test"
    bandwidth_tests = [
        ("comb_bw1", f"{bw_base}/d_g1_cmb.wav", "dq"),
        ("comb_bw2", f"{bw_base}/d_g2_cmb.wav", "dq"),
        ("comb_bw3", f"{bw_base}/d_g3_cmb.wav", "dq"),
        ("comb_bw4", f"{bw_base}/d_g4_cmb.wav", "sq"),
        ("comb_bw5", f"{bw_base}/d_g5_cmb.wav", "sq"),
    ]
    # Non-audio criteria questions 3-8 and their expected answer(s) ("|"-separated
    # when several are acceptable). Questions 5 and 6 are recency screeners with no
    # fixed correct answer.
    criteria = {
        "ans_3_mother_tongue": "english|en",
        "ans_4_ld": "in-ear|over-ear",
        "ans_5_last_subjective": "",
        "ans_6_audio_test": "",
        "ans_7_working_area": "N",
        "ans_8_hearing": "normal",
    }

    n_samples = max(1, int(getattr(args, "n_samples", 1) or 1))
    general_path = args.general_assets or os.path.join(
        os.path.dirname(__file__), "assets_master_script/general.csv"
    )
    assert os.path.exists(general_path), f"No general assets csv in {general_path}"
    df_general = pd.read_csv(general_path)

    # write the qualification HTML (placeholders are filled by the HIT app server)
    template_path = os.path.join(os.path.dirname(__file__), "P808Template/Qualification.html")
    with open(template_path, "r", encoding="utf-8") as file:
        html = file.read()
    html = _strip_author_lines(html)

    os.makedirs(args.project, exist_ok=True)
    out_path = os.path.join(args.project, f"{args.project}_qualification.html")
    with open(out_path, "w", encoding="utf-8") as file:
        file.write(html)
    print(f"  [{out_path}] is created")

    # answers CSV: one row per instance, q_* (audio URL) and ans_* (correct answer)
    columns = []
    for i in range(1, 6):
        columns += [f"q_num{i}", f"ans_num{i}"]
    for name, _url, _ans in bandwidth_tests:
        columns += [f"q_{name}", f"ans_{name}"]
    columns += list(criteria.keys())

    rows = []
    for _ in range(n_samples):
        # a fresh random sampling of the hearing-test number clips per instance
        sample_cfg = prepare_basic_cfg(df_general)
        row = {}
        for i in range(1, 6):
            encoded = sample_cfg.get(f"num{i}_ans")
            row[f"q_num{i}"] = sample_cfg.get(f"num{i}_url", "")
            row[f"ans_num{i}"] = base64.b64decode(encoded).decode("ascii") if encoded else ""
        for name, url, answer in bandwidth_tests:
            row[f"q_{name}"] = url
            row[f"ans_{name}"] = answer
        row.update(criteria)
        rows.append(row)

    answers_df = pd.DataFrame(rows, columns=columns)
    answers_path = os.path.join(args.project, f"{args.project}_qualification_answers.csv")
    answers_df.to_csv(answers_path, index=False)
    print(f"  [{answers_path}] ({n_samples} instance(s)) is created")

    # optional local preview built from the first instance
    if getattr(args, "create_local_test", False):
        from utils.preview_html import (
            replace_placeholders,
            replace_with_public_urls,
            _disable_fetch_for_local,
        )
        preview_html = _disable_fetch_for_local(
            replace_placeholders(replace_with_public_urls(html), answers_df.iloc[0])
        )
        preview_path = os.path.join(args.project, f"{args.project}_qualification_row-1.html")
        with open(preview_path, "w", encoding="utf-8") as file:
            file.write(preview_html)
        print(f"  [{preview_path}] is created")

    return out_path


def get_path(test_method, is_p831_fest):
    """
    check all the preequsites and see if all resources are available
    :param test_method:
    :param is_p831_fest:
    :return:
    """

    #   for acr
    acr_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/ACR_template.html')
    acr_cfg_template_path = os.path.join(os.path.dirname(__file__),
                                         'assets_master_script/acr_result_parser_template.cfg')
    
    
    
    #   for dcr
    dcr_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/DCR_template.html')
    #   for ccr
    ccr_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/CCR_template.html')
    dcr_ccr_cfg_template_path = os.path.join(os.path.dirname(__file__),
                                             'assets_master_script/dcr_ccr_result_parser_template.cfg')
    #   for  p835
    p835_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/P835_template.html')
    
    # for personalized p835
    pp835_template_path = os.path.join(
        os.path.dirname(__file__), "P808Template/P835_personalized_template3.html"
    )
    pp835_cfg_template_path = os.path.join(
        os.path.dirname(__file__), "assets_master_script/pp835_result_parser_template.cfg"
    )

    # for P804
    p804_template_path = os.path.join(
        os.path.dirname(__file__), "P808Template/P808_multi.html"
    )
    p804_cfg_template_path = os.path.join(
        os.path.dirname(__file__), "assets_master_script/p804_result_parser_template.cfg"
    )

    # for echo_impairment_test
    echo_impairment_test_fest_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/echo_impairment_test_fest_template.html')
    echo_impairment_test_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/echo_impairment_test_template.html')

    #   for p831-acr
    p831_acr_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/P831_ACR_template.html')
    p831_acr_cfg_template_path = os.path.join(os.path.dirname(__file__),
                                              'assets_master_script/acr_result_parser_template.cfg')

    #   for p831-dcr
    p831_dcr_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/P831_DCR_template.html')
    p831_dcr_cfg_template_path = os.path.join(os.path.dirname(__file__),
                                              'assets_master_script/dcr_ccr_result_parser_template.cfg')

    method_to_template = { # (method, is_p831_fest)
        ('acr', True): (p831_acr_template_path, p831_acr_cfg_template_path),
        ('dcr', True): (p831_dcr_template_path, p831_dcr_cfg_template_path),
        ('echo_impairment_test', True): (echo_impairment_test_fest_template_path, acr_cfg_template_path),
        ('acr', False): (acr_template_path, acr_cfg_template_path),
        ('dcr', False): (dcr_template_path, dcr_ccr_cfg_template_path),
        ('ccr', False): (ccr_template_path, dcr_ccr_cfg_template_path),
        ('p835', False): (p835_template_path, acr_cfg_template_path),
        (p835_personalized, False): (pp835_template_path, pp835_cfg_template_path),
        ('echo_impairment_test', False): (echo_impairment_test_template_path, acr_cfg_template_path),
        ("p804", False): (p804_template_path, p804_cfg_template_path),
    }
    # TODO: check if it works correctly by Personalized P.835
    template_path, cfg_path = method_to_template[test_method, is_p831_fest]
    assert os.path.exists(
        template_path
    ), f"No html template file found  in {template_path}"
    assert os.path.exists(cfg_path), f"No cfg template  found  in {cfg_path}"

    return template_path, cfg_path


def extend_general_cfg_bw(general, hitapp):
    # add BW check config
    if 'bw_min' not in hitapp or 'bw_max' not in hitapp :
        print("Warning: No bandwidth range specified in the config file, consider using updated template for master script. All bandwidth ranges will be allowed.")
        bw_min = 'NB-WB'
        bw_max = 'FB'
    else:
        assert hitapp['bw_min'] in ['NB-WB', 'SWB', 'FB'], f'bw_min should be one of NB-WB, SWB, FB, but got {hitapp["bw_min"]}'
        assert hitapp['bw_max'] in ['NB-WB', 'SWB', 'FB'], f'bw_max should be one of NB-WB, SWB, FB, but got {hitapp["bw_max"]}'
        bw_min = hitapp['bw_min']
        bw_max = hitapp['bw_max']
    general['bw_min'] = bw_min
    general['bw_max'] = bw_max
    return general


def _get_screenout_code(hitapp, key):
    """
    Resolve a study-level screen-out completion code from the HIT app config section.

    :param hitapp: Config section (SectionProxy) holding the HIT app settings.
    :param key: Config key holding the code (e.g. 'screenout_code_qualification' or
        'screenout_code_setup').
    :return: The configured code, or the literal '${<key>}' placeholder when it is not
        set, so the HIT app server can fill it at runtime. A warning is printed when the
        code is missing so the user knows to provide it when uploading to the HIT App Server.
    """
    code = (hitapp.get(key, '') or '').strip()
    if code:
        return code
    print(f"WARNING: '{key}' is not set in the configuration. The screen-out code will be "
          f"left as the ${{{key}}} placeholder; please provide it when uploading the study "
          f"to the HIT App Server.")
    return '${' + key + '}'


def _is_true(value):
    """
    Interpret a config value as a boolean flag, defaulting to True.

    :param value: Raw config value (string or None).
    :return: False when the value is one of false/0/no/off (case-insensitive),
        otherwise True.
    """
    return str(value).strip().lower() not in ("false", "0", "no", "off")


async def main(cfg, test_method, args):
    # check assets
    if args.general_assets:
        general_path = args.general_assets
    else:
        general_path = os.path.join(os.path.dirname(__file__), 'assets_master_script/general.csv')
    is_p831_fest = args.p831_fest

    assert os.path.exists(general_path), f"No csv file containing general infos in {general_path}"
    template_path, cfg_path = get_path(test_method, is_p831_fest)

    cfg_hit_app = None
    if "hit_app_html" in cfg:
        cfg_hit_app = cfg["hit_app_html"]
    else:
        print("\nWARNING: Your configuration file is outdated. Consider to use the new version.\n")
        if is_p831_fest:
            cfg_hit_app = cfg['p831_html']
        elif test_method == 'acr':
            cfg_hit_app = cfg['acr_html']
        elif test_method == 'p835':
            cfg_hit_app = cfg['p835_html']
        elif test_method == 'echo_impairment_test':
            cfg_hit_app = cfg['echo_impairment_test_html']
        else:
            cfg_hit_app = cfg['hit_app_html']        
    

    # check clip_packing_strategy
    clip_packing_strategy = "random"
    if "clip_packing_strategy" in cfg["create_input"]:
        clip_packing_strategy = cfg["create_input"]["clip_packing_strategy"].strip().lower()
        if clip_packing_strategy == "balanced_block":
            # condition pattern is needed
            if not(("condition_pattern" in cfg["create_input"]) & ("condition_keys" in cfg["create_input"])):
                raise SystemExit("Error: by 'balanced_block' strategy, 'condition_pattern' and 'condition_keys' should "
                                 "be specified in the configuration.")
            if (',' in cfg["create_input"]["condition_keys"]) & ("block_keys" not in cfg["create_input"]):
                raise SystemExit("Error: In 'balanced_block' strategy, 'block_keys' should be specified in "
                                 "configuration when 'condition_keys' contains more than one key.")
        elif not(clip_packing_strategy == "random"):
            raise SystemExit("Error: Unexpected value for 'clip_packing_strategy' in the configuration file")

    # prepare format
    print("Starting to prepare the mturk clips")
    df = await prepare_csv_for_create_input(
        cfg, test_method, args.clips, args.gold_clips, args.trapping_clips, general_path
    )
    print("... finished.")

    # create inputs
    print("Starting to validate input")
    ca.validate_inputs(cfg["create_input"], df, test_method)
    print("... finished.")

    # create output folder
    output_dir = args.project
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    output_csv_file = os.path.join(output_dir, args.project+'_publish_batch.csv')
    n_HITs = ca.create_input_for_mturk(
        cfg["create_input"], df, test_method, output_csv_file
    )

    # check settings of quantity bonus
    if not (int(cfg_hit_app["quantity_hits_more_than"]) in range(int(n_HITs/2),  int(n_HITs*2/3)+1)):
        print("\nWARNING: it seems that 'quantity_hits_more_than' not set properly. Consider to use a number in"
                              f" the range of [{int(n_HITs/2)}, {int(n_HITs*2/3)}].\n")

    # create general config
    general_cfg = prepare_basic_cfg(df)
    # add BW check config
    general_cfg = extend_general_cfg_bw(general_cfg, cfg_hit_app)
    # optional study-level screen-out completion codes (paid for the screening effort).
    # Left as ${screenout_code_*} placeholders for the HIT app server to fill when not set
    # in the config; a warning is printed for each missing code.
    general_cfg['screenout_code_qualification'] = _get_screenout_code(cfg_hit_app, 'screenout_code_qualification')
    general_cfg['screenout_code_setup'] = _get_screenout_code(cfg_hit_app, 'screenout_code_setup')

    # Online (in-HIT) evaluation toggles for the qualification and setup sections
    # (both default true). When a flag is false, the section's correct answers are not
    # embedded in the HTML, the client-side check and its "Check answers" button are
    # hidden, and grading is left entirely to result_parser.
    run_online_eval_qual = _is_true(cfg_hit_app.get("run_online_eval_qualification", "true"))
    run_online_eval_setup = _is_true(cfg_hit_app.get("run_online_eval_setup", "true"))
    general_cfg['run_online_eval_qualification'] = "true" if run_online_eval_qual else "false"
    general_cfg['run_online_eval_setup'] = "true" if run_online_eval_setup else "false"
    if not run_online_eval_setup:
        # do not embed the setup (CMP) correct answers in the page
        general_cfg['cmp_correct_answers'] = []
    if not run_online_eval_qual:
        # do not embed the hearing-test answers in the page
        for i in range(1, 6):
            general_cfg[f'num{i}_ans'] = ""

    # Listening-device check: the required active playback device ("headset" or
    # "loudspeaker") that the objective (acoustic echo) check must confirm, and the
    # coupling threshold in dB above which the microphone is judged to hear the
    # loudspeaker. The check is mandatory; the participant cannot continue until the
    # detected device matches this requirement (and their self-report).
    required_device = str(cfg_hit_app.get("required_playback_device", "headset")).strip().lower()
    if required_device not in ("headset", "loudspeaker"):
        print(f"WARNING: 'required_playback_device' should be 'headset' or 'loudspeaker', "
              f"got '{required_device}'; defaulting to 'headset'.")
        required_device = "headset"
    general_cfg['required_playback_device'] = required_device
    general_cfg['device_check_threshold_db'] = str(cfg_hit_app.get("device_check_threshold_db", "6")).strip()
    # Probe-tone level (linear gain, 0..1) for the acoustic echo check. Kept low for
    # hearing safety: the check runs before the volume-adjust step, so the participant's
    # system volume is unknown. Detection is ratio-based, so a quiet tone still works.
    general_cfg['device_check_probe_gain'] = str(cfg_hit_app.get("device_check_probe_gain", "0.1")).strip()

    # create hit_app
    output_file_name = f"{args.project}_p831_{test_method}.html" if is_p831_fest else f"{args.project}_{test_method}.html"       
    output_html_file = os.path.join(output_dir, output_file_name)

    cfg_trapping = cfg['TrappingQuestions'] if cfg.has_section('TrappingQuestions') else None

    if test_method == 'acr':
        await create_hit_app_acr(cfg_hit_app, template_path, output_html_file, args.training_clips,
                                 args.trapping_clips, cfg['create_input'], cfg_trapping, general_cfg, n_HITs)
    elif test_method in ['p835', 'echo_impairment_test']:
        await create_hit_app_p835(cfg_hit_app, template_path, output_html_file, args.training_clips,
                                  args.trapping_clips, cfg['create_input'], cfg_trapping, general_cfg, n_HITs)
    elif test_method in [p835_personalized, 'p804']:
        await create_hit_app_pp835_p804(
            cfg_hit_app,
            template_path,
            output_html_file,
            args.training_clips if args.training_clips else None,
            args.trapping_clips,
            cfg["create_input"],
            cfg_trapping,
            general_cfg,
            n_HITs
        )
    else:
        await create_hit_app_ccr_dcr(cfg_hit_app, template_path, output_html_file, args.training_clips,
                                     cfg['create_input'], general_cfg)

    # create a config file for analyzer
    output_cfg_file_name = f"{args.project}_p831_{test_method}_result_parser.cfg" if is_p831_fest else f"{args.project}_{test_method}_result_parser.cfg"
    output_cfg_file = os.path.join(output_dir, output_cfg_file_name)

    if test_method in ['acr', 'p835', 'echo_impairment_test', p835_personalized, 'p804']:
        create_analyzer_cfg_general(cfg, cfg_hit_app, cfg_path, output_cfg_file, general_cfg, n_HITs)
    else:
        create_analyzer_cfg_dcr_ccr(cfg, cfg_path, output_cfg_file, general_cfg, n_HITs)


def check_url_exist(url):
    try:        
        response = requests.head(url)
        if response.status_code == 200:
            if int(response.headers['content-length']) > 1000:                
                return None
        print('Clip does not exists, try it on your browser: ' + url)
        return url
    except:
        print('Clip does not exists, try it on your browser: ' + url)
        return url

expected_columns_single_stimuli = {
        'clips': ['rating_clips'],
        'training': ['training_clips'],
        'gold': ['gold_url'],
        'trapping': ['trapping_clips'],
}

expected_columns_double_stimuli = {
       'clips': ['rating_clips', 'references'],
        'training': ['training_clips', 'training_references'],
}

def check_urls_in_files_exist(csv_file_path, columns):
    """
    Check if the csv file exists and contains the required columns.
    :param csv_file_path: Path to the csv file.
    :param columns: List of required columns.
    :return: True if the file exists and contains the required columns, False otherwise.
    """
    
    df = pd.read_csv(csv_file_path)

    count_links = 0
    # sort based on src
    urls = []
    for column in columns:
        urls.extend(df[column].tolist())

    # remove duplicates
    urls = list(set(urls))
    urls = [url for url in urls if isinstance(url, str) and url.strip()]
 
    errors = []
    print(" Checking URLs in the csv file:", csv_file_path, ', total links:', len(urls))
    # get number of cores
    n_cores = os.cpu_count()
    pool_size = int(0.8* n_cores) if n_cores > 2 else n_cores
    # use parallel processing to check the links
    with Pool(pool_size) as p:
        file_processed = 0
        issues = 0
        for result in p.imap_unordered(check_url_exist, urls, chunksize=10):
            if result is None:
                file_processed += 1
                if (file_processed % 100) == 0:
                    print('      Checked: ' + str(file_processed) + ' links')
            else:
                errors.append(result)
                issues += 1

               
    if len(errors) > 0:
        # Print in red if there are errors
        print('\033[91m' + f'  Total links evaluated: {len(urls)} ({len(errors)} links are invalid)' + '\033[0m')
    else:
        print(f'  Total links evaluated: {len(urls)} ({len(errors)} links are invalid)')
    if len(errors) > 0:
        print('   Errors: ')
        for error in errors:
            print('   ',error)

if __name__ == '__main__':
    print("Welcome to the Master script for P808 Toolkit.")
    parser = argparse.ArgumentParser(description='Master script to prepare the P.808 subjective test')
    parser.add_argument("--project", help="Name of the project", required=True)
    parser.add_argument("--cfg", help="Configuration file, see master.cfg", required=False)
    parser.add_argument("--method", required=False,
                        help=f"one of the test methods: 'acr', 'dcr', 'ccr', 'p835','{p835_personalized}', p804, or 'echo_impairment_test'")
    parser.add_argument("--p831_fest", action='store_true', help="Use the question set of P.831 for FEST")
    parser.add_argument("--clips", help="A csv containing urls of all clips to be rated in column 'rating_clips', in "
                                        "case of ccr/dcr it should also contain a column for 'references'")
    parser.add_argument("--gold_clips", help="A csv containing urls of all gold clips in column 'gold_clips' and their "
                                             "answer in column 'gold_clips_ans'")
    parser.add_argument("--training_clips", help="A csv containing urls of all training clips to be rated in training "
                                                 "section. Column 'training_clips'", required=False)
    parser.add_argument("--trapping_clips", help="A csv containing urls of all trapping clips. Columns 'trapping_clips'"
                                                 "and 'trapping_ans'")
    parser.add_argument(
        "--training_gold_clips",
        default=None,
        help="A csv containing urls and details of gold training questions ",
        required=False
    )
    # check links default to False
    parser.add_argument("--check_urls", action='store_true', help="Check if all links in the csv files are valid. "
                                                                    "Default is False")
    parser.add_argument("--check_silence", action='store_true',
                        help="Run a Voice Activity Detector (Silero VAD) over the rating clips and report clips "
                             "with little or no speech. Optional, like --check_urls. Default is False.")
    parser.add_argument("--create_local_test", action='store_true',
                        help="Generate a local preview HTML file after the project is created.")
    parser.add_argument(
        "--general_assets",
        default=None,
        help="Path to the general assets CSV (default: assets_master_script/general.csv). "
             "Use assets_master_script/general_assets_internal.csv for internal assets."
    )
    parser.add_argument(
        "--qualification_only", action='store_true',
        help="Only generate the standalone qualification page (Qualification.html) for this "
             "project, e.g. to publish a separate qualification screener. Skips clip/session generation."
    )
    parser.add_argument(
        "--n_samples", type=int, default=1,
        help="Number of qualification instances (rows) to generate in the answers CSV "
             "when using --qualification_only. Default: 1."
    )
    
    # check input arguments
    args = parser.parse_args()

    if args.qualification_only:
        # only generate the standalone qualification page; this mode needs just
        # --project (and optionally --general_assets), not --method or --cfg.
        create_qualification_only(args)
        raise SystemExit(0)

    assert args.method, "--method is required (except with --qualification_only)"
    methods = ["acr", "dcr", "ccr", "p835", "echo_impairment_test", p835_personalized, 'p804']
    test_method = args.method.lower()
    assert (
        test_method in methods
    ), f"No such a method supported, please select between 'acr', 'dcr', 'ccr', 'p835', '{p835_personalized}', 'echo_impairment_test', 'p804'"

    p831_methods = ["acr", "dcr", "echo_impairment_test"]
    if args.p831_fest:
        assert test_method in p831_methods, f"This method is not supported with p831, please choose one of {p831_methods}"

    assert args.cfg, "--cfg is required (except with --qualification_only)"
    assert os.path.exists(args.cfg), f"No config file in {args.cfg}"
    if args.training_clips:
        assert os.path.exists(
            args.training_clips
        ), f"No training clips file in {args.training_clips}"
    elif args.training_gold_clips:
        assert os.path.exists(args.training_gold_clips), f"No csv file containing training_gold_clips in {args.training_gold_clips}"
        if test_method not in [p835_personalized,"p804"]:
            raise ValueError("training_gold clips are only supported for personalized p835 and p804")
    else:
        raise ValueError("No training or training_gold clips provided")

    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(args.cfg)

    if args.clips:
        assert os.path.exists(args.clips), f"No csv file containing clips in {args.clips}"
    elif cfg.has_option('RatingClips', 'RatingClipsConfigurations'):
        assert len(cfg['RatingClips']['RatingClipsConfigurations']) > 0, f"No cloud store for clips specified in config"
    else:
        assert True, "Neither clips file not cloud store provided for rating clips"

    if test_method in ["acr", "p835", "echo_impairment_test", p835_personalized, 'p804']:
        if args.gold_clips:
            assert os.path.exists(args.gold_clips), f"No csv file containing gold clips in {args.gold_clips}"
        elif cfg.has_option('GoldenSample', 'Path'):
            assert len(cfg['GoldenSample']['Path']) > 0, "No golden clips store found"
        else:
            assert True, "Neither gold clips file nor store configuration provided"

        if args.trapping_clips:
            assert os.path.exists(args.trapping_clips), f"No csv file containing trapping  clips in {args.trapping_clips}"
        elif cfg.has_option('TrappingQuestions', 'Path'):
            assert len(cfg['TrappingQuestions']['Path']) > 0, "No golden clips store found"
        else:
            assert True, "Neither Trapping clips file nor store configuration provided"

    if args.check_urls:
        # check if all links in the csv files are valid
        #  'acr', 'dcr', 'ccr', 'p835','{p835_personalized}', p804, or 'echo_impairment_test'"
        print("Checking if all links in the csv files are valid ...")
        if test_method in ['acr', 'p835', f'{p835_personalized}', 'p804', 'echo_impairment_test']:
            check_urls_in_files_exist(args.clips, expected_columns_single_stimuli['clips'])
            check_urls_in_files_exist(args.training_gold_clips, expected_columns_single_stimuli['training'])
            check_urls_in_files_exist(args.gold_clips, expected_columns_single_stimuli['gold'])
            check_urls_in_files_exist(args.trapping_clips, expected_columns_single_stimuli['trapping'])
        elif test_method in ['dcr', 'ccr']:
            check_urls_in_files_exist(args.clips, expected_columns_double_stimuli['clips'])
            check_urls_in_files_exist(args.training_gold_clips, expected_columns_double_stimuli['training'])
            check_urls_in_files_exist(args.gold_clips, expected_columns_double_stimuli['gold'])
            check_urls_in_files_exist(args.trapping_clips, expected_columns_double_stimuli['trapping'])
        else:
            raise SystemExit(f"Error: No such a method supported for checking links: {test_method}")

    if args.check_silence:
        # optional VAD pre-screen of rating clips for silent / no-speech content.
        # Rating clips passed to the master script must always be publicly accessible.
        print("Running VAD silence pre-screen over the rating clips ...")
        if not args.clips:
            raise SystemExit("Error: --check_silence requires a rating clips csv (--clips).")
        from utils.detect_silence_vad import prescreen_clips
        rating_column = (
            expected_columns_double_stimuli["clips"][0]
            if test_method in ["dcr", "ccr"]
            else expected_columns_single_stimuli["clips"][0]
        )
        prescreen_clips(args.clips, column=rating_column)

    asyncio.run(main(cfg, test_method, args))

    if args.create_local_test:
        print("Generating local test preview...")
        generate_previews(args.project, samples=1)
