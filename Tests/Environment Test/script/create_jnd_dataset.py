"""
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
@author: Babak Naderi
"""

from audiolib import audioread, audiowrite, snr_mixer
from os.path import isfile, join,  basename
import os
import numpy as np


"""
Given a source folder, add white-noise in a range of different SNR levels to all files in the source folder.
"""

if __name__=="__main__":

    source_folder = "clips"
    source_files = [join(source_folder, f) for f in os.listdir(source_folder) if isfile(join(source_folder, f))]
    output_folder = source_folder+"_snr"
    snr_min = 30
    snr_max = 50

    for f in source_files:
        clean, fs = audioread(f)
        # white-noise
        noise = np.random.normal(0, 1, len(clean))
        for i in range (snr_min,snr_max):
            clean_snr, noise_snr, noisy_snr = snr_mixer(clean=clean, noise=noise, snr=i)
            output_filename = join(output_folder,
                                   f'{i}S_{os.path.splitext(basename(f))[0]}.wav')
            audiowrite(noisy_snr, fs,output_filename, norm=False)


