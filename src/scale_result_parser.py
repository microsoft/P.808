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
import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import scaleapi

now = datetime.now()  # current date and time


def main(cfg, args):
    scaleapi_key = cfg.get("CommonAccountKeys", 'ScaleAPIKey')
    client = scaleapi.ScaleClient(scaleapi_key)

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
            start_time=(now - timedelta(days=args.ago)).strftime("%Y-%m-%d"),
            next_token=next_token,
            project=cfg.get("CommonAccountKeys", 'ScaleAccountName'),
        )
        for task in tasks:
            counter += 1
            # print(f'Downloading Task {counter} | ${task.task_id}')
            all_tasks.append(task)
            next_token = tasks.next_token
        if (next_token == None):
            break

    results = []

    for task in all_tasks:
        # Filter out results that are not a part of the interested project
        if task.param_dict['metadata']['group'] != args.project:
            continue

        for file_url in task.param_dict['metadata']['file_urls']:
            clip_dict = {
                'short_file_name': task.param_dict['metadata']['file_shortname']}
            clip_dict['model'] = file_url
            clip_dict['file_url'] = task.param_dict['metadata']['file_urls'][file_url]
            ratings = task.param_dict['response']['annotations'][file_url]
            for i in range(len(ratings)):
                vote = 'vote_' + str(i+1)
                clip_dict[vote] = ratings[i]
            clip_dict['MOS'] = np.mean(ratings)
            clip_dict['n'] = len(ratings)
            clipset_match = re.match(
                '.*[/](?P<clipset>audioset|ms_realrec|noreverb_clnsp|reverb_clnsp|stationary)', clip_dict['file_url'])
            clip_dict['clipset'] = clipset_match.groupdict()['clipset']
            results.append(clip_dict)

    df = pd.DataFrame(results)
    df.to_csv(os.path.join(
        output_dir, "Batch_{0}_per_clip_results.csv".format(now.strftime("%m%d%Y"))))
    model_pivot_table = df.pivot_table(
        values='MOS', index='model', columns='clipset', margins=True, margins_name='Overall', aggfunc=[np.mean, len, np.std])
    model_pivot_table = model_pivot_table.swaplevel(axis=1)
    model_pivot_table.drop('Overall', inplace=True)
    for cols in model_pivot_table.columns.levels[0]:
        model_pivot_table.loc[:, (cols, 'CI')] = model_pivot_table.loc[:, cols].apply(lambda x: 1.96 * x['std']/np.sqrt(x['len']), axis=1)
        model_pivot_table.loc[:, (cols, 'DMOS')] = model_pivot_table.loc[:, cols]. apply(lambda x: x['mean'] - model_pivot_table.loc['noisy', (cols, 'mean')], axis=1)

    model_pivot_table = model_pivot_table.sort_values(('Overall', 'mean'), ascending=False).sort_index(axis=1, ascending=False)
    model_pivot_table.to_csv(os.path.join(
        output_dir, "Batch_{0}_per_condition_results.csv".format(now.strftime("%m%d%Y"))))


if __name__ == '__main__':
    print("Welcome to the Scale result parsing script for ACR test.")
    parser = argparse.ArgumentParser(
        description='Master script to prepare the ACR test')
    parser.add_argument(
        "--project", help="Name of the batch to club results by", required=True)
    parser.add_argument(
        "--cfg", help="Configuration file, see master.cfg", required=True)
    parser.add_argument(
        "--ago", help="Number of days ago to start the search from", default=1, type=int)

    # check input arguments
    args = parser.parse_args()

    assert os.path.exists(args.cfg), f"No config file in {args.cfg}"

    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(args.cfg)

    main(cfg, args)
