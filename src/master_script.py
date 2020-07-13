"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

import argparse
import os
import configparser as CP
from jinja2 import Template
import pandas as pd
import create_input as ca
from azure.storage.blob import BlockBlobService, PageBlobService, AppendBlobService
from azure.storage.file import FileService
import asyncio

class ClipsInAzureStorageAccount(object):
    def __init__(self, config, alg):
        self._account_name = os.path.basename(config['StorageUrl']).split('.')[0]
        if '.file.core.windows.net' in config['StorageUrl']:
            self._account_type = 'FileStore'
        elif '.blob.core.windows.net' in config['StorageUrl']:
            self._account_type = 'BlobStore'
        self._account_key = config['StorageAccountKey']
        self._container = config['Container']
        self._alg = alg
        self._clips_path = config['Path'].lstrip('/')
        self._clip_names = []
        self._modified_clip_names = []
        self._SAS_token = ''

    @property
    def container(self):
        return self._container

    @property
    def alg(self):
        return self._alg

    @property
    def clips_path(self):
        return self._clips_path

    @property
    async def clip_names(self):
        if len(self._clip_names) <= 0:
            await self.get_clips()
        return self._clip_names

    @property
    def store_service(self):
        if self._account_type == 'FileStore':
            return FileService(account_name = self._account_name, account_key = self._account_key)
        elif self._account_type == 'BlobStore':
            return BlockBlobService(account_name=self._account_name, account_key=self._account_key)

    @property
    def modified_clip_names(self):
        self._modified_clip_names = [os.path.basename(clip) for clip in self._clip_names]
        return self._modified_clip_names

    async def traverse_down_filestore(self, dirname):
        files = self.store_service.list_directories_and_files(self.container, os.path.join(self.clips_path, dirname))
        await self.retrieve_contents(files, dirname)

    async def retrieve_contents(self, list_generator, dirname=''):
        for e in list_generator:
            if '.wav' in e.name:
                if not dirname:
                    self._clip_names.append(e.name)
                else:
                    self._clip_names.append(posixpath.join(dirname.lstrip('/'), e.name))
            else:
                await self.traverse_down_filestore(e.name)

    async def get_clips(self):
        if self._account_type == 'FileStore':
            files = self.store_service.list_directories_and_files(self.container, self.clips_path)
            if not self._SAS_token:
                self._SAS_token = self.store_service.generate_share_shared_access_signature(self.container, permission='read', expiry=datetime.datetime(2019, 10, 30, 12, 30), start=datetime.datetime.now())
            await self.retrieve_contents(files)
        elif self._account_type == 'BlobStore':
            blobs = self.store_service.list_blobs(self.container, self.clips_path)
            await self.retrieve_contents(blobs)

    def make_clip_url(self, filename):
        if self._account_type == 'FileStore':
            source_url = self.store_service.make_file_url(self.container, self.clips_path, filename, sas_token=self._SAS_token)
        elif self._account_type == 'BlobStore':
            source_url = self.store_service.make_blob_url(self.container, filename)
        return source_url

class GoldSamplesInStore(ClipsInAzureStorageAccount):
    def __init__(self, config, alg):
        super().__init__(config, alg)
        self._SAS_token = ''

    async def get_dataframe(self):
        clips = await self.clip_names
        df = pd.DataFrame(columns=['gold_clips', 'gold_clips_ans'])
        clipsList = []
        for clip in clips:
            clipUrl = self.make_clip_url(clip)
            rating = 5
            if 'noisy' in clipUrl.lower():
                rating = 1

            clipsList.append({'gold_clips':clipUrl, 'gold_clips_ans':rating})

        df = df.append(clipsList)
        return df

class TrappingSamplesInStore(ClipsInAzureStorageAccount):
    async def get_dataframe(self):
        clips = await self.clip_names
        df = pd.DataFrame(columns=['trapping_clips', 'trapping_ans'])
        clipsList = []
        for clip in clips:
            clipUrl = self.make_clip_url(clip)
            rating = 0
            if '_bad_' in clip.lower():
                rating = 1
            elif '_poor_' in clip.lower():
                rating = 2
            elif '_fair_' in clip.lower():
                rating = 3
            elif '_good_' in clip.lower():
                rating = 4
            elif '_excellent_' in clip.lower():
                rating = 5

            clipsList.append({'trapping_clips':clipUrl, 'trapping_ans':rating})

        df = df.append(clipsList)
        return df

class PairComparisonSamplesInStore(ClipsInAzureStorageAccount):
    async def get_dataframe(self):
        clips = await self.clip_names
        pair_a_clips = [self.make_clip_url(clip) for clip in clips if '40S_' in clip]
        pair_b_clips = [clip.replace('40S_', '50S_') for clip in pair_a_clips]

        df = pd.DataFrame({'pair_a':pair_a_clips, 'pair_b':pair_b_clips})
        return df


def create_analyzer_cfg_acr(cfg, template_path, out_path):
    """
    create cfg file to be used by analyzer script (acr method)
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating config file for result_parser")
    config = {}

    config['q_num'] = int(cfg['create_input']['number_of_clips_per_session']) + \
                      int(cfg['create_input']['number_of_trapping_per_session']) + \
                      int(cfg['create_input']['number_of_gold_clips_per_session'])

    config['max_allowed_hits'] = cfg['acr_html']['allowed_max_hit_in_project']

    config['quantity_hits_more_than'] = cfg['acr_html']['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['acr_html']['quantity_bonus']
    config['quality_top_percentage'] = cfg['acr_html']['quality_top_percentage']
    config['quality_bonus'] = cfg['acr_html']['quality_bonus']

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    t = Template(content)
    cfg_file = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(cfg_file)
        file.close()
    print(f"  [{out_path}] is created")


def create_analyzer_cfg_p835(cfg, template_path, out_path):
    """
    create cfg file to be used by analyzer script (acr method)
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating config file for result_parser")
    config = {}

    config['q_num'] = int(cfg['create_input']['number_of_clips_per_session']) + \
                      int(cfg['create_input']['number_of_trapping_per_session']) + \
                      int(cfg['create_input']['number_of_gold_clips_per_session'])

    config['max_allowed_hits'] = cfg['p835_html']['allowed_max_hit_in_project']

    config['quantity_hits_more_than'] = cfg['p835_html']['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['p835_html']['quantity_bonus']
    config['quality_top_percentage'] = cfg['p835_html']['quality_top_percentage']
    config['quality_bonus'] = cfg['p835_html']['quality_bonus']

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    t = Template(content)
    cfg_file = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(cfg_file)
        file.close()
    print(f"  [{out_path}] is created")


def create_analyzer_cfg_dcr_ccr(cfg, template_path, out_path):
    """
    create cfg file to be used by analyzer script (ccr/dcr method)
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating config file for result_parser")
    config = {}

    config['q_num'] = int(cfg['create_input']['number_of_clips_per_session']) + \
                      int(cfg['create_input']['number_of_trapping_per_session'])

    config['max_allowed_hits'] = cfg['dcr_ccr_html']['allowed_max_hit_in_project']

    config['quantity_hits_more_than'] = cfg['dcr_ccr_html']['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['dcr_ccr_html']['quantity_bonus']
    config['quality_top_percentage'] = cfg['dcr_ccr_html']['quality_top_percentage']
    config['quality_bonus'] = cfg['dcr_ccr_html']['quality_bonus']

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    t = Template(content)
    cfg_file = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(cfg_file)
        file.close()
    print(f"  [{out_path}] is created")


async def create_hit_app_ccr_dcr(cfg, template_path, out_path, training_path, cfg_g):
    """
    Create the hit_app (html file) corresponding to this project for ccr and dcr
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating custom hit_app (html)")

    config = {}
    config['cookie_name'] = cfg['cookie_name']
    config['qual_cookie_name'] = cfg['qual_cookie_name']
    config['allowed_max_hit_in_project'] = cfg['allowed_max_hit_in_project']

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = float(cfg['quality_bonus']) + float(cfg['quantity_bonus'])
    config['sum_quantity'] = float(cfg['quantity_bonus']) + float(cfg['hit_base_payment'])
    config['sum_quality'] = config['quality_bonus'] + float(cfg['hit_base_payment'])

    # rating urls
    rating_urls = []
    n_clips = int(cfg_g['number_of_clips_per_session'])
    n_traps = int(cfg_g['number_of_trapping_per_session'])
    #'dummy':'dummy' is added becuase of current bug in AMT for replacing variable names. See issue #6
    for i in range(0, n_clips):
        rating_urls.append({"ref": f"${{Q{i}_R}}", "processed": f"${{Q{i}_P}}", 'dummy': 'dummy'})

    if n_traps > 1:
        print("more than 1 trapping clips question is not supported. Proceed with 1 trap")
    rating_urls.append({"ref": "${TP}", "processed": "${TP}", 'dummy': 'dummy'})
    if 'number_of_gold_clips_per_session' in cfg_g:
        print("Gold clips are not supported for CCR and DCR method. Proceed without them")
    config['rating_urls'] = rating_urls

    # training urls
    df_train = pd.read_csv(training_path)
    train_urls = []
    train_ref = None
    for index, row in df_train.iterrows():
        if train_ref is None:
            train_ref = row['training_references']
        train_urls.append({"ref": f"{row['training_references']}", "processed": f"{row['training_clips']}"})
    # add a trapping clips to the training section
    train_urls.append({"ref": f"{train_ref}", "processed": f"{train_ref}"})
    config['training_urls'] = train_urls
    config['training_trap_urls'] = train_ref

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(html)
    print(f"  [{out_path}] is created")


async def create_hit_app_acr(cfg, template_path, out_path, training_path, trap_path, cfg_g, cfg_trapping_store):
    """
    Create the ACR.html file corresponding to this project
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating custom acr.html")
    df_trap = pd.DataFrame()
    if trap_path and os.path.exists(trap_path):
        df_trap = pd.read_csv(trap_path, nrows=1)
    else:
        trapclipsstore = TrappingSamplesInStore(cfg_trapping_store, 'TrappingQuestions')
        df_trap = await trapclipsstore.get_dataframe()

    for index, row in df_trap.iterrows():
        trap_url = row['trapping_clips']
        trap_ans = row['trapping_ans']

    config = {}
    config['cookie_name'] = cfg['cookie_name']
    config['qual_cookie_name'] = cfg['qual_cookie_name']
    config['allowed_max_hit_in_project'] = cfg['allowed_max_hit_in_project']
    config['training_trap_urls'] = trap_url
    config['training_trap_ans'] = trap_ans

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = float(cfg['quality_bonus']) + float(cfg['quantity_bonus'])
    config['sum_quantity'] = float(cfg['quantity_bonus']) + float(cfg['hit_base_payment'])
    config['sum_quality'] = config['quality_bonus'] + float(cfg['hit_base_payment'])

    df_train = pd.read_csv(training_path)
    train = []
    for index, row in df_train.iterrows():
        train.append(row['training_clips'])
    train.append(trap_url)
    config['training_urls'] = train

    # rating urls
    rating_urls = []
    n_clips = int(cfg_g['number_of_clips_per_session'])
    n_traps = int(cfg_g['number_of_trapping_per_session'])
    n_gold_clips = int(cfg_g['number_of_gold_clips_per_session'])

    for i in range(0, n_clips ):
        rating_urls.append('${Q'+str(i)+'}')
    if n_traps > 1:
        raise Exception("more than 1 trapping clips question is not supported.")
    if n_traps == 1:
        rating_urls.append('${TP}')

    if  n_gold_clips > 1:
        raise Exception("more than 1 gold question is not supported.")
    if n_gold_clips == 1:
        rating_urls.append('${gold_clips}')

    config['rating_urls'] = rating_urls

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(html)
    print(f"  [{out_path}] is created")


async def create_hit_app_p835(cfg, template_path, out_path, training_path, trap_path, cfg_g, cfg_trapping_store):
    """
    Create the p835.html file corresponding to this project
    :param cfg:
    :param template_path:
    :param out_path:
    :return:
    """
    print("Start creating custom p835.html")
    df_trap = pd.DataFrame()
    if trap_path and os.path.exists(trap_path):
        df_trap = pd.read_csv(trap_path, nrows=1)
    else:
        trapclipsstore = TrappingSamplesInStore(cfg_trapping_store, 'TrappingQuestions')
        df_trap = await trapclipsstore.get_dataframe()

    for index, row in df_trap.iterrows():
        trap_url = row['trapping_clips']
        trap_ans = row['trapping_ans']

    config = {}
    config['cookie_name'] = cfg['cookie_name']
    config['qual_cookie_name'] = cfg['qual_cookie_name']
    config['allowed_max_hit_in_project'] = cfg['allowed_max_hit_in_project']
    config['training_trap_urls'] = trap_url
    config['training_trap_ans'] = trap_ans

    config['hit_base_payment'] = cfg['hit_base_payment']
    config['quantity_hits_more_than'] = cfg['quantity_hits_more_than']
    config['quantity_bonus'] = cfg['quantity_bonus']
    config['quality_top_percentage'] = cfg['quality_top_percentage']
    config['quality_bonus'] = float(cfg['quality_bonus']) + float(cfg['quantity_bonus'])
    config['sum_quantity'] = float(cfg['quantity_bonus']) + float(cfg['hit_base_payment'])
    config['sum_quality'] = config['quality_bonus'] + float(cfg['hit_base_payment'])

    df_train = pd.read_csv(training_path)
    train = []
    for index, row in df_train.iterrows():
        train.append(row['training_clips'])
    train.append(trap_url)
    config['training_urls'] = train

    # rating urls
    rating_urls = []
    n_clips = int(cfg_g['number_of_clips_per_session'])
    n_traps = int(cfg_g['number_of_trapping_per_session'])
    n_gold_clips = int(cfg_g['number_of_gold_clips_per_session'])

    for i in range(0, n_clips ):
        rating_urls.append('${Q'+str(i)+'}')
    if n_traps > 1:
        raise Exception("more than 1 trapping clips question is not supported.")
    if n_traps == 1:
        rating_urls.append('${TP}')

    if  n_gold_clips > 1:
        raise Exception("more than 1 gold question is not supported.")
    if n_gold_clips == 1:
        rating_urls.append('${gold_clips}')

    config['rating_urls'] = rating_urls

    with open(template_path, 'r') as file:
        content = file.read()
        file.seek(0)
    t = Template(content)
    html = t.render(cfg=config)

    with open(out_path, 'w') as file:
        file.write(html)
    print(f"  [{out_path}] is created")


async def prepare_csv_for_create_input(cfg, test_method, clips, gold, trapping, general):
    """
    Merge different input files into one dataframe
    :param test_method
    :param clips:
    :param trainings:
    :param gold:
    :param trapping:
    :param general:
    :return:
    """
    df_clips = pd.DataFrame()
    df_gold = pd.DataFrame()
    df_trap = pd.DataFrame()
    rating_clips = []
    if clips and os.path.exists(clips):
        df_clips = pd.read_csv(clips)
    else:
        rating_clips_stores = cfg.get('RatingClips', 'RatingClipsConfigurations').split(',')
        for model in rating_clips_stores:
            enhancedClip = ClipsInAzureStorageAccount(cfg[model], model)
            eclips = await enhancedClip.clip_names
            eclips_urls = [enhancedClip.make_clip_url(clip) for clip in eclips]

            print('length of urls for store [{0}] is [{1}]'.format(model, len(await enhancedClip.clip_names)))
            rating_clips = rating_clips + eclips_urls

        df_clips = pd.DataFrame({'rating_clips':rating_clips})
    
    df_general = pd.read_csv(general)
    if test_method in ["acr", "p835"]:
        if gold and os.path.exists(gold):
            df_gold = pd.read_csv(gold)
        else:
            goldclipsstore = GoldSamplesInStore(cfg['GoldenSample'], 'GoldenSample')
            df_gold = await goldclipsstore.get_dataframe()
            print('total gold clips from store [{0}]'.format(len(await goldclipsstore.clip_names)))

        if trapping and os.path.exists(trapping):
            df_trap = pd.read_csv(trapping)
        else:
            trapclipsstore = TrappingSamplesInStore(cfg['TrappingQuestions'], 'TrappingQuestions')
            df_trap = await trapclipsstore.get_dataframe()
            print('total trapping clips from store [{0}]'.format(len(await trapclipsstore.clip_names)))
    else:
        df_gold = None
        if not os.path.exists(clips):
            testclipsstore = ClipsInAzureStorageAccount(cfg['noisy'], 'noisy')
            testclipsurls = [testclipsstore.make_clip_url(clip) for clip in await testclipsstore.clip_names]
            print('The total test clips for our study is [{0}]'.format(len(testclipsurls)))

            clipdictList = []
            for eclip in rating_clips:
                for i, c in enumerate(testclipsurls):
                    if os.path.basename(c) in eclip:
                        clipdictList.append({'rating_clips':eclip, 'references':testclipsurls[i]})
                        break

            df_clips = pd.DataFrame(clipdictList)
        df_trap = df_clips[['references']].copy()
        df_trap.rename(columns={'references': 'trapping_clips'}, inplace=True)

    result = pd.concat([df_clips, df_gold, df_trap, df_general], axis=1, sort=False)
    return result


async def main(cfg, test_method, args):
    # check assets
    general_path = os.path.join(os.path.dirname(__file__), 'assets_master_script/general.csv')
    #   for acr
    acr_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/ACR_template.html')
    acr_cfg_template_path = os.path.join(os.path.dirname(__file__),
                                         'assets_master_script/acr_result_parser_template.cfg')
    #   for dcr
    dcr_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/DCR_template.html')
    #   for ccr
    ccr_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/CCR_template.html')
    dcr_ccr_cfg_template_path = os.path.join(os.path.dirname(__file__),
                                             'assets_master_script/dcr_ccr_result_parser_template.cfg')
    #   for  p835
    p835_template_path = os.path.join(os.path.dirname(__file__), 'P808Template/P835_template.html')
    p835_cfg_template_path = os.path.join(os.path.dirname(__file__),
                                          'assets_master_script/acr_result_parser_template.cfg')
    template_path = ''

    assert os.path.exists(general_path), f"No csv file containing general infos in {general_path}"
    if test_method == "acr":
        assert os.path.exists(acr_template_path), f"No html template file found  in {acr_template_path}"
        assert os.path.exists(acr_cfg_template_path), f"No cfg template  found  in {acr_cfg_template_path}"
        template_path = acr_template_path

    if test_method == "dcr":
        assert os.path.exists(dcr_template_path), f"No html template file found  in {dcr_template_path}"
        assert os.path.exists(dcr_ccr_cfg_template_path), f"No cfg template  found  in {dcr_ccr_cfg_template_path}"
        template_path = dcr_template_path

    if test_method == "ccr":
        assert os.path.exists(ccr_template_path), f"No html template file found  in {ccr_template_path}"
        assert os.path.exists(dcr_ccr_cfg_template_path), f"No cfg template  found  in {dcr_ccr_cfg_template_path}"
        template_path = ccr_template_path

    if test_method == "p835":
        assert os.path.exists(p835_template_path), f"No html template file found  in {p835_template_path}"
        assert os.path.exists(p835_cfg_template_path), f"No cfg template  found  in {p835_cfg_template_path}"
        template_path = p835_template_path

    # create output folder
    output_dir = args.project
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    # prepare format
    df = await prepare_csv_for_create_input(cfg, test_method, args.clips, args.gold_clips, args.trapping_clips, general_path)

    # create inputs
    print('Start validating inputs')
    ca.validate_inputs(cfg['create_input'], df, test_method)
    print('... validation is finished.')

    output_csv_file = os.path.join(output_dir, args.project+'_publish_batch.csv')
    ca.create_input_for_mturk(cfg['create_input'], df, test_method, output_csv_file)

    # create hit_app
    output_html_file = os.path.join(output_dir, f"{args.project}_{test_method}.html")
    if test_method == 'acr':
        await create_hit_app_acr(cfg['acr_html'], template_path, output_html_file, args.training_clips,
                           args.trapping_clips, cfg['create_input'], cfg['TrappingQuestions'])
    elif test_method == 'p835':
        await create_hit_app_p835(cfg['acr_html'], template_path, output_html_file, args.training_clips,
                                 args.trapping_clips, cfg['create_input'], cfg['TrappingQuestions'])
    else:
        await create_hit_app_ccr_dcr(cfg['dcr_ccr_html'], template_path, output_html_file, args.training_clips,
                               cfg['create_input'])

    # create a config file for analyzer
    output_cfg_file = os.path.join(output_dir, f"{args.project}_{test_method}_result_parser.cfg")
    if test_method == 'acr':
        create_analyzer_cfg_acr(cfg, acr_cfg_template_path, output_cfg_file)
    elif test_method == 'p835':
        create_analyzer_cfg_p835(cfg, p835_cfg_template_path, output_cfg_file)
    else:
        create_analyzer_cfg_dcr_ccr(cfg, dcr_ccr_cfg_template_path, output_cfg_file)

if __name__ == '__main__':
    print("Welcome to the Master script for ACR test.")
    parser = argparse.ArgumentParser(description='Master script to prepare the ACR test')
    parser.add_argument("--project", help="Name of the project", required=True)
    parser.add_argument("--cfg", help="Configuration file, see master.cfg", required=True)
    parser.add_argument("--method", required=True,
                        help="one of the test methods: 'acr', 'dcr', or 'ccr'")
    parser.add_argument("--clips", help="A csv containing urls of all clips to be rated in column 'rating_clips', in "
                                        "case of ccr/dcr it should also contain a column for 'references'")
    parser.add_argument("--gold_clips", help="A csv containing urls of all gold clips in column 'gold_clips' and their "
                                             "answer in column 'gold_clips_ans'")
    parser.add_argument("--training_clips", help="A csv containing urls of all training clips to be rated in training "
                                                 "section. Column 'training_clips'", required=True)
    parser.add_argument("--trapping_clips", help="A csv containing urls of all trapping clips. Columns 'trapping_clips'"
                                                 "and 'trapping_ans'")
    # check input arguments
    args = parser.parse_args()

    methods = ['acr', 'dcr', 'ccr', 'p835']
    test_method = args.method.lower()
    assert test_method in methods, f"No such a method supported, please select between 'acr', 'dcr', 'ccr', 'p835'"
    assert os.path.exists(args.cfg), f"No config file in {args.cfg}"
    assert os.path.exists(args.training_clips), f"No csv file containing training clips in {args.training_clips}"

    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(args.cfg)

    if args.clips:
        assert os.path.exists(args.clips), f"No csv file containing clips in {args.clips}"
    elif cfg.has_option('RatingClips', 'RatingClipsConfigurations'):
        assert len(cfg['RatingClips']['RatingClipsConfigurations']) > 0, f"No cloud store for clips specified in config"
    else:
        assert True, "Neither clips file not cloud store provided for rating clips"

    if test_method in ["acr", "p835"]:
        if args.gold_clips:
            assert os.path.exists(args.gold_clips), f"No csv file containing gold clips in {args.gold_clips}"
        elif cfg.has_option('GoldenSample', 'Path'):
            assert len(cfg['GoldenSample']['Path']) > 0, "No golden clips store found"
        else:
            assert True, "Neither gold clips file nor store configuration provided"

        if args.trapping_clips:
            assert os.path.exists(args.trapping_clips), f"No csv file containing trapping  clips in {args.trapping_clips}"
        elif cfg.has_option('TrappingQuestions', 'Path'):
            assert len(cfg['TrappingQuestions']['Path']) > 0, "No golden clips store found"
        else:
            assert True, "Neither Trapping clips file nor store configuration provided"

    asyncio.run(main(cfg, test_method, args))
