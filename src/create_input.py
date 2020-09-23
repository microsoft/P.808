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
    if method in ['acr', 'p835']:
        req = required_columns_acr
    else:
        req = required_columns_ccr

    for column in req:
        assert column in columns, f"No column found with '{column}' in input file"

    # check optionals
    #   gold_clips
    if method in ['acr', 'p835'] and 'number_of_gold_clips_per_session' in cfg and int(cfg['number_of_gold_clips_per_session'])>0:
        assert 'gold_clips' in columns, f"No column found with 'gold_clips' in input file"
        assert 'gold_clips_ans' in columns, f"No column found with 'gold_clips_ans' in input file " \
            f"(required since v.1.0)"


def create_input_for_acr(cfg, df, output_path):
    """
    create the input for the acr methods
    :param cfg:
    :param df:
    :param output_path:
    :return:
    """
    clips = df['rating_clips'].dropna()
    n_clips = clips.count()
    n_sessions = math.ceil(n_clips / int(cfg['number_of_clips_per_session']))

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

    output_df = pd.DataFrame({'CMP1_A': new_4[:, 0], 'CMP1_B': new_4[:, 1],
                              'CMP2_A': new_4[:, 2], 'CMP2_B': new_4[:, 3],
                              'CMP3_A': new_4[:, 4], 'CMP3_B': new_4[:, 5],
                              'CMP4_A': new_4[:, 6], 'CMP4_B': new_4[:, 7]})

    # add math
    output_df['math'] = math_output
    # rating_clips
    #   repeat some clips to have a full design
    n_questions = int(cfg['number_of_clips_per_session'])
    needed_clips = n_sessions * n_questions
    all_clips = np.tile(clips.to_numpy(), (needed_clips // n_clips) + 1)[:needed_clips]
    #   check the method: clips_selection_strategy
    random.shuffle(all_clips)

    clips_sessions = np.reshape(all_clips, (n_sessions, n_questions))

    for q in range(n_questions):
        output_df[f'Q{q}'] = clips_sessions[:, q]

    # trappings
    if int(cfg['number_of_trapping_per_session']) > 0:
        if int(cfg['number_of_trapping_per_session']) > 1:
            print("more than one TP is not supported for now - continue with 1")
        # n_trappings = int(cfg['general']['number_of_trapping_per_session']) * n_sessions
        n_trappings = n_sessions
        trap_source = df['trapping_clips'].dropna()
        trap_ans_source = df['trapping_ans'].dropna()

        full_trappings = np.tile(trap_source.to_numpy(), (n_trappings // trap_source.count()) + 1)[:n_trappings]
        full_trappings_answer = np.tile(trap_ans_source.to_numpy(), (n_trappings // trap_ans_source.count()) + 1)[
                                :n_trappings]

        full_tp = list(zip(full_trappings, full_trappings_answer))
        random.shuffle(full_tp)

        full_trappings, full_trappings_answer = zip(*full_tp)
        output_df['TP'] = full_trappings
        output_df['TP_ANS'] = full_trappings_answer
    # gold_clips
    if int(cfg['number_of_gold_clips_per_session']) > 0:
        if int(cfg['number_of_gold_clips_per_session']) > 1:
            print("more than one gold_clip is not supported for now - continue with 1")
        n_gold_clips = n_sessions
        gold_clip_source = df['gold_clips'].dropna()
        gold_clip_ans_source = df['gold_clips_ans'].dropna()

        full_gold_clips = np.tile(gold_clip_source.to_numpy(),
                                  (n_gold_clips // gold_clip_source.count()) + 1)[:n_gold_clips]
        full_gold_clips_answer = np.tile(gold_clip_ans_source.to_numpy(), (n_gold_clips // gold_clip_ans_source.count())
                                         + 1)[:n_gold_clips]
        full_gc = list(zip(full_gold_clips, full_gold_clips_answer))
        random.shuffle(full_gc)

        full_gold_clips, full_gold_clips_answer = zip(*full_gc)
        output_df['gold_clips'] = full_gold_clips
        output_df['gold_clips_ans'] = full_gold_clips_answer

    output_df.to_csv(output_path, index=False)


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
        raise Exception('size of "rating_clips" and "references" are not equal.')
    n_sessions = math.ceil(n_clips / int(cfg['number_of_clips_per_session']))
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

    output_df = pd.DataFrame({'CMP1_A': new_4[:, 0], 'CMP1_B': new_4[:, 1],
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


def create_input_for_mturk(cfg, df, method, output_path):
    """
    Create input.csv for MTurk
    :param cfg: configuration  file
    :param df:  row input, see validate_inputs for details
    :param output_path: path to output file
    """
    if method in ['acr', 'p835']:
        create_input_for_acr(cfg, df, output_path)
    else:
        create_input_for_dcrccr(cfg, df, output_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create input.csv for ACR, DCR, CCR, or P835 test. ')
    # Configuration: read it from trapping clips.cfg
    parser.add_argument("--row_input", required=True,
                        help="All urls depending to the test method, for ACR: 'rating_clips', 'math', 'pair_a', "
                             "'pair_b', 'trapping_clips', 'trapping_ans',  for DCR/CCR: 'rating_clips', 'references', "
                             "'math', 'pair_a', 'pair_b', 'trapping_clips'")
    parser.add_argument("--cfg", default="create_input.cfg",
                        help="explains the test")

    parser.add_argument("--method", default="acr", required=True,
                        help="one of the test methods: acr, dcr, ccr, or p835")
    args = parser.parse_args()

    #row_input = join(dirname(__file__), args.row_input)
    row_input = args.row_input
    assert os.path.exists(row_input), f"No file in {row_input}]"

    #cfg_path = join(dirname(__file__), args.cfg)
    cfg_path = args.cfg
    assert os.path.exists(cfg_path), f"No file in {cfg_path}]"

    methods = ["acr", "dcr", "ccr", "p835"]
    exp_method = args.method.lower()
    assert exp_method in methods, f"{exp_method} is not a supported method, select from: acr, dcr, ccr or p835."

    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(cfg_path)

    print('Start validating inputs')
    df = pd.read_csv(row_input)
    validate_inputs(cfg['general'], df, exp_method)
    print('... validation is finished.')

    output_file = os.path.splitext(row_input)[0]+'_'+exp_method+'_publish_batch.csv'

    create_input_for_mturk(cfg['general'], df, exp_method, output_file)


