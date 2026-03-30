from .Skim import Skim
from tables import open_file
import numpy as np
from Lookups import MAX_SF_ZONE

class TransitTripSkim(Skim):
    """
    Transit Trip Skim class.
    """
     
    #: Matching of matrix in h5 file and attribute name
    TABLE_NUMBER_TO_NAME = {1:"LIVT", 2:"RIVT", 3:"MIVT", 4:"PIVT", 5:"FIVT", 6:"BIVT", 
                            7:"ACC_TIME", 8:"EGR_TIME", 9:"ACC_DIST", 10:"EGR_DIST",
                            11:"IWAIT", 12:"XWAIT", 
                            13:"TrDIST", 14:"DrDIST", 
                            15:"FUNTIME", 16:"XWKTIME", 17:"NUM_LINKS", 18:"TOT_FARE",
                            19:"ACCNODE", 20:"EGRNODE"}
    
    TABLE_NAME_TO_NUMBER = dict((v,k) for k, v in TABLE_NUMBER_TO_NAME.items())
    
    #: All variables returned
    ALL_VARS = list(TABLE_NUMBER_TO_NAME.values())
    ALL_VARS.append("TOT_TIME")
    
    #: Skims related to time (for converting hundredths of mins to mins)
    TIME_SKIMS = ["LIVT", "RIVT", "MIVT", "PIVT", "FIVT", "BIVT",
                  "ACC_TIME", "EGR_TIME", "IWAIT", "XWAIT", "FUNTIME", "XWKTIME"]
    #: Skims related to distances (for converting hundredths of miles to miles)
    DIST_SKIMS = ["TrDIST", "DrDIST", "ACC_DIST", "EGR_DIST"]
    #: Skims related to cost
    FARE_SKIMS = ["TOT_FARE"]
      
    def __init__(self, file_dir, timeperiod, transitmode, suffix=None):
        """
        Opens the given skim
        """
        #TODO: Make this open all transitmodes
        
        self.trn_skim_file = "TRN%s%s%s.h5" % (transitmode, timeperiod, suffix if suffix else "")      
        Skim.__init__(self, file_dir, [self.trn_skim_file])
    
    def getTripAttributes(self, orig_taz, dest_taz):
        """
        Returns a dict of all transit attributes listed in TABLE_NUMBER_TO_NAME
        Units are minutes, miles and 1989 cents.
        """
        
        transitAttributes = {}
        tot_time = 0
        for tablenum,tablename in TransitTripSkim.TABLE_NUMBER_TO_NAME.items():
            # convert hundredths of minutes to minutes
            if tablename in TransitTripSkim.TIME_SKIMS:
                transitAttributes[tablename] = 0.01 * self.skim_table_files[self.trn_skim_file].root._f_get_child("%d" % tablenum)[orig_taz-1][dest_taz-1]
                tot_time += transitAttributes[tablename]
            # convert hundredths of miles to miles
            elif tablename in TransitTripSkim.DIST_SKIMS:
                transitAttributes[tablename] = 0.01 * self.skim_table_files[self.trn_skim_file].root._f_get_child("%d" % tablenum)[orig_taz-1][dest_taz-1]
            # FAREs are in the correct units already
            else:
                transitAttributes[tablename] = self.skim_table_files[self.trn_skim_file].root._f_get_child("%d" % tablenum)[orig_taz-1][dest_taz-1]
            
            transitAttributes["TOT_TIME"] = tot_time
        
        return transitAttributes
    
    def getTripAttribute(self, orig_taz, dest_taz, tablename):
        """
        Returns the single relevant number
        """
        if tablename not in TransitTripSkim.ALL_VARS: 
            print("Requested transit trip table %s not available" % (tablename))
            raise
        
        tablenum = TransitTripSkim.TABLE_NAME_TO_NUMBER[tablename]
        if tablename in TransitTripSkim.TIME_SKIMS or tablename in TransitTripSkim.DIST_SKIMS:
            return 0.01 * self.skim_table_files[self.trn_skim_file].root._f_get_child("%d" % tablenum)[orig_taz-1][dest_taz-1]
        
        return self.skim_table_files[self.trn_skim_file].root._f_get_child("%d" % tablenum)[orig_taz-1][dest_taz-1]
        
    
    def getSkimTable(self, variable):
        if variable not in TransitTripSkim.ALL_VARS: 
            print("Requested Variable %s not available" % (variable))
            exit(2)
        
        tablenum     = TransitTripSkim.TABLE_NAME_TO_NUMBER[variable]
        table        = np.zeros((MAX_SF_ZONE, MAX_SF_ZONE))
        table[:, :]  = self.skim_table_files[self.trn_skim_file].root._f_get_child("%d" % tablenum).read()[:MAX_SF_ZONE,:MAX_SF_ZONE]
        
        if variable in self.TIME_SKIMS or variable in self.DIST_SKIMS:
            table = 0.01 * table 
        return table