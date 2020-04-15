# -*- coding: utf-8 -*-
"""
Created on Fri Feb 21 11:35:55 2020

@author: vigopal
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.formula.api import ols
from scipy import stats

input_file = r"C:\Users\vigopal\source\repos\hitapp_p808\src\TFNet_Bigmodel_04_14_2020\Batch_3994382_batch_results_votes_per_clip.csv"
output_file = r"C:\Users\vigopal\source\repos\hitapp_p808\src\TFNet_Bigmodel_04_14_2020\summary_phasen.txt"


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

formula = 'rating ~ C(model, Treatment(reference = "noisy_700_testclips_validated_adsp_filtered_v134_20mslookahead_3msoverlap")) + C(file, Sum)'
lm = ols(formula, dfmelt).fit()

with open(output_file, 'w') as fh:
    fh.write(lm.summary().as_text())


