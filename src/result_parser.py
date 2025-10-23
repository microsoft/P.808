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
from scipy.stats import spearmanr, pearsonr
import time
import itertools
import configparser as CP
import collections
import warnings
import logging
import base64
max_found_per_file = -1
p835_personalized = "pp835"

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

    modified_z_scores = [
        np.abs(0.6745 * (v - median_v) / median_absolute_deviation_v) for v in votes
    ]
    x = np.array(modified_z_scores)
    v = np.array(votes)
    v = v[(x < threshold)]
    return v.tolist()


def outliers_z_score(votes):
    """
    return  outliers, using z-score
    :param votes:
    :return:
    """
    if len(votes) < 2 or statistics.stdev(votes) == 0:
        return votes

    threshold = 3.29

    z = np.abs(stats.zscore(votes))
    x = np.array(z)
    v = np.array(votes)
    v = v[x < threshold]
    return v.tolist()


def check_if_session_accepted(data):
    """
    Check if the session can be acceptd given the criteria in config and the calculations
    :param data:
    :return:
    """
    msg = "Make sure you follow the instruction:"
    accept = True
    failures = []

    if data["all_audio_played"] != int(
        config["acceptance_criteria"]["all_audio_played_equal"]
    ):
        accept = False
        msg += "All clips should be played until the end;"
        failures.append("all_audio_played")
    if data["correct_math"] is not None and data["correct_math"] < int(
        config["acceptance_criteria"]["correct_math_bigger_equal"]
    ):
        accept = False
        msg += "Failed in math problem. Both earplugs should be used."
        failures.append("math")
    if data["correct_tps"] < int(
        config["acceptance_criteria"]["correct_tps_bigger_equal"]
    ):
        accept = False
        msg += "Your HIT was rejected because you rated one or more control clip incorrectly. Control clips with instructions are ones where an interruption message asks you to select a score for all questions. We include control clips in the HIT to ensure raters pay attention during the entire HIT and their environment hasn't changed.;"
        failures.append("tps")
        
    if "gold_standard_bigger_equal" in config["acceptance_criteria"] and "correct_gold_question"  in data and data["correct_gold_question"] < int(
        config["acceptance_criteria"]["gold_standard_bigger_equal"]):
        accept = False
        msg += "Your HIT was rejected because you rated one or more control clip incorrectly. Control clips are ones that we know that answer for and should be very easy to rate (they are clearly very good or very poor). They can target one or more scales. We include control clips in the HIT to ensure raters are paying attention during the entire HIT and their environment hasn't changed."
        failures.append("gold")   
    if data['qualification'] is not None and data['qualification'] != 1:
        accept = False
        msg += "Qualification did not passed;"

    if not accept:
        data['Reject'] = msg
    else:
        data['Reject'] = ""
    return accept, failures


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

    if 'speaker_identification' in data and not data['speaker_identification']:
        should_be_used = False
        failures.append("speaker_identification")
    return should_be_used, failures


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
        elif method == "p804":
            for q_name in question_names:
                if (int(row[f"answer.audio_n_finish_{q_name}_audio"])> 0):
                    question_played += 1
        elif method in ['p835', 'echo_impairment_test', p835_personalized]:
            for q_name in question_names:
                if int(row[f'answer.audio_n_finish_{q_name}{question_name_suffix}_audio']) > 0:
                    question_played += 1
        elif method == "ccr":
            for q_name in question_names:
                if int(row[f'answer.audio_n_finish_q_{q_name[1:]}']) > 0:
                    question_played += 1
        else:
            for q_name in question_names:
                if int(row[f'answer.audio_n_finish_q_a{q_name[1:]}']) > 0 and int(row[f'answer.audio_n_finish_q_b{q_name[1:]}']) > 0:
                    question_played += 1
    except:
        return False
    return question_played == len(question_names)


def check_tps(row, method):
    """
    Check if the trapping clips questions are answered correctly
    :param row:
    :param method: acr, dcr, or ccr
    :return:
    """
    correct_tps = 0
    if int(config["acceptance_criteria"]["correct_tps_bigger_equal"])==0 :
        # no trappings
        return 1
    if config["trapping"]["url_found_in"] not in row:
        raise Exception("No trapping questions found in input data")
    tp_url = row[config["trapping"]["url_found_in"]]
    if method in ["acr", "p835", "echo_impairment_test", p835_personalized, "p804"] :
        tp_correct_ans = [int(float(row[config["trapping"]["ans_found_in"]]))]
    elif method == "dcr":
        tp_correct_ans = [4, 5]
    elif method == "ccr":
        tp_correct_ans = [-1, 0, 1]
    else:
        return -1

    try:
        suffix = ""
        # p835 
        if method=="p835":
            # only look at the ovrl for tps.
            suffix = "_ovrl"
        if method == "echo_impairment_test":
            suffix = "_echo"

        if method in["p804", p835_personalized]:
            if method == 'p804':
                items = ['noise', 'col', 'loud', 'disc', 'reverb', 'sig', 'ovrl']
            else:
                # to be tested with personalized P835
                items = ['bak', 'sig', 'ovrl']
            found_wrong_ans = False
            for q_name in question_names:
                if tp_url in row[f"answer.{q_name}_url"]:
                    # found a trapping clips question
                    for item in items:
                        if int(row[f"answer.{q_name}_{item}"]) not in tp_correct_ans:
                            found_wrong_ans = True
            if found_wrong_ans: 
                correct_tps = 0
            else:   
                correct_tps = 1

        else:
            for q_name in question_names:
                if tp_url in row[f"answer.{q_name}_url"]:
                    # found a trapping clips question
                    if int(row[f"answer.{q_name}{suffix}"]) in tp_correct_ans:
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
    for q_name in question_names:
        if (
            "gold_question" in config
            and row[config["gold_question"]["url_found_in"]]
            in row[f"answer.{q_name}_url"]
        ):
            continue
        if (
            "gold_question" in config
            and 'url2_found_in' in config["gold_question"] and
            row[config["gold_question"]["url2_found_in"]]
            in row[f"answer.{q_name}_url"]
        ):
            continue
        if config["trapping"]["url_found_in"] in row and len (row[config["trapping"]["url_found_in"]])>0 and row[config["trapping"]["url_found_in"]] in row[f"answer.{q_name}_url"]:
            continue
        try:            
            for suf in suffixes:
                r.append(int(row[f"answer.{q_name}{suf}"]))
        except:
            pass
    try:        
        v = statistics.variance(r)
        return v
    except:
        pass
    return -1


p835_personalized_gold_ans= dict()

def get_encoded_gold_ans(url, ans):
    ans = f"{url}_{round(ans)}"
    return base64.b64encode(ans.encode("ascii")).decode("ascii")


def get_encoded_correct_ans(url, endcoded_ans_sig, endcoded_ans_bak, endcoded_ans_ovrl):
    if url in p835_personalized_gold_ans:
        return p835_personalized_gold_ans[url]
    sig = None
    bak = None
    ovrl = None
    for i in range (1, 6):
        tmp = get_encoded_gold_ans(url, i)
        if tmp==endcoded_ans_sig:
            sig = i
        if tmp==endcoded_ans_bak:
            bak = i
        if tmp==endcoded_ans_ovrl:
            ovrl = i
    p835_personalized_gold_ans[url] = {'sig': sig, 'bak': bak, 'ovrl': ovrl}    
    return p835_personalized_gold_ans[url]


encoded_to_decoded_ans= dict()
def decode_answer(url, encoded):
    if encoded in encoded_to_decoded_ans:
        return encoded_to_decoded_ans[encoded]
    for i in range (1, 6):
        tmp = get_encoded_gold_ans(url, i)
        if tmp == encoded:
            encoded_to_decoded_ans[encoded] = i
            return i
    return None   
            


def check_person_rec_qualification(row):
    correct_ans ={'dist1':'N', 'dist2':'N', 'dist3':'Y', 'dist4':'N', 'dist5':'Y'}
    pref = 'answer.'
    false_list = []
    if row[f'{pref}dist1'] is None or len(row[f'{pref}dist1'].strip()) == 0:
        return True, -1, false_list
    count_false = 0
    for k,v in correct_ans.items():
        if row[f'{pref}{k}'] != v:
            count_false += 1
            false_list.append(k)
    # one wrong answer is accepted
    if count_false > 1:
        return False, count_false, false_list   
    return True, count_false , false_list 

def check_gold_personalized_question(method, row):    
    correct_gq = 0
    try:
        gq_url = row[config["gold_question"]["url_found_in"]]
        #input.gold_sig_ans,input.gold_bak_ans,input.gold_ovrl_ans
        endcoded_ans_sig = row['input.gold_sig_ans_2']
        endcoded_ans_bak = row['input.gold_bak_ans_2']
        endcoded_ans_ovrl = row['input.gold_ovrl_ans_2']

        correct_ans = get_encoded_correct_ans(gq_url, endcoded_ans_sig, endcoded_ans_bak, endcoded_ans_ovrl)
        gq_var = int(config["gold_question"]["variance"])
        suffix = ""
        if "p835" in method:
            # only look at the ovrl for tps.
            suffix = "_ovrl"
        gq_correct_ans = correct_ans['ovrl']
        ans = []
        correct_gq = 1
        for q_name in question_names:
            if gq_url in row[f"answer.{q_name}_url"]:
                # found a gold standard question
                if correct_ans['sig'] is not None and int(row[f"answer.{q_name}_sig"]) not in range(
                    correct_ans['sig'] - gq_var, correct_ans['sig'] + gq_var + 1
                ):
                    correct_gq = 0
                #else:
                    ans.append("sig: "+row[f"answer.{q_name}_sig"]+ ', correct: '+str(correct_ans['sig']))
                
                if correct_ans['bak'] is not None and int(row[f"answer.{q_name}_bak"]) not in range(
                    correct_ans['bak'] - gq_var, correct_ans['bak'] + gq_var + 1
                ):
                    correct_gq = 0
                #else:
                    ans.append("bak: "+ row[f"answer.{q_name}_bak"] + ', correct: '+str(correct_ans['bak']))
                
                if correct_ans['ovrl'] is not None and int(row[f"answer.{q_name}_ovrl"]) not in range(
                    correct_ans['ovrl'] - gq_var, correct_ans['ovrl'] + gq_var + 1
                ):
                    correct_gq = 0
                #else:
                    ans.append("ovrl: "+ row[f"answer.{q_name}_ovrl"] + ', correct: '+str(correct_ans['ovrl']))   
    except:
        return None, None, None
    return correct_gq, gq_url, ans

# Will be called when two gold questions are used
def check_2_gold_personalized_question(method, row):    
    post_fix = ["", '_2']
    #post_fix = [""]
    correct_gq = 1
    ans = []
    urls =''
    rec = {}
    correct = 0
    wrong = 0
    for pf in post_fix:
        try:
            gq_url = row[f'input.gold_url{pf}']
            #input.gold_sig_ans,input.gold_bak_ans,input.gold_ovrl_ans
            endcoded_ans_sig = row[f'input.gold_sig_ans{pf}']
            endcoded_ans_bak = row[f'input.gold_bak_ans{pf}']
            endcoded_ans_ovrl = row[f'input.gold_ovrl_ans{pf}']
            rec[f'url{pf}'] = gq_url
            correct = 1
            correct_ans = get_encoded_correct_ans(gq_url, endcoded_ans_sig, endcoded_ans_bak, endcoded_ans_ovrl)
            gq_var = int(config["gold_question"]["variance"])
            for q_name in question_names:
                if gq_url in row[f"answer.{q_name}_url"]:
                    # found a gold standard question
                    if correct_ans['sig'] is not None and int(row[f"answer.{q_name}_sig"]) not in range(
                        correct_ans['sig'] - gq_var, correct_ans['sig'] + gq_var + 1
                    ):
                        correct_gq = 0
                        rec[f'sig{pf}']= -1
                        correct = 0
                    #else:
                        ans.append(pf+"sig: "+row[f"answer.{q_name}_sig"]+ ', correct: '+str(correct_ans['sig']))
                        if gq_url not in urls:
                            urls += gq_url
                            urls += ','

                    
                    if correct_ans['bak'] is not None and int(row[f"answer.{q_name}_bak"]) not in range(
                        correct_ans['bak'] - gq_var, correct_ans['bak'] + gq_var + 1
                    ):
                        correct_gq = 0
                        rec[f'bak{pf}']= -1
                        correct = 0
                    #else:
                        ans.append(pf+"bak: "+ row[f"answer.{q_name}_bak"] + ', correct: '+str(correct_ans['bak']))
                        if gq_url not in urls:
                            urls += gq_url
                            urls += ','
                    
                    if correct_ans['ovrl'] is not None and int(row[f"answer.{q_name}_ovrl"]) not in range(
                        correct_ans['ovrl'] - gq_var, correct_ans['ovrl'] + gq_var + 1
                    ):
                        correct_gq = 0
                        rec[f'ovrl{pf}']= -1
                        correct = 0
                    #else:
                        ans.append(pf+"ovrl: "+ row[f"answer.{q_name}_ovrl"] + ', correct: '+str(correct_ans['ovrl']))   
                        if gq_url not in urls:
                            urls += gq_url
                            urls += ','
            rec[f'correct{pf}'] = correct
        except:
            return None, None, None, None
    return correct_gq, urls, ans, rec


def check_gold_question_P804(method, row):
    correct_gq = 0
    try:
        gq_url = row[config["gold_question"]["url_found_in"]]
        # Input.gold_sig_ans	Input.gold_ovrl_ans	Input.gold_noise_ans	Input.gold_col_ans	Input.gold_loud_ans	Input.gold_disc_ans	Input.gold_reverb_ans
        # ["_slide_col", "_slide_disc", "_slide_loud", "_slide_noise", "_slide_reverb", "_sig", "_ovrl"]
        #items = ['noise', 'col', 'loud', 'disc', 'reverb', 'sig', 'ovrl']
        items = ['noise', 'col',  'loud', 'disc', 'reverb', 'sig', 'ovrl']
        gq_var = int(config["gold_question"]["variance"])
        given_ans_report = []
        correct_gq = 1
        found_question = False
        rec = {}
        #print(row)
        correct = 0
        wrong = 0
        for q_name in question_names:
            if gq_url in row[f"answer.{q_name}_url"]:
                found_question = True
                rec['url'] = gq_url
                #print("Found the g-question:"+q_name, ', url:', gq_url)
                # found a gold standard question
                for item in items:
                    # check for all subdimensions
                    encoded_correct_ans = row["input.gold_"+item+"_ans"]
                    decodec_correct_ans = decode_answer(gq_url, encoded_correct_ans) 
                    rec[item] = decodec_correct_ans
                    rec[f'{item}_given'] = row[f"answer.{q_name}_{item}"]
                    #print("correct ans:", decodec_correct_ans)
                    #slider = "" if item in ['sig', 'ovrl'] else "_slide"                                            
                    #ans = row[f"answer.{q_name}{slider}_{item}"]
                    ans = row[f"answer.{q_name}_{item}"]
                    #print('Given ans:'+ans)
                    #print(row['assignmentid'])
                    if (decodec_correct_ans is not None) and (int(ans) not in range(
                        decodec_correct_ans - gq_var, decodec_correct_ans + gq_var + 1)):
                        correct_gq = 0
                        given_ans_report.append(f"{item}: "+ans)
                        wrong += 1
                        rec[f'{item}_wrong']= 1
                    else:
                        correct += 1
                        rec[f'{item}_wrong']= 0

        rec['wrong'] = wrong
        rec['correct'] = correct
    except:
        print('#######################################')
        logger.info(re)
        return -1, gq_url, given_ans_report, None
   # if correct_gq == 0:
    #    raise Exception(f"Wrong answer for gq: {gq_url}, {given_ans_report}")  

    return correct_gq, gq_url, given_ans_report, rec
    #return 1, gq_url, given_ans_report, rec

def check2_gold_questions_P804(method, row):
    
    post_fix = ["", '_2']
    #post_fix = [""]
    
    correct_gq_all = 0
    ans = []
    rec = {}
    given_ans_report = []
    items = ['noise', 'col',  'loud', 'disc', 'reverb', 'sig', 'ovrl']
    gq_var = int(config["gold_question"]["variance"])
    for pf in post_fix:        
        try:
            correct_gq = 1
            gq_url = row[f'input.gold_url{pf}']                    
            rec[f'url{pf}'] = gq_url                        
            found_question = False
            
            correct = 0
            wrong = 0
            for q_name in question_names:
                if gq_url in row[f"answer.{q_name}_url"]:
                    found_question = True                   
                    # found a gold standard question
                    for item in items:
                        # check for all subdimensions
                        encoded_correct_ans = row["input.gold_"+item+f"_ans{pf}"]                        
                        decodec_correct_ans = decode_answer(gq_url, encoded_correct_ans)                         
                        rec[f'{item}_{pf}'] = decodec_correct_ans
                        rec[f'{item}_{pf}_given'] = row[f"answer.{q_name}_{item}"]
                        
                        ans = row[f"answer.{q_name}_{item}"]                        
                        
                        if (decodec_correct_ans is not None) and ( len(ans)==0 or (int(float(ans)) not in range(
                            decodec_correct_ans - gq_var, decodec_correct_ans + gq_var + 1))):
                            correct_gq = 0
                            given_ans_report.append(f"{item}_{pf}: "+ans)
                            wrong += 1
                            rec[f'{item}_{pf}_wrong']= 1
                        else:
                            correct += 1
                            rec[f'{item}_{pf}_wrong']= 0
            
                
            if not found_question:
                raise Exception(f"Gold question was not found in rating section: {gq_url}")  
            rec[f'wrong{pf}'] = wrong
            rec[f'correct{pf}'] = correct
            correct_gq_all += correct_gq
        except Exception as e:
            print('#######################################')
            logger.info(e)
            return -1, gq_url, given_ans_report, rec
    # if correct_gq == 0:
        #    raise Exception(f"Wrong answer for gq: {gq_url}, {given_ans_report}")  

    return correct_gq_all, gq_url, given_ans_report, rec
    #return 1, gq_url, given_ans_report, rec


def check_gold_question(method, row):
    """
    Check if the gold_question is answered correctly
    :param row:
    :return:
    """
    correct_gq = 0
    #try:
    gq_url = row[config["gold_question"]["url_found_in"]]
   
    if method ==p835_personalized and "input.gold_url_2" in row:   
        return check_2_gold_personalized_question(method, row)
    if method =="p804":
        if "url2_found_in" in config["gold_question"]:
            return check2_gold_questions_P804(method, row)
        return check_gold_question_P804(method, row)

    # gq_correct_ans = int(float(row[config['gold_question']['ans_found_in']]))
    #  tp_correct_ans = int(float(row[config['trapping']['ans_found_in']]))
    gq_correct_ans = -1
    # check if it is hardcoded correct answer or dynamic one
    if config.has_option("gold_question", "correct_ans"):
        gq_correct_ans = int(config["gold_question"]["correct_ans"])
    elif config.has_option("gold_question", "ans_found_in"):
        gq_correct_ans = int(float(row[config["gold_question"]["ans_found_in"]]))
    else:
        return -1
    gq_var = int(config["gold_question"]["variance"])
    suffix = ""
    if "p835" in method:
        # only look at the ovrl for tps.
        suffix = "_ovrl"
    if method == "echo_impairment_test":
        suffix = "_echo"
    ans = []
    for q_name in question_names:
        if gq_url in row[f"answer.{q_name}_url"]:
            # found a gold standard question
            if int(row[f"answer.{q_name}{suffix}"]) in range(
                gq_correct_ans - gq_var, gq_correct_ans + gq_var + 1
            ):
                correct_gq = 1
                return correct_gq, gq_url, ans, None
            else:
                if "p835" in method:
                    ans.append("sig: "+row[f"answer.{q_name}_sig"])
                    ans.append("bak: "+ row[f"answer.{q_name}_bak"])
                    ans.append("ovrl: "+ row[f"answer.{q_name}_ovrl"])

                    
    #except Exception as e:
    #    print(e)
    #    return None
    return correct_gq, gq_url, ans, None
    


def digitsum(x):
    """
    sum of the digits in a string
    :param x:
    :return:
    """
    total = 0
    for letter in str(x):
        total += int(letter)
    return total


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
    keys = list(config["math"].keys())
    try:
        ans = int(float(output))
    except:
        return False
    # it could be a case that participant typed in the 2 or 3 numbers that they heard rather their sum.
    if ans > 9:
        ans = digitsum(ans)
    try:
        for key in keys:
            if key in input and int(config['math'][key]) == ans:
                return True
    except:
        return False
    return False

def check_qualification_answer(row):
    checked = True
    # TODO hearing test - correct ans should be added in the inputs -update in master script is needed
    
    # check bw contrill
    if "answer.comb_bw1" not in row:
        return checked, ''
    # check if 'bw_min' and 'bw_max' are in config
    if 'bw_min' not in config['acceptance_criteria'] or 'bw_max' not in config['acceptance_criteria']:
        return checked, ''
    
    bw_v2_test_data ={"comb_bw1":'dq', "comb_bw2":'dq', "comb_bw3":'dq', "comb_bw4":'sq', "comb_bw5":'sq'}
    bw_messages= {"comb_bw1":'BW TP failed', "comb_bw2":'SWB failed', "comb_bw3":'FB failed', "comb_bw4":'BW TP failed', "comb_bw5":'BW TP failed'}
    ans_array= [0, 0, 0 ,0, 0]
    msg = ''
    for i in range(1, 6):
        if row[f'answer.comb_bw{i}'] != bw_v2_test_data[f'comb_bw{i}']:            
            msg += bw_messages[f'comb_bw{i}'] + ', '
            ans_array[i-1] = 0
        else:
            ans_array[i-1] = 1
    

    bw_min = config['acceptance_criteria']['bw_min'].upper()
    bw_max = config['acceptance_criteria']['bw_max'].upper()
    if ans_array[0] + ans_array[3] + ans_array[4] !=3:
		#failed in trapping of obvious questions
        return False, msg
    if (bw_min == 'SWB' and ans_array[1] != 1) or (bw_min == 'FB' and ans_array[1]+ans_array[2] != 2):
        return False, msg

    if (bw_max == 'NB-WB' and ans_array[1]+ans_array[2] != 0) or (bw_max == 'SWB' and ans_array[2] != 0):
        return False, msg	

    return checked, msg


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
def data_cleaning(filename, method, wrong_vcodes):
   """
   Data screening process
   :param filename:
   :param method: acr, dcr, or ccr
   :return:
   """
   logger.info('Start by Data Cleaning...')
   with open(filename, encoding="utf8") as csvfile:

    reader = csv.DictReader(csvfile)
    # lowercase the fieldnames
    reader.fieldnames = [field.strip().lower().replace('_slide','') for field in reader.fieldnames]
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
    not_accepted_reasons = []

    rec_list = []
    for row in reader:
        correct_cmp_ans = 0
        #print(row['answer.8_hearing'] is None)
        #print(row['answer.8_hearing'] is None or len(row['answer.8_hearing'].strip()) == 0)
        if 'answer.8_hearing' in row:
            qualification_was_hidden = (row['answer.8_hearing'] is None) or len(row['answer.8_hearing'].strip()) == 0
        else:
            qualification_was_hidden = True
        if "answer.cmp1" in row:
            setup_was_hidden = row['answer.cmp1'] is None or len(row['answer.cmp1'].strip()) == 0
        else:
            setup_was_hidden = True

        d = dict()

        d['worker_id'] = row['workerid']
        d['HITId'] = row['hitid']
        d['assignment'] = row['assignmentid']
        d['status'] = row['assignmentstatus']
        
        d['ip'] = row['x-real-ip'] if 'x-real-ip' in row else None
        d['study_url'] = row['study_url'] if 'study_url' in row else None

        # step1. check if audio of all X questions are played at least once
        d['all_audio_played'] = 1 if check_audio_played(row, method) else 0

        # check qualification if it was shown
        if not qualification_was_hidden:
            check_qualification, msg = check_qualification_answer(row)
            d['qualification'] = 1 if check_qualification else 0
            d['qualification_msg'] = msg
        else: 
            d['qualification'] = None
            d['qualification_msg'] = 'no qualification was shown'
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
        if method == p835_personalized and 'answer.dist1' in row:
            d['speaker_identification'], d['count_false_speaker_id'], d['count_false_list'] = check_person_rec_qualification(row)

        # step 4. check tps
        d['correct_tps'] = check_tps(row, method)
        # step5. check gold_standard, just for acr
        if method in ["acr", "p835", "echo_impairment_test", p835_personalized, 'p804']:
            d["correct_gold_question"],d["gq_url"] ,d["gq_ans"], rec = check_gold_question(method, row)
            if rec is not None:
                rec['HITID'] = row["hitid"]
                rec['worker_id'] = row["workerid"]
                rec['correct_tps'] = d["correct_tps"]
            rec_list.append(rec)
            if  method =="p804" and 'url_2' in rec:
                gold_question_wrong = (1 if rec['wrong']>0 else 0)+ (2 if rec['wrong_2']>0 else 0)
                d["gold_question_wrong"] = gold_question_wrong
                # remove the commnet to only reject on first gold question
                #if rec['wrong']==0:
                #    d["correct_gold_question"] = 1
                if 'url_2' in rec:
                    d['gq_url'] = rec['url']
                    d['gq_url_2'] = rec['url_2'] 
        # step6. check variance in a session rating
        d['variance_in_ratings'] = check_variance(row)
        accept, failures_accept = check_if_session_accepted(d)
        if accept:
            d['accept'] = 1
            d['Approve'] = 'x'
        else:
            d['accept'] = 0
            d['Approve'] = ''
        not_accepted_reasons.extend(failures_accept)
        should_be_used, failures = check_if_session_should_be_used(d)
        d['failures'] = failures
        not_using_further_reasons.extend(failures)
        if should_be_used:
            d['accept_and_use'] = 1
            use_sessions.append(row)
            if 'p835' in method and row['answer.p835_order'] == 'sig_bak':
                count_sig_bak += 1
        else:
            d['accept_and_use'] = 0

        worker_list.append(d)
    tmp_df = pd.DataFrame(rec_list)
    tmp_df.to_csv('detailed_gold_question_performance.csv')
    #
    logger.info(f"Number of submissions: {len(worker_list)}")
    report_file = os.path.splitext(filename)[0] + '_data_cleaning_report.csv'

    approved_file = os.path.splitext(filename)[0] + '_accept.csv'
    rejected_file = os.path.splitext(filename)[0] + '_rejection.csv'

    accept_reject_gui_file = os.path.splitext(filename)[0] + '_accept_reject_gui.csv'
    extending_hits_file = os.path.splitext(filename)[0] + '_extending.csv'
    block_list_file = os.path.splitext(filename)[0] + '_block_list.csv'

    # reject hits when the user performed more than the limit
    worker_list = evaluate_maximum_hits(worker_list)
    # check performance criteria
    # TODO: maybe only for PP835 and P804
    worker_list, use_sessions, num_rej_perform, block_list = evaluate_rater_performance(worker_list, use_sessions, True)
    worker_list, use_sessions, num_not_used_sub_perform, _ = evaluate_rater_performance(worker_list, use_sessions)
    wrong_v_code_freq = check_wrong_vcode_should_block(wrong_vcodes)
    accept_and_use_sessions = [d for d in worker_list if d['accept_and_use'] == 1]
    not_using_further_reasons = []
    for d in worker_list:
        if d['accept'] == 1 and d['accept_and_use'] == 0:
            not_using_further_reasons.extend(d['failures'])

    write_dict_as_csv(worker_list, report_file)
    save_approved_ones(worker_list, approved_file)
    save_rejected_ones(worker_list, rejected_file, wrong_vcodes, not_accepted_reasons, num_rej_perform)
    save_approve_rejected_ones_for_gui(worker_list, accept_reject_gui_file, wrong_vcodes)
    save_hits_to_be_extended(worker_list, extending_hits_file)
    if len(block_list) > 0:
        save_block_list(block_list, block_list_file, wrong_v_code_freq)
    not_used_reasons_list = list(collections.Counter(not_using_further_reasons).items())
    not_used_reasons_list.append(('performance', num_not_used_sub_perform))
    logger.info(f"   {len(accept_and_use_sessions)} answers ({round(len(accept_and_use_sessions)*100/len(worker_list),2)}%) are good to be used further {not_used_reasons_list}")
    logger.info(f"   Data cleaning report is saved in: {report_file}")
    if 'p835' in method:
        logger.info(f"   percentage of 'sig_bak':  {round(count_sig_bak*100/len(accept_and_use_sessions),2)} %")
    return worker_list, use_sessions

# new from p910 
def evaluate_rater_performance(data, use_sessions, reject_on_failure=False):
    """
    Evaluate the workers performance based on the following criteria in cofnig file:
        rater_min_acceptance_rate_current_test
        rater_min_accepted_hits_current_test
    :param data:
    :param use_sessions:
    :param reject_on_failure: if True, check the criteria on [acceptance_criteria] otehrwise check it in the
    [accept_and_use] section of config file.
    :return:
    """
    section = 'acceptance_criteria' if reject_on_failure else 'accept_and_use'

    if ('rater_min_acceptance_rate_current_test' not in config[section]) \
            and ('rater_min_accepted_hits_current_test' not in config[section]):
        logger.info('* Attention: you are using older version of config file. Performance criteria are missing and will not be applied. ')
        return data, use_sessions, 0, []

    df = pd.DataFrame(data)

    # rater_min_accepted_hits_current_test

    grouped = df.groupby(['worker_id', 'accept_and_use']).size().unstack(fill_value=0).reset_index()    
    grouped = grouped.rename(columns={0: 'not_used_count', 1: 'used_count'})
    # check if not_used_count is in grouped
    if 'not_used_count' in grouped.columns:
        grouped['acceptance_rate'] = (grouped['used_count'] * 100)/(grouped['used_count'] + grouped['not_used_count'])
    else:
        grouped['acceptance_rate'] = 100
    #grouped.to_csv('tmp.csv')

    if 'rater_min_acceptance_rate_current_test' in config[section]:
        rater_min_acceptance_rate_current_test = int(config[section]['rater_min_acceptance_rate_current_test'])
    else:
        rater_min_acceptance_rate_current_test = 0

    if 'rater_min_accepted_hits_current_test' in config[section]:
        rater_min_accepted_hits_current_test = int(config[section]['rater_min_accepted_hits_current_test'])
    else:
        rater_min_accepted_hits_current_test = 0

    grouped_rej = grouped[(grouped.acceptance_rate < rater_min_acceptance_rate_current_test)
                      | (grouped.used_count < rater_min_accepted_hits_current_test)]
    n_submission_removed_only_for_performance = grouped_rej['used_count'].sum()
    logger.info(f'{n_submission_removed_only_for_performance} sessions are removed only becuase of performance criteria ({section}).')
    workers_list_to_remove = list(grouped_rej['worker_id'])
    
    result = []
    num_not_used_submissions = 0
    for d in data:
        if d['worker_id'] in workers_list_to_remove:
            d['accept_and_use'] = 0
            d['rater_performance_pass'] = 0
            num_not_used_submissions += 1
            if reject_on_failure:
                d['accept'] = 0
                d['Approve'] = ""
                tmp = grouped_rej[grouped_rej['worker_id'].str.contains(d['worker_id'])]
                if len(d['Reject'])>0:
                    d['Reject'] = d['Reject'] + f" Failed in performance criteria- only {tmp['acceptance_rate'].iloc[0]:.2f}% of submissions passed data cleansing."
                else:
                    d['Reject'] = f"Make sure you follow the instruction: Failed in performance criteria- only { tmp['acceptance_rate'].iloc[0]:.2f}% of submissions passed data cleansing."
        else:
            d['rater_performance_pass'] = 1
        result.append(d)

    u_session_update = []
    for us in use_sessions:
        if us['workerid'] not in workers_list_to_remove:
            u_session_update.append(us)

    block_list = []
    if 'block_rater_if_acceptance_and_used_rate_below' in config[section]:
        tmp = grouped[(grouped.acceptance_rate < int(config[section]['block_rater_if_acceptance_and_used_rate_below']))]
        block_list = list(tmp['worker_id'])

    return result, u_session_update, num_not_used_submissions, block_list




# p835
def evaluate_maximum_hits(data):
    df = pd.DataFrame(data)
    small_df = df[['worker_id']].copy()
    grouped = small_df.groupby(['worker_id']).size().reset_index(name='counts')
    grouped = grouped[grouped.counts > int(config['acceptance_criteria']['allowedMaxHITsInProject'])]
    # grouped.to_csv('out.csv')
    logger.info(f"{len(grouped.index)} workers answered more than the allowedMaxHITsInProject"
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


def save_approve_rejected_ones_for_gui(data, path, wrong_vcodes):
    """
    save approved/rejected in a csv-file to be used in GUI
    :param data:
    :param path:
    :return:
    """
    df = pd.DataFrame(data)
    df = df[df.status == 'Submitted']
    small_df = df[['worker_id','assignment', 'HITId', 'Approve', 'Reject']].copy()
    small_df.rename(columns={'assignment': 'assignmentId', 'worker_id':'WorkerId'}, inplace=True)

    if wrong_vcodes is not None:
        wrong_vcodes_assignments = wrong_vcodes[['WorkerId','AssignmentId', 'HITId']].copy()
        wrong_vcodes_assignments["Approve"] = ""
        wrong_vcodes_assignments["Reject"] = "wrong verification code or incomplete submission"
        wrong_vcodes_assignments.rename(columns={'AssignmentId': 'assignmentId'}, inplace=True)        
        small_df = pd.concat([small_df, wrong_vcodes_assignments], ignore_index=True)

    # Count number of duplicate in assignmentId
    small_df['n_duplicate'] = small_df.groupby('assignmentId')['assignmentId'].transform('size')
    small_df['n_duplicate'] = small_df['n_duplicate'].apply(lambda x: x - 1)
            
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
        logger.info(f'    {c_accepted} answers are accepted')
    else:
        logger.info(f'    overall {c_accepted} answers are accepted, from them {df.shape[0]} were in submitted status')
    small_df = df[['assignment']].copy()
    small_df.rename(columns={'assignment': 'assignmentId'}, inplace=True)
    small_df.to_csv(path, index=False)


def save_block_list(block_list, path, wrong_v_code_freq):
    """
    write the list of workers to be blocked in a csv file.
    :param block_list:
    :param path:
    :return:
    """
    df = pd.DataFrame(block_list, columns=['Worker ID'])
    df['UPDATE BlockStatus'] = "Block"
    df['BlockReason'] = f'Less than {config["acceptance_criteria"]["block_rater_if_acceptance_and_used_rate_below"]}% acceptance rate'

    if wrong_v_code_freq is not None and len(wrong_v_code_freq) > 0:
        df2 = pd.DataFrame(wrong_v_code_freq, columns=['Worker ID'])
        df2['UPDATE BlockStatus'] = "Block"
        df2['BlockReason'] = "Wrong verification code"
        # concat the two dataframes
        df = pd.concat([df, df2], ignore_index=True)
    df.to_csv(path, index=False)


def check_wrong_vcode_should_block(wrong_vcodes):
    if wrong_vcodes is None:
        return []       
    # count the number of wrong verification code per worker
    small_df = wrong_vcodes[['WorkerId']].copy()
    grouped = small_df.groupby(['WorkerId']).size().reset_index(name='counts')
    # get the workers that have more than 5 wrong verification code
    grouped = grouped[grouped.counts >= 5]
    logger.info(f"{len(grouped.index)} workers have more than 5 wrong verification code")
    cheater_workers_list = list(grouped['WorkerId'])
    return cheater_workers_list



def save_rejected_ones(data, path, wrong_vcodes, not_accepted_reasons, num_rej_perform):
    """
    Save the rejected ones in the path
    :param data:
    :param path:
    :return:
    """
    df = pd.DataFrame(data)
    df = df[df.accept == 0]
    c_rejected = df.shape[0]
    if wrong_vcodes is not None:
        c_rejected += len(wrong_vcodes.index)
    df = df[df.status == 'Submitted']
    if df.shape[0] == c_rejected:
        logger.info(f'    {c_rejected} answers are rejected')
    else:
        logger.info(f'    overall {c_rejected} answers are rejected, from them {df.shape[0]} were in submitted status')

    not_accepted_reasons_list = list(collections.Counter(not_accepted_reasons).items())
    if wrong_vcodes is not None:
        not_accepted_reasons_list.append(('Wrong Verification Code', len(wrong_vcodes.index)))

    if num_rej_perform != 0:
        not_accepted_reasons_list.append(('Performance', num_rej_perform))

    logger.info(f'         Rejection reasons: {not_accepted_reasons_list}')

    small_df = df[['assignment', 'Reject']].copy()
    small_df.rename(columns={'assignment': 'assignmentId', 'Reject': 'feedback'}, inplace=True)
    if wrong_vcodes is not None:
        wrong_vcodes_assignments = wrong_vcodes[['AssignmentId']].copy()
        wrong_vcodes_assignments["feedback"] = "Wrong verificatioon code or incomplete submission"
        wrong_vcodes_assignments.rename(columns={'AssignmentId': 'assignmentId'}, inplace=True)
        small_df = pd.concat([small_df, wrong_vcodes_assignments], ignore_index=True)

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
        logger.info('Calculate the quantity bonuses...')
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
        logger.info(f'   Quantity bonuses report is saved in: {path}')
    return merged


def calc_inter_rater_reliability(answer_list, overall_mos, test_method, question_name_suffix, use_condition_level, save_tmp_for_debug=False):
    """
    Calculate the inter_rater reliability for all workers and also average for the study
    :param answer_list:
    :param overall_mos:
    :return:
    """
    mos_name = method_to_mos[f"{test_method}{question_name_suffix}"]

    reliability_list = []
    df = pd.DataFrame(answer_list)
    
    tmp = pd.DataFrame(overall_mos)
    if use_condition_level:
        aggregate_on = 'condition_name'
    else:
        aggregate_on = 'file_url'
        # if it is per file, make sure to consider clips tha has at least 3 votes
        tmp = tmp[tmp['n'] >= 3]    
    c_df = tmp[[aggregate_on, mos_name]].copy()
    c_df.rename(columns={mos_name: 'mos'}, inplace=True)

    candidates = df['workerid'].unique().tolist()

    for worker in candidates:
        # select answers
        worker_answers = df[df['workerid'] == worker].copy()
        votes_p_file, votes_per_condition, _ = transform(test_method, worker_answers.to_dict('records'),
                                                         use_condition_level, True)
        aggregated_data = pd.DataFrame(votes_per_condition if use_condition_level else votes_p_file)

        if len(aggregated_data) > 0:
            merged = pd.merge(aggregated_data, c_df, how='inner', left_on=aggregate_on, right_on=aggregate_on)
            if save_tmp_for_debug:
                merged.to_csv(f'{worker}_{mos_name}.csv')
            # calculate the variance of mos cal in merged dataframe
            v1 , v2 = merged['mos'].var(), merged[mos_name].var()
            if v1== 0 or v2==0 or len(merged.index) < 2:
                r = -2                   
            else:
                try:
                    r = calc_correlation(merged["mos"].tolist(), merged[mos_name].tolist())
                except:
                    r = -2
                    logger.info(f'Error in calculating correlation for {worker}')
                    #merged.to_csv(f'error.csv')
        else:
            r = -2
        entry = {'workerId': worker, 'r': r,'n_samples': len(merged.index)}
        reliability_list.append(entry)
    irr = pd.DataFrame(reliability_list)
    return irr, irr['r'].mean()



# p835
def calc_quality_bonuses(
    quantity_bonus_result,
    answer_list,
    overall_mos,
    conf,
    path,
    n_workers,
    test_method,
    use_condition_level,
):
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
    logger.info('Calculate the quality bonuses...')
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
            votes_p_file, votes_per_condition, _ = transform(test_method, worker_answers.to_dict('records'),
                                                             use_condition_level, True)
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
    logger.info(f'   Quality bonuses report is saved in: {path}')


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
    "acr": "MOS",
    "ccr": "CMOS",
    "dcr": "DMOS",
    "p835_bak": "MOS_BAK",
    "p835_sig": "MOS_SIG",
    "p835_ovrl": "MOS_OVRL",
    "echo_impairment_test_echo": "MOS_ECHO",
    "echo_impairment_test_other": "MOS_OTHER",
    "p835_personalized_enrol": "MOS_ENROL",
    "p835_personalized_bak": "MOS_BAK",
    "p835_personalized_sig": "MOS_SIG",
    "p835_personalized_ovrl": "MOS_OVRL",

    'p804_noise':'MOS_NOISE',
    'p804_col':'MOS_COL', 
    'p804_loud':'MOS_LOUD',
    'p804_disc':'MOS_DISC',
    'p804_reverb':'MOS_REVERB', 
    'p804_sig':'MOS_SIG', 
    'p804_ovrl':'MOS_OVRL',

    "pp835_bak": "MOS_BAK",
    "pp835_sig": "MOS_SIG",
    "pp835_ovrl": "MOS_OVRL",
}

p835_columns = ['condition_name', 'n', 'MOS_BAK', 'MOS_SIG', 'MOS_OVRL', 'std_bak', 'std_sig', 'std_ovrl',
                '95%CI_bak', '95%CI_sig', '95%CI_ovrl']
p835_personalized_columns = [
    "condition_name",
    "n",
    "MOS_BAK",
    "MOS_SIG",
    "MOS_OVRL",
    "std_bak",
    "std_sig",
    "std_ovrl",
    "95%CI_bak",
    "95%CI_sig",
    "95%CI_ovrl",
]

p804_columns = [
    "condition_name",
    "n",
    "MOS_NOISE", "MOS_COL", "MOS_LOUD", "MOS_DISC", "MOS_REVERB", "MOS_SIG", "MOS_OVRL",
    "std_NOISE", "std_col", "std_LOUD", "std_DISC", "std_REVERB", "std_SIG", "std_OVRL",
    "95%CI_NOISE", "95%CI_col", "95%CI_LOUD", "95%CI_DISC", "95%CI_REVERB", "95%CI_SIG", "95%CI_OVRL",
]
echo_impairment_test_columns = ['condition_name', 'n', 'MOS_ECHO', 'MOS_OTHER', 'std_echo', 'std_other',
                '95%CI_echo', '95%CI_other']

question_names = []
question_name_suffix = ""
suffixes = [""]
p835_suffixes = ["_bak", "_sig", "_ovrl"]
p835_personalized_suffixes = ["_enrol", "_bak", "_sig", "_ovrl"]
echo_impairment_test_suffixes = ["_echo", "_other"]
p804_suffixes = ["_col", "_disc", "_loud", "_noise", "_reverb", "_sig", "_ovrl"]
create_per_worker = True


def transform(test_method, sessions, agrregate_on_condition, is_worker_specific):
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
            if (config["trapping"]["url_found_in"] in session and 
                session[config["trapping"]["url_found_in"]]
                == session[f"answer.{question}_url"]
            ):
                continue
            # is it a gold clips
            if (
                test_method in ["acr", "p835", "echo_impairment_test", p835_personalized, 'p804']
                and not found_gold_question
                and session[config["gold_question"]["url_found_in"]]
                == session[f"answer.{question}_url"]
            ):
                found_gold_question = True
                continue
            # for cases where we have two gold clips
            if f'{config["gold_question"]["url_found_in"]}_2' in session and session[f'{config["gold_question"]["url_found_in"]}_2'] == session[f"answer.{question}_url"]:
                continue

            short_file_name = session[f"answer.{question}_url"].rsplit("/", 1)[-1]
            file_name = session[f"answer.{question}_url"]
            if file_name not in data_per_file:
                data_per_file[file_name] = []
            votes = data_per_file[file_name]
            try:
                votes.append(int(float(session[f"answer.{question}{question_name_suffix}"])))
                cond = conv_filename_to_condition(file_name)
                tmp = {
                    "HITId": session["hitid"],
                    "workerid": session["workerid"],
                    "assignment_id": session["assignmentid"],
                    #"creation_time": session["creationtime"],
                    "assignmentstatus": session["assignmentstatus"],
                    #"requesterannotation": session["requesterannotation"],
                    "file": file_name,
                    "short_file_name": file_name.rsplit("/", 1)[-1],
                    "vote": int(float(session[f"answer.{question}{question_name_suffix}"])),
                    "question_type": mos_name,
                }

                tmp.update(cond)
                data_per_worker.append(tmp)
            except Exception as err:
                logger.info(err)
                pass
    # convert the format: one row per file
    group_per_file = []
    condition_detail = {}
    for key in data_per_file.keys():
        tmp = dict()
        votes = data_per_file[key]
        vote_counter = 1
        # apply z-score outlier detection
        if "outlier_removal_clip" in config["accept_and_use"] and (
                config["accept_and_use"]["outlier_removal_clip"].lower()
                in ["true", "1", "t", "y", "yes"]
            ):
                v_len = len(votes)
                if v_len>5:
                    votes = outliers_z_score(votes)
                    v_len_after = len(votes)
                    if v_len != v_len_after:
                        logger.info(
                            f'{v_len-v_len_after} votes are removed, remains {v_len_after}'
                        )

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
            if (not(is_worker_specific) and 'outlier_removal' in config['accept_and_use']) \
                    and (config['accept_and_use']['outlier_removal'].lower() in ['true', '1', 't', 'y', 'yes']):
                v_len = len(votes)
                votes = outliers_z_score(votes)
                v_len_after = len(votes)
                if v_len != v_len_after:
                    logger.info(f'Condition{tmp["condition_name"]}: {v_len-v_len_after} votes are removed, remains {v_len_after}')
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
    if test_method in ["p835", "echo_impairment_test", p835_personalized, 'p804']:
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


def calc_payment_stat(df):
    """
    Calculate the statistics for payments
    :param df:
    :return:
    """
    if df is None or len(df) == 0:
        logger.info('No data to calculate payment statistics')
        return 'No-case', 'No-case'

    # return 0 if Reward not if column
    if 'Reward' not in df.columns:
        if args.rewards is not None:
            df['Reward'] = "$"+args.rewards
        else:
            df['Reward'] = '$0.00' # from Prolific we doing get the rewards in the csv file
    word_duration_col = "work_duration_sec" if 'WorkTimeInSeconds' not in df.columns else 'WorkTimeInSeconds'
    if word_duration_col not in df.columns:
        # internal run
        return None, None
    if 'Answer.time_page_hidden_sec' in df.columns:

        #df['Answer.time_page_hidden_sec'].where(df['Answer.time_page_hidden_sec'] < 3600, 0, inplace=True)
        # set all values smaller than 3600 to 0
        df['Answer.time_page_hidden_sec'] = np.where(df['Answer.time_page_hidden_sec'] < 3600, 0, df['Answer.time_page_hidden_sec'])
        df['time_diff'] = df[word_duration_col] - df['Answer.time_page_hidden_sec']
        median_time_in_sec = df["time_diff"].median()
    else:
        median_time_in_sec = df[word_duration_col].median()
        
    payment_text = df['Reward'].values[0]
    paymnet = re.findall(r"\d+\.\d+", payment_text)

    avg_pay = 3600*float(paymnet[0])/median_time_in_sec
    formatted_time = time.strftime("%M:%S", time.gmtime(median_time_in_sec))

    return formatted_time, avg_pay


def calc_stats(input_file):
    """
    calc the statistics considering the time worker spend
    :param input_file:
    :return:
    """

    df = pd.read_csv(input_file, low_memory=False)
    df_full = df.copy()
    overall_time, overall_pay = calc_payment_stat(df)

    # full study, all sections were shown
    df_full = df_full[~df_full['Answer.2_birth_year'].isna()]
    full_time, full_pay = calc_payment_stat(df_full)

    # no qual
    df_no_qual = df[df['Answer.2_birth_year'].isna()]
    df_no_qual_no_setup = df_no_qual[df_no_qual['Answer.Math'].isna()]
    # TODO: update for other methods
    if test_method in ['p835', 'multi', 'p804', p835_personalized]:
        only_rating = df_no_qual_no_setup[df_no_qual_no_setup['Answer.t1_ovrl'].isna()].copy()
    else:
        only_rating = df_no_qual_no_setup[df_no_qual_no_setup['Answer.t1'].isna()].copy()

    if len(only_rating)>0:
        only_r_time, only_r_pay = calc_payment_stat(only_rating)
    else:
        only_r_time = 'No-case'
        only_r_pay = 'No-case'
    data = {'Case': ['All submissions', 'All sections', 'Only rating'],
            'Percent of submissions': [1, len(df_full.index)/len(df.index), len(only_rating.index)/len(df.index)],
            'Work duration (median) MM:SS': [overall_time, full_time, only_r_time ],
            'payment per hour ($)': [overall_pay, full_pay, only_r_pay]}
    stat = pd.DataFrame.from_dict(data)
    logger.info('Payment statistics:')
    logger.info(stat.to_string(index=False))

def calc_correlation(cs, lab, spearman=False):
    """
    calc the spearman's correlation
    :param cs:
    :param lab:
    :return:
    """
    if spearman:
        rho, pval = spearmanr(cs, lab)
        return rho
    
    r, pval = pearsonr(cs, lab)
    return r


def number_of_uniqe_workers(answers):
    """
    return numbe rof unique workers
    :param answers:
    :return:
    """
    df = pd.DataFrame(answers)
    df.drop_duplicates('worker_id', keep='first', inplace=True)
    return len(df)


def get_ans_suffixes(test_method):
    if "p835" in test_method:
        question_name_suffix = p835_suffixes[2]
        suffixes = p835_suffixes
    elif test_method == "echo_impairment_test":
        question_name_suffix = echo_impairment_test_suffixes[1]
        suffixes = echo_impairment_test_suffixes
    elif test_method == p835_personalized:
        question_name_suffix = p835_personalized_suffixes[3]
        suffixes = p835_personalized_suffixes
    elif test_method == "p804":
        question_name_suffix = p804_suffixes[6]
        suffixes = p804_suffixes
    else:
        suffixes = [""]
        question_name_suffix= ""
    return suffixes, question_name_suffix

def combine_prolific_hit_server(prolific_ans_path, hitapp_ans_path):
    """
    Combine the answers from the Prolific and the HIT_APP Server
    :param amt_ans_path:
    :param hitapp_ans_path:
    :return:
    """
    prolific_ans = pd.read_csv(prolific_ans_path, low_memory=False)
    hitapp_ans = pd.read_csv(hitapp_ans_path, low_memory=False)
    # copy index as id column
    hitapp_ans['h_id'] = hitapp_ans.index
    prolific_ans['p_id'] = prolific_ans.index   

    columns_to_remove = prolific_ans.columns.difference(['Submission id','Participant id', 'Completion code', 'Country of birth',
                                             'Country of residence', 'Ethnicity simplified', 'Language',
                                             'Nationality', 'Primary language', 'Sex', 'Time taken', 'Total approvals', 'URL'])
    
    prolific_ans.drop(columns=columns_to_remove, inplace=True)
    
    
    hitapp_ans["hitapp_workerid"] = hitapp_ans["WorkerId"]
    hitapp_ans["hitapp_assignmentid"] = hitapp_ans["AssignmentId"].str.lower()
    hitapp_ans["hitapp_hitid"] = hitapp_ans["HITId"]
    hitapp_ans["hitapp_hittypeid"] = hitapp_ans["HITTypeId"]
    hitapp_ans["HITTypeId"] = hitapp_ans["Answer.studyId"]
    hitapp_ans.rename(columns={"work_duration_sec": "hitapp_work_duration_sec"},  inplace=True)

    # cut rows with no browser_info value from hitapp and save them separately. 
    # These rows are the ones that are not submitted by the workers
    hitapp_ans_incomplete = hitapp_ans[hitapp_ans['Answer.browser_info'].isna()]
    hitapp_ans = hitapp_ans[~hitapp_ans['Answer.browser_info'].isna()]
    hitapp_ans_incomplete.to_csv(os.path.splitext(hitapp_ans_path)[0] + '_incomplete_submissions.csv', index=False)
    unique_assignments = hitapp_ans_incomplete['hitapp_assignmentid'].unique()
    # print the size
    logger.info(f"** {len(unique_assignments)} submissions are not completed by the workers.")
    
    # prolific rename columsn
    prolific_ans.rename(columns={"Participant id": "prolific_participant_id",
                               "Completion code": "Answer.v_code",
                               'Time taken': "WorkTimeInSeconds", 
                               'Submission id':'prolific_submission_id', 
                               'Total approvals':'prolific_total_approvals',
                               'URL':'study_url'},  inplace=True)
    
    # marke prolific_ans to remove when study_url is nan and lenght of Answer.v_code is not 32 
    prolific_ans['to_remove'] = prolific_ans['study_url'].isna() & (prolific_ans['Answer.v_code'].str.strip().str.len() != 32)
    # drop the rows
    prolific_ans.drop(prolific_ans[prolific_ans['to_remove']].index, inplace=True)
    # remove the to_remove column
    prolific_ans.drop(columns=['to_remove'], inplace=True)

    # drop rows with no URL, when the concent is revoked the url is empty
    #prolific_ans.dropna(subset=['study_url'], inplace=True)
   
    # check for duplicates in prolific_submission_id and hitapp_assignmentid and keep first
    prolific_ans['prolific_submission_id'] = prolific_ans['prolific_submission_id'].str.strip().str.lower()
    count_duplicate_prolific = prolific_ans['prolific_submission_id'].duplicated(keep='first')
    count_duplicate_hitapp = hitapp_ans['hitapp_assignmentid'].duplicated(keep='first')
    if count_duplicate_prolific.any():
        logger.info(f"** {len(prolific_ans[count_duplicate_prolific])} duplicates in the Prolific data.")
        # save the duplicates in a separate file
        prolific_ans[count_duplicate_prolific].to_csv(prolific_ans_path.replace('.csv' , '_duplicate_submission_id.csv'), index=False)
        prolific_ans.drop_duplicates(subset=['prolific_submission_id'], keep='first', inplace=True)
    if count_duplicate_hitapp.any():
        logger.info(f"** {len(hitapp_ans[count_duplicate_hitapp])} duplicates in the HITAPP data.")
        # save the duplicates in a separate file
        hitapp_ans[count_duplicate_hitapp].to_csv(hitapp_ans_path.replace('.csv' , '_duplicate_assignment_id.csv'), index=False)
        hitapp_ans.drop_duplicates(subset=['hitapp_assignmentid'], keep='first', inplace=True)   

    # check if there are submission without conuter part key in hitapp servers
    #not_in_hitapp = prolific_ans[~prolific_ans['Answer.v_code'].isin(hitapp_ans.v_code)]
    not_in_hitapp = prolific_ans[~prolific_ans['prolific_submission_id'].isin(hitapp_ans.hitapp_assignmentid)].copy()
    # print the lenght
    logger.info(f"** {len(not_in_hitapp)} submissions are not found in the HITAPP server.")
    # Todo check if it can be adapted
    #recover_submission_withoiut_matching_vcode(hitapp_ans, amt_ans, not_in_hitapp)

    # print number of rows for both dataframes
    logger.info(f"** {len(prolific_ans)} rows in the Prolific data.")
    logger.info(f"** {len(hitapp_ans)} rows in the HITAPP server data.")
    #merged = pd.merge(hitapp_ans, prolific_ans, left_on='v_code', right_on='Answer.v_code')
    merged = pd.merge(hitapp_ans, prolific_ans, left_on='hitapp_assignmentid', right_on='prolific_submission_id')
    # save as tmp
    merged.to_csv(os.path.splitext(hitapp_ans_path)[0] + '_tmp_merged.csv', index=False)

    columns_to_remove = ['Answer.v_code']
    if "work_duration_sec" not in merged.columns:
        merged.rename(columns={"WorkTimeInSeconds": "work_duration_sec"}, inplace=True)
    else:
        columns_to_remove.append("WorkTimeInSeconds")
    merged.drop(columns=columns_to_remove, inplace=True)

    merged_ans_path = os.path.splitext(hitapp_ans_path)[0] + '_merged.csv'
    merged.to_csv(merged_ans_path, index=False)

    # filter hitapp_ans and only keep the ones that are not in merged using the id column
    hitapp_ans_not_found_in_amt = hitapp_ans[~hitapp_ans['h_id'].isin(merged['h_id'])]
    hitapp_ans_not_found_in_amt.to_csv(os.path.splitext(hitapp_ans_path)[0] + '_not_found_in_prolific.csv', index=False)
    # print the size
    logger.info(f"** {len(hitapp_ans_not_found_in_amt)} submissions in HITAPP data are not found in the Prolific data.")

    # add WorkerId and AssignmentId to the not_in_hitapp dataframe
    not_in_hitapp['WorkerId'] = not_in_hitapp['prolific_participant_id']
    not_in_hitapp['AssignmentId'] = not_in_hitapp['prolific_submission_id']

    # last part of prolific_export_68114a150c74b353a03bfd9e.csv
    hitgroup_id =  os.path.basename(prolific_ans_path).split('_')[-1].split('.')[0]
    not_in_hitapp['HITId'] = 'created_'+hitgroup_id+not_in_hitapp['AssignmentId']    
    
    return merged_ans_path, not_in_hitapp

def analyze_results(config, test_method, answer_path,prolific_ans_path, list_of_req, quality_bonus):
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
    global suffixes
    suffixes, question_name_suffix = get_ans_suffixes(test_method)
    all_data_per_worker = []
    if prolific_ans_path:
        answer_path, wrong_v_code = combine_prolific_hit_server(prolific_ans_path, answer_path)
    # clean the data
    full_data, accepted_sessions = data_cleaning(answer_path, test_method, wrong_v_code)
    n_workers = number_of_uniqe_workers(full_data)
    logger.info(f"{n_workers} workers participated in this batch.")
    calc_stats(answer_path)
    irr = []

    # clean data based on IRR
    if config.has_option("accept_and_use", "rater_min_irr"):
        logger.info('Checking inter-rater reliability...')
        rater_min_irr = config.getfloat("accept_and_use", "rater_min_irr")
        workers_to_remove = []
        for suffix in suffixes:
            question_name_suffix = suffix
            
            use_condition_level = config.has_option("general", "condition_pattern")
            
            votes_per_file, vote_per_condition, data_per_worker = transform(
                test_method,
                accepted_sessions,
                config.has_option("general", "condition_pattern"),
                False,
            )            
            votes_to_use = votes_per_file
            #save_tmp_for_debug = True if 'ovrl' in suffix else False
            save_tmp_for_debug = False
            inter_rate_reliability, avg_irr = calc_inter_rater_reliability(accepted_sessions, votes_to_use, test_method, question_name_suffix,
            False, save_tmp_for_debug=save_tmp_for_debug)

            # select all worker with IRR > 0.7
            # experimental: only remove workers on sig and ovrl questions. For other if r = -2 (no variance) remove
            irr_workers =[]
            if 'sig' in suffix or 'ovrl' in suffix:
                irr_workers = inter_rate_reliability[inter_rate_reliability['r'] <rater_min_irr]['workerId'].tolist()
            workers_to_remove.extend(irr_workers)

        #remove duplicated from list
        workers_to_remove = list(set(workers_to_remove))
        #print(workers_to_remove)
        logger.info(f'{len(workers_to_remove)} workers with IRR < {rater_min_irr} will be removed')
        # remove workers with low IRR
        u_session_update = []
        for us in accepted_sessions:
            if us['workerid'] not in workers_to_remove:
                u_session_update.append(us)
        logger.info(f' {len(accepted_sessions) - len(u_session_update)} sessions removed due to low IRR')
        accepted_sessions = u_session_update
        logger.info(f' {len(accepted_sessions) } ({round(len(accepted_sessions)*100/len(full_data),2)}%) sessions are remained')

    # votes_per_file, votes_per_condition = transform(accepted_sessions)
    if len(accepted_sessions) > 1:
        condition_set = []
        for suffix in suffixes:
            question_name_suffix = suffix
            logger.info(
                "Transforming data (the ones with 'accepted_and_use' ==1 --> group per clip"
            )
            use_condition_level = config.has_option("general", "condition_pattern")
            
            votes_per_file, vote_per_condition, data_per_worker = transform(
                test_method,
                accepted_sessions,
                config.has_option("general", "condition_pattern"),
                False,
            )
            
            all_data_per_worker.extend(data_per_worker)

            votes_per_file_path = (
                os.path.splitext(answer_path)[0]
                + f"_votes_per_clip{question_name_suffix}.csv"
            )
            votes_per_cond_path = (
                os.path.splitext(answer_path)[0]
                + f"_votes_per_cond{question_name_suffix}.csv"
            )

            condition_keys = []
            if config.has_option("general", "condition_pattern"):
                condition_keys = config["general"]["condition_keys"].split(",")
                votes_per_file = sorted(
                    votes_per_file, key=lambda i: i[condition_keys[0]]
                )
                condition_keys.append("Unknown")
            headers = create_headers_for_per_file_report(test_method, condition_keys)
            
            write_dict_as_csv(votes_per_file, votes_per_file_path, headers=headers)
            logger.info(f'   Votes per files are saved in: {votes_per_file_path}')
            if use_condition_level:
                vote_per_condition = sorted(vote_per_condition, key=lambda i: i['condition_name'])
                write_dict_as_csv(vote_per_condition, votes_per_cond_path)
                logger.info(f'   Votes per files are saved in: {votes_per_cond_path}')
                condition_set.append(pd.DataFrame(vote_per_condition))
            if create_per_worker:
                write_dict_as_csv(
                    data_per_worker,
                    os.path.splitext(answer_path)[0]
                    + f"_votes_per_worker_{question_name_suffix}.csv",
                )
            # Inter-rater reliability in clip level
            """
            votes_to_use = votes_per_file
            inter_rate_reliability, avg_irr = calc_inter_rater_reliability(accepted_sessions, votes_to_use, test_method, question_name_suffix,
            False)
            """                                                                
            votes_to_use = votes_per_file
            inter_rate_reliability, avg_irr = calc_inter_rater_reliability(accepted_sessions, votes_to_use, test_method, question_name_suffix,
            False)

            irr_path = os.path.splitext(answer_path)[0] + f'_{question_name_suffix}_irr_report.csv'
            inter_rate_reliability.to_csv(irr_path, index=False)
            irr.append({'scale': question_name_suffix.replace('_',''), 'avg_irr':avg_irr})
            
            

        df_irr_summary = pd.DataFrame(irr)
        df_irr_summary.to_csv(os.path.splitext(answer_path)[0] + f'_irr_summary.csv', index=False)

        if use_condition_level and len(suffixes) > 1:
            # aggregate multiple conditions into one file for p.835
            full_set_conditions = None
            for df in condition_set:
                if full_set_conditions is None:
                    full_set_conditions = df
                else:
                    # get list of shared columns between two dataframes
                    shared_columns = list(set(full_set_conditions.columns).intersection(df.columns))
                    #drop condition_name from the shared_columns
                    shared_columns.remove('condition_name')
                    # remove shared_columns from df
                    df.drop(columns=shared_columns, inplace=True)
                    full_set_conditions = pd.merge(full_set_conditions, df, left_on="condition_name", right_on="condition_name")                    

            votes_per_all_cond_path = (
                os.path.splitext(answer_path)[0] + f"_votes_per_cond_all.csv"
            )
            if test_method == p835_personalized:
                column_names = p835_personalized_columns
            elif test_method == "p835" :
                column_names = p835_columns
            elif test_method == "p804":
                column_names = p804_columns
            else :
                column_names= echo_impairment_test_columns
            # todo debug
            if test_method != "p804":
                full_set_conditions.to_csv(
                    votes_per_all_cond_path,
                    index=False,
                    columns=column_names,
                )

        # add aggregated results per all scales
        if len(suffixes) > 1:
            merged = None
            merged_cond = None
            for item in suffixes:
                votes_per_file_path = (os.path.splitext(answer_path)[0]+ f"_votes_per_clip{item}.csv")
                df = pd.read_csv(votes_per_file_path)
                df = df[['file_url','n' ,f'MOS{item.upper()}', f'std{item}', f'95%CI{item}']]                
                if merged is None:
                    merged = df.copy()                    
                else:
                    df = df.drop(['n'], axis=1)
                    merged =  pd.merge(merged, df, on='file_url')   
                if use_condition_level:
                    votes_per_cond_path = (os.path.splitext(answer_path)[0]+ f"_votes_per_cond{item}.csv")
                    df = pd.read_csv(votes_per_cond_path)
                    df = df[['condition_name','n' ,f'MOS{item.upper()}', f'std{item}', f'95%CI{item}']]                
                    if merged_cond is None:
                        merged_cond = df.copy()                    
                    else:
                        df = df.drop(['n'], axis=1)
                        merged_cond =  pd.merge(merged_cond, df, on='condition_name')   

            merged.to_csv(os.path.splitext(answer_path)[0]+ f"_votes_per_clip_all-scales.csv", index=False)
            if use_condition_level:
                merged_cond.sort_index(inplace = True, axis = 1)
                merged_cond['M'] = ((merged_cond['MOS_SIG']-1) / 4 + (merged_cond['MOS_OVRL']-1) /4 ) / 2
                merged_cond.to_csv(os.path.splitext(answer_path)[0]+ f"_votes_per_cond_all-scales.csv", index=False)

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
            calc_quality_bonuses(
                quantity_bonus_df,
                accepted_sessions,
                votes_to_use,
                config,
                quality_bonus_path,
                n_workers,
                test_method,
                use_condition_level,
            )
    all_votes_per_file_path = (
                os.path.splitext(answer_path)[0]
                + f"_all_votes_per_clip.csv"
            )
    write_dict_as_csv(all_data_per_worker, all_votes_per_file_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Utility script to evaluate answers to the P.808 subjective test."
    )
    # Configuration: read it from mturk.cfg
    parser.add_argument("--cfg", required=True,
                        help="Contains the configurations see acr_result_parser.cfg as an example")
    parser.add_argument("--method", required=True,
                        help=f"one of the test methods: 'acr', 'dcr', 'ccr', 'p835', p804 or '{p835_personalized}'",)
    parser.add_argument("--answers", required=True,
                        help="Answers csv file, path relative to current directory (either from AMT or HITApp server)")
    parser.add_argument("--prolific_answers",
                        help="Answers csv file from Prolific (demographic data), path relative to current directory")

    parser.add_argument('--quantity_bonus', help="specify status of answers which should be counted when calculating "
                                                " the amount of quantity bonus. All answers will be used to check "
                                                "eligibility of worker, but those with the selected status here will "
                                                "be used to calculate the amount of bonus. A comma separated list:"
                                                " all|submitted. Default: submitted",
                        default="submitted")

    parser.add_argument('--quality_bonus', help="Quality bonus will be calculated. Just use it with your final download"
                                                " of answers and when the project is completed", action="store_true")
    parser.add_argument('--rewards', help="If using Prolific the amount of rewards are not included in CSV file, specifiz it here like 2.10"
                                                , required=False, default=None)
    #parser.add_argument('--adc' , help="name of Advance Data Cleaning script. If set, the answers will be filtered by that as well",  default=None)
    
    args = parser.parse_args()
    methods = ['acr', 'dcr', 'ccr', 'p835', 'p804','echo_impairment_test', p835_personalized]
    test_method = args.method.lower()
    assert test_method in methods, f"No such a method supported, please select between 'acr', 'dcr', 'ccr', 'p804' or 'p835' "

    cfg_path = args.cfg
    assert os.path.exists(cfg_path), f"No configuration file at [{cfg_path}]"
    config = CP.ConfigParser()
    config.read(cfg_path)

    assert (args.answers is not None), f"--answers  are required]"
    # answer_path = os.path.join(os.path.dirname(__file__), args.answers)
    answer_path = args.answers

    if args.prolific_answers is None:     
        prolific_ans_path = None
    else:
        prolific_ans_path = args.prolific_answers

    if prolific_ans_path is None:
        warnings.warn("If you are using HIT App server, Note: the WorkerId, HITIds, ect. are internal "
                      "HIT APP server ids. Therefore bonus reports cannot be used." )

    assert os.path.exists(answer_path), f"No input file found in [{answer_path}]"
    list_of_possible_status = ['all', 'submitted']

    list_of_req = args.quantity_bonus.lower().split(',')
    for req in list_of_req:
        assert req.strip() in list_of_possible_status, f"unknown status {req} used in --quantity_bonus"

    np.seterr(divide='ignore', invalid='ignore')
    question_names = [f"q{i}" for i in range(1, int(config['general']['number_of_questions_in_rating']) + 1)]
    # setup the logging system
    logger = logging.getLogger("my_logger")
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    file_log_path = os.path.splitext(answer_path)[0] + f'_logs.txt'
    file_handler = logging.FileHandler(file_log_path)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.info(f"Start analyzing the results of {test_method} test")
    # start
    analyze_results(config, test_method,  answer_path,prolific_ans_path, list_of_req, args.quality_bonus)