"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

import csv
import statistics
import math
import pandas as pd
import argparse
import os

config= {
    'math': {
     'math1.wav': 3,
     'math2.wav': 7,
     'math3.wav': 6,
    },
    'question_names': [ 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7', 'q8', 'q9', 'q10', 'q11', 'q12'],
    'acceptance_criteria': {
        'all_audio_played_equal': 1,
        'correct_math_bigger_equal': 1,
        'correct_cmp_bigger_equal': 2,
        'correct_tps_bigger_equal': 1
    }

}


def check_if_session_accepted(data):

    if data['all_audio_played'] == config['acceptance_criteria']['all_audio_played_equal'] and \
        data['correct_math'] >= config['acceptance_criteria']['correct_math_bigger_equal'] and \
        (data['correct_cmps'] is None or  data['correct_cmps']>= config['acceptance_criteria']['correct_cmp_bigger_equal'] )and \
        data['correct_tps'] >= config['acceptance_criteria']['correct_tps_bigger_equal']:
        return True
    return False

def check_audio_played(row):
    question_played=0
    try:
        for q_name in config['question_names']:
            if int(row[f'answer.{q_name}']) > 0:
                question_played += 1
        print (question_played)
    except:
        return False
    return question_played == len(config['question_names'])


def check_tps(row):
    if int(row[f'answer.tp_check']) == 0:
        return 1
    return 0

def check_tps_old(row):
    found_tps=0
    correct_tps = 0
    tp_urls_contain = list (config['trappings']['correct_answers'])

    try:
        for q_name in config['question_names']:
            if config['trappings']['tp_url_contains'] in row[f'input.{q_name}']:
                # found a trapping question
                found_tps += 1
                for tp_name in  tp_urls_contain:
                    if tp_name in row[f'input.{q_name}']:
                        # found which to is used
                        if int(row[f'answer.{q_name}']) == config['trappings']['correct_answers'][tp_name]:
                            correct_tps += 1
                        break
    except:
        pass
    return found_tps, correct_tps


def check_math(input,output,audio_played):
    if (audio_played==0):
        return False
    keys= list(config['math'].keys())
    try:
        for key in keys:
            if key in input and config['math'][key]==int(output):
                return True
    except:
        return False
    return False
def check_a_cmp(file_a, file_b,ans, audio_a_played, audio_b_played):
    if (audio_a_played==0 or
            audio_b_played == 0):
        return False
    # https://s3-us-west-1.amazonaws.com/itutest.qu.tuberlin.de/snr_2019/34S_P501_C_english_f2_FB_48k_2.wav	https://s3-us-west-1.amazonaws.com/itutest.qu.tuberlin.de/snr_2019/40S_P501_C_english_f2_FB_48k_2.wav
    a = int((file_a.rsplit('/', 1)[-1])[:2])
    b = int((file_b.rsplit('/', 1)[-1])[:2])
    # one is 50 and one is 42, the one with bigger number (higher SNR) has to have a better quality
    answer_is_correct = False
    if a > b and ans.strip() == 'a':
        answer_is_correct = True
    elif b > a and ans.strip() == 'b':
        answer_is_correct = True
    elif a == b and ans.strip() == 'o':
        answer_is_correct = True
   # print (f'({a},{b},{ans})--> {answer_is_correct} ')
    return answer_is_correct

def data_cleaning(filename):
    with open(filename) as csvfile:

        reader = csv.DictReader(csvfile)
        #lowercase the fieldnames
        reader.fieldnames = [field.strip().lower() for field in reader.fieldnames]
        #----------- cmps
        #Input.CMP1_A	Input.CMP1_B	Input.CMP2_A	Input.CMP2_B	Input.CMP3_A	Input.CMP3_B	Input.CMP4_A	Input.CMP4_B
        # Answer.cmp1	Answer.cmp2	Answer.cmp3	Answer.cmp4
        #Answer.audio_n_play_CMP1_A	Answer.audio_n_play_CMP1_B	Answer.audio_n_play_CMP2_A	Answer.audio_n_play_CMP2_B	Answer.audio_n_play_CMP3_A	Answer.audio_n_play_CMP3_B	Answer.audio_n_play_CMP4_A	Answer.audio_n_play_CMP4_B
        # WorkerId
        #---------------- math
        # Input.math, Answer.Math,Answer.audio_n_play_math1
        worker_list=[]
        accepted_sessions =[]
        for row in reader:
            correct_cmp_ans = 0
            d = {}
            # step1. check cmp
            if row[f'input.cmp1_a'] is None:
                # the setup is not shown
                d['correct_cmps']= None
            else:
                for i in range(1,5):
                    if check_a_cmp(row[f'input.cmp{i}_a'],row[f'input.cmp{i}_b'],
                            row[f'answer.cmp{i}'],
                            row[f'answer.audio_n_play_cmp{i}_a'],
                            row[f'answer.audio_n_play_cmp{i}_b']):
                        correct_cmp_ans += 1
                d['correct_cmps'] = correct_cmp_ans

            d['worker_id'] = row['workerid']
            d['assignment'] = row['assignmentid']

            # step2. check math
            d['correct_math']= 1 if check_math(row['input.math'], row['answer.math'], row['answer.audio_n_play_math1']) else 0
            # step3. check if audio of all X questions are played at least once
            d['all_audio_played'] = 1 if check_audio_played (row) else 0
            # step 4. check tps
           # found_tps, correct_tps = check_tps(row)
           # d['found_tps'] = found_tps
           # d['correct_tps'] = correct_tps
            d['correct_tps'] = check_tps(row)
            if check_if_session_accepted(d):
                accepted_sessions.append(row)
                d['accepted'] = 1
            else:
                d['accepted'] = 0
            worker_list.append(d)
        report_file = os.path.splitext(filename)[0] + '_data_cleaning_report.csv'
        write_dict_as_csv(worker_list,report_file)
        #calc_bonuses(worker_list)
        return accepted_sessions


def calc_bonuses(worker_list):
    print ('---')
    df = pd.DataFrame(worker_list)
    grouped= df.groupby(['worker_id'], as_index=False)['accepted'].sum()
    # condition  more than 30 hits, I would be generus giv eones with more than >28
    grouped =grouped[grouped.accepted>=28]
    print(grouped)
    # now find an assignment id
    df.drop_duplicates('worker_id',keep ='first', inplace = True )
    print(df)
    df.to_excel("tmp.xlsx")
    df.drop(df.columns.difference(['worker_id','assignment']), 1, inplace=True)
    print(df.head())

    #print(pd.concat([grouped,df],  axis=1, join='inner',ignore_index=False))
   # df.join(grouped.set_index('worker_id'), on='worker_id')
    df.set_index('worker_id').join(grouped.set_index('worker_id'))

    #full_df= grouped.join(df,on='worker_id')
    #print(full_df)
    grouped.to_excel("bonus_count2.xlsx")


def write_dict_as_csv(dic_to_write, file_name):
    with open(file_name, 'w', newline='') as output_file:
        if len(dic_to_write) > 0:
            fieldnames = list(dic_to_write[0].keys())
        else:
            fieldnames = []
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for d in dic_to_write:
            writer.writerow(d)

'''
Given the valid sessions from answer.csv, group votes per files, and per conditions. 
Assumption: file name starts with Cxx where xx is condition number.
'''


def transform(sessions):
    data_per_file = {}
    data_per_condition = {}
    for session in sessions:
        for question in config['question_names']:
            # is it a trapping question
            if session['input.tp'] == session[f'answer.{question}_url']:
                continue
            file_name = session[f'answer.{question}_url'].rsplit('/', 1)[-1]
            if file_name not in data_per_file:
                data_per_file[file_name] = []
            votes = data_per_file[file_name]
            try:
                votes.append(int(session[f'answer.{question}']))
            except:
                votes.append(-1)
    print(data_per_file)

    # convert the format: one row per file
    group_per_file = []
    for key in data_per_file.keys():
        tmp={}
        tmp['file_name'] = key
        votes = data_per_file[key]
        vote_counter = 1
        """
        # extra step:: add votes to the per-condition dict
        condition = key[0:3]
        if condition not in data_per_condition:
            data_per_condition[condition]=[]
        data_per_condition[condition].extend(votes)
        """
        for vote in votes:
            tmp[f'vote{vote_counter}'] = vote
            vote_counter += 1
        count = vote_counter

        while 12-vote_counter >= 0:
            tmp[f'vote{vote_counter}'] = None
            vote_counter += 1
        tmp['n'] = count
        tmp['mean'] = statistics.mean(votes)
        tmp['std'] = statistics.stdev(votes)
        tmp['95%CI'] = (1.96 * tmp['std']) / math.sqrt(tmp['n'])
        group_per_file.append(tmp)
    """
    # how to do that, the condition name is unknown!?
    # convert the format: one row per condition
    group_per_condition = []
    for key in data_per_condition.keys():
        tmp = {}
        tmp['condition_name'] = key
        votes = data_per_condition[key]

        tmp['n'] = len(votes)
        tmp['mean'] = statistics.mean(votes)
        tmp['std'] = statistics.stdev(votes)
        tmp['95%CI'] = (1.96 * tmp['std']) / math.sqrt(tmp['n'])
        group_per_condition.append(tmp)

    return group_per_file, group_per_condition
    """
    return group_per_file

def data_import(filename):
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile)
        # lowercase the fieldnames
        reader.fieldnames = [field.strip().lower() for field in reader.fieldnames]

        data_per_condition = {}
        for row in reader:
            condition = row['filename'][0:3]
            if condition not in data_per_condition:
                data_per_condition[condition] = []
            data_per_condition[condition].append(int(row['mos']))

        print (data_per_condition)

        group_per_condition = []
        for key in data_per_condition.keys():
            tmp = {}
            tmp['condition_name'] = key
            votes = data_per_condition[key]

            tmp['n'] = len(votes)
            tmp['mean'] = statistics.mean(votes)
            tmp['std'] = statistics.stdev(votes)
            tmp['95%CI'] = (1.96 * tmp['std']) / math.sqrt(tmp['n'])
            group_per_condition.append(tmp)
        return group_per_condition


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Utility script to evaluate answers to the acr batch')
    # Configuration: read it from mturk.cfg
    parser.add_argument("--answers",
                        help="Answers csv file")

    args = parser.parse_args()

    assert (args.answers is not None), f"--answers  are required]"
    assert os.path.exists(args.answers), f"No input file found in [{args.answers}]"

    accepted_sessions = data_cleaning(args.answers)

    #votes_per_file, votes_per_condition = transform(accepted_sessions)
    if (len(accepted_sessions)> 1):
        votes_per_file= transform(accepted_sessions)

        votes_per_file_path = os.path.splitext(args.answers)[0] + '_votes_per_file.csv'
        write_dict_as_csv(votes_per_file, votes_per_file_path)
        """
        write_dict_as_csv(votes_per_condition, 'votes_per_condition.csv')
    
        votes_per_condition_psamd1 = data_import('psamd1.csv')
        write_dict_as_csv(votes_per_condition_psamd1, 'votes_per_condition_psamd1.csv')
        """