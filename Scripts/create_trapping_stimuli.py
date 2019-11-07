"""
@author: Babak Naderi
"""
import argparse
from os.path import isfile, join, basename, dirname
import os
import configparser as CP
import librosa as lr
import numpy as np
import soundfile as sf
import csv

message_to_values={
    "bad_short": 1,
    "poor_short": 2,
    "fair_short": 3,
    "good_short": 4,
    "excellent_short": 5
}


def create_trap_db(cfg):
    """
    Creates the trapping dataset
    :param cfg: configuration file
    :return:
    """
    # create directory names
    source_folder = join(dirname(__file__), cfg['input_directory'], 'source')
    msg_folder = join(dirname(__file__), cfg['input_directory'], 'messages')
    output_folder = join(dirname(__file__), cfg['input_directory'], 'output')

    # check directories exist
    assert os.path.exists(source_folder), f"No 'source' directory found, expected in {source_folder}]"
    assert os.path.exists(msg_folder), f"No 'messages' directory found, expected in {msg_folder}]"

    # find list of files
    source_files = [join(source_folder, f) for f in os.listdir(source_folder) if isfile(join(source_folder, f))]
    msg_files = [join(msg_folder, f) for f in os.listdir(msg_folder)
                 if isfile(join(msg_folder, f)) and cfg['message_file_prefix'] in f]
    count = 0
    list_of_file=[]
    for s_f in source_files:
        for msg_f in msg_files:
            # cut last part of message file name to be appended to the output file
            # e.g. from "ACR_Bad_short.wav" --> took "Bad_short"
            msg = os.path.splitext(
                basename(msg_f))[0].replace(cfg['message_file_prefix'], '').lower()
            # create output filename format [source_filename]_tp_[suffix from
            output_f_name = f'{os.path.splitext(basename(s_f))[0]}_{msg}.wav'
            output_path = join(output_folder,
                               output_f_name)
            create_trap_stimulus(s_f,
                                 msg_f,
                                 output_path,cfg)
            count +=1
            list_of_file.append({'trapping_clips':output_f_name, 'trapping_ans':message_to_values[msg]})
    output_report = join(output_folder,'output_report.csv')
    with open(output_report, 'w', newline='') as output_file:
        headers_written = False
        for f in list_of_file:
            if not headers_written:
                writer = csv.DictWriter(output_file, fieldnames=sorted(f))
                headers_written = True
                writer.writeheader()
            writer.writerow(f)

    return count


def create_trap_stimulus(source, message, output, cfg):
    """
    Create a trapping stimulus
    :param source: path to source stimuli from dataset
    :param message: path to the message clip
    :param output: path to output file
    :param cfg: configuration
    :return:
    """
    # check how to set the duration
    if ('keep_original_duration' in cfg) and \
            (cfg['keep_original_duration'].upper() == 'TRUE'):
        source_duration = lr.get_duration(filename=source)
        msg_duration = lr.get_duration(filename=message)
        # if it negative, just use the default 3 seconds
        prefix_duration = source_duration-msg_duration
        if prefix_duration <= 0:
            prefix_duration = 3
        source, source_sr = lr.load(source, duration=prefix_duration)
    else:
        source, source_sr = lr.load(source, duration=int(cfg["include_from_source_stimuli_in_second"]))
    msg, msg_sr = lr.load(message)
    msg = lr.resample(msg,source_sr,msg_sr)
    merged = np.append(source, msg)
    sf.write(output, merged, source_sr, subtype='PCM_24')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create trapping/gold standard stimuli dataset. ')
    # Configuration: read it from trapping.cfg
    parser.add_argument("--cfg", default="trapping.cfg",
                        help="Check trapping.cfg for all the details")
    args = parser.parse_args()

    cfgpath = join(dirname(__file__), args.cfg)
    assert os.path.exists(cfgpath), f"No configuration file in {cfgpath}]"
    cfg = CP.ConfigParser()
    cfg._interpolation = CP.ExtendedInterpolation()
    cfg.read(cfgpath)

    tp_cfg = cfg._sections['trappings']

    print('Start creating files')
    n_created_files= create_trap_db(tp_cfg)
    print(f'{n_created_files} files created.')

