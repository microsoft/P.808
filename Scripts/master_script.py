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
import librosa as lr
import numpy as np
import soundfile as sf
import csv
import pandas as pd

import create_input_acr as cacr

def prepare_csv_for_create_input_acr (clips,trainings,gold,trapping,general):
    df_clips = pd.read_csv(clips)
    df_train = pd.read_csv(trainings)
    df_gold = pd.read_csv(gold)
    df_trap = pd.read_csv(trapping)
    df_general = pd.read_csv(general)

    result = pd.concat([df_clips, df_train, df_gold, df_trap, df_general], axis=1, sort=False)
    print(result.head())
    result.to_csv("out.csv", index=False)
if __name__ == '__main__':
    print("Welcome to the Master script for ACR test.")
    parser = argparse.ArgumentParser(description='Master script to prepare the ACR test')
    parser.add_argument("--cfg", help="Configuration file, see master.cfg", required=True)
    parser.add_argument("--clips", help="A csv containing urls of all clips to be rated in column 'rating_clips'",
                        required=True)
    parser.add_argument("--gold_clips", help="A csv containing urls of all gold clips in column 'gold_clips' and their "
                                             "answer in column 'gold_clips_ans'", required=True)
    parser.add_argument("--training_clips", help="A csv containing urls of all training clips to be rated in training "
                                                 "section. Column 'training_clips'", required=True)
    parser.add_argument("--trapping_clips", help="A csv containing urls of all trapping clips. Columns 'trapping_clips'"
                                                 "and 'trapping_ans'", required=True)
    args = parser.parse_args()

    assert os.path.exists(args.cfg), f"No config file in {args.cfg}"
    assert os.path.exists(args.clips), f"No csv file containing clips in {args.clips}"
    assert os.path.exists(args.gold_clips), f"No csv file containing gold clips in {args.gold_clips}"
    assert os.path.exists(args.training_clips), f"No csv file containing training clips in {args.training_clips}"
    assert os.path.exists(args.trapping_clips), f"No csv file containing trapping clips in {args.trapping_clips}"
    general = 'cfgs_and_inputs/master_script_inputs/general.csv'
    assert os.path.exists(general), f"No csv file containing general infos in {general}"

    prepare_csv_for_create_input_acr(args.clips, args.training_clips, args.gold_clips, args.trapping_clips, general)


