"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Vishak Gopal
"""
import argparse
import configparser as CP
import os
from datetime import datetime

import numpy as np
import pandas as pd
import scaleapi

now = datetime.now()  # current date and time


def main(args, scale_api_key, scale_account_name):
    client = scaleapi.ScaleClient(scale_api_key)

    # create output folder
    output_dir = args.project
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # create list to collect all tasks
    all_tasks = []
    counter = 0
    next_token = None

    while (True):
        tasks = client.tasks(
            batch=args.project,
            status='completed',
            next_token=next_token,
            project=scale_account_name,
        )
        for task in tasks:
            counter += 1
            # print(f'Downloading Task {counter} | ${task.task_id}')
            all_tasks.append(task)
            next_token = tasks.next_token
        if (next_token == None):
            break

    if args.method == 'acr':
        results, rater_stats = parse_acr(all_tasks)
        df = pd.DataFrame(results)
        df.to_csv(os.path.join(
            output_dir, f'{args.project}_Batch_{now.strftime("%Y%m%d")}_per_clip_results.csv'), index=False)

        # TODO: This doesn't mesh well with other uses of P.808 ratings, something needs to be figured out
        """
        model_pivot_table = df.pivot_table(
            values='MOS', index='model', columns='clipset', margins=True, margins_name='Overall', aggfunc=[np.mean, len, np.std])
        model_pivot_table = model_pivot_table.swaplevel(axis=1)
        model_pivot_table.drop('Overall', inplace=True)
        for cols in model_pivot_table.columns.levels[0]:
            model_pivot_table.loc[:, (cols, 'CI')] = model_pivot_table.loc[:, cols].apply(
                lambda x: 1.96 * x['std']/np.sqrt(x['len']), axis=1)
            model_pivot_table.loc[:, (cols, 'DMOS')] = model_pivot_table.loc[:, cols]. apply(
                lambda x: x['mean'] - model_pivot_table.loc['noisy', (cols, 'mean')], axis=1)

        model_pivot_table = model_pivot_table.sort_values(
            ('Overall', 'mean'), ascending=False).sort_index(axis=1, ascending=False)
        model_pivot_table.to_csv(os.path.join(
            output_dir, f'{args.project}_Batch_{now.strftime("%Y%m%d")}_per_condition_results.csv'))
        """

    elif args.method == 'echo':
        echo_results, deg_results, rater_stats = parse_echo(all_tasks)

        df_echo = pd.DataFrame(echo_results)
        df_echo.to_csv(os.path.join(
            output_dir, f'{args.project}_Batch_{now.strftime("%Y%m%d")}_per_clip_results_echo.csv'), index=False)

        df_deg = pd.DataFrame(deg_results)
        df_deg.to_csv(os.path.join(
            output_dir, f'{args.project}_Batch_{now.strftime("%Y%m%d")}_per_clip_results_deg.csv'), index=False)
    elif args.method == 'p835':
        p835_results, rater_stats = parse_p835(all_tasks)

        df = pd.DataFrame(p835_results)
        df.to_csv(os.path.join(
            output_dir, f'{args.project}_Batch_{now.strftime("%Y%m%d")}_per_clip_results.csv'), index=False)
    else:
        raise Exception(f'Unknown method {args.method}')

    df_rater = pd.DataFrame(rater_stats)
    df_rater.to_csv(os.path.join(
        output_dir, f'{args.project}_Batch_{now.strftime("%Y%m%d")}_rater_stats.csv'))


def parse_acr(tasks):
    results = list()
    rater_stats = list()
    for task in tasks:

        for file_url in task.as_dict()['metadata']['file_urls']:
            clip_dict = {
                'short_file_name': task.as_dict()['metadata']['file_shortname']}
            clip_dict['model'] = file_url
            clip_dict['file_url'] = task.as_dict()['metadata']['file_urls'][file_url]
            if 'response' not in task.as_dict():
                print('Found task that has not been rated yet')
                continue

            ratings = task.as_dict()['response'][file_url]['responses']
            rater_stats.extend(ratings)

            for i in range(len(ratings)):
                vote = 'vote_' + str(i+1)
                clip_dict[vote] = ratings[i]['rating']

            clip_dict['MOS'] = np.mean([rating['rating']
                                        for rating in ratings])
            clip_dict['n'] = len(ratings)
            clip_dict['std'] = np.std([rating['rating']
                                       for rating in ratings], ddof=1)
            clip_dict['95%CI'] = 1.96 * \
                clip_dict['std'] / np.sqrt(len(ratings))

            """
            clipset_match = re.match(
                '.*[/](?P<clipset>audioset|ms_realrec|noreverb_clnsp|reverb_clnsp|stationary)', clip_dict['file_url'])
            clip_dict['clipset'] = clipset_match.groupdict()['clipset']
            """

            results.append(clip_dict)

    return results, rater_stats


def parse_p835(tasks):
    results = list()
    rater_stats = list()

    for task in tasks:
        for file_url in task.as_dict()['metadata']['file_urls']:
            clip_dict = {
                'short_file_name': task.as_dict()['metadata']['file_shortname']}
            clip_dict['model'] = file_url
            clip_dict['file_url'] = task.as_dict()['metadata']['file_urls'][file_url]
            if 'response' not in task.as_dict():
                print('Found task that has not been rated yet')
                continue

            ratings = task.as_dict()['response'][file_url]['responses']
            rater_stats.extend(ratings)

            clip_dict.update(get_labelled_rating(ratings, 'distortion'))
            clip_dict.update(get_labelled_rating(ratings, 'background'))
            clip_dict.update(get_labelled_rating(ratings, 'overall'))
            results.append(clip_dict)

    return results, rater_stats


def get_labelled_rating(ratings, rating_label):
    votes_dict = dict()

    mos = np.mean([rating[rating_label] for rating in ratings])
    num_votes = len(ratings)
    stdev = np.std([rating[rating_label] for rating in ratings], ddof=1)
    ci95 = 1.96 * stdev / np.sqrt(num_votes)

    votes_dict = {
        f'MOS_{rating_label}': mos,
        'n': num_votes,
        f'std_{rating_label}': stdev,
        f'95%CI_{rating_label}': ci95,
    }

    for i, rating in enumerate(ratings):
        votes_dict[f'vote_{rating_label}_{i+1}'] = rating[rating_label]

    return votes_dict


def parse_echo(tasks):
    echo_results = list()
    deg_results = list()
    rater_stats = list()

    for task in tasks:

        for file_url in task.as_dict()['metadata']['file_urls']:
            clip_dict = {
                'short_file_name': task.as_dict()['metadata']['file_shortname']}
            clip_dict['model'] = file_url
            clip_dict['file_url'] = remove_query_string_from_url(task.as_dict()['metadata']['file_urls'][file_url])
            if 'response' not in task.as_dict():
                print('Found task that has not been rated yet')
                continue

            ratings = task.as_dict()['response'][file_url]['responses']
            print(ratings)
            rater_stats.extend(ratings)

            clip_dict_echo = dict(clip_dict)
            clip_dict_deg = dict(clip_dict)
            for i, rating in enumerate(ratings):
                vote = f'vote_{i+1}'
                clip_dict_echo[vote] = rating['rating_echo']
                clip_dict_deg[vote] = rating['rating_deg']

            clip_dict_echo['MOS_ECHO'] = np.mean(
                [rating['rating_echo'] for rating in ratings])
            clip_dict_echo['n'] = len(ratings)
            clip_dict_echo['std_echo'] = np.std(
                [rating['rating_echo'] for rating in ratings], ddof=1)
            clip_dict_echo['95%CI_echo'] = 1.96 * \
                clip_dict_echo['std_echo'] / np.sqrt(len(ratings))
            echo_results.append(clip_dict_echo)

            clip_dict_deg['MOS_OTHER'] = np.mean(
                [rating['rating_deg'] for rating in ratings])
            clip_dict_deg['n'] = len(ratings)
            clip_dict_deg['std_other'] = np.std(
                [rating['rating_deg'] for rating in ratings], ddof=1)
            clip_dict_deg['95%CI_other'] = 1.96 * \
                clip_dict_deg['std_other'] / np.sqrt(len(ratings))
            deg_results.append(clip_dict_deg)

    return echo_results, deg_results, rater_stats


# TODO: some sort of structured URL parsing is more reasonable than this hack
def remove_query_string_from_url(url):
    filename_cutoff_index = url.index('.wav') + 4
    return url[:filename_cutoff_index]


if __name__ == '__main__':
    print("Welcome to the Scale result parsing script for ACR test.")
    parser = argparse.ArgumentParser(
        description='Master script to prepare the ACR test')
    parser.add_argument(
        "--project", help="Name of the batch to club results by", required=True)
    parser.add_argument(
        "--cfg", help="Configuration file, see master.cfg", required=True)
    parser.add_argument(
        "--method", default="acr", const="acr", nargs="?",
        choices=("acr", "echo", "p835"), help="Use regular ACR questions or echo questions")

    # check input arguments
    args = parser.parse_args()

    assert os.path.exists(args.cfg), f"No config file in {args.cfg}"

    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(args.cfg)

    main(
        args=args,
        scale_api_key = cfg.get("CommonAccountKeys", 'ScaleAPIKey'),
        scale_account_name = cfg.get("CommonAccountKeys", 'ScaleAccountName')
    )
