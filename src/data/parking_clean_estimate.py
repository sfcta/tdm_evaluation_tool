import sys, os
import numpy as np
import pandas as pd
import geopandas as gpd

def calc_spaces(row, tag='g1', std_len=17.0, std_wid = 9,
                com_len = 17.0, com_wid = 7.5):
    std_rows = row['%sd1' % tag] / (std_len + 12.0)
    std_cols = row['%sd2' % tag] / std_wid - 1
    std_spaces = std_rows * std_cols
    com_rows = row['%sd1' % tag] / (com_len + 12.0)
    com_cols = row['%sd2' % tag] / com_wid - 1
    com_spaces = com_rows * com_cols
    est_spaces_1 = round((std_spaces + com_spaces) / 2.0, 0)

    std_rows = row['%sd2' % tag] / (std_len + 12.0)
    std_cols = row['%sd1' % tag] / std_wid - 1
    std_spaces = std_rows * std_cols
    com_rows = row['%sd2' % tag] / (com_len + 12.0)
    com_cols = row['%sd1' % tag] / com_wid - 1
    com_spaces = com_rows * com_cols
    est_spaces_2 = round((std_spaces + com_spaces) / 2.0, 0)

    return max(est_spaces_1, est_spaces_2)

def get_best_estimate(row, tag='g1', thresh=14):
    if min(row['%sd1' % tag], row['%sd2' % tag]) < 14:
        return row['%s_est_sqft' % tag]
    else:
        return row['%s_est_rxc' % tag]

def format_blklot(blklot):
    blklot = str(blklot)
    if len(blklot) < 7:
        blklot = "0"*(7-len(blklot)) + blklot
    return blklot

if __name__=='__main__':
    # I/O Files
    CTL_FILE                = os.environ.get('control_file')
    print(CTL_FILE)
    config = configparser.ConfigParser()
    config.read(CTL_FILE)
    
    #inpath                  = r'Q:\Model Projects\ATG\TSS Task Force\Parking Supply\parking_supply_estimates'
    DBI_PARKING_FILE   = config['parking_supply']['DBI']
    AMS_FILE           = config['parking_supply']['TAZ_AMS']
    PARKMERCED_FILE    = config['parking_supply']['PARKMERCED_LOTS']
    LOT_FILE           = config['parking_supply']['LOTS']
    LOT_TO_TAZ_FILE    = config['parking_supply']['LOT_TO_TAZ']
    #LOT_UPDATE_FILE    = config['parking_supply']['']
    LOT_TO_MAZ_FILE    = config['parking_supply']['LOT_TO_MAZ']
    outpath = '.'
    outfile = 'parking_estimate_clean.csv'

    # area of parking
    std_sqft = config['parking_supply']['STANDARD_PARKING_SPACE_SQFT']
    com_sqft = config['parking_supply']['COMPACT_PARKING_SPACE_SQFT']
    #sqft     = 278 # from Parkmerced
    
    # vehicle dimensions - NOT USED
    #veh_std_len = 190.0 / 12.0
    #veh_std_wid = 71.0 / 12.0
    #veh_com_len = 177.2 / 12.0
    #veh_com_wid = 68.8 / 12.0

    # parking dimensions
    spc_std_len = config['parking_supply']['STANDARD_PARKING_SPACE_LENGTH']
    spc_std_wid = config['parking_supply']['STANDARD_PARKING_SPACE_WIDTH']
    spc_com_len = config['parking_supply']['COMPACT_PARKING_SPACE_LENGTH']
    spc_com_wid = config['parking_supply']['COMPACT_PARKING_SPACE_WIDTH']

    print "reading parking data"
    parking_data = pd.read_csv(DBI_PARKING_FILE, usecols=['GROUP','MAPBLKLOT','BLKLOT','LOT_NUM','FROM_ST','TO_ST','STREET',
                                                               'RESUNITS','YRBUILT','AMSZone',
                                                               'parking_supply','estimated','manual_override','qc_flag',
                                                               'g1d1','g1d2','g2d1','g2d2','g3d1','g3d2','g4d1','g4d2'])
    parking_data.rename(columns={x:x.lower() for x in parking_data.columns.tolist()}, inplace=True)                                                           
    print "reformatting BLKLOT"
    parking_data['BLKLOT'] = parking_data['BLKLOT'].map(format_blklot)
    
    print "reading all parcel data"
    print "...reading parcels..."
    parcels = dataIO.dbf2df(LOT_FILE,cols=['MAPBLKLOT','BLKLOT','BLOCK_NUM','RESUNITS','YRBUILT','TAZ'])
    print "...reading parcel_to_taz..."
    parcel_to_taz = dataIO.dbf2df(LOT_TO_TAZ_FILE,cols=['MAPBLKLOT','BLKLOT','BLOCK_NUM','TAZ'])
    print "...reading parcel_update..."
    parcel_update = dataIO.dbf2df(LOT_UPDATE_FILE,cols=['MAPBLKLOT','BLKLOT','BLOCK_NUM','TAZ','YRBUILT','RESUNITS'])
    print "...reading parcel_to_maz..."
    parcel_to_maz = dataIO.dbf2df(LOT_TO_MAZ_FILE,cols=['MAPBLKLOT','BLKLOT','BLOCK_NUM','MAZ'])

    #print "mapping parcels to tazs for missing "
    parcels = parcels.set_index('BLKLOT')
    #parcel_update = parcel_update.set_index('BLKLOT')

    #print "updating parcel attributes for suspect values, using land use 2013"
    #print "...updating TAZs..."
    #parcels.loc[(pd.isnull(parcels['TAZ'])) | (parcels['TAZ'] == 0),'TAZ'] = parcel_update['TAZ']
    #print "...updating RESUNITS..."
    #parcels['new_RESUNITS'] = parcel_update['RESUNITS']
    #parcels.loc[pd.isnull(parcels['RESUNITS']), 'RESUNITS'] = parcels['new_RESUNITS']
    #parcels.loc[parcels['RESUNITS'] < parcels['new_RESUNITS'], 'RESUNITS'] = parcels['new_RESUNITS']
    #print "...updating YRBUILT..."
    #parcels['new_YRBUILT'] = parcel_update['YRBUILT']
    #parcels.loc[pd.isnull(parcels['YRBUILT']),'YRBUILT'] = parcels['new_YRBUILT']
    #parcels.loc[(parcels['YRBUILT'] < 1500) | (parcels['YRBUILT'] > 2016), 'YRBUILT'] = parcels['new_YRBUILT']

    print "attaching MAZs"
    parcel_to_maz = parcel_to_maz.set_index('BLKLOT')
    parcels['MAZ'] = parcel_to_maz['TAZ']
    parcels = parcels.reset_index()
    #parcel_update = parcel_update.reset_index()
    del parcel_update, parcel_to_maz
    
    print "reading AMS data"
    ams = pd.read_csv(AMS_FILE, usecols=['TAZ','ams_all','rs_ams'])

    print "merging data"
    parking_data = pd.merge(parking_data,parcel_to_taz,how='left',on='BLKLOT')
    parking_data = pd.merge(parking_data,ams,how='left',on='TAZ')
    del parcel_to_taz

    print "updating building attributes in parking_data file"
    parking_data = parking_data.set_index('BLKLOT')
    parcels_overlap = parcels.set_index('BLKLOT')
    parcels_overlap = parcels_overlap[parcels_overlap.index.isin(parking_data.index.tolist())]
    parking_data['new_RESUNITS'] = parcels_overlap['RESUNITS']
    parking_data['new_YRBUILT'] = parcels_overlap['YRBUILT']
    parking_data.loc[parking_data['new_RESUNITS'] > parking_data['RESUNITS'], 'RESUNITS'] = parking_data.loc[parking_data['new_RESUNITS'] > parking_data['RESUNITS'], 'new_RESUNITS']
    parking_data.loc[pd.isnull(parking_data['YRBUILT']) | (parking_data['YRBUILT'] < 1500) | (parking_data['YRBUILT'] > 2016),'YRBUILT'] = parking_data.loc[pd.isnull(parking_data['YRBUILT']) | (parking_data['YRBUILT'] < 1500) | (parking_data['YRBUILT'] > 2016),'new_YRBUILT']
    parking_data.to_csv(os.path.join(outpath,'log_new_vs_old.csv'))
    parking_data = parking_data.reset_index()
    
    no_year = parcels[(parcels['YRBUILT'].lt(1500)) | (parcels['YRBUILT'].gt(2016))]
    parcels_gb_block = parcels.groupby(['BLOCK_NUM'])
    parcels_gb_taz = parcels.groupby(['TAZ'])
    parcels['GROUP'] = np.nan
    parcels['year_estimated'] = 0
    parking_data['year_estimated'] = 0
    
    print "checking parking data for missing years"
    logfile = open(os.path.join(outpath,'logfile.txt'),'w')
    logfile.write('blklot,yrbuild_old,using,block_num_or_taz,yrbuilt_new,count,std\n')
    for idx, parcel in no_year.iterrows():
        block = parcels_gb_block.get_group(parcel['BLOCK_NUM'])
        block = block[pd.notnull(block['YRBUILT'])]
        block = block[block['YRBUILT'].between(1500,2016)]
        block_mean = block['YRBUILT'].mean()
        block_count = block['YRBUILT'].count()
        block_std = block['YRBUILT'].std()
        using = 'BLOCK'
        if pd.isnull(block_mean):
            block = parcels_gb_taz.get_group(parcel['TAZ'])
            block = block[pd.notnull(block['YRBUILT'])]
            block = block[block['YRBUILT'].between(1500,2016)]
            block_mean = block['YRBUILT'].mean()
            block_count = block['YRBUILT'].count()
            block_std = block['YRBUILT'].std()
            using = 'TAZ'
        try:
            parcels.loc[idx,'YRBUILT'] = int(block_mean)
            parcels.loc[idx,'year_estimated'] = 1
            parking_data.loc[parking_data['BLKLOT']==parcel['BLKLOT'], 'YRBUILT'] = int(block_mean)
            parking_data.loc[parking_data['BLKLOT']==parcel['BLKLOT'], 'year_estimated'] = 1
            print 'parcel %s, replace YRBUILT %d with block %s average %d (std: %f)' % (parcel['BLKLOT'], parcel['YRBUILT'], parcel['BLOCK_NUM'], block_mean, block_std)
            logfile.write('%s,%d,%s,%s,%d,%d,%f\n' % (parcel['BLKLOT'], parcel['YRBUILT'], using, parcel['BLOCK_NUM'], block_mean, block_count, block_std))
        except Exception as e:
            print e
            print 'idx: %s, parcel: %s, block_mean: %s' % (idx, parcel['BLKLOT'], block_mean)
            year = parcels.loc[idx,'YRBUILT']
            if not pd.isnull(year):
                try1 = int("1" + str(int(year))[1:])
                try2 = int("19" + str(int(year))[2:])
                try3 = int("2" + str(int(year))[1:])
                try4 = int("20" + str(int(year))[2:])
                best_try = np.nan
                for name, tr in zip(['try1','try2','try3','try4'],[try1, try2, try3, try4]):
                    if tr > 1500 and tr < 2016:
                        logfile.write('%s,%d,simplereplace_%s,,%d,,\n' % (parcel['BLKLOT'],parcel['YRBUILT'],name,tr))
                        parcels.loc[idx,'YRBUILT'] = tr
                        parking_data.loc[parking_data['BLKLOT']==parcel['BLKLOT'], 'YRBUILT'] = tr
                        parcels.loc[idx,'year_estimated'] = 1
                        parking_data.loc[parking_data['BLKLOT']==parcel['BLKLOT'], 'year_estimated'] = 1
                        break

    print "calculating bins"
    parking_data['size_bin'] = np.nan
    parking_data.loc[parking_data['RESUNITS'].eq(1),            'size_bin'] = 0
    parking_data.loc[parking_data['RESUNITS'].between(2,9),     'size_bin'] = 1
    parking_data.loc[parking_data['RESUNITS'].between(10,19),   'size_bin'] = 2
    parking_data.loc[parking_data['RESUNITS'].ge(20),           'size_bin'] = 3
    parking_data['area_type'] = np.nan
    parking_data.loc[parking_data['ams_all'].between(0.0,0.4),  'area_type'] = 0
    parking_data.loc[parking_data['ams_all'].between(0.4,0.65), 'area_type'] = 1
    parking_data.loc[parking_data['ams_all'].between(0.65,1.0), 'area_type'] = 2
    parking_data['year_bin'] = np.nan
    parking_data.loc[parking_data['YRBUILT'].between(1500,1955),'year_bin'] = 0
    parking_data.loc[parking_data['YRBUILT'].between(1956,2016),'year_bin'] = 1
    parking_data['GROUP'] = parking_data['GROUP'].fillna('None')

    print "estimating spaces based on garage dimensions using multiple methods"
    for g in ['g1','g2','g3','g4']:
        parking_data['%s_est_std_sqft' % g] = parking_data['%sd1' % g] * parking_data['%sd2' % g] / std_sqft
        parking_data['%s_est_com_sqft' % g] = parking_data['%sd1' % g] * parking_data['%sd2' % g] / com_sqft
        parking_data['%s_est_sqft' % g] = parking_data['%s_est_std_sqft' % g] + parking_data['%s_est_com_sqft' % g] / 2
        parking_data['%s_est_rxc' % g] = parking_data.apply(calc_spaces, axis=1, tag=g) # , std_len=spc_std_len, std_wid=spc_std_wid, com_len=spc_com_len, com_wid=spc_com_wid)
        parking_data['%s_spaces_best' % g] = parking_data.apply(get_best_estimate, axis=1, tag=g)
        #print parking_data['%s_spaces_best']

    print "getting best estimate of spaces from dimensions"
    parking_data['total_spaces_best'] = parking_data['g1_spaces_best']
    parking_data['total_spaces_best'] += parking_data['g2_spaces_best'] * pd.isnull(parking_data['g2_spaces_best'])
    parking_data['total_spaces_best'] += parking_data['g3_spaces_best'] * pd.isnull(parking_data['g3_spaces_best'])
    parking_data['total_spaces_best'] += parking_data['g4_spaces_best'] * pd.isnull(parking_data['g4_spaces_best'])
    parking_data.loc[parking_data['parking_supply'].convert_objects(convert_numeric=True).between(0,5000),'spaces'] = parking_data['parking_supply'].convert_objects(convert_numeric=True)
    parking_data.loc[(parking_data['estimated'].isin(['y','Y'])) & (~pd.isnull(parking_data['total_spaces_best'])), 'spaces'] = parking_data['total_spaces_best'].convert_objects(convert_numeric=True)

    print "applying manual overrides"
    parking_data.loc[~pd.isnull(parking_data['manual_override']),'spaces'] = parking_data['manual_override'].convert_objects(convert_numeric=True)
    print "removing qc flagged records"
    parking_data.loc[parking_data['qc_flag'].isin(['y','Y']),'spaces'] = np.nan
    print "calulating parking rate"
    parking_data['parking_rate'] = parking_data['spaces'] / parking_data['RESUNITS']
    print "replacing inf with nan"
    parking_data['parking_rate'] = parking_data['parking_rate'].replace([np.inf, -np.inf],np.nan)
    print "dropping high parking rates (>= 7 per unit)"
    parking_data.loc[parking_data['parking_rate'].ge(7),'spaces'] = np.nan
    parking_data.loc[parking_data['parking_rate'].ge(7),'parking_rate'] = np.nan

    print "excluding PARKMERCED from parcel-level parking rate estimates"
    parkmerced_parcels = pd.read_csv(PARKMERCED_FILE)
    parkmerced_parcels['BLKLOT'] = parkmerced_parcels['BLKLOT'].map(format_blklot)
    parkmerced_parcels = parkmerced_parcels.set_index('BLKLOT')
    parcels = parcels.set_index('BLKLOT')
    parcels.loc[parkmerced_parcels.index,'GROUP'] = 'PARKMERCED'
    parcels = parcels.reset_index()
    parking_data.loc[parking_data['BLKLOT'].isin(parkmerced_parcels.index.tolist()),'GROUP'] = 'PARKMERCED'
    parking_data.loc[parking_data['BLKLOT'].isin(parkmerced_parcels.index.tolist()),'spaces'] = np.nan
    parking_data.loc[parking_data['BLKLOT'].isin(parkmerced_parcels.index.tolist()),'parking_rate'] = np.nan

    print "calulating count, sum, avg rate"
    count = parking_data.pivot_table(index=['year_bin','size_bin'],columns=['area_type'],values=['spaces'],aggfunc='count')
    sum_spaces = parking_data.pivot_table(index=['year_bin','size_bin'],columns=['area_type'],values=['spaces'],aggfunc='sum')
    avg_rate = parking_data.pivot_table(index=['year_bin','size_bin'],columns=['area_type'],values=['parking_rate'],aggfunc='mean')
    
    print "writing %s" % outfile
    parking_data.to_csv(os.path.join(outpath,outfile))
    count.to_csv('count.csv')
    sum_spaces.to_csv('sum_spaces.csv')
    avg_rate.to_csv('avg_rate.csv')

    print "calculating bins for all parcels"
    parcels = pd.merge(parcels,ams,on='TAZ')
    parcels['size_bin'] = np.nan
    parcels.loc[parcels['RESUNITS'].eq(1),            'size_bin'] = 0
    parcels.loc[parcels['RESUNITS'].between(2,9),     'size_bin'] = 1
    parcels.loc[parcels['RESUNITS'].between(10,19),   'size_bin'] = 2
    parcels.loc[parcels['RESUNITS'].ge(20),           'size_bin'] = 3
    parcels['area_type'] = np.nan
    parcels.loc[parcels['ams_all'].between(0.0,0.4),  'area_type'] = 0
    parcels.loc[parcels['ams_all'].between(0.4,0.65), 'area_type'] = 1
    parcels.loc[parcels['ams_all'].between(0.65,1.0), 'area_type'] = 2
    parcels['year_bin'] = np.nan
    parcels.loc[parcels['YRBUILT'].between(1500,1955),'year_bin'] = 0
    parcels.loc[parcels['YRBUILT'].between(1956,2016),'year_bin'] = 1

    print "calculating average parking rate by classification"
    avg_rate2 = parking_data.groupby(['year_bin','size_bin','area_type']).mean()

    print "estimating number of parking spaces based on parking rate by classification"
    parcels = parcels.set_index(['year_bin','size_bin','area_type'])
    parcels['parking_rate'] = avg_rate2['parking_rate']
    parcels['parking_est'] = parcels['RESUNITS'] * parcels['parking_rate']
    parcels = parcels.reset_index().set_index('BLKLOT')
    #parking_data = parking_data.set_index('BLKLOT')
    actual_parking = parking_data[pd.notnull(parking_data['spaces'])]
    actual_parking = actual_parking.set_index('BLKLOT')
    parcels.loc[actual_parking.index,'parking_est'] = actual_parking['spaces']
    parcels.loc[actual_parking.index,'parking_rate'] = actual_parking['spaces'] / actual_parking['RESUNITS']

    print "reinserting PARKMERCED parcel estimates (these are not used in parcel-level parking rate calcs)"
    parcels.loc[parkmerced_parcels.index,'parking_est'] = parkmerced_parcels['Total Parking Estimate']
    parcels.loc[parkmerced_parcels.index,'parking_rate'] = parcels.loc[parkmerced_parcels.index,'parking_est'] / parcels.loc[parkmerced_parcels.index,'RESUNITS']
    parcels.to_csv(os.path.join(outpath,'parcels.csv'))
    #print parcels['parking_est'].sum()
    print "summing to taz"
    tazs = parcels.reset_index().groupby(['TAZ']).sum()
    tazs['parking_rate'] = tazs['parking_est'] / tazs['RESUNITS']
    tazs.to_csv(os.path.join(outpath,'taz_parking_estimates.csv'))

    print "summing to maz"
    mazs = parcels.reset_index().groupby(['MAZ']).sum()
    mazs['parking_rate'] = mazs['parking_est'] / mazs['RESUNITS']
    mazs.to_csv(os.path.join(outpath,'maz_parking_estimates.csv'))
    print "done."