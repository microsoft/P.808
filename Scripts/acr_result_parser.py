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
import sys
import re
from scipy import stats
import time
from enum import Enum,IntEnum

config = {
    "math": {
     "math1.wav": 3,
     "math2.wav": 7,
     "math3.wav": 6,
    },
    "question_names": ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "q10", "q11", "q12"],
    "expected_votes_per_file": 10,
    "trapping": {
        "url_found_in": "input.tp",
        "ans_found_in": "input.tp_ans",
    },
    "gold_question": {
        "url_found_in": "input.gold_clips",
        #"ans_found_in": "input.gold_clips_ans",
        "correct_ans": 5,
        "variance": 1
    },
    "acceptance_criteria": {
        "all_audio_played_equal": 1,
        "correct_math_bigger_equal": 1,
        "correct_tps_bigger_equal": 1,
        # NOTE: this value should be synchronied by the corresponding value in the ACR.html
        "allowedMaxHITsInProject": 60,
        #"correct_gold_q_bigger_equal": 1
    },
    "accept_and_use": {
        # including acceptance_criteria
        "variance_bigger_equal": 0.1,
        "gold_standard_bigger_equal": 1,
        "correct_cmp_bigger_equal": 2,
    },
    "bonus": {
        "when_HITs_more_than": 5,
        "extra_pay_per_HIT": 0.25
    },
    "rejection_feedback": "Answer to this assigmnet did not pass the quality control "
                          "check. Make sure to use headset (wear both earbuds), perform the task in quiet environment,"
                          " and use the entire scale range.",
    #"book_04753_chp_0059_reader_10797_6.wav" mask "????????????????????????????????xxxxxx":book_04753_chp_0059_reader_10797
    "condition_pattern": "????????????????????????????????xxxxxx"
}


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


def check_if_session_accepted(data):
    """
    Check if the session can be acceptd given the criteria in config and the calculations
    :param data:
    :return:
    """
    msg = "Make sure you follow the instruction:"
    accept = True
    if data['all_audio_played'] != config['acceptance_criteria']['all_audio_played_equal']:
        accept = False
        msg += "All clips should be played until the end;"
    if data['correct_math'] is not None and data['correct_math'] < config['acceptance_criteria']['correct_math_bigger_equal']:
        accept = False
        msg += "Wear both earbuds;"
    if data['correct_tps'] < config['acceptance_criteria']['correct_tps_bigger_equal']:
        accept = False
        msg += "Trapping question(s) answered wrongly;"

    if not accept:
        data['Reject'] = msg
    else:
        data['Reject'] =''
    return accept


def check_if_session_should_be_used(data):
    """
    Check if the session should be used given the criteria in config
    :param data:
    :return:
    """
    if data['accept'] == 1 and \
            data['variance_in_ratings'] >= config['accept_and_use']['variance_bigger_equal'] and \
            data['correct_gold_question'] >= config['accept_and_use']['gold_standard_bigger_equal'] and \
            (data['correct_cmps'] is None or data['correct_cmps'] >= config['accept_and_use']['correct_cmp_bigger_equal']):
        return True
    return False


def check_audio_played(row):
    """
    check if all audios for questions played until the end
    :param row:
    :return:
    """
    question_played = 0
    try:
        for q_name in config['question_names']:
            if int(row[f'answer.audio_n_finish_{q_name}']) > 0:
                question_played += 1
    except:
        return False
    return question_played == len(config['question_names'])


def check_tps(row):
    """
    Check if the trapping questions are answered correctly
    :param row:
    :return:
    """
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
    """
    Check how is variance of ratings in the session (if the worker just clicked samething)
    :param row:
    :return:
    """
    r = []
    for q_name in config['question_names']:
        if row[config['gold_question']['url_found_in']] in row[f'answer.{q_name}_url']:
            continue
        if row[config['trapping']['url_found_in']] in row[f'answer.{q_name}_url']:
            continue
        try:
            r.append(int(row[f'answer.{q_name}']))
        except:
            pass
    return statistics.variance(r)


def check_gold_question(row):
    """
    Check if the gold_question is answered correctly
    :param row:
    :return:
    """
    correct_gq = 0
    try:
        gq_url = row[config['gold_question']['url_found_in']]
        # gq_correct_ans = int(float(row[config['gold_question']['ans_found_in']]))
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
    return correct_gq


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
            if key in input and config['math'][key] == int(output):
                return True
    except:
        return False
    return False


def check_a_cmp(file_a, file_b,ans, audio_a_played, audio_b_played):
    """
    check if pair comparision answered correctly
    :param file_a:
    :param file_b:
    :param ans:
    :param audio_a_played:
    :param audio_b_played:
    :return:
    """
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
    return answer_is_correct


def data_cleaning(filename, bonus_calc_conf):
    """
    Data screening process
    :param filename:
    :return:
    """
    print('Start by Data Cleaning...')
    with open(filename) as csvfile:

        reader = csv.DictReader(csvfile)
        # lowercase the fieldnames
        reader.fieldnames = [field.strip().lower() for field in reader.fieldnames]
        # ----------- cmps
        # Input.CMP1_A	Input.CMP1_B	Input.CMP2_A	Input.CMP2_B	Input.CMP3_A	Input.CMP3_B	Input.CMP4_A	Input.CMP4_B
        # Answer.cmp1	Answer.cmp2	Answer.cmp3	Answer.cmp4
        # Answer.audio_n_play_CMP1_A	Answer.audio_n_play_CMP1_B	Answer.audio_n_play_CMP2_A	Answer.audio_n_play_CMP2_B
        # Answer.audio_n_play_CMP3_A	Answer.audio_n_play_CMP3_B	Answer.audio_n_play_CMP4_A	Answer.audio_n_play_CMP4_B
        # WorkerId
        # ---------------- math
        # Input.math, Answer.Math,Answer.audio_n_play_math1
        worker_list = []
        use_sessions = []
        for row in reader:
            correct_cmp_ans = 0
            setup_was_hidden = row['answer.cmp1'] is None or len(row['answer.cmp1'].strip()) == 0
            d = dict()

            d['worker_id'] = row['workerid']
            d['HITId'] = row['hitid']
            d['assignment'] = row['assignmentid']
            d['status'] = row['assignmentstatus']

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
                d['Approve'] = 'x'
            else:
                d['accept'] = 0
                d['Approve'] = ''

            if check_if_session_should_be_used(d):
                d['accept_and_use'] = 1
                use_sessions.append(row)
            else:
                d['accept_and_use'] = 0

            worker_list.append(d)
        report_file = os.path.splitext(filename)[0] + '_data_cleaning_report.csv'
        bonus_file = os.path.splitext(filename)[0] + '_bonus_report.csv'
        approved_file = os.path.splitext(filename)[0] + '_accept.csv'
        rejected_file = os.path.splitext(filename)[0] + '_rejection.csv'
        accept_reject_gui_file = os.path.splitext(filename)[0] + '_accept_reject_gui.csv'

        # reject hits when the user performed more than the limit
        worker_list = evaluate_maximum_hits(worker_list)

        accept_and_use_sessions = [d for d in worker_list if d['accept_and_use'] == 1]

        write_dict_as_csv(worker_list, report_file)
        save_approved_ones(worker_list, approved_file)
        save_rejected_ones(worker_list, rejected_file)
        save_approve_rejected_ones_for_gui(worker_list, accept_reject_gui_file)
        print(f"   {len(accept_and_use_sessions)} answers are good to be used further")
        print(f"   Data cleaning report is saved in: {report_file}")
        calc_bonuses(worker_list, bonus_calc_conf, bonus_file)
        return use_sessions


def evaluate_maximum_hits(data):
    df = pd.DataFrame(data)
    small_df = df[['worker_id']].copy()
    grouped = small_df.groupby(['worker_id']).size().reset_index(name='counts')
    grouped = grouped[grouped.counts > config['acceptance_criteria']['allowedMaxHITsInProject']]
    #grouped.to_csv('out.csv')
    print(f"{len(grouped.index)} workers answerd more than the allowedMaxHITsInProject(>{config['acceptance_criteria']['allowedMaxHITsInProject']})")
    cheater_workers_list = list(grouped['worker_id'])

    cheater_workers_work_count = dict.fromkeys(cheater_workers_list, 0)
    result=[]
    for d in data:
        if d['worker_id'] in cheater_workers_work_count:
            if (cheater_workers_work_count[ d['worker_id']]>= config['acceptance_criteria']['allowedMaxHITsInProject']):
                d['accept'] = 0
                d['Reject'] += f"More than allowed limit of {config['acceptance_criteria']['allowedMaxHITsInProject']}"
                d['accept_and_use'] = 0
            else:
                cheater_workers_work_count[d['worker_id']] +=1
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
    small_df = small_df.assign(feedback=config['rejection_feedback'])
    small_df.to_csv(path, index=False)


def filter_answer_by_status_and_workers(answer_df, all_time_worker_id_in, new_woker_id_in, status_in):
    """
    return answered who are
    :param status_in:
    :return:
    """

    frames = []
    if 'all' in status_in:
        #new_woker_id_in.extend(old_worker_id_in)
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


def calc_bonuses(answer_list, conf, path):
    """
    Calculate the bonuses given the configurations
    :param answer_list:
    :param conf:
    :param path:
    :return:
    """
    print('Calculate the bonuses...')
    df = pd.DataFrame(answer_list)

    old_answers = df[df['status'] != "Submitted"]
    grouped = df.groupby(['worker_id'], as_index=False)['accept'].sum()
    old_answers_groupped = old_answers.groupby(['worker_id'], as_index=False)['accept'].sum()

    # condition more than 30 hits
    grouped = grouped[grouped.accept >= config['bonus']['when_HITs_more_than']]
    old_answers_groupped = old_answers_groupped[old_answers_groupped.accept>= config['bonus']['when_HITs_more_than']]

    old_eligables= list(old_answers_groupped['worker_id'])
    eligables_all= list(grouped['worker_id'])
    new_eligables=list (set(eligables_all)-set(old_eligables))

    # the bonus should be given to the tasks that are either automatically accepted or submited. The one with status
    # accepted should have been already payed.
    filtered_answers = filter_answer_by_status_and_workers(df, eligables_all, new_eligables , conf)

    grouped = filtered_answers.groupby(['worker_id'], as_index=False)['accept_and_use'].sum()
    grouped['bonusAmount'] = grouped['accept_and_use']*config['bonus']['extra_pay_per_HIT']

    # now find an assignment id
    df.drop_duplicates('worker_id', keep='first', inplace = True )
    w_ids = list(dict(grouped['worker_id']).values())
    df = df[df.isin(w_ids).worker_id]
    small_df = df[['worker_id', 'assignment']].copy()

    merged = pd.merge( grouped, small_df, how='inner', left_on='worker_id', right_on='worker_id')
    merged.rename(columns={'worker_id': 'workerId', 'assignment': 'assignmentId'}, inplace=True)

    merged['reason'] = f'Well done! More than {config["bonus"]["when_HITs_more_than"]} high quality submission'
    merged.to_csv(path, index=False)
    print(f'   Bonuses report is saved in: {path}')


def write_dict_as_csv(dic_to_write, file_name):
    """
    write the dict object in a file
    :param dic_to_write:
    :param file_name:
    :return:
    """
    with open(file_name, 'w', newline='') as output_file:
        if len(dic_to_write) > 0:
            fieldnames = list(dic_to_write[0].keys())
        else:
            fieldnames = []
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for d in dic_to_write:
            writer.writerow(d)


file_to_condition_map = {}


def filename_to_condition(f_name):
    """
    extract the condition name from filename given the mask in the config
    :param f_name:
    :return:
    """
    if f_name in file_to_condition_map:
        return file_to_condition_map[f_name]
    condition_name = ""
    f_char = list(f_name)
    p_chars = list(config['condition_pattern'])
    # "book_04753_chp_0059_reader_10797_6.wav"
    #  --> "????????????????????????????????xxxxxx":book_04753_chp_0059_reader_10797
    for i in range(0, len(p_chars)):
        if p_chars[i] == '?':
            condition_name += f_char[i]
    file_to_condition_map[f_name] = condition_name
    return condition_name


def transform(sessions, path_per_file, path_per_condition):
    """
    Given the valid sessions from answer.csv, group votes per files, and per conditions.
    Assumption: file name starts with Cxx where xx is condition number.
    :param sessions:
    :param path_per_file:
    :param path_per_condition:
    :return:
    """
    print("Transforming data (the ones with 'accepted_and_use' ==1 --> group per clip")
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

    # convert the format: one row per file
    group_per_file = []
    for key in data_per_file.keys():
        tmp = initiate_file_row({})
        tmp['file_name'] = key
        votes = data_per_file[key]
        vote_counter = 1

        # extra step:: add votes to the per-condition dict
        condition = filename_to_condition(key)
        if condition not in data_per_condition:
            data_per_condition[condition]=[]
        data_per_condition[condition].extend(votes)

        for vote in votes:
            tmp[f'vote_{vote_counter}'] = vote
            vote_counter += 1
        count = vote_counter

        tmp['n'] = count-1
        tmp['mean'] = statistics.mean(votes)
        if tmp['n'] > 1:
            tmp['std'] = statistics.stdev(votes)
            tmp['95%CI'] = (1.96 * tmp['std']) / math.sqrt(tmp['n'])
        else:
            tmp['std'] = None
            tmp['95%CI'] = None
        group_per_file.append(tmp)

    # convert the format: one row per condition
    group_per_condition = []
    for key in data_per_condition.keys():
        tmp = dict()
        tmp['condition_name'] = key
        votes = data_per_condition[key]
        # apply z-score outlier detection
        #votes = outliers_z_score(votes)

        tmp['n'] = len(votes)
        if tmp['n'] > 0:
            tmp['mean'] = statistics.mean(votes)
        else:
            tmp['mean'] = None
        if tmp['n'] > 1:
            tmp['std'] = statistics.stdev(votes)
            tmp['95%CI'] = (1.96 * tmp['std']) / math.sqrt(tmp['n'])
        else:
            tmp['std'] = None
            tmp['95%CI'] = None

        group_per_condition.append(tmp)

    # return group_per_file, group_per_condition
    write_dict_as_csv(group_per_file, path_per_file)
    write_dict_as_csv(group_per_condition, path_per_condition)
    print(f'   Votes per files are saved in: {path_per_file}')
    print(f'   Votes per files are saved in: {path_per_condition}')
    return group_per_file, group_per_condition


def initiate_file_row(d):
    """
    add difault values in the dict
    :param d:
    :return:
    """
    d['file_name'] = None
    d['n'] = None
    d['mean'] = None
    d['std'] = None
    d['95%CI'] = None
    for i in range(1, config['expected_votes_per_file']+1):
        d[f'vote_{i}'] = None
    return d


def stats(input_file):
    df = pd.read_csv(input_file,low_memory=False)
    median_time_in_sec= df["WorkTimeInSeconds"].median()
    peyment_text = df['Reward'].values[0]
    paymnet = re.findall("\d+\.\d+", peyment_text)

    avg_pay= 3600*float(paymnet[0])/median_time_in_sec
    formated_time= time.strftime("%M:%S", time.gmtime(median_time_in_sec))
    print(f"Stats: work duration (median) {formated_time} (MM:SS), payment per hour: ${avg_pay:.2f}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Utility script to evaluate answers to the acr batch')
    # Configuration: read it from mturk.cfg
    parser.add_argument("--answers",
                        help="Answers csv file, path relative to current directory")

    parser.add_argument('--bonus',  help="specify status of answers which should "
                                                                             "be counted "
                                                                   "in bonus amount calculation. All answers will be "
                                                                   "used to check eligibility of worker, but those with"
                                                                   " the selected status here will be used to calculate"
                                                                   " the amount of bonus. A comma separated list"
                                                                   ":all|submitted"
                                                                   "Default: submitted",
                        default="submitted")

    #parser.add_argument('text', nargs='*')

    args = parser.parse_args()
    assert (args.answers is not None), f"--answers  are required]"
    #answer_path = os.path.join(os.path.dirname(__file__), args.answers)
    answer_path = args.answers
    assert os.path.exists(answer_path), f"No input file found in [{answer_path}]"
    list_of_possible_status = ['all', 'submitted']

    list_of_req = args.bonus.lower().split(',')
    for req in list_of_req:
        assert req.strip() in list_of_possible_status, f"unknown status {req} used in --bonus"

    np.seterr(divide='ignore', invalid='ignore')

    accepted_sessions = data_cleaning(answer_path, list_of_req)

    stats(answer_path)
    # votes_per_file, votes_per_condition = transform(accepted_sessions)
    if len(accepted_sessions) > 1:
        votes_per_file_path = os.path.splitext(args.answers)[0] + '_votes_per_clip.csv'
        votes_per_cond_path = os.path.splitext(args.answers)[0] + '_votes_per_cond.csv'
        votes_per_file, vote_per_condition = transform(accepted_sessions, votes_per_file_path, votes_per_cond_path)
