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
import re
import numpy as np
import sys
import re
from scipy import stats
from scipy.stats import spearmanr
import time
import itertools
import configparser as CP
import collections

max_found_per_file = -1


def outliers_modified_z_score(votes):
    """
    return  outliers, using modified z-score
    :param votes:
    :return:
    """
    threshold = 3.5

    median_v = np.median(votes)
    median_absolute_deviation_v = np.median([np.abs(v - median_v) for v in votes])

    if median_absolute_deviation_v == 0:
        median_absolute_deviation_v = sys.float_info.min

    modified_z_scores = [np.abs(0.6745 * (v - median_v) / median_absolute_deviation_v)
                         for v in votes]
    x = np.array(modified_z_scores)
    v = np.array(votes)
    v = v[(x < threshold)]
    return v


def outliers_z_score(votes):
    """
    return  outliers, using z-score
    :param votes:
    :return:
    """
    if len(votes) == 0:
        return votes

    threshold = 3.29

    z = np.abs(stats.zscore(votes))
    x = np.array(z)
    v = np.array(votes)
    v = v[x < threshold]
    return v

#p835
def check_if_session_accepted(data):
    """
    Check if the session can be acceptd given the criteria in config and the calculations
    :param data:
    :return:
    """
    msg = "Make sure you follow the instruction:"
    accept = True
    if data['all_audio_played'] != int(config['acceptance_criteria']['all_audio_played_equal']):
        accept = False
        msg += "All clips should be played until the end;"
    if data['correct_math'] is not None and data['correct_math'] < \
            int(config['acceptance_criteria']['correct_math_bigger_equal']):
        accept = False
        msg += "Gold or trapping clips question are answered wrongly;"
    if data['correct_tps'] < int(config['acceptance_criteria']['correct_tps_bigger_equal']):
        accept = False
        msg += "Gold or trapping clips question are answered wrongly;"

    if not accept:
        data['Reject'] = msg
    else:
        data['Reject'] = ""
    return accept

#p835
def check_if_session_should_be_used(data):
    if data['accept'] != 1:
        return False, []
    
    should_be_used = True
    failures = []

    if data['variance_in_ratings'] < float(config['accept_and_use']['variance_bigger_equal']):
        should_be_used = False
        failures.append('variance')
    
    if 'correct_gold_question' in data and data['correct_gold_question'] < int(config['accept_and_use']['gold_standard_bigger_equal']):
        should_be_used = False
        failures.append('gold')
    
    if data['correct_cmps'] is not None and data['correct_cmps'] < int(config['accept_and_use']['correct_cmp_bigger_equal']):
        should_be_used = False
        failures.append('comparisons')
    
    return should_be_used, failures

# p835
def check_audio_played(row, method):
    """
    check if all audios for questions played until the end
    :param row:
    :param method: acr,dcr, ot ccr
    :return:
    """
    question_played = 0
    try:
        if method == 'acr':
            for q_name in question_names:
                if int(row[f'answer.audio_n_finish_{q_name}']) > 0:
                    question_played += 1
        elif method in ['p835', 'echo_impairment_test']:
            for q_name in question_names:
                if int(row[f'answer.audio_n_finish_{q_name}{question_name_suffix}_audio']) > 0:
                    question_played += 1
        else:
            for q_name in question_names:
                if int(row[f'answer.audio_n_finish_q_a{q_name[1:]}']) > 0 and int(row[f'answer.audio_n_finish_q_b{q_name[1:]}']) > 0:
                    question_played += 1
    except:
        return False
    return question_played == len(question_names)

# p835
def check_tps(row, method):
    """
    Check if the trapping clips questions are answered correctly
    :param row:
    :param method: acr, dcr, or ccr
    :return:
    """
    correct_tps = 0
    tp_url = row[config['trapping']['url_found_in']]
    if method in ['acr', 'p835', 'echo_impairment_test']:
        tp_correct_ans = [int(float(row[config['trapping']['ans_found_in']]))]
    elif method == "dcr":
        tp_correct_ans = [4, 5]
    elif method == "ccr":
        tp_correct_ans = [-1, 0, 1]
    else:
        return -1

    try:
        suffix = ''
        if method == 'p835':
            # only look at the ovrl for tps.
            suffix = "_ovrl"
        if method == 'echo_impairment_test':
            suffix = '_echo'
        for q_name in question_names:
            if tp_url in row[f'answer.{q_name}_url']:
                # found a trapping clips question
                if int(row[f'answer.{q_name}{suffix}']) in tp_correct_ans:
                    correct_tps = 1
                    return correct_tps
    except:
        pass
    return correct_tps

#p835
def check_variance(row):
    """
    Check how is variance of ratings in the session (if the worker just clicked samething)
    :param row:
    :return:
    """
    r = []
    for q_name in question_names:
        if 'gold_question' in config and row[config['gold_question']['url_found_in']] in row[f'answer.{q_name}_url']:
            continue
        if row[config['trapping']['url_found_in']] in row[f'answer.{q_name}_url']:
            continue
        try:
            r.append(int(row[f'answer.{q_name}{question_name_suffix}']))
        except:
            pass
    try:
        v = statistics.variance(r)
        return v
    except:
        pass
    return -1

#p835
def check_gold_question(method, row):
    """
    Check if the gold_question is answered correctly
    :param row:
    :return:
    """
    correct_gq = 0
    try:
        gq_url = row[config['gold_question']['url_found_in']]
        # gq_correct_ans = int(float(row[config['gold_question']['ans_found_in']]))
        #  tp_correct_ans = int(float(row[config['trapping']['ans_found_in']]))
        gq_correct_ans= -1
        # check if it is hardcoded correct answer or dynamic one
        if config.has_option('gold_question', 'correct_ans'):
            gq_correct_ans = int(config['gold_question']['correct_ans'])
        elif config.has_option('gold_question', 'ans_found_in'):
            gq_correct_ans = int(float(row[config['gold_question']['ans_found_in']]))
        else:
            return -1
        gq_var = int(config['gold_question']['variance'])
        suffix = ''
        if method == 'p835':
            # only look at the ovrl for tps.
            suffix = "_ovrl"
        if method == 'echo_impairment_test':
            suffix = '_echo'
        for q_name in question_names:
            if gq_url in row[f'answer.{q_name}_url']:
                # found a gold standard question
                if int(row[f'answer.{q_name}{suffix}']) in range(gq_correct_ans-gq_var, gq_correct_ans+gq_var+1):
                    correct_gq = 1
                    return correct_gq
    except:
        return None
    return correct_gq


def check_math(input, output, audio_played):
    """
    check if the math question is answered correctly
    :param input:
    :param output:
    :param audio_played:
    :return:
    """
    if audio_played == 0:
        return False
    keys = list(config['math'].keys())
    try:
        for key in keys:
            if key in input and int(config['math'][key]) == int(output):
                return True
    except:
        return False
    return False


def check_a_cmp(file_a, file_b, ans, audio_a_played, audio_b_played):
    """
    check if pair comparision answered correctly
    :param file_a:
    :param file_b:
    :param ans:
    :param audio_a_played:
    :param audio_b_played:
    :return:
    """
    if (audio_a_played == 0 or
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
    return answer_is_correct

# p835
def data_cleaning(filename, method):
   """
   Data screening process
   :param filename:
   :param method: acr, dcr, or ccr
   :return:
   """
   print('Start by Data Cleaning...')
   with open(filename, encoding="utf8") as csvfile:

    reader = csv.DictReader(csvfile)
    # lowercase the fieldnames
    reader.fieldnames = [field.strip().lower() for field in reader.fieldnames]
    # ----------- pair comparision
    # Input.CMP1_A	Input.CMP1_B	Input.CMP2_A	Input.CMP2_B	Input.CMP3_A	Input.CMP3_B	Input.CMP4_A	Input.CMP4_B
    # Answer.cmp1	Answer.cmp2	Answer.cmp3	Answer.cmp4
    # Answer.audio_n_play_CMP1_A	Answer.audio_n_play_CMP1_B	Answer.audio_n_play_CMP2_A	Answer.audio_n_play_CMP2_B
    # Answer.audio_n_play_CMP3_A	Answer.audio_n_play_CMP3_B	Answer.audio_n_play_CMP4_A	Answer.audio_n_play_CMP4_B
    # WorkerId
    # ---------------- math
    # Input.math, Answer.Math,Answer.audio_n_play_math1
    worker_list = []
    use_sessions = []
    count_sig_bak = 0
    not_using_further_reasons = []
    for row in reader:
        correct_cmp_ans = 0
        setup_was_hidden = row['answer.cmp1'] is None or len(row['answer.cmp1'].strip()) == 0
        d = dict()

        d['worker_id'] = row['workerid']
        d['HITId'] = row['hitid']
        d['assignment'] = row['assignmentid']
        d['status'] = row['assignmentstatus']

        # step1. check if audio of all X questions are played at least once
        d['all_audio_played'] = 1 if check_audio_played(row, method) else 0

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
            for i in range(1, 5):
                if check_a_cmp(row[f'input.cmp{i}_a'], row[f'input.cmp{i}_b'], row[f'answer.cmp{i}'],
                               row[f'answer.audio_n_play_cmp{i}_a'],
                               row[f'answer.audio_n_play_cmp{i}_b']):
                    correct_cmp_ans += 1
            d['correct_cmps'] = correct_cmp_ans
        # step 4. check tps
        d['correct_tps'] = check_tps(row, method)
        # step5. check gold_standard, just for acr
        if method in ['acr','p835', 'echo_impairment_test']:
            d['correct_gold_question'] = check_gold_question(method, row)
        # step6. check variance in a session rating
        d['variance_in_ratings'] = check_variance(row)

        if check_if_session_accepted(d):
            d['accept'] = 1
            d['Approve'] = 'x'
        else:
            d['accept'] = 0
            d['Approve'] = ''

        should_be_used, failures = check_if_session_should_be_used(d)
        not_using_further_reasons.extend(failures)
        if should_be_used:
            d['accept_and_use'] = 1
            use_sessions.append(row)
            if method == 'p835' and row['answer.p835_order'] == 'sig_bak':
                count_sig_bak += 1
        else:
            d['accept_and_use'] = 0

        worker_list.append(d)
    report_file = os.path.splitext(filename)[0] + '_data_cleaning_report.csv'

    approved_file = os.path.splitext(filename)[0] + '_accept.csv'
    rejected_file = os.path.splitext(filename)[0] + '_rejection.csv'

    accept_reject_gui_file = os.path.splitext(filename)[0] + '_accept_reject_gui.csv'
    extending_hits_file = os.path.splitext(filename)[0] + '_extending.csv'

    # reject hits when the user performed more than the limit
    worker_list = evaluate_maximum_hits(worker_list)

    accept_and_use_sessions = [d for d in worker_list if d['accept_and_use'] == 1]

    write_dict_as_csv(worker_list, report_file)
    save_approved_ones(worker_list, approved_file)
    save_rejected_ones(worker_list, rejected_file)
    save_approve_rejected_ones_for_gui(worker_list, accept_reject_gui_file)
    save_hits_to_be_extended(worker_list, extending_hits_file)

    print(f"   {len(accept_and_use_sessions)} answers are good to be used further {list(collections.Counter(not_using_further_reasons).items())}")
    print(f"   Data cleaning report is saved in: {report_file}")
    if method == 'p835':
        print(f"   percentage of 'sig_bak':  {round(count_sig_bak/len(accept_and_use_sessions),4)*100} %")
    return worker_list, use_sessions

#p835
def evaluate_maximum_hits(data):
    df = pd.DataFrame(data)
    small_df = df[['worker_id']].copy()
    grouped = small_df.groupby(['worker_id']).size().reset_index(name='counts')
    grouped = grouped[grouped.counts > int(config['acceptance_criteria']['allowedMaxHITsInProject'])]
    # grouped.to_csv('out.csv')
    print(f"{len(grouped.index)} workers answered more than the allowedMaxHITsInProject"
          f"(>{config['acceptance_criteria']['allowedMaxHITsInProject']})")
    cheater_workers_list = list(grouped['worker_id'])

    cheater_workers_work_count = dict.fromkeys(cheater_workers_list, 0)
    result = []
    for d in data:
        if d['worker_id'] in cheater_workers_work_count:
            if cheater_workers_work_count[d['worker_id']] >= int(config['acceptance_criteria']['allowedMaxHITsInProject']):
                d['accept'] = 0
                d['Reject'] += f"More than allowed limit of {config['acceptance_criteria']['allowedMaxHITsInProject']}"
                d['accept_and_use'] = 0
                d['Approve'] = ''
            else:
                cheater_workers_work_count[d['worker_id']] += 1
        result.append(d)
    return result


def save_approve_rejected_ones_for_gui(data, path):
    """
    save approved/rejected in file t be used in GUI
    :param data:
    :param path:
    :return:
    """
    df = pd.DataFrame(data)
    df = df[df.status == 'Submitted']
    small_df = df[['assignment', 'HITId', 'Approve', 'Reject']].copy()
    small_df.rename(columns={'assignment': 'assignmentId'}, inplace=True)
    small_df.to_csv(path, index=False)


def save_approved_ones(data, path):
    """
    save approved results in the given path
    :param data:
    :param path:
    :return:
    """
    df = pd.DataFrame(data)
    df = df[df.accept == 1]
    c_accepted = df.shape[0]
    df = df[df.status == 'Submitted']
    if df.shape[0] == c_accepted:
        print(f'    {c_accepted} answers are accepted')
    else:
        print(f'    overall {c_accepted} answers are accepted, from them {df.shape[0]} were in submitted status')
    small_df = df[['assignment']].copy()
    small_df.rename(columns={'assignment': 'assignmentId'}, inplace=True)
    small_df.to_csv(path, index=False)


def save_rejected_ones(data, path):
    """
    Save the rejected ones in the path
    :param data:
    :param path:
    :return:
    """
    df = pd.DataFrame(data)
    df = df[df.accept == 0]
    c_rejected = df.shape[0]
    df = df[df.status == 'Submitted']
    if df.shape[0] == c_rejected:
        print(f'    {c_rejected} answers are rejected')
    else:
        print(f'    overall {c_rejected} answers are rejected, from them {df.shape[0]} were in submitted status')
    small_df = df[['assignment']].copy()
    small_df.rename(columns={'assignment': 'assignmentId'}, inplace=True)
    small_df = small_df.assign(feedback= config['acceptance_criteria']['rejection_feedback'])
    small_df.to_csv(path, index=False)


def save_hits_to_be_extended(data, path):
    """
    Save the list of HITs that are accepted but not to be used. The list can be used to extend those hits
    :param data:
    :param path:
    :return:
    """
    df = pd.DataFrame(data)
    df = df[(df.accept == 1) & (df.accept_and_use == 0)]
    small_df = df[['HITId']].copy()
    grouped = small_df.groupby(['HITId']).size().reset_index(name='counts')
    grouped.rename(columns={'counts': 'n_extended_assignments'}, inplace=True)
    grouped.to_csv(path, index=False)


def filter_answer_by_status_and_workers(answer_df, all_time_worker_id_in, new_woker_id_in, status_in):
    """
    return answered who are
    :param answer_df:
    :param all_time_worker_id_in:
    :param new_woker_id_in:
    :param status_in:
    :return:
    """

    frames = []
    if 'all' in status_in:
        # new_worker_id_in.extend(old_worker_id_in)
        answer_df = answer_df[answer_df['worker_id'].isin(all_time_worker_id_in)]
        return answer_df
    if 'submitted' in status_in:
        d1 = answer_df[answer_df['status'] == "Submitted"]
        d1 = d1[d1['worker_id'].isin(all_time_worker_id_in)]
        frames.append(d1)
        d2 = answer_df[answer_df['status'] != "Submitted"]
        d2 = d2[d2['worker_id'].isin(new_woker_id_in)]
        frames.append(d2)
        return pd.concat(frames)

#p835
def calc_quantity_bonuses(answer_list, conf, path):
    """
    Calculate the quantity bonuses given the configurations
    :param answer_list:
    :param conf:
    :param path:
    :return:
    """
    if path is not None:
        print('Calculate the quantity bonuses...')
    df = pd.DataFrame(answer_list)

    old_answers = df[df['status'] != "Submitted"]
    grouped = df.groupby(['worker_id'], as_index=False)['accept'].sum()
    old_answers_grouped = old_answers.groupby(['worker_id'], as_index=False)['accept'].sum()

    # condition more than 30 hits
    grouped = grouped[grouped.accept >= int(config['bonus']['quantity_hits_more_than'])]
    old_answers_grouped = old_answers_grouped[old_answers_grouped.accept >= int(config['bonus']['quantity_hits_more_than'])]

    old_eligible = list(old_answers_grouped['worker_id'])
    eligible_all = list(grouped['worker_id'])
    new_eligible = list(set(eligible_all)-set(old_eligible))

    # the bonus should be given to the tasks that are either automatically accepted or submited. The one with status
    # accepted should have been already payed.
    filtered_answers = filter_answer_by_status_and_workers(df, eligible_all, new_eligible, conf)
    # could be also accept_and_use
    grouped = filtered_answers.groupby(['worker_id'], as_index=False)['accept'].sum()
    grouped['bonusAmount'] = grouped['accept']*float(config['bonus']['quantity_bonus'])

    # now find an assignment id
    df.drop_duplicates('worker_id', keep='first', inplace=True)
    w_ids = list(dict(grouped['worker_id']).values())
    df = df[df.isin(w_ids).worker_id]
    small_df = df[['worker_id', 'assignment']].copy()
    merged = pd.merge(grouped, small_df, how='inner', left_on='worker_id', right_on='worker_id')
    merged.rename(columns={'worker_id': 'workerId', 'assignment': 'assignmentId'}, inplace=True)

    merged['reason'] = f'Well done! More than {config["bonus"]["quantity_hits_more_than"]} accepted submissions.'
    merged = merged.round({'bonusAmount': 2})

    if path is not None:
        merged.to_csv(path, index=False)
        print(f'   Quantity bonuses report is saved in: {path}')
    return merged

#p835
def calc_quality_bonuses(quantity_bonus_result, answer_list, overall_mos, conf, path, n_workers, test_method, use_condition_level):
    """
    Calculate the bonuses given the configurations
    :param quantity_bonus_result:
    :param answer_list:
    :param overall_mos:
    :param conf:
    :param path:
    :param test_method:
    :param use_condition_level: if true the condition level aggregation will be used otherwise file level
    :return:
    """
    print('Calculate the quality bonuses...')
    mos_name = method_to_mos[f"{test_method}{question_name_suffix}"]

    eligible_list = []
    df = pd.DataFrame(answer_list)
    tmp = pd.DataFrame(overall_mos)
    if use_condition_level:
        aggregate_on = 'condition_name'
    else:
        aggregate_on = 'file_url'
    c_df = tmp[[aggregate_on, mos_name]].copy()
    c_df.rename(columns={mos_name: 'mos'}, inplace=True)

    candidates = quantity_bonus_result['workerId'].tolist()
    max_workers = int(n_workers * int(conf['bonus']['quality_top_percentage']) / 100)

    for worker in candidates:
            # select answers
            worker_answers = df[df['workerid'] == worker]
            votes_p_file, votes_per_condition, _ = transform(test_method, worker_answers.to_dict('records'), use_condition_level)
            if use_condition_level:
                aggregated_data = pd.DataFrame(votes_per_condition)
            else:
                aggregated_data = pd.DataFrame(votes_p_file)
            if len(aggregated_data) > 0:
                merged = pd.merge(aggregated_data, c_df, how='inner', left_on=aggregate_on, right_on=aggregate_on)
                r = calc_correlation(merged["mos"].tolist(), merged[mos_name].tolist())
            else:
                r = 0
            entry = {'workerId': worker, 'r': r}
            eligible_list.append(entry)
    if len(eligible_list) > 0:
        eligible_df = pd.DataFrame(eligible_list)
        eligible_df = eligible_df[eligible_df['r'] >= float(conf['bonus']['quality_min_pcc'])]
        eligible_df = eligible_df.sort_values(by=['r'], ascending=False)

        merged = pd.merge(eligible_df, quantity_bonus_result, how='inner', left_on='workerId', right_on='workerId')
        smaller_df = merged[['workerId', 'r', 'accept', 'assignmentId']].copy()
        smaller_df['bonusAmount'] = smaller_df['accept'] * float(config['bonus']['quality_bonus'])

        smaller_df = smaller_df.round({'bonusAmount': 2})
        smaller_df['reason'] = f'Well done! You belong to top {conf["bonus"]["quality_top_percentage"]}%.'
    else:
        smaller_df = pd.DataFrame(columns=['workerId',	'r', 'accept', 'assignmentId', 	'bonusAmount', 'reason'])
    smaller_df.head(max_workers).to_csv(path, index=False)
    print(f'   Quality bonuses report is saved in: {path}')


def write_dict_as_csv(dic_to_write, file_name, *args, **kwargs):
    """
    write the dict object in a file
    :param dic_to_write:
    :param file_name:
    :return:
    """
    headers = kwargs.get('headers', None)
    with open(file_name, 'w', newline='') as output_file:
        if headers is None:
            if len(dic_to_write) > 0:
                headers = list(dic_to_write[0].keys())
            else:
                headers = []
        writer = csv.DictWriter(output_file, fieldnames=headers)
        writer.writeheader()
        for d in dic_to_write:
            writer.writerow(d)


file_to_condition_map = {}


def conv_filename_to_condition(f_name):
    """
    extract the condition name from filename given the mask in the config
    :param f_name:
    :return:
    """
    if f_name in file_to_condition_map:
        return file_to_condition_map[f_name]
    file_to_condition_map[f_name] = {'Unknown': 'NoCondition' }
    pattern = ''
    if config.has_option('general','condition_pattern'):
        pattern = config['general']['condition_pattern']
    m = re.match(pattern, f_name)
    if m:
        file_to_condition_map[f_name] = m.groupdict('')

    return file_to_condition_map[f_name]


def dict_value_to_key(d, value):
    for k, v in d.items():
        if v == value:
            return k
    return None


method_to_mos = {
    "acr": 'MOS',
    "ccr": 'CMOS',
    "dcr": 'DMOS',
    "p835_bak": 'MOS_BAK',
    "p835_sig": 'MOS_SIG',
    "p835_ovrl": 'MOS_OVRL',
    "echo_impairment_test_echo": 'MOS_ECHO',
    "echo_impairment_test_other": 'MOS_OTHER'
}

p835_columns = ['condition_name', 'n', 'MOS_BAK', 'MOS_SIG', 'MOS_OVRL', 'std_bak', 'std_sig', 'std_ovrl',
                '95%CI_bak', '95%CI_sig', '95%CI_ovrl']
echo_impairment_test_columns = ['condition_name', 'n', 'MOS_ECHO', 'MOS_OTHER', 'std_echo', 'std_other',
                '95%CI_echo', '95%CI_other']

question_names = []
question_name_suffix = ''
p835_suffixes = ['_bak', '_sig', '_ovrl']
echo_impairment_test_suffixes = ['_echo', '_other']
create_per_worker = True

def transform(test_method, sessions, agrregate_on_condition):
    """
    Given the valid sessions from answer.csv, group votes per files, and per conditions.
    Assumption: file name conatins the condition name/number, which can be extracted using "condition_patten" .
    :param sessions:
    :return:
    """
    data_per_file = {}
    global max_found_per_file
    global file_to_condition_map
    file_to_condition_map ={}
    data_per_condition = {}
    data_per_worker =[]
    mos_name = method_to_mos[f"{test_method}{question_name_suffix}"]

    for session in sessions:
        found_gold_question = False
        for question in question_names:
            # is it a trapping clips question
            if session[config['trapping']['url_found_in']] == session[f'answer.{question}_url']:
                continue
            # is it a gold clips
            if test_method in ['acr', 'p835', 'echo_impairment_test'] and not found_gold_question and\
                    session[config['gold_question']['url_found_in']] == session[f'answer.{question}_url']:
                found_gold_question = True
                continue
            short_file_name = session[f'answer.{question}_url'].rsplit('/', 1)[-1]
            file_name = session[f'answer.{question}_url']
            if file_name not in data_per_file:
                data_per_file[file_name] = []
            votes = data_per_file[file_name]
            try:
                votes.append(int(session[f'answer.{question}{question_name_suffix}']))
                cond =conv_filename_to_condition(file_name)
                tmp = {'workerid': session['workerid'],
                        'file':file_name,
                       'short_file_name': file_name.rsplit('/', 1)[-1],
                        'vote': int(session[f'answer.{question}{question_name_suffix}'])}

                tmp.update(cond)
                data_per_worker.append(tmp)
            except Exception as err:
                print(err)
                pass
    # convert the format: one row per file
    group_per_file = []
    condition_detail = {}
    for key in data_per_file.keys():
        tmp = dict()
        votes = data_per_file[key]
        vote_counter = 1

        # extra step:: add votes to the per-condition dict
        tmp_n = conv_filename_to_condition(key)
        if agrregate_on_condition:
            condition_keys = config['general']['condition_keys'].split(',')
            condition_keys.append('Unknown')
            condition_dict = {k: tmp_n[k] for k in tmp_n.keys() & condition_keys}
            tmp = condition_dict.copy()
            condition_dict = collections.OrderedDict(sorted(condition_dict.items()))
            for num_combinations in range(len(condition_dict)):
                combinations = list(itertools.combinations(condition_dict.values(), num_combinations + 1))
                for combination in combinations:
                    condition = '____'.join(combination).strip('_')
                    if condition not in data_per_condition:
                        data_per_condition[condition]=[]
                        pattern_dic ={dict_value_to_key(condition_dict, v): v for v in combination}
                        for k in condition_dict.keys():
                            if k not in pattern_dic:
                                pattern_dic[k] = ""
                        condition_detail[condition] = pattern_dic

                    data_per_condition[condition].extend(votes)

        else:
            condition = 'Overall'
            if condition not in data_per_condition:
                data_per_condition[condition] = []
            data_per_condition[condition].extend(votes)

        tmp['file_url'] = key
        tmp['short_file_name'] = key.rsplit('/', 1)[-1]
        for vote in votes:
            tmp[f'vote_{vote_counter}'] = vote
            vote_counter += 1
        count = vote_counter

        tmp['n'] = count-1
        # tmp[mos_name] = abs(statistics.mean(votes))
        tmp[mos_name] = statistics.mean(votes)
        if tmp['n'] > 1:
            tmp[f'std{question_name_suffix}'] = statistics.stdev(votes)
            tmp[f'95%CI{question_name_suffix}'] = (1.96 * tmp[f'std{question_name_suffix}']) / math.sqrt(tmp['n'])
        else:
            tmp[f'std{question_name_suffix}'] = None
            tmp[f'95%CI{question_name_suffix}'] = None
        if tmp['n'] > max_found_per_file:
            max_found_per_file = tmp['n']
        group_per_file.append(tmp)

    # convert the format: one row per condition
    group_per_condition = []
    if agrregate_on_condition:
        for key in data_per_condition.keys():
            tmp = dict()
            tmp['condition_name'] = key
            votes = data_per_condition[key]
            # apply z-score outlier detection
            # votes = outliers_z_score(votes)
            tmp = {**tmp, **condition_detail[key]}
            tmp['n'] = len(votes)
            if tmp['n'] > 0:
                # tmp[mos_name] = abs(statistics.mean(votes))
                tmp[mos_name] = statistics.mean(votes)
            else:
                tmp[mos_name] = None
            if tmp['n'] > 1:
                tmp[f'std{question_name_suffix}'] = statistics.stdev(votes)
                tmp[f'95%CI{question_name_suffix}'] = (1.96 * tmp[f'std{question_name_suffix}']) / math.sqrt(tmp['n'])
            else:
                tmp[f'std{question_name_suffix}'] = None
                tmp[f'95%CI{question_name_suffix}'] = None

            group_per_condition.append(tmp)

    return group_per_file, group_per_condition, data_per_worker

# p835
def create_headers_for_per_file_report(test_method, condition_keys):
    """
    add default values in the dict
    :param d:
    :return:
    """
    mos_name = method_to_mos[f"{test_method}{question_name_suffix}"]
    if test_method in ["p835", "echo_impairment_test"]:
        header = ['file_url', 'n', mos_name, f'std{question_name_suffix}', f'95%CI{question_name_suffix}',
                  'short_file_name'] + condition_keys
    else:
        header = ['file_url', 'n', mos_name, 'std', '95%CI', 'short_file_name'] + condition_keys
    max_votes = max_found_per_file
    if max_votes == -1:
        max_votes = int(config['general']['expected_votes_per_file'])
    for i in range(1, max_votes+1):
        header.append(f'vote_{i}')

    return header


def stats(input_file):
    """
    calc the statistics considering the time worker spend
    :param input_file:
    :return:
    """
    df = pd.read_csv(input_file, low_memory=False)
    median_time_in_sec = df["WorkTimeInSeconds"].median()
    payment_text = df['Reward'].values[0]
    paymnet = re.findall("\d+\.\d+", payment_text)

    avg_pay = 3600*float(paymnet[0])/median_time_in_sec
    formatted_time = time.strftime("%M:%S", time.gmtime(median_time_in_sec))
    print(f"Stats: work duration (median) {formatted_time} (MM:SS), payment per hour: ${avg_pay:.2f}")


def calc_correlation(cs, lab):
    """
    calc the spearman's correlation
    :param cs:
    :param lab:
    :return:
    """
    rho, pval = spearmanr(cs, lab)
    return rho


def number_of_uniqe_workers(answers):
    """
    return numbe rof unique workers
    :param answers:
    :return:
    """
    df = pd.DataFrame(answers)
    df.drop_duplicates('worker_id', keep='first', inplace=True)
    return len(df)


def analyze_results(config, test_method, answer_path, list_of_req, quality_bonus):
    """
    main method for calculating the results
    :param config:
    :param test_method:
    :param answer_path:
    :param list_of_req:
    :param quality_bonus:
    :return:
    """
    global question_name_suffix
    if test_method == 'p835':
        question_name_suffix = p835_suffixes[2]
        suffixes = p835_suffixes
    elif test_method == 'echo_impairment_test':
        question_name_suffix = echo_impairment_test_suffixes[1]
        suffixes = echo_impairment_test_suffixes
    else:
        suffixes = ['']
    full_data, accepted_sessions = data_cleaning(answer_path, test_method)
    n_workers = number_of_uniqe_workers(full_data)
    print(f"{n_workers} workers participated in this batch.")
    stats(answer_path)
    # votes_per_file, votes_per_condition = transform(accepted_sessions)
    if len(accepted_sessions) > 1:
        condition_set = []
        for suffix in suffixes:
            question_name_suffix = suffix
            print("Transforming data (the ones with 'accepted_and_use' ==1 --> group per clip")
            use_condition_level = config.has_option('general', 'condition_pattern')
            votes_per_file, vote_per_condition, data_per_worker = transform(test_method, accepted_sessions,
                                                           config.has_option('general', 'condition_pattern'))

            votes_per_file_path = os.path.splitext(answer_path)[0] + f'_votes_per_clip{question_name_suffix}.csv'
            votes_per_cond_path = os.path.splitext(answer_path)[0] + f'_votes_per_cond{question_name_suffix}.csv'

            condition_keys = []
            if config.has_option('general', 'condition_pattern'):
                condition_keys = config['general']['condition_keys'].split(',')
                votes_per_file = sorted(votes_per_file, key=lambda i: i[condition_keys[0]])
                condition_keys.append('Unknown')
            headers = create_headers_for_per_file_report(test_method, condition_keys)
            write_dict_as_csv(votes_per_file, votes_per_file_path, headers=headers)
            print(f'   Votes per files are saved in: {votes_per_file_path}')
            if use_condition_level:
                vote_per_condition = sorted(vote_per_condition, key=lambda i: i['condition_name'])
                write_dict_as_csv(vote_per_condition, votes_per_cond_path)
                print(f'   Votes per files are saved in: {votes_per_cond_path}')
                condition_set.append(pd.DataFrame(vote_per_condition))
            if create_per_worker:
                write_dict_as_csv(data_per_worker, os.path.splitext(answer_path)[0] + f'_votes_per_worker_{question_name_suffix}.csv')
        if use_condition_level and len(suffixes) > 1:
            # aggregate multiple conditions into one file for p.835
            full_set_conditions = None
            for df in condition_set:
                if full_set_conditions is None:
                    full_set_conditions = df
                else:
                    df = df.drop(columns='n')
                    full_set_conditions = pd.merge(full_set_conditions, df, left_on='condition_name', right_on='condition_name')
            votes_per_all_cond_path = os.path.splitext(answer_path)[0] + f'_votes_per_cond_all.csv'
            column_names = p835_columns if test_method == 'p835' else echo_impairment_test_columns
            full_set_conditions.to_csv(votes_per_all_cond_path, index=False,
                                       columns=['condition_name', 'n', 'MOS_BAK', 'MOS_SIG', 'MOS_OVRL', 'std_bak',
                                                'std_sig', 'std_ovrl', '95%CI_bak', '95%CI_sig', '95%CI_ovrl'])

        bonus_file = os.path.splitext(answer_path)[0] + '_quantity_bonus_report.csv'
        quantity_bonus_df = calc_quantity_bonuses(full_data, list_of_req, bonus_file)

        if quality_bonus:
            quality_bonus_path = os.path.splitext(answer_path)[0] + '_quality_bonus_report.csv'
            if 'all' not in list_of_req:
                quantity_bonus_df = calc_quantity_bonuses(full_data, ['all'], None)
            if use_condition_level:
                votes_to_use = vote_per_condition
            else:
                votes_to_use = votes_per_file
            calc_quality_bonuses(quantity_bonus_df, accepted_sessions, votes_to_use, config, quality_bonus_path,
                                 n_workers, test_method, use_condition_level)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Utility script to evaluate answers to the acr batch')
    # Configuration: read it from mturk.cfg
    parser.add_argument("--cfg", required=True,
                        help="Contains the configurations see acr_result_parser.cfg as an example")
    parser.add_argument("--method", required=True,
                        help="one of the test methods: 'acr', 'dcr', 'ccr', 'p835', or 'echo_impairment_test'")
    parser.add_argument("--answers", required=True,
                        help="Answers csv file, path relative to current directory")

    parser.add_argument('--quantity_bonus', help="specify status of answers which should be counted when calculating "
                                                " the amount of quantity bonus. All answers will be used to check "
                                                "eligibility of worker, but those with the selected status here will "
                                                "be used to calculate the amount of bonus. A comma separated list:"
                                                " all|submitted. Default: submitted",
                        default="submitted")

    parser.add_argument('--quality_bonus', help="Quality bonus will be calculated. Just use it with your final download"
                                                " of answers and when the project is completed", action="store_true")
    args = parser.parse_args()
    methods = ['acr', 'dcr', 'ccr', 'p835', 'echo_impairment_test']
    test_method = args.method.lower()
    assert test_method in methods, f"No such a method supported, please select between 'acr', 'dcr', 'ccr', or 'p835'"

    cfg_path = args.cfg
    assert os.path.exists(cfg_path), f"No configuration file at [{cfg_path}]"
    config = CP.ConfigParser()
    config.read(cfg_path)

    assert (args.answers is not None), f"--answers  are required]"
    # answer_path = os.path.join(os.path.dirname(__file__), args.answers)
    answer_path = args.answers
    assert os.path.exists(answer_path), f"No input file found in [{answer_path}]"
    list_of_possible_status = ['all', 'submitted']

    list_of_req = args.quantity_bonus.lower().split(',')
    for req in list_of_req:
        assert req.strip() in list_of_possible_status, f"unknown status {req} used in --quantity_bonus"

    np.seterr(divide='ignore', invalid='ignore')
    question_names = [f"q{i}" for i in range(1, int(config['general']['number_of_questions_in_rating']) + 1)]
    # start
    analyze_results(config, test_method,  answer_path, list_of_req, args.quality_bonus)
