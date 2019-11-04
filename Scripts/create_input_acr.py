"""
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

import librosa as lr
import numpy as np
import soundfile as sf
import csv


"""
validate the structure, and fields in row_input.csv and configuration file
"""
def validate_inputs(cfg,row_input_path):

    columns = list(pd.read_csv(row_input_path, nrows=1).columns)

    # check mandatory columns
    required_columns=['rating_clips', 'math', 'pair_a', 'pair_b', 'trapping_clips', 'trapping_ans']
    for column in required_columns:
        assert column in columns, f"No column found with '{column}' in [{row_input_path}]"

    # check optionals
    ## gold_clips
    if 'number_of_gold_clips_per_session' in cfg['general'] and int(cfg['general']['number_of_gold_clips_per_session'])>0:
        assert 'gold_clips' in columns, f"No column found with 'gold_clips' in [{row_input_path}]"

    ## training_clips
   # if 'include_training' in cfg['training'] and cfg['training'].getboolean('include_training'):
   #     assert 'training_clips' in columns, f"No column found with 'training_clips' in [{row_input_path}]"


def create_input_for_mturk(cfg,row_input_path, output_path):
    df = pd.read_csv(row_input_path)

    clips = df['rating_clips'].dropna()
    n_clips = clips.count()
    n_sessions = math.ceil(n_clips / int(cfg['general']['number_of_clips_per_session']))

    print (f'{n_clips} clips and {n_sessions} sessions')

    # create math
    math_source = df['math'].dropna()
    math_output= np.tile(math_source.to_numpy(),(n_sessions //math_source.count())+1)[:n_sessions]

    #CMPs: 4 pairs are needed for 1 session
    nPairs= 4 *n_sessions
    pair_a = df['pair_a'].dropna()
    pair_b= df['pair_b'].dropna()
    pair_a_extended= np.tile(pair_a.to_numpy(),(nPairs //pair_a.count())+1)[:nPairs]
    pair_b_extended = np.tile(pair_b.to_numpy(), (nPairs // pair_b.count()) + 1)[:nPairs]

    tmpa= np.copy(pair_a_extended)
    tmpb = np.copy(pair_b_extended)

    # randomly select paies and swap a and b
    swap_me=np.random.randint(2, size=nPairs)
    tmp= np.copy(pair_a_extended)
    pair_a_extended[swap_me==1] = pair_b_extended[swap_me==1]
    pair_b_extended[swap_me == 1] = tmp[swap_me==1]

    full_array= np.transpose(np.array([pair_a_extended,pair_b_extended]))
    print(full_array)
    new_4= np.reshape(full_array, (n_sessions,8))
    print (new_4)
    for i in range(n_sessions):
        new_4[i] = np.roll(new_4[i], random.randint(1, 3)*2)


    output_df = pd.DataFrame({'CMP1_A': new_4[:,0], 'CMP1_B': new_4[:,1],
                              'CMP2_A': new_4[:, 2], 'CMP2_B': new_4[:, 3],
                              'CMP3_A': new_4[:, 4], 'CMP3_B': new_4[:, 5],
                              'CMP4_A': new_4[:, 6], 'CMP4_B': new_4[:, 7]})


    #------ add math
    output_df['math']= math_output
    # rating_clips
    ## repeat some clips to have a full design
    n_questions = int(cfg['general']['number_of_clips_per_session'])
    needed_clips= n_sessions* n_questions
    all_clips = np.tile(clips.to_numpy(),(needed_clips //n_clips)+1)[:needed_clips]
    ## check the method: clips_selection_strategy
    random.shuffle(all_clips)

    clips_sessions = np.reshape(all_clips, (n_sessions, n_questions))

    for q in range(n_questions):
        output_df[f'Q{q}']= clips_sessions[:, q]

    # trappings
    if (int(cfg['general']['number_of_trapping_per_session']) >0 ):
        if int(cfg['general']['number_of_trapping_per_session']) >1:
            print ("more than one TP is not supported for now - continue with 1")
        #n_trappings = int(cfg['general']['number_of_trapping_per_session']) * n_sessions
        n_trappings = n_sessions
        trap_source = df['trapping_clips'].dropna()
        trap_ans_source = df['trapping_ans'].dropna()

        full_trappings= np.tile(trap_source.to_numpy(),(n_trappings //trap_source.count())+1)[:n_trappings]
        full_trappings_answer = np.tile(trap_ans_source.to_numpy(), (n_trappings // trap_ans_source.count()) + 1)[:n_trappings]

        full_tp = list(zip(full_trappings, full_trappings_answer))
        random.shuffle(full_tp)

        full_trappings, full_trappings_answer= zip(*full_tp)
        output_df['TP'] = full_trappings
        output_df['TP_ANS'] = full_trappings_answer

    if (int(cfg['general']['number_of_gold_clips_per_session']) >0 ):
        if int(cfg['general']['number_of_gold_clips_per_session']) >1:
            print ("more than one gold_clip is not supported for now - continue with 1")
        n_gold_clips = n_sessions
        gold_clip_source = df['gold_clips'].dropna()

        full_gold_clips = np.tile(gold_clip_source.to_numpy(), (n_gold_clips // gold_clip_source.count()) + 1)[:n_gold_clips]
        random.shuffle(full_gold_clips)
        output_df['gold_clips'] = full_gold_clips


    output_df.to_csv(output_path, index=False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create input.csv for ACR test. ')
    # Configuration: read it from trapping.cfg
    parser.add_argument("--row_input",
                        help="All urls: rating_clips, TP, TP_ANs, math, Pair_a, Pair_b")
    parser.add_argument("--cfg", default="create_input.cfg",
                        help="explains the test")
    args = parser.parse_args()

    row_input = join(dirname(__file__), args.row_input)
    assert os.path.exists(row_input), f"No file in {row_input}]"

    cfg_path = join(dirname(__file__), args.cfg)
    assert os.path.exists(cfg_path), f"No file in {cfg_path}]"


    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(cfg_path)

    print('Start validating inputs')
    validate_inputs(cfg, row_input)
    print('... validation is finished.')

    output_file = os.path.splitext(row_input)[0]+'_publish_batch.csv'
    create_input_for_mturk(cfg, row_input, output_file)


