"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""
import argparse
import json
import os
import configparser as CP
import pandas as pd
import requests
import datetime
import glob
import logging

base_url = "https://api.prolific.com/api/v1"



rdp_group_id = None
low_quality_group_id = None

def accept_reject_submission(worker_id, assignment_id, reason):
    
    def _message_to_prolific(message):
        control_failed_phrases = [
            "control clip incorrectly", "All clips should be played", "Both earplugs should be used.", "Qualification did not passed"
        ]
        
        if "wrong verification code" in message:
            return "REJECT", "NO_CODE"
        if any(phrase in message for phrase in control_failed_phrases):
            return "REJECT", "FAILED_CHECK"
        if "approve" in message:
            return "APPROVE", None
        return None, None

    url = f"{base_url}/submissions/{assignment_id}/transition/"
    action, categorry = _message_to_prolific(reason)
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json', 
        'Accept': 'application/json',
        
    }
    payload = {
       "action": action
        
    }
    if categorry is not None:
        payload["rejection_category"] = categorry
        payload["message"] = reason

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
    except requests.exceptions.RequestException as e:
        logger.info(f"Submission {assignment_id}  - An error occurred: {e}")
        return
    if response.status_code == 200:
        logger.info(f"Submission {assignment_id} {action} successfully.")
    else:
        logger.info(f"Error: {response.status_code}")
        logger.info(f"Response: {response.text}")


def bulk_approve_submission(assignment_ids):

    url = f"{base_url}/submissions/bulk-approve/"

    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json', 
        'Accept': 'application/json',
        
    }

    payload = {
       "submission_ids": assignment_ids
        
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    except requests.exceptions.RequestException as e:
        logger.info(f"Submission {assignment_ids}  - An error occurred: {e}")
        return
    if response.status_code == 200:
        logger.info(f"{len(assignment_ids)} Submission approved successfully.")
    else:
        logger.info(f"Error: {response.status_code}")
        logger.info(f"Response: {response.text}")


def ask_return(assignment_id, reason):

    url = f"{base_url}/submissions/{assignment_id}/request-return/"

    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json', 
        'Accept': 'application/json',
        
    }

    payload = {
       "request_return_reasons": [reason]
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    except requests.exceptions.RequestException as e:
        logger.info(f"Submission {assignment_id}  - An error occurred: {e}")
        return
    if response.status_code == 200:
        logger.info(f"Submission {assignment_id} asked to return successfully.")
    else:
        logger.info(f"Error: {response.status_code}")
        logger.info(f"Response: {response.text}")


def get_submission_data(assignment_id):
    url = f"{base_url}/submissions/{assignment_id}/"
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json', 
        'Accept': 'application/json',
       
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        logger.info(f"Submission {assignment_id} data: {data}")
        return data
    else:
        logger.info(f"Error: {response.status_code}")
        logger.info(f"Response: {response.text}")
        return None

def get_submission_status(assignment_id):
    url = f"{base_url}/submissions/{assignment_id}/"
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json', 
        'Accept': 'application/json',
       
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        status = data.get("status")
        logger.info(f"Submission {assignment_id} status: {status}")
        return status
    else:
        logger.info(f"Error: {response.status_code}")
        logger.info(f"Response: {response.text}")
        return None
    

def send_reviews_for_study(csv_data_path, detailed_data_cleaning_report=None, block_report=None):
    count = 0
    df = pd.read_csv(csv_data_path)
    # Approve is x
    df_approved = df[df['Approve'] == 'x']
    df_rejected = df[df['Approve'] != 'x']

    submission_to_approve = df_approved['assignmentId'].tolist()
    bulk_approve_submission(submission_to_approve)

    for index, row in df_rejected.iterrows():
        # WorkerId	assignmentId	HITId	Approve	Reject
        worker_id = row['WorkerId'].lower()
        assignment_id = row['assignmentId'].lower()
        hit_id = row['HITId']
        count = count+ 1
        
        if row['Approve'] is not None and not pd.isna(row['Approve']) and row['Approve'].strip() != "":
            continue # already handled in bulk approve
        else:
            reason = row['Reject']
            if args.force_reject:
                accept_reject_submission(worker_id, assignment_id, reason)
            else:
                ask_return(assignment_id, reason)

     # assign participants with rdp to the group to be excluded from the future studies
    if detailed_data_cleaning_report and rdp_group_id is not None:
        df_detailed = pd.read_csv(detailed_data_cleaning_report)
        # filter the participants with rdp
        df_rdp = df_detailed[df_detailed['remote_desktop_failed'] == 1]
        participant_ids = df_rdp['worker_id'].tolist()
        if len(participant_ids) > 0:
            unique_participant_ids = list(set(participant_ids))
            logger.info(f"Adding {len(unique_participant_ids)} participants with rdp to the group")
            add_participants_to_group(rdp_group_id, unique_participant_ids)

    if block_report is not None and low_quality_group_id is not None:
        # if block report is provided, save the participants with rdp to the block report
        df_block = pd.read_csv(block_report)

        participant_ids = df_block['Worker ID'].tolist()
        if len(participant_ids) > 0:
            unique_participant_ids = list(set(participant_ids))            
            logger.info(f"Added {len(unique_participant_ids)} participants to the block group")
            add_participants_to_group(low_quality_group_id, unique_participant_ids)


def reject_remain_waiting(csv_data_path):
    count = 0
    df = pd.read_csv(csv_data_path)
    # Approve is x    
    df_rejected = df[df['Approve'] != 'x']

    for index, row in df_rejected.iterrows():
        # WorkerId	assignmentId	HITId	Approve	Reject
        worker_id = row['WorkerId']
        assignment_id = row['assignmentId']
        hit_id = row['HITId']
        count = count+ 1
        status = get_submission_status(assignment_id)
        if status is not None and status.strip().upper() == "AWAITING REVIEW":
            reason = row['Reject']
            accept_reject_submission(worker_id, assignment_id, reason)
            


def get_rejected_submission_status(csv_data_path):
    count = 0
    df = pd.read_csv(csv_data_path)
    # Approve is x
    df_approved = df[df['Approve'] == 'x']
    df_rejected = df[df['Approve'] != 'x']

    submission_to_approve = df_approved['assignmentId'].tolist()
    bulk_approve_submission(submission_to_approve)
    data = []
    for index, row in df_rejected.iterrows():
        # WorkerId	assignmentId	HITId	Approve	Reject
        worker_id = row['WorkerId']
        assignment_id = row['assignmentId']
        hit_id = row['HITId']
        count = count+ 1
        
        status = get_submission_status(assignment_id)
        
        data.append({
            "worker_id": worker_id,
            "assignment_id": assignment_id,
            "hit_id": hit_id,
            "status": status,
            "reason": row['Reject']
        })
    df_status = pd.DataFrame(data)
    date_name_formated_now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # save in csv_data_path path
    df_status.to_csv(os.path.join(os.path.dirname(csv_data_path), f"prolific_submission_status_{date_name_formated_now}.csv"), index=False)

def add_participants_to_group(group_id, participant_ids):
    url = f"{base_url}/participant-groups/{group_id}/participants/"

    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json', 
        'Accept': 'application/json',
    }

    payload = {
       "participant_ids": participant_ids
        
    }
    
    try:
        logger.info(f"Adding {len(participant_ids)} participants  to group {group_id}")
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        if response.status_code == 200:
            logger.info(f"Participants {participant_ids} added to group {group_id} successfully.")
        else:
            logger.info(f"Error: {response.status_code}")
            logger.info(f"Response: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.info(f"Participants {participant_ids}  - An error occurred: {e}")
        return
   


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Utility script to handle a Prolific study.')
    # Configuration: read it from mturk.cfg
    parser.add_argument("--cfg", default="prolific.cfg",
                        help="Read prolific.cfg for all the details (path relative to current working directory)")

    parser.add_argument("--review", type=str, default=None,
                        help="approve/or reject assignments, provide the path to your project directory (that should include a file with *_accept_reject_gui.csv file) or specific csv file. "
                             )
    parser.add_argument("--force_reject", action="store_true", default=False,
                        help="If present, submissions with 'reject' decisions will be rejected, otherwise they will be asked to return the hit.")
    
    parser.add_argument("--reject_remainings", action="store_true", default=False,
                        help="If present, submissions with 'reject' decisions that are still AWAITING REVIEW will be rejected.")
    
    parser.add_argument("--status", type=str, default=None,
                        help="get status of rejected submissions")


    args = parser.parse_args()

    cfgpath = args.cfg
    assert os.path.exists(cfgpath), f"No configuration file as [{cfgpath}]"
    cfg = CP.ConfigParser()
    cfg.read(cfgpath)

    # create mturk client
    api_token = cfg['general'].get('token')
    #they are optional and set them to None if not provided
    rdp_group_id = cfg['optional'].get('rdp_group_id') if cfg.has_section('optional') else None
    low_quality_group_id = cfg['optional'].get('low_quality_group_id') if cfg.has_section('optional') else None
    # check for "none" string
    if rdp_group_id is not None and rdp_group_id.lower() == "none":
        rdp_group_id = None
    if low_quality_group_id is not None and low_quality_group_id.lower() == "none":
        low_quality_group_id = None


    logger = logging.getLogger("my_logger")
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
   

    if args.review is not None:
        review_file_path = args.review
        assert os.path.exists(review_file_path), f"No input file found in [{review_file_path}]"
        if os.path.isdir(review_file_path):
            file_log_path = os.path.join(review_file_path, "prolific_review.log")
            file_handler = logging.FileHandler(file_log_path)
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)
            logger.info(f"Start review for project {review_file_path} at {datetime.datetime.now()}")

            # if it is a directory, find the csv file
            review_file_path = os.path.join(review_file_path, "*_accept_reject_gui.csv")
            review_file_path = glob.glob(review_file_path)
            assert len(review_file_path) == 1, f"Expected one csv file in [{review_file_path}]"
            review_file_path = review_file_path[0]
            # look for *_data_cleaning_report.csv
            detailed_data_cleaning_report = os.path.join(os.path.dirname(review_file_path), "*_data_cleaning_report.csv")
            detailed_data_cleaning_report = glob.glob(detailed_data_cleaning_report)
            if len(detailed_data_cleaning_report) == 0:
                detailed_data_cleaning_report = None
            else:
                 detailed_data_cleaning_report = detailed_data_cleaning_report[0]

            block_list_report = os.path.join(os.path.dirname(review_file_path), "*_block_list.csv")
            block_list_report = glob.glob(block_list_report)
            if len(block_list_report) == 0:
                block_list_report = None
                logger.warning(f"No block list report found for project {review_file_path}")    
            else:
                block_list_report = block_list_report[0]


        else:
            assert review_file_path.endswith(".csv"), f"Expected a csv file, got [{review_file_path}]"
            detailed_data_cleaning_report = None
            block_list_report = None
        if args.reject_remainings:
            reject_remain_waiting(review_file_path)
        else:
            send_reviews_for_study(review_file_path, detailed_data_cleaning_report, block_list_report)

    elif args.status is not None:
        review_file_path = args.status
        assert os.path.exists(review_file_path), f"No input file found in [{review_file_path}]"
        if os.path.isdir(review_file_path):
            file_log_path = os.path.join(review_file_path, "prolific_review.log")
            file_handler = logging.FileHandler(file_log_path)
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)
            logger.info(f"Start review for project {review_file_path} at {datetime.datetime.now()}")

            # if it is a directory, find the csv file
            review_file_path = os.path.join(review_file_path, "*_accept_reject_gui.csv")
            review_file_path = glob.glob(review_file_path)
            assert len(review_file_path) == 1, f"Expected one csv file in [{review_file_path}]"
            review_file_path = review_file_path[0]
            # look for *_data_cleaning_report.csv
            detailed_data_cleaning_report = os.path.join(os.path.dirname(review_file_path), "*_data_cleaning_report.csv")
            detailed_data_cleaning_report = glob.glob(detailed_data_cleaning_report)
            if len(detailed_data_cleaning_report) == 0:
                detailed_data_cleaning_report = None
            else:
                 detailed_data_cleaning_report = detailed_data_cleaning_report[0]


        else:
            assert review_file_path.endswith(".csv"), f"Expected a csv file, got [{review_file_path}]"
            detailed_data_cleaning_report = None
        get_rejected_submission_status(review_file_path)
        