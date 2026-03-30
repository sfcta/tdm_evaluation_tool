from .Skim import Skim
from tables import open_file
import math, os, random
import numpy as np
from Lookups import MAX_SF_ZONE
import dbf
import pandas as pd

class HighwaySkim(Skim):
    """
    Highway Skim class.
    
    """
  
    #: Indices to point to correct matrices in HWYALLXX.h5 files
    TIMEINDEX   = {"DA":"1", "SR2":"7", "SR3":"13", "TollDA":"19", "TollSR2":"26", "TollSR3":"33"}
    DISTINDEX   = {"DA":"2", "SR2":"8", "SR3":"14", "TollDA":"20", "TollSR2":"27", "TollSR3":"34"}
    BTOLLINDEX  = {"DA":"3", "SR2":"9", "SR3":"15", "TollDA":"21", "TollSR2":"28", "TollSR3":"35"}
    VTOLLINDEX  = {                                 "TollDA":"22", "TollSR2":"29", "TollSR3":"36"}
    DISTVC08    = {"DA":"4", "SR2":"10","SR3":"16", "TollDA":"23", "TollSR2":"30", "TollSR3":"37"}
    DISTVC09    = {"DA":"5", "SR2":"11","SR3":"17", "TollDA":"24", "TollSR2":"31", "TollSR3":"38"}
    DISTVC10    = {"DA":"6", "SR2":"12","SR3":"18", "TollDA":"25", "TollSR2":"32", "TollSR3":"39"}

    #: For converting vehicle costs to passenger costs
    PAXPERVEH   = {"DA":1, "SR2":2, "SR3":3.5, "TollDA":1, "TollSR2":2, "TollSR3":3.5} 

    #: Mode number to readable string
    MODE_NUM_TO_STR = {1:"DA",  2:"SR2", 3:"SR3", 4:"TollDA", 5:"TollSR2", 6:"TollSR3"}
        
    #: Mode number to bool describing if it's tolled mode or not
    MODE_TOLLED     = {1:False, 2:False, 3:False, 4:True,     5:True,      6:True}

    #: Mode readable string to number
    MODE_STR_TO_NUM = dict((str,num) for num,str in MODE_NUM_TO_STR.items())
    
    def __init__(self, file_dir, timeperiod):
        """
        Initializes a roadway skim.
        * *file_dir* is the location of the skim  
        * *timeperiod* can be one of `AM`, `MD`, `PM`, `EV`, `EA`.
        Also reads tazdata from the same dir, and TAZcoords.txt
        """
        
        # open the h5 files
        self.hwy_skim_file = "HWYALL%s.h5" % timeperiod      
        self.termtime_file = "OPTERM.h5"
        Skim.__init__(self, file_dir, ["HWYALL%s.h5" % timeperiod, "OPTERM.h5"]) 
        
        # read in TAZcoords.txt
        self.tazcoords = {}  # taznum -> (x,y)
        f = open(os.path.join(file_dir, "TAZcoords.txt"))
        for line in f:
            fields = line.split()
            if fields[0][0] == "*": continue # comment
            self.tazcoords[int(fields[0])] = (float(fields[1]), float(fields[2]))
        f.close()
        
        # read in land use data
        tazdatadbf = dbf.Table(filename=os.path.join(file_dir,"tazdata.dbf"))
        tazdatadbf.open(dbf.READ_ONLY)
        df = pd.DataFrame(tazdatadbf)
        df.columns = tazdatadbf.field_names
        tazdatadbf.close()

        self.prkcstwh  = dict(zip(df['SFTAZ'], df['PRKCSTWH']))
        self.prkcstoh  = dict(zip(df['SFTAZ'], df['PRKCSTOH']))
        self.ppaying   = dict(zip(df['SFTAZ'], df['PPAYING']))
        self.prkavind  = dict(zip(df['SFTAZ'], df['PRKAVIND']))
        self.hhlds     = dict(zip(df['SFTAZ'], df['HHLDS']))
        self.totalemp  = dict(zip(df['SFTAZ'], df['TOTALEMP']))
        self.visitor   = dict(zip(df['SFTAZ'], df['VISITOR']))
        self.totpark   = dict(zip(df['SFTAZ'], df['TOTPARK']))

        del tazdatadbf
        
        # calculate parkavind for SF tazs, like sftourmc.cpp
        for itaz in list(self.tazcoords.keys()):
            denom = 0.0
            numer = 0.0
            for jtaz in list(self.tazcoords.keys()):
                x = (self.tazcoords[itaz][0] - self.tazcoords[jtaz][0])*(self.tazcoords[itaz][0] - self.tazcoords[jtaz][0])
                y = (self.tazcoords[itaz][1] - self.tazcoords[jtaz][1])*(self.tazcoords[itaz][1] - self.tazcoords[jtaz][1])
                dist = math.sqrt(x+y)
                
                if dist<(0.25*5280):
                    denom += (self.hhlds[jtaz] + self.totalemp[jtaz] + 4*self.visitor[jtaz])
                    numer += self.totpark[jtaz]
            if denom<=0 or numer<=0 or numer>denom:
                self.prkavind[itaz] = 0
            else:
                self.prkavind[itaz] = -3.96*math.log(numer/denom)
                self.prkavind[itaz] = min(self.prkavind[itaz], 4.0)
            
        # debug
        #print "Average Parking Index Values"
        #for itaz in self.tazcoords.keys():
        #    print "%5d %6.2f" % (itaz, self.prkavind[itaz])
            
    def getHwySkimAttributes(self, origtaz, desttaz, mode, segdir):
           
        """
        For HWY modes, Returns a 8-tuple of
          (drive time in mins,
           term time in mins,
           distance in miles,
           bridge toll in 1989 cents,
           value toll in 1989 cents,
           distance with vc>0.8,
           distance with vc>0.9,
           distance with vc>1.0)
        """

        #Lookup terminal times (time to walk to/from vehicle)
        if (origtaz >= self.skim_table_files[self.termtime_file].root._f_get_child("1").shape[0] or
            desttaz >= self.skim_table_files[self.termtime_file].root._f_get_child("1").shape[0]):
            termtime = 0               
        #If outbound trip based on origin
        elif segdir == 1:
            termtime = self.skim_table_files[self.termtime_file].root._f_get_child("1")[origtaz-1][desttaz-1]
        #If inbound trip based on destination
        else:
            termtime = self.skim_table_files[self.termtime_file].root._f_get_child("1")[desttaz-1][origtaz-1]
             
        #Point to the proper matrices in skim file
        drivetimeIndexStr = HighwaySkim.TIMEINDEX[HighwaySkim.MODE_NUM_TO_STR[mode]]
        distIndexStr      = HighwaySkim.DISTINDEX[HighwaySkim.MODE_NUM_TO_STR[mode]]
        btollIndexStr     = HighwaySkim.BTOLLINDEX[HighwaySkim.MODE_NUM_TO_STR[mode]]
        distVC08IndexStr  = HighwaySkim.DISTVC08[HighwaySkim.MODE_NUM_TO_STR[mode]]
        distVC09IndexStr  = HighwaySkim.DISTVC09[HighwaySkim.MODE_NUM_TO_STR[mode]]
        distVC10IndexStr  = HighwaySkim.DISTVC10[HighwaySkim.MODE_NUM_TO_STR[mode]]
        PaxPerVeh         = HighwaySkim.PAXPERVEH[HighwaySkim.MODE_NUM_TO_STR[mode]]

        #Read attributes from matrices
        drivetime = self.skim_table_files[self.hwy_skim_file].root._f_get_child(drivetimeIndexStr    )[origtaz-1,desttaz-1]
        dist  = self.skim_table_files[self.hwy_skim_file].root._f_get_child(distIndexStr    )[origtaz-1,desttaz-1]
        dist08= self.skim_table_files[self.hwy_skim_file].root._f_get_child(distVC08IndexStr)[origtaz-1,desttaz-1]
        dist09= self.skim_table_files[self.hwy_skim_file].root._f_get_child(distVC09IndexStr)[origtaz-1,desttaz-1]
        dist10= self.skim_table_files[self.hwy_skim_file].root._f_get_child(distVC10IndexStr)[origtaz-1,desttaz-1]
        btoll = self.skim_table_files[self.hwy_skim_file].root._f_get_child(btollIndexStr   )[origtaz-1,desttaz-1]/(PaxPerVeh)
        
        if HighwaySkim.MODE_TOLLED[mode]:
            vtollIndexStr = HighwaySkim.VTOLLINDEX[HighwaySkim.MODE_NUM_TO_STR[mode]]
            vtoll = self.skim_table_files[self.hwy_skim_file].root._f_get_child(vtollIndexStr)[origtaz-1,desttaz-1]/(PaxPerVeh)
        else:
            vtoll = 0

        return (drivetime, termtime, dist, btoll, vtoll, dist08, dist09, dist10)

    def getTripParkCost(self, origtaz, desttaz, mode, purp):

        '''Returns a 6-tuple of:
            trip origin taz parking cost in 1989 cents per hour
            trip destination taz parking cost in 1989 cents per hour
            trip origin percent of paid parking spaces
            trip destination taz percent of paid parking spaces
            trip origin taz parking availability index
            trip destination taz parking availability index            '''
 
        PaxPerVeh = HighwaySkim.PAXPERVEH[HighwaySkim.MODE_NUM_TO_STR[mode]]
        
        if Skim.PURPOSE_NUM_TO_STR[purp] in ["Other","WorkBased"]:
            origparkcost = self.prkcstoh[origtaz] * 100 / PaxPerVeh
            destparkcost = self.prkcstoh[desttaz] * 100 / PaxPerVeh
        else:
            origparkcost = self.prkcstwh[origtaz] * 100 / PaxPerVeh
            destparkcost = self.prkcstwh[desttaz] * 100 / PaxPerVeh

        origppaying = self.ppaying[origtaz] 
        destppaying = self.ppaying[desttaz]
        origprkavailind = self.prkavind[origtaz]        
        destprkavailind = self.prkavind[desttaz]        
        
        return (origparkcost, destparkcost, origppaying, destppaying, origprkavailind, destprkavailind)
 
    def getTourParkCost(self, origtaz, desttaz, mode, purp):  
        ''' returns a tuple of 
                hourly parking cost at tour primary purpose destination taz in 1989 cents per hour
                percent paid parking spaces in tour primary purpose destination taz
                parking availability index in tour primary purpose destination taz'''
 
        PaxPerVeh = HighwaySkim.PAXPERVEH[HighwaySkim.MODE_NUM_TO_STR[mode]]

        if Skim.PURPOSE_NUM_TO_STR[purp] in ["Other","WorkBased"]:
            hrlyparkcost = self.prkcstoh[desttaz] * 100 / PaxPerVeh
        else:
            hrlyparkcost = self.prkcstwh[desttaz] * 100 / PaxPerVeh

        ppaying = self.ppaying[desttaz]
        prkavailind = self.prkavind[desttaz]        
        
        return (hrlyparkcost, ppaying, prkavailind)
    
    @classmethod
    def getSkimTable(cls, file_dir, timeperiod, mode, variable):
        if variable.lower() not in ['terminaltime','distance','occupancy','drivetime','btoll','vtoll']:
            print("Variable %s not in available list of variables" % (variable))
            exit(2)
        
        skimInstance = HighwaySkim(file_dir, timeperiod)
        #if given a number, convert to string mode representation
        try:
            int(mode)
            mode = cls.MODE_NUM_TO_STR[mode]
        except:
            pass
        table = np.zeros((MAX_SF_ZONE, MAX_SF_ZONE))
        if variable.lower() == 'terminaltime':
            table = skimInstance.skim_table_files[skimInstance.termtime_file].root._f_get_child("1").read()[:MAX_SF_ZONE,:MAX_SF_ZONE]

        elif variable.lower() == 'distance':
            distIndexStr      = HighwaySkim.DISTINDEX[mode]
            table = skimInstance.skim_table_files[skimInstance.hwy_skim_file].root._f_get_child(distIndexStr).read()[:MAX_SF_ZONE,:MAX_SF_ZONE]
        
        elif variable.lower() == 'occupancy':
            table = HighwaySkim.PAXPERVEH[mode]
        
        elif variable.lower() == 'drivetime':
            drivetimeIndexStr = HighwaySkim.TIMEINDEX[mode]
            table = skimInstance.skim_table_files[skimInstance.hwy_skim_file].root._f_get_child(drivetimeIndexStr).read()[:MAX_SF_ZONE,:MAX_SF_ZONE]
        
        elif variable.lower() == 'btoll':
            btollIndexStr = HighwaySkim.BTOLLINDEX[mode]
            table = skimInstance.skim_table_files[skimInstance.hwy_skim_file].root._f_get_child(btollIndexStr).read()[:MAX_SF_ZONE,:MAX_SF_ZONE]
            
        elif variable.lower() == 'vtoll':
            vtollIndexStr = HighwaySkim.VTOLLINDEX[mode]
            table = skimInstance.skim_table_files[skimInstance.hwy_skim_file].root._f_get_child(vtollIndexStr).read()[:MAX_SF_ZONE,:MAX_SF_ZONE]
        # print mode, table.sum()
        return table