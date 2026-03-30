'''
utils.py
'''
import re

def format_block(x):
    c = re.compile('(?P<head>\d\/\d\/)?(?P<num>[0-9]{0,4})(?P<let>[a-zA-Z]{0,5})')
    m = c.match(str(x)).groupdict()
    num, let = m['num'].replace('/1/',''), m['let']
    
    return '{:04d}{}'.format(int(num), let)

def format_lot(x):
    c = re.compile('(?P<head>[a-zA-Z]{0,4})(?P<body>[0-9]{0,3})(?P<tail>[a-zA-Z]{0,2})')
    m = c.match(str(x)).groupdict()
    head, body, tail = m['head'], m['body'], m['tail']
    
    if len(head) == 0:
        body = '{:03d}'.format(int(body))
    return head+body+tail

def format_blklot(blklot):
    blklot = str(blklot)
    if len(blklot) < 7:
        blklot = "0"*(7-len(blklot)) + blklot
    return blklot