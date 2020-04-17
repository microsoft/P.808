# -*- coding: utf-8 -*-
"""
Created on Fri Feb 21 11:35:55 2020

@author: vigopal
"""

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from statsmodels.formula.api import ols
from scipy import stats
import argparse

def main(args):
  input_file = args.input_file
  output_file = args.input_file.replace(os.path.basename(args.input_file), "summary.txt")


  # load data
  df = pd.read_csv(input_file)

  # prepare file for anova
  dfmelt = pd.melt(df, id_vars = ['file_url', 'n', 'MOS', 'std', '95%CI', 'clipset',
                                  'short_file_name', 'model'],
                   value_vars = ['vote_1', 'vote_2', 'vote_3', 'vote_4', 'vote_5'],
                                 value_name = 'rating').sort_values(by = 'short_file_name', axis=0)
  dfmelt = dfmelt.dropna(subset=['rating'])
  #dfmelt['model_clipset'] = dfmelt.apply(lambda x: x['model'] + '__' + x['clipset'], axis = 1)
  # drop clips with less than 3 ratings per model
  models = dfmelt['model'].value_counts().index
  low_sample_clips = []
  for m in models:
      fcount = dfmelt[dfmelt.model==m].groupby(['short_file_name'])['rating'].count()
      low_sample_clips_m = fcount[fcount<3].index.tolist()
      if len(low_sample_clips_m)>0:
          print(low_sample_clips_m)
          low_sample_clips = low_sample_clips + low_sample_clips_m

  low_sample_clips = np.unique(low_sample_clips)
  dfmelt = dfmelt[~dfmelt['short_file_name'].isin(low_sample_clips)]

  # anova
  rating = dfmelt.rating
  model = dfmelt.model
  file = dfmelt.short_file_name

  formula = 'rating ~ C(model, Treatment(reference = "{0}")) + C(file, Sum)'.format(args.model_name)
  lm = ols(formula, dfmelt).fit()

  with open(output_file, 'w') as fh:
      fh.write(lm.summary().as_text())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Utility script to compute anova for models')
    # Configuration: read it from mturk.cfg
    parser.add_argument("--input_file", required=True,
                        help="Per clip rating file produced after result parsing")
    parser.add_argument("--model_name", required=True,
                        help="The name of the model to use as baseline for comparison")
    args = parser.parse_args()
    
    main(args)
