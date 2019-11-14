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
import numpy as np

config= {
    'math': {
     'math1.wav': 3,
     'math2.wav': 7,
     'math3.wav': 6,
    },
    'question_names': [ 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7', 'q8', 'q9', 'q10', 'q11', 'q12'],
    'expected_votes_per_file': 10,
    'trapping': {
        'url_found_in': 'input.tp',
        'ans_found_in': 'input.tp_ans',
    },
    'gold_question': {
        'url_found_in': 'input.gold_clips',
        #'ans_found_in': 'input.gold_clips_ans',
        'correct_ans': 5,
        'variance': 1
    },

    'acceptance_criteria': {
        'all_audio_played_equal': 1,
        'correct_math_bigger_equal': 1,
        'correct_tps_bigger_equal': 1,
        'variance_bigger_equal': 0.1,
        #'correct_gold_q_bigger_equal': 1
    }, 'accept_and_use': {
        # including acceptance_criteria
        'gold_standard_bigger_equal': 1,
        'correct_cmp_bigger_equal': 2,
    },
    'bonus':{
        'when_HITs_more_than': 30,
        'extra_pay_per_HIT': 0.25
    }


}


def outliers_modified_z_score(votes):
    """
    return  outliers, cleans
    :param votes:
    :return:
    """
    threshold = 3.5

    median_v = np.median(votes)
    median_absolute_deviation_v = np.median([np.abs(v - median_v) for v in votes])
    modified_z_scores = [0.6745 * (v - median_v) / median_absolute_deviation_v
                         for v in votes]
    print(modified_z_scores)
    return np.where(np.abs(modified_z_scores) > threshold), np.where(np.abs(modified_z_scores) <= threshold)


def check_if_session_accepted(data):

    if data['all_audio_played'] == config['acceptance_criteria']['all_audio_played_equal'] and \
        (data['correct_math'] is None or data['correct_math'] >= config['acceptance_criteria']['correct_math_bigger_equal']) and \
        data['correct_tps'] >= config['acceptance_criteria']['correct_tps_bigger_equal'] and \
        data['variance_in_ratings'] >= config['acceptance_criteria']['variance_bigger_equal']:
        return True
    return False


def check_if_session_should_be_used(data):
    if data['accept'] == 1 and \
            data['correct_gold_question']>= config['accept_and_use']['gold_standard_bigger_equal'] and \
            (data['correct_cmps'] is None or \
             data['correct_cmps'] >= config['accept_and_use']['correct_cmp_bigger_equal']):
        return True
    return False


def check_audio_played(row):
    question_played=0
    try:
        for q_name in config['question_names']:
            if int(row[f'answer.audio_n_finish_{q_name}']) > 0:
                question_played += 1
    except:
        return False
    return question_played == len(config['question_names'])


def check_tps(row):
    correct_tps = 0

    tp_url = row[config['trapping']['url_found_in']]
    tp_correct_ans = int(float(row[config['trapping']['ans_found_in']]))
    try:
        for q_name in config['question_names']:
            if tp_url in row[f'answer.{q_name}_url']:
                # found a trapping question
                if int(row[f'answer.{q_name}']) == tp_correct_ans:
                    correct_tps = 1
                    return correct_tps
    except:
        pass
    return correct_tps


def check_variance(row):
    r=[]
    for q_name in config['question_names']:
        if row[config['gold_question']['url_found_in']] in row[f'answer.{q_name}_url']:
            continue
        if row[config['trapping']['url_found_in']] in row[f'answer.{q_name}_url']:
            continue
        r.append(int(row[f'answer.{q_name}']))
    return statistics.variance(r)


def check_gold_question(row):
    correct_gq = 0
    try:
        gq_url = row[config['gold_question']['url_found_in']]
        #gq_correct_ans = int(float(row[config['gold_question']['ans_found_in']]))
        gq_correct_ans = config['gold_question']['correct_ans']
        gq_var= config['gold_question']['variance']
        for q_name in config['question_names']:
            if gq_url in row[f'answer.{q_name}_url']:
                # found a gold standard question
                if int(row[f'answer.{q_name}']) in range(gq_correct_ans-gq_var, gq_correct_ans+gq_var+1):
                    correct_gq = 1
                    return correct_gq
    except:
        return None
    return  correct_gq


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
    print('Start by Data Cleaning...')
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
        accept_and_use_sessions =[]
        for row in reader:
            correct_cmp_ans = 0
            setup_was_hidden = row['answer.cmp1'] is None or len(row['answer.cmp1'].strip()) == 0
            d = {}

            d['worker_id'] = row['workerid']
            d['assignment'] = row['assignmentid']
            # step1. check if audio of all X questions are played at least once
            d['all_audio_played'] = 1 if check_audio_played(row) else 0

            # check if setup was shown
            if setup_was_hidden:
                # the setup is not shown
                d['correct_cmps'] = None
                d['correct_math'] = None
            else:
                # step2. check math
                d['correct_math'] = 1 if check_math(row['input.math'], row['answer.math'],
                                                    row['answer.audio_n_play_math1']) else 0
                # step3. check pair comparision
                for i in range(1,5):
                    if check_a_cmp(row[f'input.cmp{i}_a'],row[f'input.cmp{i}_b'],
                            row[f'answer.cmp{i}'],
                            row[f'answer.audio_n_play_cmp{i}_a'],
                            row[f'answer.audio_n_play_cmp{i}_b']):
                        correct_cmp_ans += 1
                d['correct_cmps'] = correct_cmp_ans
            # step 4. check tps
            d['correct_tps'] = check_tps(row)
            # step5. check gold_standard
            d['correct_gold_question'] = check_gold_question(row)
            # step6. check variance in a session rating
            d['variance_in_ratings'] = check_variance(row)
            if check_if_session_accepted(d):
                d['accept'] = 1
            else:
                d['accept'] = 0

            if check_if_session_should_be_used(d):
                d['accept_and_use'] = 1
                accept_and_use_sessions.append(row)
            else:
                d['accept_and_use'] = 0

            worker_list.append(d)
        report_file = os.path.splitext(filename)[0] + '_data_cleaning_report.csv'
        bonus_file = os.path.splitext(filename)[0] + '_bonus_report.csv'
        write_dict_as_csv(worker_list, report_file)
        print(f"   Data cleaning report is saved in: {report_file}")
        calc_bonuses(worker_list, bonus_file)
        return accept_and_use_sessions


def calc_bonuses(worker_list,path):
    print('Calculate the bonuses...')
    df = pd.DataFrame(worker_list)
    grouped = df.groupby(['worker_id'], as_index=False)['accept'].sum()

    # condition  more than 30 hits
    grouped = grouped[grouped.accept >= config['bonus']['when_HITs_more_than']]
    grouped['bonusAmount']= grouped['accept']*config['bonus']['extra_pay_per_HIT']

    # now find an assignment id
    df.drop_duplicates('worker_id',keep ='first', inplace = True )
    w_ids = list(dict(grouped['worker_id']).values())
    df = df[df.isin(w_ids).worker_id]
    small_df = df[['worker_id', 'assignment']].copy()

    merged= pd.merge( grouped, small_df, how='inner', left_on='worker_id', right_on='worker_id')
    merged.rename(columns={'worker_id': 'workerId',
                     'assignment': 'assignmentId'},
            inplace=True)

    merged['reason']= f'Well done! More than {config["bonus"]["when_HITs_more_than"]} high quality submission'
    merged.to_csv(path)
    print(f'   Bonuses report is saved in: {path}')

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


def transform(sessions, path):
    """
    Given the valid sessions from answer.csv, group votes per files, and per conditions.
    Assumption: file name starts with Cxx where xx is condition number.
    :param sessions:
    :return:
    """

    print ("Transforming data (the ones with 'accepted_and_use' ==1 --> group per clip")
    data_per_file = {}
    data_per_condition = {}
    for session in sessions:
        for question in config['question_names']:
            # is it a trapping question
            if session[config['trapping']['url_found_in']] == session[f'answer.{question}_url']:
                continue
            # is it a gold clips
            if session[config['gold_question']['url_found_in']] == session[f'answer.{question}_url']:
                continue
            file_name = session[f'answer.{question}_url'].rsplit('/', 1)[-1]
            if file_name not in data_per_file:
                data_per_file[file_name] = []
            votes = data_per_file[file_name]
            try:
                votes.append(int(session[f'answer.{question}']))
            except:
                pass
    #print(data_per_file)

    # convert the format: one row per file
    group_per_file = []
    for key in data_per_file.keys():
        tmp = initiate_file_row({})
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
            tmp[f'vote_{vote_counter}'] = vote
            vote_counter += 1
        count = vote_counter

       # while config['expected_votes_per_file']-vote_counter >= 0:
       #     tmp[f'vote_{vote_counter}'] = None
       #     vote_counter += 1
        tmp['n'] = count-1
        tmp['mean'] = statistics.mean(votes)
        if tmp['n'] > 1:
            tmp['std'] = statistics.stdev(votes)
            tmp['95%CI'] = (1.96 * tmp['std']) / math.sqrt(tmp['n'])
        else:
            tmp['std'] = None
            tmp['95%CI'] = None
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
    write_dict_as_csv(group_per_file, path)
    print(f'   Votes per files are saved in: {path}')
    return group_per_file


def initiate_file_row(d):
    d['file_name'] = None
    d['n'] = None
    d['mean'] = None
    d['std'] = None
    d['95%CI'] = None
    for i in range(1, config['expected_votes_per_file']+1):
        d[f'vote_{i}'] = None
    return d


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
        votes_per_file_path = os.path.splitext(args.answers)[0] + '_votes_per_clip.csv'
        votes_per_file= transform(accepted_sessions, votes_per_file_path)


        """
        write_dict_as_csv(votes_per_condition, 'votes_per_condition.csv')
    
        votes_per_condition_psamd1 = data_import('psamd1.csv')
        write_dict_as_csv(votes_per_condition_psamd1, 'votes_per_condition_psamd1.csv')
        """
