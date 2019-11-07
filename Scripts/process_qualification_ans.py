"""
@author: Babak Naderi
"""
import argparse
import csv
import os

# configuration which explains how to decide whether accept/reject one worker
config = {
    # criteria to accept/reject one workers
    'acceptance_criteria': {
        # which questions to include
        'consider_fileds': ['3_mother_tongue', '4_ld', '7_working_area', '8_hearing'],
        # how many of answers to hearing test should be correct
        'correct_hearing_test_bigger_equal': 3
    },
    # correct answers
    '3_mother_tongue': ['english','en'],
    '4_ld': ['in-ear', 'over-ear'],
    '5_last_subjective': ['7d', '30d', 'nn'],
    '6_audio_test': ['7d', '30d', 'nn'],
    '7_working_area': ['N'],
    '8_hearing': ['normal'],
    'hearing_test': {
        'num1': '289',
        'num2': '246',
        'num3': '626',
        'num4': '802',
        'num5': '913'
    }
}


def check_mother_tongue(ans):
    """
    check if the answer is in accepted monther_tongues
    """
    return ans.strip().lower() in config['3_mother_tongue']


def check_listening_device(ans):
    """
    check if the answer contains of of accepted listening_devices
    """
    for device in config['4_ld']:
        if device in ans:
            return True
    return False


def check_last_subjective_test(ans):
    """
    check if the last_subjective_test performed by user was far enough
    """
    return ans in config['5_last_subjective']


def check_last_audio_test(ans):
    """
    check if the last_audio_test performed by user was far enough
    """
    return ans in config['6_audio_test']


def check_working_experities(ans):
    """
    user should not have working experince in this area
    """
    return ans in config['7_working_area']


def check_hearing_question(ans):
    """
    check the answer to self-judgment on hearing ability
    """
    return ans in config['8_hearing']


def check_hearing_test(num1,num2,num3,num4,num5):
    """
    check how many answers to hearing test was correct
    """
    correct_ans = 0
    nums = config['hearing_test']
    if num1 == nums['num1']: correct_ans += 1
    if num2 == nums['num2']: correct_ans += 1
    if num3 == nums['num3']: correct_ans += 1
    if num4 == nums['num4']: correct_ans += 1
    if num5 == nums['num5']: correct_ans += 1

    return correct_ans


def evaluate_asnwers(answe_path):
    """
    check answers given by crowdworkers to Qualification.html given rules specified in config object.
    It  prints a report on number of accepted and reject answers, detailed report on why, and write
    the list of workerIds whome their answers are accepte din [answe_path}_output.csv
    """

    report = {}
    accepted_list = []
    n_rejections = 0
    fields_to_consider = config['acceptance_criteria']['consider_fileds']
    for field in fields_to_consider:
        report[field] = 0
    report['hearing_test'] = 0
    full_list=[]

    with open(answe_path, mode='r') as input:
        reader = csv.DictReader(input)
        for row in reader:
            judge={}
            accept = True
            if '3_mother_tongue' in fields_to_consider:
                r = check_mother_tongue(row['Answer.3_mother_tongue'])
                accept = accept and r
                if not r: report['3_mother_tongue'] += 1
                judge['3_'] = r
            if '4_ld' in fields_to_consider:
                r = check_listening_device(row['Answer.4_ld'])
                accept = accept and r
                if not r: report['4_ld'] += 1
                judge['4_'] = r
            if '5_last_subjective' in fields_to_consider:
                r = check_last_subjective_test(row['Answer.5_last_subjective'])
                accept = accept and r
                if not r: report['5_last_subjective'] += 1
                judge['5'] = r
            if '6_audio_test' in fields_to_consider:
                r = check_last_audio_test(row['Answer.6_audio_test'])
                accept = accept and r
                if not r: report['6_audio_test'] += 1
                judge['6_'] = r
            if '7_working_area' in fields_to_consider:
                r = check_working_experities(row['Answer.7_working_area'])
                accept = accept and r
                if not r: report['7_working_area'] += 1
                judge['7_'] = r

            if '8_hearing' in fields_to_consider:
                r = check_hearing_question(row['Answer.8_hearing'])
                accept = accept and r
                if not r: report['8_hearing'] += 1
                judge['8_'] = r

            n_correct = check_hearing_test(row['Answer.num1'],
                                           row['Answer.num2'],
                                           row['Answer.num3'],
                                           row['Answer.num4'],
                                           row['Answer.num5'])
            if n_correct < config['acceptance_criteria']['correct_hearing_test_bigger_equal']:
                accept = False
                report['hearing_test'] += 1
            judge['9_'] = n_correct

            if accept:
                accepted_list.append(row['WorkerId'])
                judge['finall_'] = 'accept'
            else:
                n_rejections += 1
                judge['finall_'] = 'reject'
            judge['wid'] = row['WorkerId']
            full_list.append(judge)

    print(f'In total reject {n_rejections} and accept {len(accepted_list)}')
    print('detailed report')
    print(report)

    output_file_path = os.path.splitext(answe_path)[0] + '_output.csv'
    '''
    with open(output_file_path, 'w', newline='') as output_file:
        headers_written = False
        for f in full_list:
            if not headers_written:
                writer = csv.DictWriter(output_file, fieldnames=sorted(f))
                headers_written = True
                writer.writeheader()
            writer.writerow(f)
    '''
    with open(output_file_path, 'w', newline='') as output_file:
        writer = csv.writer(output_file)
        writer.writerow(['WorkerId'])
        for wid in accepted_list:
                    writer.writerow([wid])

    print(f'WorkerIds for accepted ones are saved in {output_file_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Utility script to handle a MTurk study.')

    parser.add_argument("--check", type=str,
                        help="Check answers of the qualification job"
                             "(input: Batch_xxx_results.csv)")
    args = parser.parse_args()
    answers_path = os.path.join(os.path.dirname(__file__), args.check)
    assert os.path.exists(answers_path), f"No input file found in [{answers_path}]"

    evaluate_asnwers(answers_path)
