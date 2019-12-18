"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

import argparse
import os
import configparser as CP
from jinja2 import Template
import pandas as pd
import create_input as ca


def create_analyzer_cfg(cfg, template_path, out_path):
    """
    create cfg file to be used by analyzer script
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating config file for acr_result_parser")
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
    t = Template(content)
    cfg_file = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(cfg_file)
        file.close()
    print(f"  [{out_path}] is created")


def create_acr_html(cfg, template_path, out_path, training_path, trap_path, cfg_g):
    """
    Create the ACR.html file corresponding to this project
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating custom acr.html")
    df_trap = pd.read_csv(trap_path, nrows=1)
    for index, row in df_trap.iterrows():
        trap_url = row['trapping_clips']
        trap_ans = row['trapping_ans']

    config = {}
    config['cookie_name'] = cfg['cookie_name']
    config['qual_cookie_name'] = cfg['qual_cookie_name']
    config['allowed_max_hit_in_project'] = cfg['allowed_max_hit_in_project']
    config['training_trap_urls'] = trap_url
    config['training_trap_ans'] = trap_ans

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = float(cfg['quality_bonus']) + float(cfg['quantity_bonus'])
    config['sum_quantity'] = float(cfg['quantity_bonus']) + float(cfg['hit_base_payment'])
    config['sum_quality'] = config['quality_bonus'] + float(cfg['hit_base_payment'])

    df_train = pd.read_csv(training_path)
    train = []
    for index, row in df_train.iterrows():
        train.append(row['training_clips'])
    train.append(trap_url)
    config['training_urls'] = train

    # rating urls
    rating_urls = []
    n_clips = int(cfg_g['number_of_clips_per_session'])
    n_traps = int(cfg_g['number_of_trapping_per_session'])
    n_gold_clips = int(cfg_g['number_of_gold_clips_per_session'])

    for i in range(0, n_clips ):
        rating_urls.append('${Q'+str(i)+'}')
    if n_traps > 1:
        raise Exception("more than 1 trapping question is not supported.")
    if n_traps == 1:
        rating_urls.append('${TP}')

    if  n_gold_clips > 1:
        raise Exception("more than 1 gold question is not supported.")
    if n_gold_clips == 1:
        rating_urls.append('${gold_clips}')

    config['rating_urls'] = rating_urls

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(html)
    print(f"  [{out_path}] is created")

def create_ccr_html(cfg, template_path, out_path, training_path, cfg_g):
    """
    Create the CCR.html file corresponding to this project
    :param cfg:
    :param template_path:
    :param out_path:
    :param training_path:
    :param cfg_g:
    :return:
    """
    print("Start creating custom ccr.html")
    config = {}
    config['cookie_name'] = cfg['cookie_name']
    config['qual_cookie_name'] = cfg['qual_cookie_name']
    config['allowed_max_hit_in_project'] = cfg['allowed_max_hit_in_project']
    config['training_trap_urls'] = trap_url
    config['training_trap_ans'] = trap_ans

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = float(cfg['quality_bonus']) + float(cfg['quantity_bonus'])
    config['sum_quantity'] = float(cfg['quantity_bonus']) + float(cfg['hit_base_payment'])
    config['sum_quality'] = config['quality_bonus'] + float(cfg['hit_base_payment'])

    df_train = pd.read_csv(training_path)
    train = []
    for index, row in df_train.iterrows():
        train.append(row['training_clips'])
    train.append(trap_url)
    config['training_urls'] = train

    # rating urls
    rating_urls = []
    for i in range(0, cfg_g['number_of_clips_per_session']):
        rating_urls.append('${Q'+i+'}')
    if cfg_g['number_of_trapping_per_session'] > 1:
        raise Exception("more than 1 trapping question is not supported.")
    if cfg_g['number_of_trapping_per_session'] == 1:
        rating_urls.append('${TP}')

    if cfg_g['number_of_gold_clips_per_session'] > 1:
        raise Exception("more than 1 gold question is not supported.")
    if cfg_g['number_of_gold_clips_per_session'] == 1:
        rating_urls.append('${gold_clips}')

    config['rating_urls'] = rating_urls

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(html)
    print(f"  [{out_path}] is created")


def prepare_csv_for_create_input_acr(clips, gold, trapping, general):
    """
    Merge different input files into one dataframe
    :param clips:
    :param trainings:
    :param gold:
    :param trapping:
    :param general:
    :return:
    """
    df_clips = pd.read_csv(clips)
    df_gold = pd.read_csv(gold)
    df_trap = pd.read_csv(trapping)
    df_general = pd.read_csv(general)

    result = pd.concat([df_clips, df_gold, df_trap, df_general], axis=1, sort=False)

    return result


if __name__ == '__main__':
    print("Welcome to the Master script for ACR test.")
    parser = argparse.ArgumentParser(description='Master script to prepare the ACR test')
    parser.add_argument("--project", help="Name of the project", required=True)
    parser.add_argument("--cfg", help="Configuration file, see master.cfg", required=True)
    parser.add_argument("--method", required=True,
                        help="one of the test methods: 'acr', 'dcr', or 'ccr'")
    parser.add_argument("--clips", help="A csv containing urls of all clips to be rated in column 'rating_clips', in "
                                        "case of ccr/dcr it should also contain a column for 'references'",
                        required=True)
    parser.add_argument("--gold_clips", help="A csv containing urls of all gold clips in column 'gold_clips' and their "
                                             "answer in column 'gold_clips_ans'")
    parser.add_argument("--training_clips", help="A csv containing urls of all training clips to be rated in training "
                                                 "section. Column 'training_clips'", required=True)
    parser.add_argument("--trapping_clips", help="A csv containing urls of all trapping clips. Columns 'trapping_clips'"
                                                 "and 'trapping_ans'", required=True)
    args = parser.parse_args()
    methods = ['acr', 'dcr', 'ccr']
    test_method = args.method.lower()
    assert test_method in methods, f"No such a method supported, please select between 'acr', 'dcr', 'ccr'"
    assert os.path.exists(args.cfg), f"No config file in {args.cfg}"
    assert os.path.exists(args.clips), f"No csv file containing clips in {args.clips}"
    if test_method == "acr":
        assert os.path.exists(args.gold_clips), f"No csv file containing gold clips in {args.gold_clips}"
    assert os.path.exists(args.training_clips), f"No csv file containing training clips in {args.training_clips}"
    assert os.path.exists(args.trapping_clips), f"No csv file containing trapping clips in {args.trapping_clips}"

    general_path = os.path.join(os.path.dirname(__file__),'assets_master_script/general.csv')
    # for acr
    acr_template_path = os.path.join(os.path.dirname(__file__),'assets_master_script/ACR_template.html')
    acr_cfg_template_path = os.path.join(os.path.dirname(__file__),'assets_master_script/acr_result_parser_template.cfg')
    # for dcr
    # for ccr

    assert os.path.exists(general_path), f"No csv file containing general infos in {general_path}"
    assert os.path.exists(acr_template_path), f"No html template file found  in {acr_template_path}"
    assert os.path.exists(acr_cfg_template_path), f"No cfg template  found  in {acr_cfg_template_path}"

    # temporrary
    if test_method != "acr":
        print('dcr and ccr are not supported by master script yet.')
        exit()

    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(args.cfg)

    # create output folder
    output_dir = args.project
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    # prepare format
    df = prepare_csv_for_create_input_acr(args.clips, args.gold_clips, args.trapping_clips, general_path)

    # create inputs
    print('Start validating inputs')
    ca.validate_inputs(cfg['create_input'], df,test_method)
    print('... validation is finished.')

    output_csv_file = os.path.join(output_dir, args.project+'_publish_batch.csv')
    ca.create_input_for_mturk(cfg['create_input'], df, test_method, output_csv_file)

    # create acr.html
    output_html_file = os.path.join(output_dir, args.project + '_ACR.html')
    create_acr_html(cfg['acr_html'], acr_template_path, output_html_file, args.training_clips, args.trapping_clips,
                    cfg['create_input'])

    # create a config file for analyzer

    output_cfg_file = os.path.join(output_dir, args.project + '_acr_result_parser.cfg')
    create_analyzer_cfg(cfg, acr_cfg_template_path, output_cfg_file)
