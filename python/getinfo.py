from __future__ import print_function

from os import makedirs, path, sep
from sys import exit
from collections import namedtuple
from datetime import datetime
from time import strptime, mktime
import copy

def getfltid(runid):
  if runid == None:
    return None
  tmp=''
  for i in range(0,len(runid)):
    if not str.isdigit(runid[i]):
      break;
    tmp += runid[i]
  try:
    fltid = tmp
  except:
    fltid = None
  return fltid

def printinfo(info):
  print('info.runid   =',info.runid)
  print('info.datebeg =',strftime('%Y-%m-%d %H:%M:%S',info.datebeg))
  print('info.dateend =',strftime('%Y-%m-%d %H:%M:%S',info.dateend))

def getinfoinit():
  info = namedtuple('INFO', [])
  info.runid = None
  info.fltid = None
  info.datebeg = datetime(1970,1,1)
  info.dateend = datetime(2038,1,19)
  info.fltdir = '/home/emapex/data'
  info.trndir = '/home/emapex/logs'
  info.decdir = '/home/emapex/proc/dec'
  info.veldir = '/home/emapex/proc/vel'
  info.donedir = '/home/emapex/proc/donenum'
  info.hpidmax = 8999
  info.hpidmin = 0
  info.hpidonly = 0
  return info

def split_ifile(ifile):
  a = ifile.split('-')
  if len(a) != 6:
    return None
  b = a[5].split('_')
  if len(b) != 3:
    return None
  return a[0:5] + b

def getfilenameinfo(filename):
  info = namedtuple('FILEINFO',[])
  segs = filename.split('/')
  info.leaf = segs[-1]

  toks = split_ifile(info.leaf)
  if toks == None:
    print('error: getfilenameinfo: file=',file,'has incorrect form')
    print('  leaf=',leaf)
    exit(1)

  info.fltid = toks[1]
  
  try:
    info.fltid   = toks[1]
  except:
    print('error: getfilenameinfo: cannot decode fltid. toks=',toks)
    exit(1)
    # return None

  try:
    info.filedate = datetime.fromtimestamp(mktime(\
      strptime(toks[4]+'T'+toks[5],'%Y%m%dT%H%M%S')))
  except:
    print('error: getfilenameinfo: cannot decode filedate. toks=',toks)
    exit(1)
    # return None
  return info

def mkinfo(file,infofile):
  segs = file.split('/')
  leaf = segs[-1]

  toks = split_ifile(leaf)
  if toks == None:
    print('error: mkinfo: file=',file,'has incorrect form')
    print('  leaf=',leaf)
    exit(1)

  info = getinfoinit()

  info.leaf = leaf
  info.runid  = toks[1]
  info.fltid = info.runid
  info.datebeg = datetime.fromtimestamp(mktime(\
                 strptime(toks[4]+'T'+toks[5],'%Y%m%dT%H%M%S')))
  info.dateend = info.datebeg
  info.hpidonly = int(toks[3])
  info.hpidmax = info.hpidonly
  info.hpidmin = info.hpidonly
  info.odir = info.decdir + '/' + info.runid + '/extra/' + toks[4] + '-' + toks[5]
  return info

def getinfo_by_runid(runid_want, infofile):
  info = getinfoinit()

  runid_seg = None
  found_runid = False

  # read whole file
  with open(infofile) as fp:
    lins = fp.readlines()
  fp.close()

  # decode the lines
  for i in range(0,len(lins)):
    lin = lins[i]
    lineno = i + 1

    # toss comments
    j = lin.find('#')
    lin = lin[0:j]

    # split each line into tokens
    toks = lin.split()
    if len(toks) < 2:
      continue
    for j in range(0,len(toks)):
      toks[j] = str.strip(toks[j])

    nam = toks[0].lower()

    # check all lines for correct number of tokens
    if nam.find('date') == 0: 
      if len(toks) != 2 and len(toks) != 3:
        print('error: getinfo_by_runid: wrong number of tokens, lineno=',lineno,'lin=',lin)
        exit(1)
    else:
      if len(toks) != 2:
        print('error: getinfo_by_runid: wrong number of tokens, lineno=',lineno,'lin=',lin)
        exit(1)

    # keep track of which runid segment we are in
    if nam == 'runid':
      runid_seg = toks[1]
      if runid_seg == runid_want:
        found_runid = True

    elif runid_seg == copy.copy(runid_want) or runid_seg == None:
      if nam == 'fltid':
        info.fltid = toks[1]

      elif nam == 'datebeg':  # date/time of mission start
        if len(toks) == 3:
          tim = toks[1] + 'T' + toks[2]
        else:
          tim = toks[1] + 'T' + '00:00:00'
        try:
          info.datebeg = datetime.fromtimestamp(mktime(\
          strptime(tim,'%Y-%m-%dT%H:%M:%S')))
        except:
          print('error: getinfo_by_runid: cannot decode line',i+1,':',lin)
          print('  tim=',tim)
          print('  toks=',toks)
          print('  strptime=',strptime(tim,'%Y-%m-%dT%H:%M:%S'))
          exit(1)

      elif nam == 'dateend':  # date/time of mission stop
        if len(toks) == 3:
          tim = toks[1] + 'T' + toks[2]
        else:
          tim = toks[1] + 'T' + '00:00:00'
        try:
          info.dateend = datetime.fromtimestamp(mktime(\
          strptime(tim,'%Y-%m-%dT%H:%M:%S')))
        except:
          print('error: getinfo_by_runid: cannot decode line',i+1,':',lin)
          exit(1)

      elif nam == 'fltdir':    # directory of files received from float
        info.fltdir = toks[1]

      elif nam == 'trndir':    # directory of kermit transaction logs
        info.trndir = toks[1]

      elif nam == 'decdir':   # directory of decoded data
        info.decdir = toks[1]

      elif nam == 'veldir':   # directory of velocity data
        info.veldir = toks[1]

      elif nam == 'donedir':   # directory of lognums already processed
        info.donedir = toks[1]

      elif nam == 'hpidmin':
        info.hpidmin = int(toks[1])

      elif nam == 'hpidmax':
        info.hpidmax = int(toks[1])

      elif nam == 'hpidonly':
        info.hpidonly = int(toks[1])

      else:
        print('error: getinfo_by_runid: unknown nam=',nam)
        exit(1)

  if found_runid:
    info.runid = runid_want

  if info.hpidonly > 0:
    info.hpidmax = info.hpidonly
    info.hpidmin = info.hpidonly

  try:
    makedirs(info.donedir)
  except OSError:
    if not path.isdir(info.donedir):
      print('error: getinfo_by_runid: cannot create directory=',info.donedir)
      exit(1)

  return info

def getinfo(arg, infofile):
  if arg == None:
    print('error: getinfo: arg == None')
    exit(1)
  if infofile == None:
    print('error: getinfo: infofile == None')
    exit(1)

  inforet = None

  # get leaf name from possible full path name
  leaf = arg.rstrip(sep).split(sep)[-1]

  # determine type of argument: 'fltid', 'runid', 'filename'
  underbar = leaf.split('_')
  hyphen = underbar[0].split('-')
  if len(underbar) > 1:
    toks = hyphen + underbar[1:]
  else:
    toks = hyphen

    
  if len(toks) == 1:
    info = getinfo_by_runid(arg,infofile)
    if info.runid == arg:
      type = 'runid'
    else:
      type = 'fltid'
  elif len(toks) == 8:
    type = 'filename'
    filename = leaf
  else:
#   print('error: getinfo: unknown type.  arg=',arg)
#   exit(1)
    return None

  if type == 'runid':
    if info.fltid == None:
      info.fltid = getfltid(info.runid)
    return info

  if type == 'filename':
    info = getinfoinit()
    fileinfo = getfilenameinfo(filename)
    info.runid = fileinfo.fltid
    info.fltid = fileinfo.fltid
    return info

  # do below if type == 'fltid'
  # try to find a runid which has fltid or decodes to fltid and allowd the current time

  # read whole file 
  with open(infofile) as fp:
    lins = fp.readlines()
  fp.close()

  # decode the lines to get runids
  runids = []
  for i in range(0,len(lins)):
    lin = lins[i]

    # toss comments
    j = lin.find('#')
    lin = lin[0:j]

    # split each line into tokens
    toks = lin.split()
    if len(toks) != 2:
      continue
    for j in range(0,len(toks)):
      toks[j] = str.strip(toks[j])

    nam = toks[0].lower()
    val = toks[1]

    if nam == 'runid':
      runids.append(val)


  for runidchk in runids:
    infochk = getinfo_by_runid(runidchk,infofile)

    if infochk.fltid == None:
      infochk.fltid = getfltid(runidchk)
      if infochk.fltid == None:
        continue

    if infochk.fltid != arg:
      continue

    datenow = datetime.utcnow()
    if infochk.datebeg <= datenow and datenow <= infochk.dateend:
      inforet = copy.copy(infochk)

  if inforet == None:
    inforet = getinfoinit()

  if inforet.runid != None:
    if inforet.fltid == None:
      inforet.fltid = getfltid(inforet.runid)

# if inforet.fltid == None:
#   print('warning: getinfo: runid=',inforet.runid,'fltid=',inforet.fltid)

  return inforet
