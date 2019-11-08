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

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Generate a local script out of P.808 Templates')
    # Configuration: read it from mturk.cfg
    parser.add_argument("--cfg", default="acr.cfg",
                        help="Read acr.cfg for all the details")

    args = parser.parse_args()

    cfgpath = os.path.join(os.path.dirname(__file__), args.cfg)
    assert os.path.exists(cfgpath), f"No configuration file as [{cfgpath}]"
    cfg = CP.ConfigParser()
    cfg.optionxform = str
    cfg.read(cfgpath)

    acr_cfg = cfg['local_acr']

    f = open("../ACR.html", "r")
    acr_file = f.read()
    for key in acr_cfg:
        print (key)
        acr_file= acr_file.replace('${'+key+'}',acr_cfg[key])

    file_to_write = open("../ACR_local.html", "w")
    file_to_write.write(acr_file)
    file_to_write.close()