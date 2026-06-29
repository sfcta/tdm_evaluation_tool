"""Used to create config["interim"]["TAZ_PARKING"],
i.e. data\interim\taz_parking_estimate.csv"""

# -*- coding: utf-8 -*-
import click
import logging
import sys, os, csv, configparser, h5py, tomllib, 
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
#from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import format_block, format_lot, format_blklot
from SkimUtil import TransitTripSkim
    
#@click.command()
#@click.argument('input_filepath', type=click.Path(exists=True))
#@click.argument('output_filepath', type=click.Path())
def main():
    """ Runs data processing scripts to turn raw data from (../raw) into
        cleaned data ready to be analyzed (saved in ../processed).
    """
    logger = logging.getLogger(__name__)
    
    control_file = os.environ.get('control_file')
    logger.info('reading control file {}'.format(control_file))
    
    config = configparser.ConfigParser()
    config.read(control_file)
    os.environ['data_raw'] = os.path.join(os.environ.get('project_dir'),config['raw']['PATH'])
    os.environ['data_interim'] = os.path.join(os.environ.get('project_dir'),config['interim']['PATH'])
    
    logger.info('making final data set from raw data')
    
    logger.info('processing taz data.')
    process_tazdata(config, logger)
    
    logger.info('processing impedance data.')
    process_impedance(config, logger)
    
    logger.info('aggregating accessibilities.')
    aggregate_accessibility(config, logger)
    
    logger.info('processing lot data.')
    process_lot(config, logger)
    
    logger.info('process dbi.')
    process_dbi(config, logger)
    
    logger.info('estimate parking.')
    estimate_parking_rates(config, logger)
    
    logger.info('process tdm buildings.')
    process_tdm(config, logger)
    
    logger.info('writing recruitment address lists.')
    make_recruit_lists(config, logger)

def map_lot_to_taz(config, logger, force_overwrite=False):
    ''' create a 1-to-many TAZ to lot correspondence using the geographies 
        with the greatest area overlap
    '''
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    LOT_ORIG   = os.path.join(RAW, config['raw']['LOT'])
    LOT_TO_TAZ = os.path.join(INTERIM, config['interim']['LOT_TO_TAZ'])
    #LOT        = os.path.join(INTERIM, config['interim']['LOT'])
    TAZSHP     = os.path.join(RAW, config['raw']['TAZSHP'])
    
    if force_overwrite or (not os.path.exists(LOT_TO_TAZ)):
        lot = gpd.read_file(LOT_ORIG)
        lot.rename(columns={c: c.lower() for c in lot.columns}, inplace=True)
        lot.rename(columns={'blklot_1':'blklot'}, inplace=True)
        taz = gpd.read_file(TAZSHP)
        taz.to_crs(lot.crs, inplace=True)
        over = gpd.overlay(lot, taz)
        lot['area'] = lot.area
        over['area'] = over.area
        
        lot_to_taz = pd.merge(lot[['mapblklot','blklot','block_num','lot_num','area']],
                              over[['mapblklot','TAZ','area']],
                              on='mapblklot', suffixes=['_left','_right'])
        lot_to_taz = lot_to_taz.loc[lot_to_taz.groupby('mapblklot')['area_right'].idxmax(),
                                          ['mapblklot','blklot','block_num','lot_num','TAZ']]
        lot_to_taz = lot_to_taz.rename(columns={'TAZ':'taz'})
        #lot.to_file(LOT)
        lot_to_taz.to_csv(LOT_TO_TAZ, index=False)
    else:
    #    lot = gpd.read_file(LOT)
        lot_to_taz = pd.read_csv(LOT_TO_TAZ)
    return lot_to_taz
    
def map_lot_to_maz(config, logger, force_overwrite=False):
    ''' create a 1-to-many TAZ to lot correspondence using the geographies 
        with the greatest area overlap
    '''
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    LOT_ORIG   = os.path.join(RAW, config['raw']['LOT'])
    LOT_TO_MAZ = os.path.join(INTERIM, config['interim']['LOT_TO_MAZ'])
    #LOT        = os.path.join(INTERIM, config['interim']['LOT'])
    MAZSHP     = os.path.join(RAW, config['raw']['MAZSHP'])
    
    if force_overwrite or (not os.path.exists(LOT_TO_MAZ)):
        maz = gpd.read_file(MAZSHP)
        maz.to_crs(lot.crs, inplace=True)
        over = gpd.overlay(lot, maz)
        lot['area'] = lot.area
        over['area'] = over.area
        lot_to_maz = pd.merge(lot[['mapblklot','area']],
                              over[['mapblklot','MAZ','area']],
                              on='mapblklot', suffixes=['_left','_right'])
        lot_to_maz = lot_to_maz.loc[lot_to_maz.groupby('mapblklot')['area_right'].idxmax(),
                                          ['mapblklot','MAZ']]
        lot_to_maz = lot_to_maz.rename(columns={'MAZ':'maz'})
        #lot.to_file(LOT)
        lot_to_maz.to_csv(LOT_TO_MAZ, index=False)
    else:
    #    lot = gpd.read_file(LOT)
        lot_to_maz = pd.read_csv(LOT_TO_MAZ)
    return lot_to_maz
    
def process_tazdata(config, logger, force_overwrite=False):
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    TAZDATA_ORIG = os.path.join(RAW,config['raw']['TAZDATA'])
    TAZDATA      = os.path.join(INTERIM, config['interim']['TAZDATA'])
    if force_overwrite or (not os.path.exists(TAZDATA)):
        tazdata = gpd.read_file(TAZDATA_ORIG)
        tazdata = tazdata.rename(columns={c:c.lower() for c in tazdata.columns})
        tazdata.rename(columns={'sftaz':'taz'}, inplace=True)
        tazdata.to_csv(TAZDATA, index=False)
    #else:
    #    tazdata = pd.read_csv(TAZ_LANDUSE)
    
def process_impedance(config, logger, force_overwrite=False):
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    WALKSKIMS  = os.path.join(RAW, config['raw']['WALKSKIMS'])
    TRANSITSKIMDIR = config['raw']['TRANSITSKIMDIR']
    WALK_IMPEDANCE = os.path.join(INTERIM, config['interim']['WALK_IMPEDANCE'])
    TRANSIT_IMPEDANCE = os.path.join(INTERIM, config['interim']['TRANSIT_IMPEDANCE'])
    
    TIMEPERIODS = ['EA','AM','MD','PM','EV']
    TRANSITMODES = ['WBW','WMW','WLW','WPW'] # BART, Muni LRT, Local Bus, Premium Bus

    if force_overwrite or (not (os.path.exists(WALK_IMPEDANCE) and os.path.exists(TRANSIT_IMPEDANCE))):
        # walk skims
        wf = h5py.File(WALKSKIMS, 'r')

        oidx = pd.Index(np.arange(1, wf['1'].shape[0]+1), name='otaz')
        didx = pd.Index(np.arange(1, wf['1'].shape[0]+1), name='dtaz')
        walkdist = pd.DataFrame(wf['1'], index=oidx, columns=didx) # distance in miles
        walktime = walkdist * 60.0 / 3.0 # time in minutes
        walk_impedance = walktime.reset_index().melt(id_vars='otaz', value_name='walk_time')
        walk_impedance = pd.merge(walk_impedance,
                                  walkdist.reset_index().melt(id_vars='otaz', value_name='walk_dist'), 
                                  on=['otaz','dtaz'])
        walk_impedance = walk_impedance.loc[walk_impedance['walk_time'].between(0,180) | walk_impedance['otaz'].eq(walk_impedance['dtaz'])]
        for f in ['walk_time','walk_dist']:
            walk_impedance[f] = walk_impedance[f].replace(0, np.nan)
        walk_impedance.to_csv(WALK_IMPEDANCE, index=False)
        
        # transit skims
        transit_skims = {}
        for tp in TIMEPERIODS:
            best_time = None
            for tm in TRANSITMODES:
                tot_time = None
                skim = TransitTripSkim(TRANSITSKIMDIR, tp, tm)
                for ts in skim.TIME_SKIMS:
                    x = skim.getSkimTable(ts)
                    if not isinstance(tot_time, np.ndarray):
                        tot_time = x
                    else:
                        tot_time = tot_time + x
                if not isinstance(best_time, np.ndarray):
                    best_time = tot_time
                else:
                    b1 = (best_time==0) & (tot_time!=0)
                    best_time[b1] = tot_time[b1]
                    b2 = (best_time>tot_time) & (tot_time!=0)
                    best_time[b2] = tot_time[b2]
            oidx = pd.Index(np.arange(1, best_time.shape[0]+1), name='otaz')
            didx = pd.Index(np.arange(1, best_time.shape[0]+1), name='dtaz')
            transit_skims[tp] = pd.DataFrame(best_time, 
                                             index=oidx,
                                             columns=didx)
        transit_impedance = pd.concat([transit_skims['EA'].reset_index().melt(id_vars='otaz', value_name='ea_transit_time').set_index(['otaz','dtaz']),
                                       transit_skims['AM'].reset_index().melt(id_vars='otaz', value_name='am_transit_time').set_index(['otaz','dtaz']),
                                       transit_skims['MD'].reset_index().melt(id_vars='otaz', value_name='md_transit_time').set_index(['otaz','dtaz']),
                                       transit_skims['PM'].reset_index().melt(id_vars='otaz', value_name='pm_transit_time').set_index(['otaz','dtaz']),
                                       transit_skims['EV'].reset_index().melt(id_vars='otaz', value_name='ev_transit_time').set_index(['otaz','dtaz'])],
                                      axis=1,
                                      join='outer').reset_index()
        for f in ['ea_transit_time','am_transit_time','md_transit_time','pm_transit_time','ev_transit_time']:
            transit_impedance[f] = transit_impedance[f].replace(0, np.nan)
        transit_impedance.to_csv(TRANSIT_IMPEDANCE, index=False)

def aggregate_accessibility(config, logger, force_overwrite=False):
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    WALK_IMPEDANCE = os.path.join(INTERIM, config['interim']['WALK_IMPEDANCE'])
    TRANSIT_IMPEDANCE = os.path.join(INTERIM, config['interim']['TRANSIT_IMPEDANCE'])
    WALK_ACCESS = os.path.join(INTERIM, config['interim']['WALK_ACCESS'])
    TRANSIT_ACCESS = os.path.join(INTERIM, config['interim']['TRANSIT_ACCESS'])
    WALK_TIME_COEFFICIENT = float(config['access_params']['WALK_TIME_COEFFICIENT'])
    WALK_TIME_THRESHOLD = float(config['access_params']['WALK_TIME_THRESHOLD'])
    TRANSIT_TIME_COEFFICIENT = float(config['access_params']['TRANSIT_TIME_COEFFICIENT'])
    TRANSIT_TIME_THRESHOLD = float(config['access_params']['TRANSIT_TIME_THRESHOLD'])
    DESTINATION_FILE = config['access_params']['DESTINATION_FILE']
    DESTINATION_FIELD = config['access_params']['DESTINATION_FIELD']
    
    if force_overwrite or not (os.path.exists(WALK_ACCESS) and os.path.exists(TRANSIT_ACCESS)):
        walk_imp = pd.read_csv(WALK_IMPEDANCE)
        transit_imp = pd.read_csv(TRANSIT_IMPEDANCE)
        dest = pd.read_csv(DESTINATION_FILE)
        
        walk_imp = pd.merge(walk_imp, dest[['taz',DESTINATION_FIELD]].rename(columns={'taz':'dtaz'}))
        walk_imp['weight'] = np.exp(walk_imp['walk_time']*WALK_TIME_COEFFICIENT)
        walk_imp['weight'] = walk_imp['weight'] * (1 * walk_imp['walk_time'].lt(WALK_TIME_THRESHOLD))
        walk_imp.loc[walk_imp['otaz'].eq(walk_imp['dtaz']),'weight'] = 1
        walk_imp['weighted'] = walk_imp[DESTINATION_FIELD] * walk_imp['weight']
        walk_access = (walk_imp.groupby('otaz', as_index=False)
                        .agg({'weighted':'sum'})
                        .rename(columns={'otaz':'taz','weighted':DESTINATION_FIELD})
                       )
        transit_imp = pd.merge(transit_imp, dest[['taz',DESTINATION_FIELD]].rename(columns={'taz':'dtaz'}))               
        transit_imp['weight'] = np.exp(transit_imp['am_transit_time']*TRANSIT_TIME_COEFFICIENT)
        transit_imp['weight'] = transit_imp['weight'] * (1 * transit_imp['am_transit_time'].lt(TRANSIT_TIME_THRESHOLD))
        transit_imp.loc[transit_imp['otaz'].eq(transit_imp['dtaz']),'weight'] = 1
        transit_imp['weighted'] = transit_imp[DESTINATION_FIELD] * transit_imp['weight']
        transit_access = (transit_imp.groupby('otaz', as_index=False)
                           .agg({'weighted':'sum'})
                           .rename(columns={'otaz':'taz','weighted':DESTINATION_FIELD})
                          )
        walk_access.to_csv(WALK_ACCESS, index=False)
        transit_access.to_csv(TRANSIT_ACCESS, index=False)
    
def map_lot_to_zip(config, logger, force_overwrite=False):
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    
    LOT        = os.path.join(RAW, config['raw']['LOT'])
    ZIP        = os.path.join(RAW, config['raw']['ZIP'])
    
    LOT_TO_ZIP = os.path.join(INTERIM, config['interim']['LOT_TO_ZIP'])
    
    if force_overwrite or (not (os.path.exists(LOT_TO_ZIP))):
        lot = gpd.read_file(LOT)
        lot = (lot.rename(columns={c: c.lower() for c in lot.columns})
                  .rename(columns={'blklot_1':'blklot'})
                  .to_crs('epsg:2227')[['mapblklot','blklot','block_num','lot_num','geometry']]
               )
        lot = gpd.GeoDataFrame(data=lot.drop(columns='geometry'), geometry=lot.centroid)
        
        _zip = gpd.read_file(ZIP)
        _zip = (_zip[['po_name','state','zip_code','geometry']]
                    .rename(columns={'po_name':'city'})
                    .to_crs('epsg:2227')
                )
                
        lot_to_zip = gpd.sjoin(lot, _zip, how='left')
        lot_to_zip.drop(columns='geometry').to_csv(LOT_TO_ZIP, index=False)
        
    
def process_lot(config, logger, force_overwrite=False):
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    AMS_FILE   = os.path.join(RAW, config['raw']['TAZ_AMS'])
    LOT_ORIG   = os.path.join(RAW, config['raw']['LOT'])
    DBI_ORIG   = os.path.join(RAW, config['raw']['DBI'])
    LOT_TO_TAZ = os.path.join(INTERIM, config['interim']['LOT_TO_TAZ'])
    LOT_TO_ZIP = os.path.join(INTERIM, config['interim']['LOT_TO_ZIP'])
    LOT        = os.path.join(INTERIM, config['interim']['LOT'])
    WALK_ACCESS = os.path.join(INTERIM, config['interim']['WALK_ACCESS'])
    TRANSIT_ACCESS = os.path.join(INTERIM, config['interim']['TRANSIT_ACCESS'])
    DESTINATION_FIELD = config['access_params']['DESTINATION_FIELD']
    
    if force_overwrite or (not (os.path.exists(LOT_TO_ZIP))):
        map_lot_to_zip(config, logger)
        
    if force_overwrite or (not (os.path.exists(LOT_TO_TAZ) and os.path.exists(LOT))):
        lot_to_taz = map_lot_to_taz(config, logger)        
        lot = gpd.read_file(LOT_ORIG)
        ams = pd.read_csv(AMS_FILE, usecols=['TAZ','ams_all','rs_ams']).rename(columns={'TAZ':'taz'})
        walk_access = pd.read_csv(WALK_ACCESS)
        walk_access = walk_access.loc[walk_access['taz'].between(1,981)]
        transit_access = pd.read_csv(TRANSIT_ACCESS)
        transit_access = transit_access.loc[transit_access['taz'].between(1,981)]
        #walk_max = walk_access[DESTINATION_FIELD].max()
        walk_access['walk_access_bin'] = pd.cut(walk_access[DESTINATION_FIELD], bins=[0,250,1000,5000,30000], labels=[0,1,2,3])
        transit_access['transit_access_bin'] = pd.cut(transit_access[DESTINATION_FIELD], bins=[0,750,3000,15000,60000], labels=[0,1,2,3])
        
        # rename the sector fields to clarify that they are zoned square feet, not jobs
        lot.rename(columns={c:c.lower() for c in lot.columns}, inplace=True)
        lot.rename(columns={'blklot_1':'blklot'}, inplace=True)
        lot['blklot'] = lot['blklot'].map(format_blklot)
        lot.rename(columns={x: '{}_sqft'.format(x) for x in ['cie','med','mips','pdr','retail','visitor']})
        lot = pd.merge(lot,lot_to_taz[['mapblklot','taz']], how='left')
        lot = pd.merge(lot,ams,on='taz')
        lot = pd.merge(lot,
                       (walk_access[['taz',DESTINATION_FIELD,'walk_access_bin']]
                         .rename(columns={DESTINATION_FIELD:'walk_'+DESTINATION_FIELD})),
                       on='taz', how='left')
        lot = pd.merge(lot,
                       (transit_access[['taz',DESTINATION_FIELD,'transit_access_bin']]
                         .rename(columns={DESTINATION_FIELD:'am_transit_'+DESTINATION_FIELD})),
                       on='taz', how='left')
        
        assert(len(lot.loc[pd.isnull(lot['taz']) & lot['resunits'].gt(0)]) == 0)
        lot = lot.loc[pd.notnull(lot['taz'])]
        
        dbi = pd.read_csv(DBI_ORIG)
        dbi.rename(columns={c:c.lower() for c in dbi.columns}, inplace=True)
        dbi['blklot'] = dbi['blklot'].map(format_blklot)
        
        logger.info("updating lot attributes in dbi parking data file")
        inner = pd.merge(dbi[['blklot','resunits','yrbuilt']], 
                         lot[['blklot','landuse','resunits','yrbuilt']], 
                         on='blklot', how='inner',suffixes=['_dbi','_lot'])
        
        lot.set_index('blklot',inplace=True)
        inner.set_index('blklot',inplace=True)
        
        update = (inner.loc[inner['resunits_dbi'].gt(inner['resunits_lot']),['resunits_dbi']]
                       .rename(columns={'resunits_dbi':'resunits'}))
        lot.update(update)
        update = (inner.loc[inner['yrbuilt_lot'].lt(1500),['yrbuilt_dbi']]
                       .rename(columns={'yrbuilt_dbi':'yrbuilt'}))
        lot.update(update)
        
        lot.reset_index(inplace=True)
        lot_gb_block = lot.groupby(['block_num'])
        lot_gb_taz = lot.groupby(['taz'])
    
        # ID records with missing or bad year, and replace with 
        lot.loc[lot['yrbuilt'].eq(0),'yrbuilt'] = np.nan
        lot['year_missing'] = 1 * (pd.isnull(lot['yrbuilt']) | lot['yrbuilt'].lt(1500) | lot['yrbuilt'].gt(2023))
        lot['year_estimated'] = 0
        no_year = lot.loc[lot['year_missing'].eq(1)]
        logger.info('There are {} out of {} records with missing or invalid yrbuilt'.format(len(no_year), len(lot)))
        
        for idx, row in no_year.iterrows():
            year = lot.loc[idx,'yrbuilt']
            if not pd.isnull(year):
                # first try to turn a 1- or 2-digit year to 4-digit
                try1 = int("1" + str(int(year))[1:])
                try2 = int("19" + str(int(year))[2:])
                try3 = int("2" + str(int(year))[1:])
                try4 = int("20" + str(int(year))[2:])
                best_try = np.nan
                for name, tr in zip(['try1','try2','try3','try4'],[try1, try2, try3, try4]):
                    if tr > 1500 and tr < 2023:
                        #logger.debug('%s,%d,simplereplace_%s,,%d,,\n' % (lot['BLKLOT'],lot['YRBUILT'],name,tr))
                        lot.loc[idx,'yrbuilt'] = tr
                        lot.loc[idx,'year_missing'] = 0
                        lot.loc[idx,'year_estimated'] = 1
                        break
            else:
                # if that doesn't work, get the block average.  
                block = lot_gb_block.get_group(row['block_num'])
                block = block[pd.notnull(block['yrbuilt'])]
                block = block[block['yrbuilt'].ge(1800)]
                block_mean = block['yrbuilt'].mean()
                block_count = block['yrbuilt'].count()
                block_std = block['yrbuilt'].std()
                if pd.isnull(block_mean):
                    block = lot_gb_taz.get_group(row['taz'])
                    block = block[pd.notnull(block['yrbuilt'])]
                    block = block[block['yrbuilt'].ge(1800)]
                    block_mean = block['yrbuilt'].mean()
                    block_count = block['yrbuilt'].count()
                    block_std = block['yrbuilt'].std()
                try:
                    lot.loc[idx,'yrbuilt'] = int(block_mean)
                    lot.loc[idx,'year_missing'] = 0
                    lot.loc[idx,'year_estimated'] = 1
                    logger.debug('lot {}, replace yrbuilt {} with block {} average {} (std: {:0.2f})'.format(row['blklot'], row['yrbuilt'], row['block_num'], block_mean, block_std))
                except Exception as e:
                    logger.info(e)
                    logger.info('idx: {}, lot: {}, block_mean: {}'.format(idx, row['blklot'], block_mean))
        logger.info('There are {} remaining records out of {} with missing or invalid yrbuilt'.format(len(lot.loc[lot['year_missing'].eq(1)]), len(lot)))
        logger.info("calculating bins for all lots")
        
        lot['pm_size_bin'] = np.nan
        lot.loc[lot['resunits'].eq(1),            'pm_size_bin'] = 0
        lot.loc[lot['resunits'].between(2,9),     'pm_size_bin'] = 1
        lot.loc[lot['resunits'].between(10,19),   'pm_size_bin'] = 2
        lot.loc[lot['resunits'].ge(20),           'pm_size_bin'] = 3
        lot['pm_area_bin'] = np.nan
        lot.loc[lot['ams_all'].between(0.0,0.4),  'pm_area_bin'] = 0
        lot.loc[lot['ams_all'].between(0.4,0.65), 'pm_area_bin'] = 1
        lot.loc[lot['ams_all'].between(0.65,1.0), 'pm_area_bin'] = 2
        lot['pm_year_bin'] = np.nan
        lot.loc[lot['yrbuilt'].between(1500,1955),'pm_year_bin'] = 0
        lot.loc[lot['yrbuilt'].between(1956,2016),'pm_year_bin'] = 1    
        
        lot['samp_size_bin'] = np.nan
        lot.loc[lot['resunits'].lt(10),           'samp_size_bin'] = -1
        lot.loc[lot['resunits'].between(10,24),   'samp_size_bin'] = 0
        lot.loc[lot['resunits'].between(25,49),   'samp_size_bin'] = 1
        lot.loc[lot['resunits'].between(50,99),   'samp_size_bin'] = 2
        lot.loc[lot['resunits'].ge(100),          'samp_size_bin'] = 3
        lot['samp_area_bin'] = np.nan
        lot.loc[lot['ams_all'].between(0.0,0.4),  'samp_area_bin'] = 0
        lot.loc[lot['ams_all'].between(0.4,0.65), 'samp_area_bin'] = 1
        lot.loc[lot['ams_all'].between(0.65,1.0), 'samp_area_bin'] = 2
        lot['samp_year_bin'] = np.nan
        lot.loc[lot['yrbuilt'].between(1500,1955),'samp_year_bin'] = 0
        lot.loc[lot['yrbuilt'].between(1956,2016),'samp_year_bin'] = 1   
        
        lot.drop(columns=['geometry']).to_csv(LOT, index=False)

def process_dbi(config, logger, force_overwrite=False):
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
    # inputs
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    DBI_ORIG           = os.path.join(RAW, config['raw']['DBI'])
    PARKMERCED_FILE    = os.path.join(RAW, config['raw']['PARKMERCED_LOTS'])
    
    # outputs
    DBI = os.path.join(INTERIM, config['interim']['DBI'])
    
    # constants
    std_sqft = float(config['parking_params']['STANDARD_PARKING_SPACE_SQFT'])
    com_sqft = float(config['parking_params']['COMPACT_PARKING_SPACE_SQFT'])
    spc_std_len = float(config['parking_params']['STANDARD_PARKING_SPACE_LENGTH'])
    spc_std_wid = float(config['parking_params']['STANDARD_PARKING_SPACE_WIDTH'])
    spc_com_len = float(config['parking_params']['COMPACT_PARKING_SPACE_LENGTH'])
    spc_com_wid = float(config['parking_params']['COMPACT_PARKING_SPACE_WIDTH'])

    if force_overwrite or not os.path.exists(DBI):
        logger.info('reading dbi parking data')
        # just the id, parking, and qc fields
        # mapblklot joins to the landuse shapefile.  It's (I think) constant over time when parcels are 
        # split and renumbered, but isn't available for everything in this dataset.  
        # blklot is available for everything, but changes over time so might not match the landuse (i.e. "lot" or "parcel" file)
        dbi = pd.read_csv(DBI_ORIG, usecols=['MAPBLKLOT','BLKLOT','BLOCK_NUM','LOT_NUM','GROUP',
                                             'SRO','parking_supply','estimated',
                                             'manual_override','qc_flag',
                                             'g1d1','g1d2','g2d1','g2d2',
                                             'g3d1','g3d2','g4d1','g4d2'],
                          dtype={'manual_override':'float',
                                 'g1d1':'float','g1d2':'float','g2d1':'float','g2d2':'float',
                                 'g3d1':'float','g3d2':'float','g4d1':'float','g4d2':'float'})
        dbi.rename(columns={x:x.lower() for x in dbi.columns.tolist()}, inplace=True)
        
        logger.info('reformat fields')
        dbi['blklot'] = dbi['blklot'].map(format_blklot)
        dbi['block_num'] = dbi['block_num'].map(format_block)
        dbi['lot_num'] = dbi['lot_num'].map(format_lot)
        dbi['manual_override'] = dbi['manual_override'].replace('',np.nan).astype(float)
        dbi['estimated'] = 1 * dbi['estimated'].isin(['y','Y'])
        dbi['qc_flag'] = 1 * dbi['qc_flag'].isin(['y','Y'])
        dbi['sro'] = 1 * (dbi['sro'].eq(True) | dbi['sro'].eq('TRUE'))
        for f in ['g1d1','g1d2','g2d1','g2d2','g3d1','g3d2','g4d1','g4d2']:
            dbi[f] = dbi[f].fillna(0).astype(int)
        
        logger.info("estimating spaces based on garage dimensions using multiple methods")
        for g in ['g1','g2','g3','g4']:
            dbi['{}_est_std_sqft'.format(g)] = dbi['{}d1'.format(g)] * dbi['{}d2'.format(g)] / std_sqft
            dbi['{}_est_com_sqft'.format(g)] = dbi['{}d1'.format(g)] * dbi['{}d2'.format(g)] / com_sqft
            dbi['{}_est_sqft'.format(g)] = dbi['{}_est_std_sqft'.format(g)] + dbi['{}_est_com_sqft'.format(g)] / 2
            dbi['{}_est_rxc'.format(g)] = dbi.apply(calc_spaces, axis=1, tag=g) # , std_len=spc_std_len, std_wid=spc_std_wid, com_len=spc_com_len, com_wid=spc_com_wid)
            dbi['{}_spaces_best'.format(g)] = dbi.apply(get_best_estimate, axis=1, tag=g)

        logger.info("getting best estimate of spaces from dimensions")
        dbi['total_spaces_best'] = dbi['g1_spaces_best']
        dbi['total_spaces_best'] += dbi['g2_spaces_best'] * pd.isnull(dbi['g2_spaces_best'])
        dbi['total_spaces_best'] += dbi['g3_spaces_best'] * pd.isnull(dbi['g3_spaces_best'])
        dbi['total_spaces_best'] += dbi['g4_spaces_best'] * pd.isnull(dbi['g4_spaces_best'])
        
        logger.info("get the originally recorded 'parking_supply'")
        dbi['spaces'] = dbi['parking_supply'].map(lambda x: float(x) if str(x).isnumeric() else np.nan)
        logger.info("adding dimension-based space estimates")
        dbi.loc[(dbi['estimated'].eq(1)) & dbi['total_spaces_best'].gt(0), 'spaces'] = dbi['total_spaces_best']
        logger.info("adding manual overrides")
        
        dbi.loc[~pd.isnull(dbi['manual_override']),'spaces'] = dbi['manual_override'].replace('',np.nan).astype(float)
        logger.info("removing qc flagged records")
        dbi.loc[dbi['qc_flag'].isin(['y','Y']),'spaces'] = np.nan

        logger.info("update PARKMERCED parking values")
        parkmerced = pd.read_csv(PARKMERCED_FILE)
        parkmerced['BLKLOT'] = parkmerced['BLKLOT'].map(format_blklot)
        parkmerced = parkmerced.rename(columns={'BLKLOT':'blklot','Total Parking Estimate':'spaces'}).set_index('blklot')
        dbi.update(parkmerced)
        dbi.to_csv(DBI, index=False)

def estimate_parking_rates(config, logger, force_overwrite=False):
            
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    
    #PARKMERCED = os.path.join(RAW, config['raw']['PARKMERCED_LOTS'])
    DBI        = os.path.join(INTERIM, config['interim']['DBI'])
    DBI_PARKING_RATES = os.path.join(INTERIM, config['interim']['DBI_PARKING_RATES'])
    DBI_PARKING_MODEL = os.path.join(INTERIM, config['interim']['DBI_PARKING_MODEL'])
    LOT        = os.path.join(INTERIM, config['interim']['LOT'])
    LOT_PARKING_RATES = os.path.join(INTERIM, config['interim']['LOT_PARKING_RATES'])
    LOT_TO_TAZ = os.path.join(INTERIM, config['interim']['LOT_TO_TAZ'])
    TAZ_PARKING = os.path.join(INTERIM, config['interim']['TAZ_PARKING'])

    logger.info("reading data")
    lot = pd.read_csv(LOT)
    dbi = pd.read_csv(DBI)
    lot_to_taz = pd.read_csv(LOT_TO_TAZ)
    
    if force_overwrite or (not os.path.exists(TAZ_PARKING)):
        logger.info("calculating observed parking rates")
        dbi = pd.merge(dbi, lot_to_taz[['blklot','taz']], on='blklot', how='left')
        dbi = pd.merge(dbi,
                       lot[['blklot','pm_area_bin','pm_size_bin','pm_year_bin',
                            'samp_area_bin','samp_size_bin','samp_year_bin',
                            'walk_access_bin','transit_access_bin','resunits']], 
                       on='blklot', how='left')
        
        logger.info("calulating parking rate")
        dbi['parking_rate'] = dbi['spaces'] / dbi['resunits']
        
        logger.info("replacing inf with nan")
        dbi['parking_rate'] = dbi['parking_rate'].replace([np.inf, -np.inf],np.nan)
        
        logger.info("dropping high parking rates (>= 7 per unit)")
        dbi.loc[dbi['parking_rate'].ge(7),'spaces'] = np.nan
        dbi.loc[dbi['parking_rate'].ge(7),'parking_rate'] = np.nan
        
        logger.info("writing DBI_PARKING_RATES to {}".format(DBI_PARKING_RATES))
        dbi = dbi.loc[pd.notnull(dbi['spaces'])]
        
        logger.info("dropping parkmerced from rate estimation model")
        est = dbi.loc[dbi['group'].ne('PARKMERCED')]
        
        # join lot and taz attributes
        logger.info("calculating average parking rate by classification")
        avg_rate = (est.groupby(['pm_year_bin','pm_size_bin','pm_area_bin'], as_index=False)
                    .agg({'resunits':'sum','spaces':'sum'})
                    )
        avg_rate['parking_rate'] = avg_rate['spaces'] / avg_rate['resunits']
        avg_rate.to_csv(DBI_PARKING_MODEL, index=False)
        
        logger.info("estimating number of parking spaces based on parking rate by classification")
        
        lot = pd.merge(lot, 
                       avg_rate[['pm_year_bin','pm_size_bin','pm_area_bin','parking_rate']], 
                       on=['pm_year_bin','pm_size_bin','pm_area_bin'], how='left')
        lot['spaces_est'] = lot['resunits'] * lot['parking_rate']
        lot.to_csv(LOT_PARKING_RATES, index=False)
        
        logger.info("calculating taz parking rates")
        tazs = lot.reset_index().groupby(['taz'], as_index=False)[['spaces_est','resunits']].sum()
        tazs['parking_rate_est'] = tazs['spaces_est'] / tazs['resunits']
        tazs.to_csv(TAZ_PARKING, index=False)
        
        dbi = pd.merge(dbi, tazs[['taz','spaces_est','parking_rate_est','resunits']].rename(columns={'resunits':'resunits_taz'}))
        dbi.to_csv(DBI_PARKING_RATES, index=False)
    
def process_tdm(config, logger, force_overwrite=False):
    RAW        = os.environ.get('data_raw')
    INTERIM    = os.environ.get('data_interim')
    
    TDM_LOT_ORIG = os.path.join(RAW, config['raw']['TDM_FILE'])
    TDM_LOT_SHEET = config['raw']['TDM_LOT_SHEET']
    TDM_PROJECT_SHEET = config['raw']['TDM_PROJECT_SHEET']
    TDM = os.path.join(INTERIM,config['interim']['TDM'])
    TDM_LOT = os.path.join(INTERIM,config['interim']['TDM_LOT'])
    #LOT_TO_TAZ = os.path.join(INTERIM, config['interim']['LOT_TO_TAZ'])
    LOT_PARKING_RATES = os.path.join(INTERIM, config['interim']['LOT_PARKING_RATES'])
    TAZ_PARKING = os.path.join(INTERIM, config['interim']['TAZ_PARKING'])
    
    if force_overwrite or not (os.path.exists(TDM_LOT) and os.path.exists(TDM)):
        lot = pd.read_csv(LOT_PARKING_RATES, 
                          usecols=['blklot','taz','ams_all','rs_ams',
                                   'walk_totalemp','walk_access_bin',
                                   'am_transit_totalemp','transit_access_bin',
                                   'year_missing','year_estimated','pm_size_bin',
                                   'pm_area_bin','pm_year_bin','parking_rate','spaces_est'])
                                   
        #lot_to_taz = pd.read_csv(LOT_TO_TAZ)
        taz = pd.read_csv(TAZ_PARKING)
        
        tdm_lots = pd.read_excel(TDM_LOT_ORIG, TDM_LOT_SHEET)
        tdm_lots.rename(columns={c:c.lower() for c in tdm_lots.columns}, inplace=True)
        tdm_lots['block'] = tdm_lots['block'].map(lambda x: format_block(x))
        tdm_lots['lot'] = tdm_lots['lot'].map(lambda x: format_lot(x))
        tdm_lots['blklot'] = tdm_lots.apply(lambda x: x['block']+x['lot'], axis=1)
        tdm_lots['mapblklot'] = tdm_lots['block']+ tdm_lots['lot']
        
        # manual override mapblklot for 388 Beale
        tdm_lots.loc[tdm_lots['tdm_no'].eq('2018-016944TDM'),'mapblklot'] = '3747091'
        tdm_lots = pd.merge(tdm_lots, lot, on='blklot', how='left')
        tdm_lots = pd.merge(tdm_lots, taz, on='taz', how='left', suffixes=['_lot','_taz'])
        tdm_lots.to_csv(TDM_LOT, index=False, quoting=csv.QUOTE_NONNUMERIC)
        
        tdm = pd.read_excel(TDM_LOT_ORIG, TDM_PROJECT_SHEET)
        tdm.rename(columns={c:c.lower() for c in tdm.columns}, inplace=True)
        tdm.to_csv(TDM, index=False, quoting=csv.QUOTE_NONNUMERIC )
    
def make_recruit_lists(config, logger, force_overwrite=False):
    RAW = os.path.join(project_dir, config['raw']['PATH'])
    INTERIM = os.path.join(project_dir,config['interim']['PATH'])
    PROCESSED = os.path.join(project_dir,config['processed']['PATH'])
    
    DBI = os.path.join(INTERIM,config['interim']['DBI_PARKING_RATES'])
    TDM = os.path.join(INTERIM,config['interim']['TDM'])
    TDM_LOT = os.path.join(INTERIM,config['interim']['TDM_LOT'])
    LOT_TO_ZIP = os.path.join(INTERIM, config['interim']['LOT_TO_ZIP'])
    LOT = os.path.join(INTERIM,config['interim']['LOT'])
    RECRUIT_LIST_DBI = os.path.join(PROCESSED,config['processed']['RECRUIT_LIST_DBI'])
    RECRUIT_LIST_TDM = os.path.join(PROCESSED,config['processed']['RECRUIT_LIST_tdm'])
    
    if force_overwrite or (not (os.path.exists(RECRUIT_LIST_DBI) and os.path.exists(RECRUIT_LIST_TDM))):
        dbi = pd.read_csv(DBI)
        tdm = pd.read_csv(TDM)
        tdm_lot = pd.read_csv(TDM_LOT)
        lot = pd.read_csv(LOT)
        lot_to_zip = pd.read_csv(LOT_TO_ZIP)
        
        dbi = pd.merge(dbi, lot[['blklot','from_st','to_st','street','st_type']], how='left', on='blklot')
        dbi = pd.merge(dbi, lot_to_zip[['blklot','city','state','zip_code']], how='left', on='blklot')
        dbi.loc[pd.notnull(dbi['st_type']), 'PrimaryAddress'] = dbi.loc[pd.notnull(dbi['st_type'])].apply(lambda x: str(x['from_st']) + ' ' + x['street'] + ' ' + x['st_type'], axis=1)
        dbi.loc[pd.isnull(dbi['st_type']), 'PrimaryAddress'] = dbi.loc[pd.isnull(dbi['st_type'])].apply(lambda x: str(x['from_st']) + ' ' + x['street'], axis=1)
        dbi['City'] = dbi['city'].map(lambda x: x.upper())
        dbi['State'] = dbi['state']
        dbi['Zip'] = dbi['zip_code'].astype(int)
        dbi[['blklot','PrimaryAddress','City','State','Zip']].to_csv(RECRUIT_LIST_DBI, index=False)
        
        # drop non residential and conservatory of music (dorms)
        tmp = tdm_lot.loc[tdm_lot['tdm_no'].isin(tdm.loc[tdm['cat_c_dus'].gt(0) & tdm['tdm_no'].ne('2015-012994TDM'),'tdm_no'])]
        tmp = tmp[['tdm_no','blklot','address']]
        tmp = pd.merge(tmp, lot_to_zip, on='blklot', how='left')
        tmp = tmp.drop_duplicates(subset=['address','zip_code']).dropna() 
        tmp['PrimaryAddress'] = tmp['address'].map(lambda x: x.upper())
        tmp['City'] = tmp['city'].map(lambda x: x.upper())
        tmp['State'] = tmp['state']
        tmp['Zip'] = tmp['zip_code'].astype(int)
        tmp[['tdm_no','blklot','PrimaryAddress','City','State','Zip']].to_csv(RECRUIT_LIST_TDM, index=False)
    
if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)

    # not used in this stub but often useful for finding various files
    project_dir = str(Path(__file__).resolve().parents[2])
    os.environ['project_dir'] = project_dir
    os.environ['control_file'] = os.path.join(project_dir,'src','config.ctl')


    # find .env automagically by walking up directories until it's found, then
    # load up the .env entries as environment variables
    #load_dotenv(find_dotenv())

    main()
