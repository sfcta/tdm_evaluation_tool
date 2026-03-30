from .Skim import Skim
from tables import open_file

class BikeSkim(Skim):
    """
    Bike Skim class.
    
    For now, test with X:\Projects\ModelDev\TransitSkimTest\bike_model_output\BikeLogsum.h5
    """
    
    
    def __init__(self, file_dir):
        
        # open the h5 files
        self.bike_skim_file = "BikeLogsum.h5"      
        self.walk_skim_file = "walkSkim.h5"
                
        Skim.__init__(self, file_dir, ["BikeLogsum.h5", "walkSkim.h5"])        
    
    def __del__ (self):
        # Superclass does the work ?
        pass
    
    def getBikeLogSum(self, orig_taz, dest_taz):
        """
        Returns the bike log sum for the given origin and destination w/in SF.
        """
        return self.skim_table_files[self.bike_skim_file].root._f_get_child("1")[orig_taz-1][dest_taz-1]

            
    def getBikeDist(self, orig_taz, dest_taz):
        """
        Returns the walking distance for the given origin and destination outside of or to/from SF.
        """
        return self.skim_table_files[self.walk_skim_file].root._f_get_child("1")[orig_taz-1][dest_taz-1]
