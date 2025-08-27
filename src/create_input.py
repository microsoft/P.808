"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

import argparse
from os.path import isfile, join, basename, dirname
import os
import configparser as CP
import pandas as pd
import math
import random
import numpy as np
import re
import collections
from random import shuffle
import itertools

p835_personalized = 'pp835'
p804_conference = 'p804_conference'


def validate_inputs(cfg, df, method):
    """
    Validate the structure, and fields in row_input.csv and configuration file
    :param cfg: configuration file
    :param row_input_path: path to row_input
    """
    columns = list(df.columns)

    # check mandatory columns
    required_columns_acr = ['rating_clips', 'math', 'pair_a', 'pair_b', 'trapping_clips', 'trapping_ans']
    # tps are always the references.
    required_columns_ccr = ['rating_clips', 'references', 'math', 'pair_a', 'pair_b', 'trapping_clips']
    required_columns_gold_personalized = ['gold_url', 'gold_sig_ans', 'gold_bak_ans', 'gold_ovrl_ans']

    required_columns_gold_804 = ['gold_url', 'gold_sig_ans', 'gold_noise_ans', 'gold_ovrl_ans', 'gold_disc_ans', 'gold_col_ans', 'gold_loud_ans', 'gold_reverb_ans']


    if method in ['acr', 'p835', 'echo_impairment_test', 'p804', p804_conference]:
        req = required_columns_acr
    elif method in [p835_personalized]:
        req = required_columns_acr
        #req.extend(['rating_enrolment_clips', 'trapping_enrolment_clips'])
    else:
        req = required_columns_ccr

    for column in req:
        assert column in columns, f"No column found with '{column}' in input file"

    # check optionals
    #   gold_clips
    if method in ['acr', 'p835', 'echo_impairment_test'] and 'number_of_gold_clips_per_session' in cfg and int(cfg['number_of_gold_clips_per_session'])>0:
        assert 'gold_clips' in columns, f"No column found with 'gold_clips' in input file"
        assert 'gold_clips_ans' in columns, f"No column found with 'gold_clips_ans' in input file " \
            f"(required since v.1.0)"       
    if method in [p835_personalized]:
        #assert 'gold_enrolment_clips' in columns, f"No column found with 'gold_enrolment_clips' in input file"
        for column in required_columns_gold_personalized:
            assert column in columns, f"No column found with '{column}' in input file"
    if method in ['p804', p804_conference]:
        for column in required_columns_gold_804:
            assert column in columns, f"No column found with '{column}' in input file"



file_to_condition_map = {}

def conv_filename_to_condition(f_name, condition_pattern):
    """
    extract the condition name from filename given the mask in the config
    :param f_name:
    :return:
    """
    if f_name in file_to_condition_map:
        return file_to_condition_map[f_name]
    file_to_condition_map[f_name] = {'Unknown': 'NoCondition'}
    m = re.match(condition_pattern, f_name)
    if m:
        file_to_condition_map[f_name] = m.groupdict('')
        file_to_condition_map[f_name] = collections.OrderedDict(sorted(file_to_condition_map[f_name].items()))
    return file_to_condition_map[f_name]


def add_clips_balanced_block(clips, condition_pattern, keys, n_clips_per_session, output_df):
    block_keys = [x.strip() for x in keys.split(',')]
    if len(block_keys) > 2:
        raise SystemExit("Error: balanced_block design- only up to 2 keys in 'block_keys' are supported")
    data = pd.DataFrame(columns=block_keys.copy().insert(0,' url'))

    for clip in clips:
        condition = conv_filename_to_condition(clip, condition_pattern)
        tmp = condition.copy()
        tmp['url'] = clip
        data = data.append(tmp, ignore_index=True)
    if 'Unknown' in data:
        unknown_count = data['Unknown'].dropna().count()
        raise SystemExit(f"Error: balanced_block design- {unknown_count} clips did not match the 'condition_pattern'.")

    # check if block design is possible
    df_agg = data.groupby(block_keys).agg(count_url=('url', 'count'))

    #      are all combinations exists
    num_unique = {}
    for key in block_keys:
        num_unique[key] = len(data[key].unique())
    combination = np.prod(list(num_unique.values()))

    if len(df_agg) != combination:
        raise SystemExit("Error: balanced_block design- Not all combination between block_keys exist.")
    #      check if in each block similar number of clips appears
    files_per_block = df_agg.count_url.unique()
    if len(files_per_block) > 1:
        raise SystemExit("Error: balanced_block design- unequal number of clips per block")

    # check number of files and how to combine elements
    #      number of clips in the session should be a multiples of values of first block_key
    n_clips_in_block = num_unique[block_keys[0]]
    if n_clips_per_session % n_clips_in_block != 0:
        raise SystemExit("Error: balanced_block design- number_of_clips_per_session should be a multiples of values of "
                         f"first block_key. Found {num_unique[block_keys[0]]} unique values for '{block_keys[0]}'. "
                         f"Therefore number_of_clips_per_session should be a multiples of {num_unique[block_keys[0]]})")
    # create the blocks
    n_clips = clips.count()
    #  create block sets
    column_names = [f"url_{i}" for i in range(0, num_unique[block_keys[0]])]
    blocked_df = pd.DataFrame(columns=column_names)
    filtered_data_list = []

    if len(block_keys) > 1:
        # only 2 blocks were allowed
        key1_unique_values = list(data[block_keys[1]].unique())
        for val in key1_unique_values:
            filtered_data_list.append(data[data[block_keys[1]]==val].copy().reset_index(drop=True))
    else:
        filtered_data_list.append(data)

    key0_unique_values = list(data[block_keys[0]].unique())
    for d in filtered_data_list:
        i = 0
        u = {}
        for val in key0_unique_values:
            tmp = d[d[block_keys[0]] == val].url.tolist()
            random.shuffle(tmp)
            u[f"url_{i}"] = tmp
            i += 1
        tmp_df = pd.DataFrame.from_dict(u)
        blocked_df = blocked_df.append(tmp_df, ignore_index=True)

    # shuffel
    blocked_df = blocked_df.sample(frac=1)
    # add extra blocks to have complete sessions
    blocks_per_session = n_clips_per_session / n_clips_in_block
    if len(blocked_df) % blocks_per_session != 0:
        n_extra_blocks = int(blocks_per_session - (len(blocked_df) % blocks_per_session))
        extra_blocks = blocked_df.sample(n=n_extra_blocks)
        blocked_df = blocked_df.append(extra_blocks, ignore_index=True)

    # create the sessions
    np_blocks = blocked_df[column_names].to_numpy()
    np_blocks_reshaped = np.reshape(np_blocks, (-1, n_clips_per_session), order='c')
    q_order = random.sample(range(n_clips_per_session),n_clips_per_session)
    i = 0
    for q in range(n_clips_per_session):
        output_df[f'Q{q}'] = np_blocks_reshaped[:, q_order[i]]
        i += 1
    return output_df


def add_clips_balanced_block_ccr(clips, refs, condition_pattern, keys, n_clips_per_session, output_df):
    # create the structure only using clips
    add_clips_balanced_block(clips, condition_pattern, keys, n_clips_per_session, output_df)
    clips = clips.tolist()
    refs = refs.tolist()
    for q in range(n_clips_per_session):
        clip_list = output_df[f'Q{q}'].tolist()
        ref_list = []
        for c in clip_list:
            ref_list.append(refs[clips.index(c)])
        output_df[f'Q{q}_R'] = ref_list
        output_df.rename(columns={f'Q{q}': f'Q{q}_P'}, inplace=True)


def add_clips_random(clips, n_clips_per_session, output_df, method, column_names):
    n_clips = len(clips)
    n_sessions = math.ceil(n_clips / n_clips_per_session)
    needed_clips = n_sessions * n_clips_per_session

    all_clips = pd.DataFrame()
    for i in range(int(math.ceil(needed_clips * 1.0 / n_clips))):
        #all_clips = all_clips.append(clips)
        all_clips = pd.concat([all_clips, clips], ignore_index=True)

    all_clips = all_clips[:needed_clips]
    all_clips = all_clips.sample(frac=1).reset_index(drop=True)

    all_clips_rating = all_clips['rating_clips'].to_numpy()
    clips_rating_sessions = np.reshape(
        all_clips_rating, (n_sessions, n_clips_per_session))
    for q in range(n_clips_per_session):
        output_df[f'Q{q}'] = clips_rating_sessions[:, q]

    
    print(f'There are {len(all_clips)} clips and {n_sessions} sessions')


def add_clips_random_ccr(clips, refs, n_clips_per_session, output_df):
    n_clips = clips.count()
    n_sessions = math.ceil(n_clips / n_clips_per_session)
    needed_clips = n_sessions * n_clips_per_session

    full_clips = np.tile(clips.to_numpy(), (needed_clips // n_clips) + 1)[:needed_clips]
    full_refs = np.tile(refs.to_numpy(), (needed_clips // n_clips) + 1)[:needed_clips]

    full = list(zip(full_clips, full_refs))
    random.shuffle(full)
    full_clips, full_refs = zip(*full)

    clips_sessions = np.reshape(full_clips, (n_sessions, n_clips_per_session))
    refs_sessions = np.reshape(full_refs, (n_sessions, n_clips_per_session))

    for q in range(n_clips_per_session):
        output_df[f'Q{q}_P'] = clips_sessions[:, q]
        output_df[f'Q{q}_R'] = refs_sessions[:, q]


def create_input_for_acr(cfg, df, output_path, method):
    """
    create the input for the acr methods
    :param cfg:
    :param df:
    :param output_path:
    :return:
    """

    columns = ['rating_clips']
    #if (method == p835_personalized):
    #    columns.append('rating_enrolment_clips')

    clips = df[columns].dropna(axis=0, how='any')
    n_clips = len(clips)
    n_clips_per_session = int(cfg['number_of_clips_per_session'])
    n_sessions = int(math.ceil(n_clips / n_clips_per_session))

    output_df = pd.DataFrame()
    packing_strategy = cfg.get(
        "clip_packing_strategy", "random").strip().lower()

    if packing_strategy == "balanced_block":
        if method == p835_personalized:
            raise Exception(
                "balanced_block strategy is not supported for personalized P835")
        add_clips_balanced_block(clips,
                                 cfg["condition_pattern"],
                                 cfg.get("block_keys", cfg["condition_keys"]),
                                 n_clips_per_session,
                                 output_df)
        print(f'There are {len(clips)} clips and {n_sessions} sessions')

    elif packing_strategy == "random":
        add_clips_random(clips,
                         n_clips_per_session,
                         output_df,
                         method,
                         columns)

    # create math
    math_source = df['math'].dropna()
    math_output = np.tile(math_source.to_numpy(),
                          (n_sessions // math_source.count()) + 1)[:n_sessions]
    # add math
    output_df['math'] = math_output

    # CMPs: 4 pairs are needed for 1 session
    nPairs = 4 * n_sessions
    pair_a = df['pair_a'].dropna()
    pair_b = df['pair_b'].dropna()
    pair_a_extended = np.tile(
        pair_a.to_numpy(), (nPairs // pair_a.count()) + 1)[:nPairs]
    pair_b_extended = np.tile(
        pair_b.to_numpy(), (nPairs // pair_b.count()) + 1)[:nPairs]

    # randomly select pairs and swap a and b
    swap_me = np.random.randint(2, size=nPairs)
    tmp = np.copy(pair_a_extended)
    pair_a_extended[swap_me == 1] = pair_b_extended[swap_me == 1]
    pair_b_extended[swap_me == 1] = tmp[swap_me == 1]

    full_array = np.transpose(np.array([pair_a_extended, pair_b_extended]))
    new_4 = np.reshape(full_array, (n_sessions, 8))
    for i in range(n_sessions):
        new_4[i] = np.roll(new_4[i], random.randint(1, 3) * 2)

    output_df = output_df.assign(**{'CMP1_A': new_4[:, 0], 'CMP1_B': new_4[:, 1],
                                    'CMP2_A': new_4[:, 2], 'CMP2_B': new_4[:, 3],
                                    'CMP3_A': new_4[:, 4], 'CMP3_B': new_4[:, 5],
                                    'CMP4_A': new_4[:, 6], 'CMP4_B': new_4[:, 7]})

    # trappings
    if int(cfg['number_of_trapping_per_session']) > 0:
        if int(cfg['number_of_trapping_per_session']) > 1:
            print("more than one TP is not supported for now - continue with 1")
        # n_trappings = int(cfg['general']['number_of_trapping_per_session']) * n_sessions
        n_trappings = n_sessions
        columns = ['trapping_clips', 'trapping_ans']
        #if (method == p835_personalized):
        #    columns.append('trapping_enrolment_clips')
        tmp = df[columns].copy()
        tmp.dropna(inplace=True, how='any')
        tmp = tmp.sample(n=n_trappings, replace=True)

        trap_source = tmp['trapping_clips'].dropna()
        full_trappings = np.tile(trap_source.to_numpy(
        ), (n_trappings // trap_source.count()) + 1)[:n_trappings]

        trap_ans_source = tmp['trapping_ans'].dropna()
        full_trappings_answer = np.tile(trap_ans_source.to_numpy(), (n_trappings // trap_ans_source.count()) + 1)[:n_trappings]

        # Shuffle
       
        full_tp = list(zip(full_trappings, full_trappings_answer))
        random.shuffle(full_tp)
        full_trappings, full_trappings_answer = zip(*full_tp)

        output_df['TP'] = full_trappings
        output_df['TP_ANS'] = full_trappings_answer       

    # gold_clips

    number_of_gold_clips_per_session = int(cfg['number_of_gold_clips_per_session'])
    if number_of_gold_clips_per_session > 0:
        if number_of_gold_clips_per_session > 2:
            print("more than two gold_clip is not supported for now - continue with 1")
        n_gold_clips = n_sessions
        #TODO: tobe changed to p835_personalized
        if (method == p835_personalized):
            df = df[['gold_url', 'gold_ovrl_ans', 'gold_sig_ans', 'gold_bak_ans', 'ver']]

            for i in range(0, number_of_gold_clips_per_session):
                small_set= df[df['ver'] == (i+1)]
                small_set = small_set.dropna(subset=['gold_url'])
                # shuffle dataset
                small_set = small_set.sample(frac=1).reset_index(drop=True)                        
                # remove nan
                small_set.dropna(inplace=True, how='any')
                # size of dataset
                size = len(small_set)              

                ans_ovrl = small_set['gold_ovrl_ans'].head(size)
                ans_sig = small_set['gold_sig_ans'].head(size)
                ans_bak = small_set['gold_bak_ans'].head(size)
                gold_clip_source = small_set['gold_url'].head(size)

                full_gold_clips = np.tile(gold_clip_source.to_numpy(),
                                        (n_gold_clips // gold_clip_source.count()) + 1)[:n_gold_clips]
                full_ans_ovrl = np.tile(ans_ovrl.to_numpy(), (n_gold_clips // ans_ovrl.count())
                                                + 1)[:n_gold_clips]
                full_ans_sig = np.tile(ans_sig.to_numpy(), (n_gold_clips // ans_sig.count())
                                                + 1)[:n_gold_clips]
                full_ans_bak = np.tile(ans_bak.to_numpy(), (n_gold_clips // ans_bak.count())
                                                + 1)[:n_gold_clips]
                
                full_gc = list(zip(full_gold_clips, full_ans_ovrl, full_ans_sig, full_ans_bak))
                random.shuffle(full_gc)
                full_gold_clips, full_ans_ovrl, full_ans_sig, full_ans_bak = zip(*full_gc)


                if i == 0:
                    suffix = ''
                else:
                    suffix = f"_{i+1}"

                output_df[f'gold_url{suffix}'] = full_gold_clips
                output_df[f'gold_sig_ans{suffix}'] = full_ans_sig
                output_df[f'gold_bak_ans{suffix}'] = full_ans_bak
                output_df[f'gold_ovrl_ans{suffix}'] = full_ans_ovrl

        elif method == 'p804' or method == p804_conference:
            #tmp = df.sample(frac=1).reset_index(drop=True)   
            
            for j in range(0, number_of_gold_clips_per_session):                
                df_small = df[df['ver'] == (j+1)].copy()
                tmp = df_small[['gold_url', 'gold_ovrl_ans', 'gold_sig_ans', 'gold_noise_ans', 'gold_col_ans', 'gold_loud_ans', 'gold_disc_ans', 'gold_reverb_ans']].copy()
                tmp = tmp.dropna(subset=['gold_url'])            
                tmp = tmp.sample(frac=1, ignore_index=True)
                # get dataframe lenght
                size = len(tmp)
                g_clips = tmp.copy()
                for i in range (1, (n_gold_clips//size)+1):
                    g_clips = pd.concat([g_clips, tmp], axis=0, ignore_index=True)
                g_clips = g_clips.head(n_gold_clips)
                g_clips = g_clips.sample(frac=1, ignore_index=True)

                if j>0:
                    suffix = f"_{j+1}"
                    g_clips.rename(columns = {'gold_url':f'gold_url{suffix}'
                                              ,'gold_ovrl_ans':f'gold_ovrl_ans{suffix}'
                                                ,'gold_sig_ans':f'gold_sig_ans{suffix}'
                                                ,'gold_noise_ans':f'gold_noise_ans{suffix}'
                                                ,'gold_col_ans':f'gold_col_ans{suffix}'
                                                ,'gold_loud_ans':f'gold_loud_ans{suffix}'
                                                ,'gold_disc_ans':f'gold_disc_ans{suffix}'
                                                ,'gold_reverb_ans':f'gold_reverb_ans{suffix}'
                                              }, inplace = True)
                output_df = pd.concat([output_df, g_clips], axis=1)

        else:
            gold_clip_source = df['gold_clips'].dropna()
            full_gold_clips = np.tile(gold_clip_source.to_numpy(),
                                    (n_gold_clips // gold_clip_source.count()) + 1)[:n_gold_clips]

            gold_clip_ans_source = df['gold_clips_ans'].dropna()
            full_gold_clips_answer = np.tile(gold_clip_ans_source.to_numpy(), (n_gold_clips // gold_clip_ans_source.count())
                                            + 1)[:n_gold_clips]

            full_gc = list(zip(full_gold_clips, full_gold_clips_answer))
            random.shuffle(full_gc)
            full_gold_clips, full_gold_clips_answer = zip(*full_gc)

            output_df['gold_clips'] = full_gold_clips
            output_df['gold_clips_ans'] = full_gold_clips_answer

    output_df.to_csv(output_path, index=False)
    return len(output_df)


def create_input_for_dcrccr(cfg, df, output_path):
    """
    create the input for the dcr and ccr method
    :param cfg:
    :param df:
    :param output_path:
    :return:
    """
    clips = df['rating_clips'].dropna()
    refs = df['references'].dropna()

    n_clips = clips.count()
    if n_clips != refs.count():
        raise SystemExit('size of "rating_clips" and "references" are not equal.')
    n_clips_per_session = int(cfg['number_of_clips_per_session'])

    output_df = pd.DataFrame()
    packing_strategy = cfg.get("clip_packing_strategy", "random").strip().lower()

    if packing_strategy == "balanced_block":
        add_clips_balanced_block_ccr(clips, refs, cfg["condition_pattern"], cfg.get("block_keys", cfg["condition_keys"])
                                     , n_clips_per_session, output_df)
    elif packing_strategy == "random":
        add_clips_random_ccr(clips, refs, n_clips_per_session, output_df)

    n_sessions = math.ceil(n_clips / n_clips_per_session)
    print(f'{n_clips} clips and {n_sessions} sessions')

    # create math
    math_source = df['math'].dropna()
    math_output = np.tile(math_source.to_numpy(), (n_sessions // math_source.count()) + 1)[:n_sessions]

    # CMPs: 4 pairs are needed for 1 session
    nPairs = 4 * n_sessions
    pair_a = df['pair_a'].dropna()
    pair_b = df['pair_b'].dropna()
    pair_a_extended = np.tile(pair_a.to_numpy(), (nPairs // pair_a.count()) + 1)[:nPairs]
    pair_b_extended = np.tile(pair_b.to_numpy(), (nPairs // pair_b.count()) + 1)[:nPairs]

    # randomly select pairs and swap a and b
    swap_me = np.random.randint(2, size=nPairs)
    tmp = np.copy(pair_a_extended)
    pair_a_extended[swap_me == 1] = pair_b_extended[swap_me == 1]
    pair_b_extended[swap_me == 1] = tmp[swap_me == 1]

    full_array = np.transpose(np.array([pair_a_extended, pair_b_extended]))
    new_4 = np.reshape(full_array, (n_sessions, 8))
    for i in range(n_sessions):
        new_4[i] = np.roll(new_4[i], random.randint(1, 3) * 2)

    output_df = output_df.assign(**{'CMP1_A': new_4[:, 0], 'CMP1_B': new_4[:, 1],
                                    'CMP2_A': new_4[:, 2], 'CMP2_B': new_4[:, 3],
                                    'CMP3_A': new_4[:, 4], 'CMP3_B': new_4[:, 5],
                                    'CMP4_A': new_4[:, 6], 'CMP4_B': new_4[:, 7]})
    # add math
    output_df['math'] = math_output
    # rating_clips
    #   repeat some clips to have a full design
    n_questions = int(cfg['number_of_clips_per_session'])
    needed_clips = n_sessions * n_questions

    full_clips = np.tile(clips.to_numpy(), (needed_clips // n_clips) + 1)[:needed_clips]
    full_refs = np.tile(refs.to_numpy(), (needed_clips // n_clips) + 1)[:needed_clips]

    full = list(zip(full_clips, full_refs))
    random.shuffle(full)
    full_clips, full_refs = zip(*full)

    clips_sessions = np.reshape(full_clips, (n_sessions, n_questions))
    refs_sessions = np.reshape(full_refs, (n_sessions, n_questions))

    for q in range(n_questions):
        output_df[f'Q{q}_P'] = clips_sessions[:, q]
        output_df[f'Q{q}_R'] = refs_sessions[:, q]

    # trappings
    if int(cfg['number_of_trapping_per_session']) > 0:
        if int(cfg['number_of_trapping_per_session']) > 1:
            print("more than one TP is not supported for now - continue with 1")
        # n_trappings = int(cfg['general']['number_of_trapping_per_session']) * n_sessions
        n_trappings = n_sessions
        trap_source = df['trapping_clips'].dropna()
        full_trappings = np.tile(trap_source.to_numpy(), (n_trappings // trap_source.count()) + 1)[:n_trappings]
        random.shuffle(full_trappings)
        output_df['TP'] = full_trappings
    output_df.to_csv(output_path, index=False)
    return len(output_df)


def create_input_for_mturk(cfg, df, method, output_path):
    """
    Create input.csv for MTurk
    :param cfg: configuration  file
    :param df:  row input, see validate_inputs for details
    :param output_path: path to output file
    """
    if method in ['acr', 'p835', 'echo_impairment_test', p835_personalized, "p804", p804_conference]:
        return create_input_for_acr(cfg, df, output_path, method)
    else:
        return create_input_for_dcrccr(cfg, df, output_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=f'Create input.csv for ACR, DCR, CCR, P835, {p835_personalized},p804, {p804_conference} echo_impairment_test test. ')
    # Configuration: read it from trapping clips.cfg
    parser.add_argument("--row_input", required=True,
                        help="All urls depending to the test method, for ACR: 'rating_clips', 'math', 'pair_a', "
                             "'pair_b', 'trapping_clips', 'trapping_ans',  for DCR/CCR: 'rating_clips', 'references', "
                             "'math', 'pair_a', 'pair_b', 'trapping_clips'")
    parser.add_argument("--cfg", default="create_input.cfg",
                        help="explains the test")

    parser.add_argument("--method", default="acr", required=True,
                        help=f"one of the test methods: acr, dcr, ccr, p835, {p835_personalized},p804, {p804_conference}, echo_impairment_test")
    args = parser.parse_args()

    #row_input = join(dirname(__file__), args.row_input)
    row_input = args.row_input
    assert os.path.exists(row_input), f"No file in {row_input}]"

    #cfg_path = join(dirname(__file__), args.cfg)
    cfg_path = args.cfg
    assert os.path.exists(cfg_path), f"No file in {cfg_path}]"

    methods = ["acr", "dcr", "ccr", "p835",
               p835_personalized, "echo_impairment_test", "p804", p804_conference]
    exp_method = args.method.lower()
    assert exp_method in methods, f"{exp_method} is not a supported method, select from: acr, dcr, ccr, p835, {p835_personalized}, echo_impairment_test, p804, {p804_conference}."

    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(cfg_path)

    print('Start validating inputs')
    df = pd.read_csv(row_input)
    validate_inputs(cfg['general'], df, exp_method)
    print('... validation is finished.')

    output_file = os.path.splitext(
        row_input)[0]+'_'+exp_method+'_publish_batch.csv'

    create_input_for_mturk(cfg['general'], df, exp_method, output_file)