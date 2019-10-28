"""
@author: Babak Naderi
"""
import argparse
import boto3
import json
import os
import configparser as CP
import csv

"""
Sends an email to list of workers given the worker ids. 
Configuration should be set in section "send_emaiil" in the mturk.cfg file
"""


def send_message(client, cfg):
    worker_ids = cfg['worker_ids'].replace(' ','').split(',')
    # in each call it is possible to send up to 100 messages
    worker_pack_size= 100
    chunked_worker_ids = [worker_ids[i:i + worker_pack_size] for i in range(0, len(worker_ids), worker_pack_size)]
    for woker_group in chunked_worker_ids:
        response = client.notify_workers(
                 Subject=cfg['subject'],
                 MessageText=cfg['message'],
                 WorkerIds=woker_group
         )
        print(json.dumps(response))

"""
Assign bonuses to group of workers.
A csv file with following columns need to be provided:
workerId, assignmentId, bonusAmount, reason  
"""


def assign_bonus(client, bonus_list_path):
    print('send bonus')
    with open(bonus_list_path, mode='r') as bonus_list:
        reader = csv.DictReader(bonus_list)
        line_count = 0
        for row in reader:
            if line_count == 0:
                assert 'workerId' in row,  f"No column found with workerId in [{bonus_list_path}]"
                assert 'assignmentId' in row,  f"No column found with assignmentId in [{bonus_list_path}]"
                assert 'bonusAmount' in row, f"No column found with bonusAmount in [{bonus_list_path}]"
                assert 'reason' in row,  f"No column found with reason in [{bonus_list_path}]"
            else:
                response = client.send_bonus(
                    WorkerId=row['workerId'],
                    BonusAmount=row['bonusAmount'],
                    AssignmentId=row['assignmentId'],
                    Reason=row['reason']
                )
                print(f'\tsend ${row["bonusAmount"]} to {row["workerId"]}({row["assignmentId"]}):')
                print(response)
            line_count += 1
        print(f'Processed {line_count} lines.')

"""
Assign bonuses to group of workers.
A csv file with following columns need to be provided:
workerId, assignmentId, bonusAmount, reason  
"""


def approve_reject_assignments(client, assignment_path, approve):
    if approve:
        print('Approving assignments')
    else:
        print('Rejecting assignments')
    with open(assignment_path, mode='r') as assignment_list:
        reader = csv.DictReader(assignment_list)
        line_count = 0
        for row in reader:
            if line_count == 0:
                assert 'assignmentId' in row,  f"No column found with assignmentId in [{assignment_path}]"
                if not approve:
                    assert 'feedback' in row, f"No column found with feedback in [{assignment_path}]"
            else:
                if approve:
                    # approving
                    response = client.approve_assignment(
                        AssignmentId=row['assignmentId']
                    )
                    print(f'\t Approving assignment ${row["assignmentId"]}:')
                    print(response)
                else:
                    # rejecting
                    response = client.reject_assignment(
                        AssignmentId=row['assignmentId'],
                        RequesterFeedback=row['feedback']
                    )
                    print(f'\t Rejecting assignment ${row["assignmentId"]}:')
                    print(response)
            line_count += 1
        print(f'Processed {line_count} lines.')




def create_hit(client, cfg, path_to_input_csv):
    if cfg['use_assignment_review_policy']:
        assignment_review_policy = {
        'PolicyName': 'ScoreMyKnownAnswers/2011-09-01',
        'Parameters': [
            {'Key': "AnswerKey",
             'MapEntries': [
                 {'Key': f"{cfg['arp_question_name']}", 'Values': [f"{cfg['arp_correct_answer']}"]}
             ]},
            {'Key': "RejectIfKnownAnswerScoreIsLessThan",
             'Values': [f"{cfg['arp_RejectIfKnownAnswerScoreIsLessThan']}"]
             },{
                'Key': "RejectReason",
                'Values': [f"{cfg['arp_RejectReason']}"]
             },{
                'Key': "ExtendIfKnownAnswerScoreIsLessThan",
                'Values': [f"{cfg['arp_ExtendIfKnownAnswerScoreIsLessThan']}"]
             }
        ]

        }
    else:
        assignment_review_policy= None


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Utility script to handle a MTurk study.')
    # Configuration: read it from mturk.cfg
    parser.add_argument("--cfg", default="mturk.cfg",
                        help="Read mturk.cfg for all the details")
    parser.add_argument("send_emails", nargs='?', help="send emails (configuration is needed)")
    parser.add_argument("--send_bonus", type=str, help="give bonus to a group of worker. Path to a csv file "
                                                       "(columns: workerId, assignmentId, bonusAmount, reason  )")

    parser.add_argument("--approve", type=str,
                        help="Approve all assignments found in the input csv file. Path to a csv file "
                             "(columns: assignmentId)")
    parser.add_argument("--reject", type=str,
                        help="Reject all assignments found in the input csv file. Path to a csv file "
                             "(columns: assignmentId,feedback)")

    parser.add_argument("--create_hit", type=str, default="../P808Template/create_acr_hit.cfg",
                        help="Create a HIT. Configuration file")
    parser.add_argument("--create_hit_input", type=str, default="../P808Template/input.csv",
                        help="Input.csv containing dynamic contents of HIT")

    args = parser.parse_args()

    cfgpath = os.path.join(os.path.dirname(__file__), args.cfg)
    assert os.path.exists(cfgpath), f"No configuration file as [{cfgpath}]"
    cfg = CP.ConfigParser()
    cfg.read(cfgpath)


    # create mturk client
    mturk_general = cfg['general']

    client = boto3.client(
        'mturk',
        endpoint_url=mturk_general['endpoint_url'],
        region_name=mturk_general['region_name'],
        aws_access_key_id=mturk_general['aws_access_key_id'],
        aws_secret_access_key=mturk_general['aws_secret_access_key'],
        )

    if args.send_emails is not None:
        send_message(client, cfg['send_email'])
    if args.send_bonus is not None:
        bonus_list_path = os.path.join(os.path.dirname(__file__), args.send_bonus)
        assert os.path.exists(bonus_list_path), f"No input file found in [{bonus_list_path}]"
        assign_bonus(client,bonus_list_path)
    if args.approve is not None:
        assignments_list_path = os.path.join(os.path.dirname(__file__), args.approve)
        assert os.path.exists(assignments_list_path), f"No input file found in [{assignments_list_path}]"
        approve_reject_assignments(client, assignments_list_path, approve=True)
    if args.reject is not None:
        assignments_list_path = os.path.join(os.path.dirname(__file__), args.reject)
        assert os.path.exists(assignments_list_path), f"No input file found in [{assignments_list_path}]"
        approve_reject_assignments(client, assignments_list_path, approve=False)

    if args.create_hit is not None:
        create_hit_cfg = os.path.join(os.path.dirname(__file__), args.create_hit)
        assert os.path.exists(create_hit_cfg), f"No configuration file for create_hit found in [{create_hit_cfg}]"

        input_csv = os.path.join(os.path.dirname(__file__), args.create_hit_input)
        assert os.path.exists(input_csv), f"No configuration file for create_hit found in [{input_csv}]"

        ch_cfg = CP.ConfigParser()
        ch_cfg.read(create_hit_cfg)

        create_hit(client, ch_cfg, input_csv)


