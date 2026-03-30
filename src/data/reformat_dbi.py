import sys, os, re
import numpy as np
import pandas as pd
import geopandas as gpd

import matplotlib.pyplot as plt

#def format_code(x):
#    x = str(x)
#    code = ''
#    for x1 in x:
#        if x1 in ['0','1','2','3','4','5','6','7','8','9']:
#            code = code +'9'
#        else:
#            code = code +'a'
#    return code
    
def format_block(x):
    c = re.compile('(?P<head>\d\/\d\/)?(?P<num>[0-9]{0,4})(?P<let>[a-zA-Z]{0,5})')
    m = c.match(x).groupdict()
    num, let = m['num'].replace('/1/',''), m['let']
    
    return '{:04d}{}'.format(int(num), let)

def format_lot(x):
    c = re.compile('(?P<head>[a-zA-Z]{0,4})(?P<body>[0-9]{0,3})(?P<tail>[a-zA-Z]{0,2})')
    m = c.match(x).groupdict()
    head, body, tail = m['head'], m['body'], m['tail']
    
    if len(head) == 0:
        body = '{:03d}'.format(int(body))
    return head+body+tail
    
if __name__=='__main__':
    DBI_IN = r'Q:\Model Projects\TSP\Shift\Parking Supply\parking_supply_estimates\Round_2_2016_04_11\2.1.2\parking_estimate_clean.csv'
    DBI_OUT = r'Q:\Model Research\TDM Evaluation Tool\Phase I\3-Data\Parking\dbi_parking.csv'
    dbi = pd.read_csv(DBI_IN, encoding= 'unicode_escape')
    dbi.rename(columns={x:x.lower() for x in dbi.columns.tolist()}, inplace=True)
    dbi.drop(columns=['unnamed: 0', 'mapblklot_x'], inplace=True)
    dbi.rename(columns={'mapblklot_y':'mapblklot'}, inplace=True)
    dbi = dbi.loc[pd.notnull(dbi['spaces'])]
    
    dbi_orig = dbi.copy()
    dbi = dbi[['mapblklot','blklot','block_num','lot_num','group','resunits','yrbuilt','spaces']]
    
    # these have changed since 2013
    dbi['change_flag'] = 0
    dbi.loc[dbi['block_num'].eq('6771') & dbi['lot_num'].isin(['40','040']),'change_flag'] = 1
    dbi.loc[dbi['block_num'].eq('4624') & dbi['lot_num'].isin(['4','04','004']),'change_flag'] = 1
    dbi.loc[dbi['block_num'].eq('4038') & dbi['lot_num'].isin(['29','029']),'change_flag'] = 1
    dbi.loc[dbi['block_num'].isin(['436D','0436D']) & dbi['lot_num'].isin(['32','032']),'change_flag'] = 1
    dbi.loc[dbi['block_num'].eq('3702') & dbi['lot_num'].isin(['51','051']),'change_flag'] = 1
    dbi.loc[dbi['block_num'].isin(['840','0840']) & dbi['lot_num'].isin(['36','036']),'change_flag'] = 1

    dbi.loc[dbi['block_num'].eq('6771') & dbi['lot_num'].isin(['40','040']),'lot_num'] = '052'
    dbi.loc[dbi['block_num'].eq('4624') & dbi['lot_num'].isin(['4','04','004']),'lot_num'] = '031'
    dbi.loc[dbi['block_num'].eq('4038') & dbi['lot_num'].isin(['29','029']),'lot_num'] = '051'
    dbi.loc[dbi['block_num'].isin(['436D','0436D']) & dbi['lot_num'].isin(['32','032']),'lot_num'] = '050'
    dbi.loc[dbi['block_num'].eq('3702') & dbi['lot_num'].isin(['51','051']),'lot_num'] = '308'
    dbi.loc[dbi['block_num'].isin(['840','0840']) & dbi['lot_num'].isin(['36','036']),'lot_num'] = '046'
    
    dbi['block_num'] = dbi['block_num'].map(lambda x: format_block(x))
    dbi['lot_num'] = dbi['lot_num'].map(lambda x: format_lot(x))
    dbi['mapblklot_orig'] = dbi['mapblklot']
    dbi['mapblklot'] = dbi['block_num']+ dbi['lot_num']
    
    dbi.loc[dbi['mapblklot'].ne(dbi['mapblklot_orig'])]
    dbi.to_csv(DBI_OUT)