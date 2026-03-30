from .Skim import Skim
from .HighwaySkim import HighwaySkim
from tables import open_file
import os
import dbf
import pandas as pd

class TaxiSkim(Skim):
    """
    Taxi Skim class.
    
    """
         
    def __init__(self, file_dir, timeperiod):
        """
        Initializes a roadway skim.
         * *file_dir* is the location of the skim  
         * *timeperiod* can be one of `AM`, `MD`, `PM`, `EV`, `EA`.
        """
        
        # open the h5 files
        # use SR3 to for attributes, and use EA for free flow travel times
        # need free flow travel times to compute in vehicle wait time for which passengers charged
        self.hwy_skim_file = "HWYALL%s.h5" % timeperiod      
        Skim.__init__(self, file_dir, ["HWYALL%s.h5" % timeperiod]) 

        # read in land use data
        tazdatadbf = dbf.Table(filename=os.path.join(file_dir,"tazdata.dbf"))
        tazdatadbf.open(dbf.READ_ONLY)
        df = pd.DataFrame(tazdatadbf)
        df.columns = tazdatadbf.field_names
        tazdatadbf.close()
        
        self.pdr = dict(zip(df['SFTAZ'], df['PDR']))
        self.totalemp = dict(zip(df['SFTAZ'], df['TOTALEMP']))
        self.totacre = dict(zip(df['SFTAZ'], df['TOTACRE']))
        
        del tazdatadbf, df
        
    def getTaxiAttributes(self, origtaz, desttaz):
           
        """
        Returns a dict of
            taxi travel time 
            taxi cost in 1989 cents
            total employment density in origin TAZ (proxy for taxi availability)
            total employment density excluding PDR sectors in origin TAZ (proxy for taxi availability)
        """
        
        #For converting vehicle costs to passenger costs
    
        INITIALCHARGE = 250 #$2.50 for first 1/5 mi
        PERMICHARGE = 40 # $0.40 for every 1/5 mi thereafter
        PERMINWAITCHARGE = 40 # $0.40 per minute waiting time - ignored here
        CPI = 1.0/1.39
 
        ###SHOULD THERE BE NON-SF TAXI PRICES???
 
        # Sources: http://www.sfmta.com/cms/rtaxi/documents/TaxiReport-Jan2008-FinalREVISED.pdf
        #          http://www.bls.gov/bls/inflation.htm - inflation calculator ratio 
        #                                                 to convert between 1989 and 2000 dollars
          
        #Read attributes from matrices
        time       = self.skim_table_files[self.hwy_skim_file].root._f_get_child(HighwaySkim.TIMEINDEX ["TollSR2"])[origtaz-1,desttaz-1]
        dist       = self.skim_table_files[self.hwy_skim_file].root._f_get_child(HighwaySkim.DISTINDEX ["TollSR2"])[origtaz-1,desttaz-1]
        btoll      = self.skim_table_files[self.hwy_skim_file].root._f_get_child(HighwaySkim.BTOLLINDEX["TollSR2"])[origtaz-1,desttaz-1]  
        vtoll      = self.skim_table_files[self.hwy_skim_file].root._f_get_child(HighwaySkim.VTOLLINDEX["TollSR2"])[origtaz-1,desttaz-1] 

        #Compute taxi cost - the // meand floordiv
        dist_charge = INITIALCHARGE + PERMICHARGE * max((dist // 0.2)-1, 0)

        cost = CPI * dist_charge + btoll + vtoll 

        #Compute origin TAZ employment densities
        totempden = float(self.totalemp[origtaz])  / self.totacre[origtaz]
        totnonpdrempden = float(self.totalemp[origtaz] - self.pdr[origtaz]) / self.totacre[origtaz]

        taxi_attrib_dict = {}
        taxi_attrib_dict["COST"] = cost
        taxi_attrib_dict["TIME"] = time
        taxi_attrib_dict["DIST"] = dist
        taxi_attrib_dict["ORIGEMPDEN"] = totempden
        taxi_attrib_dict["ORIGNONPDREMPDEN"] = totnonpdrempden

        return taxi_attrib_dict

   