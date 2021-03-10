"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

import argparse
import boto3
import json
import os
import configparser as CP
import csv
import xml.etree.ElementTree as ET
import re
import random
import botocore
import statistics


def send_message(client, cfg):
    """
    Sends an email to list of workers given the worker ids.
    Configuration should be set in section "send_emaiil" in the mturk.cfg file
    :param client: boto3 client object for communicating to MTurk
    :param cfg: configuration file with section "send_emaiil"
    :return:
    """

    worker_ids = cfg['worker_ids'].replace(' ', '').split(',')
    # in each call it is possible to send up to 100 messages
    worker_pack_size = 100
    chunked_worker_ids = [worker_ids[i:i + worker_pack_size] for i in range(0, len(worker_ids), worker_pack_size)]
    count = 1
    success_messages = 0
    failed_group=[]
    for woker_group in chunked_worker_ids:
        response = client.notify_workers(
                 Subject=cfg['subject'],
                 MessageText=cfg['message'],
                 WorkerIds=woker_group
         )
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print (f"Group {count}: sending message... Success" )
            success_messages += len(woker_group)
        else:
            failed_group.extend(woker_group)
            print(f"Group {count}: sending message... Failed")
        count += 1
    print(f"{success_messages} emails sent successfully")


def extend_hits(client, file_path):
    """
        Extending the given HIT by increasing the maximum number of assignments of an existing HIT.
        :param client: boto3 client object for communicating to MTurk
        :param file_path: list of HITs to be extended with number of extra assigned per HIT
    """
    with open(file_path, mode='r') as hit_list:
        reader = csv.DictReader(hit_list)
        line_count = 0
        success = 0
        failed = 0
        for row in reader:
            try:
                if line_count == 0:
                    assert 'HITId' in row, f"No column found with name 'HITId' in [{hit_list}]"
                    assert 'n_extended_assignments' in row, f"No column found with name 'n_extended_assignments' " \
                        f"in [{hit_list}]"
                else:
                    line_count =  line_count +1


                response = client.create_additional_assignments_for_hit(
                    HITId=row["HITId"],
                    NumberOfAdditionalAssignments=int(row["n_extended_assignments"]),
                    UniqueRequestToken=f'extend_hits_{row["HITId"]}_{row["n_extended_assignments"]}'
                )
                success = success + 1
            except Exception as ex:
                print(f'   - Error HIT: {row["HITId"]} can not be extended by {row["n_extended_assignments"]}.'
                      f' msg:{str(ex)}')
                failed = failed + 1
        print(f' ')
        print(f'{success} HITs are extended, {failed} are failed to extend.')
        print(f' ')
        print(f'Use "python mturk_utils.py --cfg YOUR_CFG --extended_hits_status {file_path}" to see the status of new assignments.')


def extended_hits_report(client, file_path):
    """
        Create a report on how many assignments are pending.
        :param client: boto3 client object for communicating to MTurk
        :param file_path: list of HITs to be extended with number of extra assigned per HIT
    """
    with open(file_path, mode='r') as hit_list:
        reader = csv.DictReader(hit_list)
        pending = 0
        available = 0
        line_count = 0
        requested = 0
        print('Start creating a report...')
        for row in reader:
            try:
                if line_count == 0:
                    assert 'HITId' in row, f"No column found with name 'HITId' in [{hit_list}]"
                    assert 'n_extended_assignments' in row, f"No column found with name 'n_extended_assignments' " \
                        f"in [{hit_list}]"
                else:
                    line_count = line_count + 1
                response = client.get_hit(
                    HITId=row["HITId"]
                )
                pending = pending + response["HIT"]["NumberOfAssignmentsPending"]
                available = available + response["HIT"]["NumberOfAssignmentsAvailable"]
                requested = requested + int(row["n_extended_assignments"])
            except Exception as e:
                print(f'Error HIT: cannot get the status of {row["HITId"]}.'
                      f' msg:{str(e)}')
                pass
        print(f'From {requested} extended assignments, {available} are available for workers, and {pending} are pending.'
              f' {requested-(available+pending)} should be completed (assuming all extensions were successful). ')


def assign_bonus(client, bonus_list_path):
    """
    Assign bonuses to group of workers.
    A csv file with following columns need to be provided: workerId, assignmentId, bonusAmount, reason
    :param client: boto3 client object for communicating to MTurk
    :param bonus_list_path: path to the csv file with following columns:workerId, assignmentId, bonusAmount, reason
    :return:
    """
    print('Sending bonuses...')
    with open(bonus_list_path, 'r') as bonus_list:
        entries = list(csv.DictReader(bonus_list))

    bonus_amounts = [float(entry['bonusAmount']) for entry in entries]
    num_bonus_workers = len(bonus_amounts)
    total_bonus = round(sum(bonus_amounts), 2)
    max_bonus = max(bonus_amounts)
    mean_bonus = round(total_bonus / num_bonus_workers, 2)
    median_bonus = statistics.median(bonus_amounts)

    print(f'Number of workers: {num_bonus_workers}, total: {total_bonus}, max: {max_bonus}, mean: {mean_bonus}, median: {median_bonus}')
    proceed = input('Proceed (y/N)?: ')
    if len(proceed) > 0 and proceed.lower() not in ['y', 'n']:
        exit(f'Unknown value "{proceed}"')
    if len(proceed) == 0 or proceed.lower() == 'n':
        exit()

    failed = 0
    for row in entries:
        assert 'workerId' in row
        assert 'assignmentId' in row
        assert 'bonusAmount' in row
        assert 'reason' in row

        response = client.send_bonus(
            WorkerId=row['workerId'],
            BonusAmount=row['bonusAmount'],
            AssignmentId=row['assignmentId'],
            Reason=row['reason']
        )

        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            print(f'Failed to send for {row}')
            failed += 1

    print(f'Bonuses sent, failed {failed}, succeeded {num_bonus_workers - failed}')        


def approve_reject_assignments_together(client, assignment_path):
    """
    Assign bonuses to group of workers.
    A csv file with following columns need to be provided: workerId, assignmentId, bonusAmount, reason
    :param client: boto3 client object for communicating to MTurk
    :param assignment_path: path to the csv file with: workerId, assignmentId, bonusAmount, reason
    :param approve: boolean when false the script reject answers
    :return:
    """

    print('Approving/Rejecting assignments')
    with open(assignment_path, mode='r') as assignment_list:
        reader = csv.DictReader(assignment_list)
        line_count = 0
        successApp = 0
        successRej = 0
        failed=0
        for row in reader:
            if line_count == 0:
                assert 'assignmentId' in row,  f"No column found with name 'assignmentId' in [{assignment_path}]"
                assert 'HITId' in row, f"No column found with name 'HITId' in [{assignment_path}]"
                assert 'Approve' in row, f"No column found with name 'Approve' in [{assignment_path}]"
                assert 'Reject' in row, f"No column found with 'Reject' in [{assignment_path}]"

            if row['Approve'] =='x':
                # approving
                response = client.approve_assignment(
                    AssignmentId=row['assignmentId']
                )
                if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    successApp += 1
                else:
                    print(f'\tFailed:  "Approving assignment" {row["assignmentId"]}:')
                    failed += 1

            else:
                # rejecting
                response = client.reject_assignment(
                    AssignmentId=row['assignmentId'],
                    RequesterFeedback=row['Reject']
                )
                if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    successRej += 1
                else:
                    print(f'\tFailed:  "Rejecting assignment" {row["assignmentId"]}:')
                    failed += 1

            line_count += 1
        print(f'Processed {line_count} assignments - Approved {successApp} assignments and reject {successRej}. '
              f'The script failed on {failed} calls.')




def approve_reject_assignments(client, assignment_path, approve):
    """
    Assign bonuses to group of workers.
    A csv file with following columns need to be provided: workerId, assignmentId, bonusAmount, reason
    :param client: boto3 client object for communicating to MTurk
    :param assignment_path: path to the csv file with: workerId, assignmentId, bonusAmount, reason
    :param approve: boolean when false the script reject answers
    :return:
    """
    if approve:
        print('Approving assignments')
    else:
        print('Rejecting assignments')
    with open(assignment_path, mode='r') as assignment_list:
        reader = csv.DictReader(assignment_list)
        line_count = 0
        success=0
        failed=0
        for row in reader:
            if line_count == 0:
                assert 'assignmentId' in row,  f"No column found with assignmentId in [{assignment_path}]"
                if not approve:
                    assert 'feedback' in row, f"No column found with feedback in [{assignment_path}]"
            if approve:
                # approving
                response = client.approve_assignment(
                    AssignmentId=row['assignmentId']
                )
                if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    success += 1
                else:
                    print(f'\tFailed:  "Approving assignment" {row["assignmentId"]}:')
                    failed += 1

            else:
                # rejecting
                response = client.reject_assignment(
                    AssignmentId=row['assignmentId'],
                    RequesterFeedback=row['feedback']
                )
                if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    success += 1
                else:
                    print(f'\tFailed:  "Rejecting assignment" {row["assignmentId"]}:')
                    failed += 1

            line_count += 1
        print(f'Processed {line_count} assignments - sent {success} calls was successful and {failed} calls failed.')


def get_assignment_review_policy(cfg):
    """
    Create an Assigment Review Policy as explained by MTurke
    :param cfg: configuration object
    :return:
    """
    assignment_review_policy = None
    if cfg['general'].getboolean('use_assignment_review_policy'):
        arp = cfg['assignment_review_policy']
        items = arp['arp_question_name'].split(',')
        map= []
        for item in items:
            map.append({'Key': item, 'Values':[f"{arp['arp_correct_answer']}"]})
        assignment_review_policy = {
         'PolicyName': 'ScoreMyKnownAnswers/2011-09-01',
         'Parameters': [
            {'Key': "AnswerKey",
             'MapEntries': map},
            {'Key': "RejectIfKnownAnswerScoreIsLessThan",
             'Values': [f"{arp['arp_RejectIfKnownAnswerScoreIsLessThan']}"]
             }, {
                'Key': "RejectReason",
                'Values': [f"{arp['arp_RejectReason']}"]
             }, {
                'Key': "ExtendIfKnownAnswerScoreIsLessThan",
                'Values': [f"{arp['arp_ExtendIfKnownAnswerScoreIsLessThan']}"]
             }
        ]}
        print (json.dumps(assignment_review_policy))
    return assignment_review_policy


def get_typical_qualifications(cfg):
    """
     create qualification list to filter just workers with:
    - + 98% approval rate
    - + 500 or more accepted HIT
    - Location USA
    :param cfg:
    :return:
    """
    if not cfg['hit_type'].getboolean('apply_qualification'):
        return []
    qualification_requirements=[
        {
            # Worker_​NumberHITsApproved
            'QualificationTypeId': '00000000000000000040',
            'Comparator': 'GreaterThanOrEqualTo',
            'IntegerValues': [
                500,
            ],
            'RequiredToPreview': False,
            'ActionsGuarded': 'Accept'
        }, {
            # Worker_​PercentAssignmentsApproved
            'QualificationTypeId': '000000000000000000L0',
            'Comparator': 'GreaterThanOrEqualTo',
            'IntegerValues': [
                98,
            ],
            'RequiredToPreview': False,
            'ActionsGuarded': 'Accept'
        }, {
            # Worker_Locale
            'QualificationTypeId': '00000000000000000071',
            'Comparator': 'EqualTo',
            'LocaleValues': [
                {
                   'Country':"US"
                }
            ],
            'RequiredToPreview': False,
            'ActionsGuarded': 'Accept'
        },
    ]
    return qualification_requirements


def create_hit(client, cfg, path_to_input_csv):
    """
    Create a batch of HITs given hit_layout_id and other configurations in the cfg file, and an input.csv.
    Generate a report which should be used for getting responses.

    NOTe: If you register a HIT type with values that match an existing HIT type, the HIT type ID of the existing type
    willbe returned. That means if some HITs from that type are existing, the new HITs will be added to them (
     from workers' perspective).
    :param client:
    :param cfg:
    :param path_to_input_csv:
    :return:
    """

    # 1. create HITType
    auto_approval_delay_in_days = cfg['hit_type'].get('auto_approve_and_pay_workers_in_days', fallback=3)
    assignment_duration_in_minutes = cfg['hit_type'].get('time_allotted_per_Worker_in_minutes', fallback=60)

    response = client.create_hit_type(
        AutoApprovalDelayInSeconds=int(auto_approval_delay_in_days) * 24*60*60,
        AssignmentDurationInSeconds=int(assignment_duration_in_minutes) * 60,
        Reward=cfg['hit_type'].get('reward', '0.4'),
        Title=cfg['hit_type'].get('title', 'title'),
        Keywords=cfg['hit_type'].get('keywords', 'keywords'),
        Description=cfg['hit_type'].get('description', 'description'),
        QualificationRequirements= get_typical_qualifications(cfg)
    )
    print(response)

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        hit_type_id = response['HITTypeId']
        # 2. create a HIT
        batch_output_file_name = f"Batch_{hit_type_id}_{random.randint(1000, 9999)}.csv"
        created_hits = []
        assignment_review_policy = get_assignment_review_policy(cfg)

        # if no path_to_input_csv available then there is no dynamic content
        if path_to_input_csv is None:
            # just create one HIT
            response = client.create_hit_with_hit_type(
                HITTypeId=hit_type_id,
                MaxAssignments=int(cfg['create_hit'].get('number_of_respondents', 10)),
                LifetimeInSeconds=int(cfg['create_hit'].get('task_expires_in_days', 7)) * 24 * 60 * 60 +
                                  random.randint(1, 59),
                AssignmentReviewPolicy=assignment_review_policy,
                HITLayoutId=cfg['general']['hit_layout_id'],
                RequesterAnnotation= batch_output_file_name
            )
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                created_hits.append({'HITTypeId': hit_type_id, 'HITId': response['HIT']['HITId'],
                                     'HITGroupId': response['HIT']['HITGroupId']})

        else:
            # for a line in path_to_input_csv
            with open(path_to_input_csv, mode='r') as input_csv:
                reader = csv.DictReader(input_csv)
                line_count = 0
                for row in reader:
                    line_count += 1
                    response = client.create_hit_with_hit_type(
                        HITTypeId=hit_type_id,
                        MaxAssignments=int(cfg['create_hit'].get('number_of_respondents', 10)),
                        LifetimeInSeconds=int(cfg['create_hit'].get('task_expires_in_days', 7)) * 24 * 60 * 60,
                        AssignmentReviewPolicy=assignment_review_policy,
                        HITLayoutId=cfg['general']['hit_layout_id'],
                        HITLayoutParameters=[{'Name': key, 'Value': row[key]} for key in row.keys()],
                        RequesterAnnotation = batch_output_file_name
                    )
                    print(f"{line_count}. Create HIT response:{response}")
                    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                        created_hits.append({'HITTypeId': hit_type_id, 'HITId': response['HIT']['HITId'],
                                             'HITGroupId': response['HIT']['HITGroupId']})

        # write the report
        with open(batch_output_file_name, 'w', newline='') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=['HITId','HITTypeId','HITGroupId'])
            writer.writeheader()
            for hit in created_hits:
                writer.writerow(hit)
        print (f"{len(created_hits)} HITs are created. Report is stored in {batch_output_file_name}")
    else:
        print("Error in create hit type:  create_hit_type: "+ response)


def get_answer_csv(client, report_file_path):
    """
    Given the report file, generated after create_hit process, it will download all available answers for those HITs.

    :param client:
    :param report_file_path:
    :return:
    """
    answer_file = os.path.splitext(report_file_path)[0]+'_answer.csv'
    with open(report_file_path, mode='r') as tmp_file:
        with open(answer_file, 'w', newline='') as output_file:
            reader = csv.DictReader(tmp_file)
            headers_written=False
            for row in reader:
                response = client.list_assignments_for_hit(
                    HITId=f'{row["HITId"]}',
                    MaxResults=100
                )
                if response and response['NumResults']>0:
                    for assignment in response['Assignments']:
                        ans_dict= xml_answer_to_dict(assignment['Answer'])

                        for key in assignment.keys():
                            if key == 'Answer': continue
                            ans_dict[key] = assignment[key]
                        if not headers_written:
                            writer = csv.DictWriter(output_file, fieldnames=sorted(ans_dict) )
                            headers_written= True
                            writer.writeheader()
                        writer.writerow(ans_dict)


def xml_answer_to_dict(xml_text):
    """
    Converts an answer in xml format to dict
    :param xml_text:
    :return:
    """
    xml_text_no_namespace = re.sub(' xmlns="[^"]+"', '', xml_text, count=1)
    root = ET.fromstring(xml_text_no_namespace)
    ans_dict = {}
    for child in root:
        question = ""
        answer = ""
        for sec_child in child:
            if sec_child.tag == 'QuestionIdentifier':
                question = sec_child.text
            if sec_child.tag == 'FreeText':
                answer = sec_child.text

        ans_dict[question] = answer
    return ans_dict


def create_qualification_type_without_test(client,cfg):
    response = client.create_qualification_type(
        Name=cfg['qualification_type']['name'],
        Description=cfg['qualification_type']['description'],
        QualificationTypeStatus=cfg['qualification_type']['qualification_type_status'],
    )
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print(f"Qualification Type {cfg['qualification_type']['name']} is created")
    else:
        print(f"Problem by creating the qualification {cfg['qualification_type']['name']}: {response}")


def create_qualification_type_with_test(client,cfg):
    with open('cfgs_and_inputs_to_removeconfigurations/qualification.xml', 'r') as test_file:
        test = test_file.read()
        #test_url_escaped= urllib.parse.quote(test)
        test_url_escaped = test
        print(test_url_escaped)
        with open('cfgs_and_inputs_to_remove/answer_key.xml', 'r') as answer_file:
            ans = answer_file.read()

            response = client.create_qualification_type(
                Name=cfg['qualification_type']['name'],
                Keywords='abc',
                Description=cfg['qualification_type']['description'],
                QualificationTypeStatus=cfg['qualification_type']['qualification_type_status'],
                RetryDelayInSeconds=120,
                Test=test_url_escaped,
                AnswerKey=ans,
                TestDurationInSeconds=3600,
                AutoGranted=False
            )
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                print(f"Qualification Type {cfg['qualification_type']['name']} is created")
            else:
                print(f"Problem by creating the qualification {cfg['qualification_type']['name']}: {response}")


def update_qualification_type_with_test(client,cfg):
    with open('cfgs_and_inputs_to_remove/qualification.xml', 'r') as test_file:
        test = test_file.read()
        #test_url_escaped= urllib.parse.quote(test)
        test_url_escaped = test
        print(test_url_escaped)
        q_id= get_qualification_id(client,'test4')
        with open('cfgs_and_inputs_to_remove/answer_key.xml', 'r') as answer_file:
            ans = answer_file.read()

            response = client.update_qualification_type(
                QualificationTypeId=q_id,
                Description=cfg['qualification_type']['description'],
                QualificationTypeStatus=cfg['qualification_type']['qualification_type_status'],
                RetryDelayInSeconds=120,
                Test=test_url_escaped,
                AnswerKey=ans,
                TestDurationInSeconds=3600,
                AutoGranted=False
            )
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                print(f"Qualification Type {cfg['qualification_type']['name']} is created")
            else:
                print(f"Problem by creating the qualification {cfg['qualification_type']['name']}: {response}")


def get_qualification_id(client, name):
    response = client.list_qualification_types(
        Query=name,
        MustBeRequestable=True,
        MustBeOwnedByCaller=True,
        MaxResults=10
    )
    print(response)
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return response['QualificationTypes'][0]['QualificationTypeId']
    else:
        print(f"Could not find qualification name {name}: {response}")
        return name


def assign_qualification_to_workers(client, input_csv_path):
    qualification_ids={}
    with open(input_csv_path, mode='r') as input:
        reader = csv.DictReader(input)
        line_count = 1
        for row in reader:
            if line_count == 1:
                assert 'workerId' in row,  f"No column found with workerId in [{input_csv_path}]"
                assert 'qualification_name' in row, f"No column found with qualification_name in [{input_csv_path}]"
                assert 'value' in row, f"No column found with value in [{input_csv_path}]"
            q_name = row['qualification_name'].strip()
            if q_name not in qualification_ids:
                qualification_ids[q_name] = get_qualification_id(client, q_name)

            response = client.associate_qualification_with_worker(
                QualificationTypeId=qualification_ids[q_name],
                WorkerId=row['workerId'],
                IntegerValue=int(row['value'])
            )
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                print(f"{line_count}. Qualification Type {q_name} with value {row['value']} is assigned to {row['workerId']}")
            else:
                print(f"Error: {line_count}. Qualification Type {q_name} with value {row['value']} is NOT assigned to {row['workerId']}")
            line_count += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Utility script to handle a MTurk study.')
    # Configuration: read it from mturk.cfg
    parser.add_argument("--cfg", default="mturk.cfg",
                        help="Read mturk.cfg for all the details (path relative to current working directory)")
    parser.add_argument("send_emails", nargs='?', help="send emails (configuration is needed)")
    parser.add_argument("--send_bonus", type=str, help="give bonus to a group of worker. Path to a csv file "
                                                       "(columns: workerId, assignmentId, bonusAmount, reason). "
                                                       "Path relative to current working directory")

    parser.add_argument("--approve", type=str,
                        help="Approve all assignments found in the input csv file. Path to a csv file "
                             "(columns: assignmentId). Path relative to current working directory")
    parser.add_argument("--reject", type=str,
                        help="Reject all assignments found in the input csv file. Path to a csv file "
                             "(columns: assignmentId,feedback). Path relative to current working directory")

    parser.add_argument("--approve_reject", type=str,
                        help="Approve or reject assignments found in the input csv file. Path to a csv file "
                             "(columns: assignmentId, HITId, approve, reject). Path relative to current working "
                             "directory")

    parser.add_argument("--create_hit", type=str,
                        help="Create one or more  HITs. Configuration file for creating HIT. "
                             "Path relative to current working directory")
    parser.add_argument("--create_hit_input", type=str,
                        help="Input.csv containing dynamic contents of HIT (columns: all Layout Parameters). "
                             "Path relative to current working directory")

    parser.add_argument("--answers", type=str,
                        help="Download answers for given report file (columns: HITId, HITTypeId,HITGroupId. "
                             "Path relative to current working directory")

    parser.add_argument("--create_qualification_type", type=str,
                        help="Create qualification type without test given the cfg file. see qualification.cfg. "
                             "Path relative to current working directory")

    parser.add_argument("--assign_qualification_type", type=str,
                        help="Assign qualification type wto workers. "
                            "Input csv file (columns: workerId, qualification_name, value). "
                             "Path relative to current working directory")

    parser.add_argument("--extend_hits", type=str,
                        help="Extends hits for the given number of extra assignments. Path to a csv file "
                             "(Columns: HITId, nExtraAssignments). Path relative to current working "
                             "directory")
    parser.add_argument("--extended_hits_status", type=str,
                        help="Get status of assignments that are generated by the extended HITs. Expect the path to the"
                             "csv file used with '--extend_hits' command.")

    args = parser.parse_args()

    #cfgpath = os.path.join(os.path.dirname(__file__), args.cfg)
    cfgpath = args.cfg
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
        #bonus_list_path = os.path.join(os.path.dirname(__file__), args.send_bonus)
        bonus_list_path = args.send_bonus
        assert os.path.exists(bonus_list_path), f"No input file found in [{bonus_list_path}]"
        assign_bonus(client, bonus_list_path)

    if args.approve is not None:
        #assignments_list_path = os.path.join(os.path.dirname(__file__), args.approve)
        assignments_list_path = args.approve
        assert os.path.exists(assignments_list_path), f"No input file found in [{assignments_list_path}]"
        approve_reject_assignments(client, assignments_list_path, approve=True)

    if args.reject is not None:
        #assignments_list_path = os.path.join(os.path.dirname(__file__), args.reject)
        assignments_list_path = args.reject
        assert os.path.exists(assignments_list_path), f"No input file found in [{assignments_list_path}]"
        approve_reject_assignments(client, assignments_list_path, approve=False)

    if args.approve_reject is not None:
        assignments_list_path = args.approve_reject
        assert os.path.exists(assignments_list_path), f"No input file found in [{assignments_list_path}]"
        approve_reject_assignments_together(client, assignments_list_path)


    if args.create_hit is not None:
        #create_hit_cfg = os.path.join(os.path.dirname(__file__), args.create_hit)
        create_hit_cfg = args.create_hit
        assert os.path.exists(create_hit_cfg), f"No configuration file for create_hit found in [{create_hit_cfg}]"

        #input_csv = os.path.join(os.path.dirname(__file__), args.create_hit_input)
        input_csv = args.create_hit_input
        # can be just one HIT
        #assert os.path.exists(input_csv), f"No input file found in [{input_csv}]"

        ch_cfg = CP.ConfigParser()
        ch_cfg.read(create_hit_cfg)

        create_hit(client, ch_cfg, input_csv)

    if args.answers is not None:
        #report_file = os.path.join(os.path.dirname(__file__), args.answers)
        report_file = args.answers
        assert os.path.exists(report_file), f"No configuration file for create_hit found in [{report_file}]"
        get_answer_csv(client, report_file)

    if args.create_qualification_type is not None:
        #qualification_cfg_path = os.path.join(os.path.dirname(__file__), args.create_qualification_type)
        qualification_cfg_path = args.create_qualification_type
        assert os.path.exists(qualification_cfg_path), f"No configuration file as [{qualification_cfg_path}]"
        cfg_qualification = CP.ConfigParser()
        cfg_qualification.read(qualification_cfg_path)
        create_qualification_type_without_test(client, cfg_qualification)
        #update_qualification_type_with_test(client, cfg_qualification)

    if args.assign_qualification_type is not None:
        #input_path = os.path.join(os.path.dirname(__file__), args.assign_qualification_type)
        input_path = args.assign_qualification_type
        assert os.path.exists(input_path), f"No configuration file as [{input_path}]"
        assign_qualification_to_workers(client,input_path)

    if args.extend_hits is not None:
        hit_list = args.extend_hits
        assert os.path.exists(hit_list), f"No input file found in [{hit_list}]"
        extend_hits(client, hit_list)

    if args.extended_hits_status is not None:
        hit_list = args.extended_hits_status
        assert os.path.exists(hit_list), f"No input file found in [{hit_list}]"
        extended_hits_report(client, hit_list)
