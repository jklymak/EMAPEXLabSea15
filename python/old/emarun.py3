#! /usr/bin/env python2
# emarun.py -- run emapex processing automatically
# run once per minute from cron
# cron should cd to /home/emapex/proc before running emarun.py
# calls emadec.py for decoding
# will call emavel.py for velocity computation
#
# Watches the lognum files made by kermit-server-new shell script
#
# Runs emapex processing when find 'Transaction Log Closed'
# in last line of kermit transaction log (.trn).
#
# /home/emapex/proc/emainfo has params and output directories
#
# to force rerun of <fltid>, remove the file: <donedir>/<fltid>

# system imports
from __future__ import print_function
from sys import exit,stdout
from optparse import OptionParser
from datetime import datetime
from subprocess import Popen, PIPE
from os import system, path, getpid, remove
# from psutil import pid_exists

# emapex imports
from getinfo import getinfo, getfltid, getinfoinit

# make a lock file
def mklock(lockfile):
  if path.exists(lockfile):
    try:
      lckfp = open(lockfile, 'rt')
      buf = lckfp.readline()
      lckfp.close()
    except:
      print( datetime.utcnow().strftime('%Y-%b-%d %H:%M:%S'), 'UTC ',end='')
      print('mklock(): cannot open,read,close lockfile=',lockfile)
      return False

    try:
      pid = int(buf.strip())
    except:
      print( datetime.utcnow().strftime('%Y-%b-%d %H:%M:%S'), 'UTC ',end='')
      print('mklock(): cannot decode pid, buf=',buf)
      return False

    # if pid_exists(pid):
    fn = '/proc/{0:d}'.format(pid)
    if path.exists(fn):
      print( datetime.utcnow().strftime('%Y-%b-%d %H:%M:%S'), 'UTC ',end='')
      print('mklock(): pid {0} is running'.format(pid),end='')
      print(' so not removing',lockfile)
      return False
    else:
      print('mklock(): removing stale lock file,', lockfile)
      remove(lockfile)
#     call(["rm", "-f", lockfile])

  pid = getpid()
  try:
    lckfp = open(lockfile, 'wt')
    lckfp.write(str.format('{0:d}\n',pid))
    lckfp.close()
  except:
    print( datetime.utcnow().strftime('%Y-%b-%d %H:%M:%S'), 'UTC ',end='')
    print('mklock(): cannot open,write,close lockfile=',lockfile)
    return False

  return True

def rmlock(lockfile):
  try:
    remove(lockfile)
  except:
    print('mklock(): cannot remove lockfile=',lockfile)
    return False
  return True

def getlognum(trndir, fltid):
  lognumfile = '{0:s}/{1:s}/lognum'.format(trndir,fltid)

  try:
    ifd = open(lognumfile, mode='rt')
  except IOError:
    if options.verbose:
      print('getlognum(): Cannot open ' + lognumfile)
    return None

  line = ifd.read()
  ifd.close()

  try:
    lognum = int(line.strip())
  except:
    if options.verbose:
      print('bad decode for lognum line=',line)
      print('lognumfile=',lognumfile)
    lognum = None
    
  return lognum

def iskermfin(trndir, fltid, lognum):

  trnfile = str.format('{0:s}/{1:s}/ema-{1:s}-log-{2:04d}.trn',trndir,fltid,lognum)

  if options.verbose:
    print('trnfile:',trnfile)

  try:
    ifd = open(trnfile, mode='rt')
  except IOError:
    if options.verbose:
      print('iskermfin(): Cannot open ' + trnfile)
    return False

  complete = None
  for line in ifd:
    if line.find('Transaction complete') >= 0:
      complete = line.strip()
  ifd.close()
  last = line.strip()
    
  if last.find('Transaction Log Closed') < 0:
    return False
  else:
    if options.verbose:
      print('fltid:',fltid)
      print('  lognum:',lognum)
      print('  complete:',complete)
      print('  last line:',last)
    return True

def isdone(donedir, fltid, lognum):

  donenumfile = '{0:s}/{1:s}'.format(donedir,fltid)
  if options.verbose:
    print('  donenumfile:',donenumfile)

  try:
    ifd = open(donenumfile, mode='rt')
  except IOError:
    if options.verbose:
      print('donenumfile file missing:',donenumfile)
    return False

  line = ifd.read()
  ifd.close()

  try:
    donenum = int(line.strip())
  except:
    if options.verbose:
      print('donenumfile=', donenumfile, 'cannot be decoded')
    return False

  if donenum == lognum:
    return True
  else:
    return False 

def setdone(donedir, fltid, lognum):
  donenumfile = '{0:s}/{1:s}'.format(donedir,fltid)
  ofp = open(donenumfile,'wt');
  print(lognum, file=ofp)
  ofp.close()

def getnewfiles(trndir,fltid,lognum):
  trnfile = str.format('{0:s}/{1:s}/ema-{1:s}-log-{2:04d}.trn',trndir,fltid,lognum)
  newfiles = []
  fp = open(trnfile, 'rt')
  for line in fp:
    if line.find('Receiving ') == 0:
      toks = line.split()
      if len(toks) == 2:
        newfiles.append(toks[1])
  fp.close()
  return newfiles

# email transaction log
def mailtrn(trndir,fltid,lognum):
  from smtplib import SMTP
  from email.mime.text import MIMEText
  from socket import gethostname
  from getpass import getuser

  # Create a text/plain message from file.
  trnfile = str.format('{0:s}/{1:s}/ema-{1:s}-log-{2:04d}.trn',trndir,fltid,lognum)
  if options.verbose:
    print('compute trnfile: ', trnfile)
  fp = open(trnfile, 'rt')
  msg = MIMEText(fp.read())
  fp.close()

  # msg = MIMEText('New trnfile: ' + trnfile)


  host = gethostname()
  user =  getuser()

  From = 'emapex@ohm.apl.uw.edu'
  From = user+'@'+host
  To = 'jdunlap@uw.edu'
  Reply_To = 'dunlap@apl.uw.edu'

  msg['Subject'] = str.format('emarun.py {0:s} {1:04d}',fltid,lognum)
  msg['From'] = From
  msg['To'] = To
  msg.add_header('Reply-To', Reply_To)

  s = SMTP('localhost')
  s.sendmail(From, To, msg.as_string())
  s.quit()

def findallrunids(trndir):
  cmd = 'find ' + trndir + ' -name lognum'
  proc = Popen(cmd, shell=True, stdout=PIPE)
  files = proc.communicate()[0].split()
  runids = []
  for i in range(0,len(files)):
    file = files[i]
    dir = path.dirname(file)
    parts = dir.split('/')
    runids.append(parts[-1])
  return sorted(runids)

if __name__ == '__main__':

# print( datetime.utcnow().strftime('%Y-%b-%d %H:%M:%S'), 'UTC')

  lockfile = './emarun.lck'  # prevents running multiple copies
  if mklock(lockfile) == False:
    exit(1)

  parser = OptionParser(usage='%prog [Options] RunId[s]')

  parser.add_option('-v', '--verbose',
                    action='store_true', dest='verbose', default=False,
                    help='print status messages to stdout')

  parser.add_option('-i', '--info', '--infofile',
    dest='infofile', default='./emainfo',
    help='file with processing parameters for each runid')

  (options, args) = parser.parse_args()


  if len(args) > 0:
    runids = args
  else:
    info = getinfo('never',options.infofile)
    if info == None:
      print('emarun(): cannot getinfo()')
      sys.exit(1)
      
    # info = getinfoinit()
    runids = findallrunids(info.trndir)

  for runid in runids:
    info = getinfo(runid,options.infofile)
    if info == None:
      continue
    # print('runid=',runid,'info.runid=',info.runid)

    if info.fltid == None:
      info.fltid = runid
      info.runid = runid

    lognum = getlognum(info.trndir,info.fltid)
    if lognum == None:
      if options.verbose:
        print('runid=',runid, 'no lognum found for fltid=',info.fltid,'-- skipped')
      continue

    if isdone(info.donedir, info.fltid, lognum):
      if options.verbose:
        print('runid=',runid,'fltid=',info.fltid,'lognum=',lognum, 'already done -- skipped')
      continue

    if not iskermfin(info.trndir, info.fltid, lognum):
      if options.verbose:
        print(info.fltid, lognum, 'Kermit not finished yet')
      continue

    # put processing code here
    print(' ')
    print( datetime.utcnow().strftime('%Y-%b-%d %H:%M:%S'), 'UTC ',end='')
    print('processing runid=',runid,'fltid=',info.fltid,'lognum=',lognum)

    # mailtrn(info.trndir,info.fltid,lognum)

    newfiles = getnewfiles(info.trndir,info.fltid,lognum)

    # special handling for files from "test gps iridium" firmware command
    t5aflag = False
    for newfile in newfiles:
      if newfile.find('-t5a-') >= 0:
        t5aflag = True
        t5afile = info.fltdir + '/' + newfile
        cmd = './emadec.py ' + t5afile
        print('cmd=', cmd)
        stdout.flush()
        system(cmd)
    
    if not t5aflag:
      print('newfiles=',newfiles)
      cmd = './emadec.py ' + info.runid
      print('cmd=',cmd)
      stdout.flush()
      system(cmd)

      cmd = './emavel.py ' + info.runid
      print('cmd=',cmd)
      stdout.flush()
      system(cmd)

      cmd = './emaplt.py ' + info.runid
      print('cmd=',cmd)
      stdout.flush()
      system(cmd)

    cmd = '/home/emapex/bin/email-newfiles.sh {0} {1}'.format(info.fltid,info.runid)
    print('cmd=',cmd)
    stdout.flush()
    system(cmd)

    # end of processing code

    if options.verbose:
      print(info.fltid, lognum, 'setting done file')
    setdone(info.donedir, info.fltid, lognum)

    print(datetime.utcnow().strftime('%Y-%b-%d %H:%M:%S'), 'UTC finished',runid)

  rmlock(lockfile)
