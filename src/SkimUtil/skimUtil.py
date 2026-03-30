'''
Created on Jan 25, 2010

@author: Lisa Zorn

Generic trip record class, plus some extra functions that will likely come up.
'''

import os,re,sys

__all__ = [ 'readDistrictsEqv', 'createExpressionForValue' ]

eqvline_re      = re.compile("^DIST (\d+)=(\d+)\s*((.+)\s*)?$")

def readDistrictsEqv(eqvfile):
    """
    Reads eqv file, returns dictionary of { taz -> district num }, 
    dictionary of { district num -> [ list of TAZs ] },
    and dictionary of { district num -> district name }
    """
    tazToDist   = {}
    distToTaz   = {}
    distToName  = {}
    infile      = open(eqvfile, 'rU') # The U is for universal newline support
    for line in infile:
        m = eqvline_re.match(line)
        if (m == None):
            sys.stderr.write("Didn't understand line [" + line + "] in " + eqvfile)
        tazToDist[int(m.group(2))] = int(m.group(1))
        if int(m.group(1)) not in distToTaz:
            distToTaz[int(m.group(1))] = []
        distToTaz[int(m.group(1))].append(int(m.group(2)))
        if (m.group(4) != None):
            # print "[%s]" % (m.group(4))
            distToName[int(m.group(1))] = m.group(4)
    infile.close()
    return (tazToDist, distToTaz, distToName)

def createExpressionForValue(tazmapping, var, value):
    """
    Creates an expression for a var (e.g. workstaz) and a mapping value (e.g. Cupertino).
    tazmapping should be a dictionary mapping tazes to names (including the given value)
    """
    retstr = '('
    tazes = list(tazmapping.keys())
    gtlt  = 0
    for i in range(len(tazes)):
        taz = tazes[i]
        v = tazmapping[taz]
        if (v == value):
            
            # within a gtlt clause
            if gtlt:
                # end it?
                if i==len(tazes)-1 or tazmapping[tazes[i+1]]!=value:
                    retstr += ' & '
                    retstr += '(' + var + ' <= ' + str(taz) + '))'
                    gtlt = 0
            # start one?
            elif (i < len(tazes)-2 and tazmapping[tazes[i+1]]==value and tazmapping[tazes[i+2]]==value):
                if (len(retstr)>1): retstr += ' | '
                retstr += '((' + var + ' >= ' + str(taz) + ')'
                gtlt = 1
            else:
                if (len(retstr)>1): retstr += ' | '
                retstr += '(' + var + ' == ' + str(taz) + ')'
    retstr += ')'
    return retstr
