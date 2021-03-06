#!/usr/bin/env python2
# emaplt.py -- plot emapex profiles

from __future__ import print_function

import matplotlib
matplotlib.use('Agg') # needed when used with cron

import matplotlib.pyplot as plt
from sys import exit
from os import listdir
import os
from scipy.io import loadmat
from collections import namedtuple
from optparse import OptionParser
import numpy as np
from optparse import OptionParser
from string import printable
from datetime import datetime, timedelta

def larger_axlim( axlim ):
    """ argument axlim expects 2-tuple 
        returns slightly larger 2-tuple """
    axmin,axmax = axlim
    axrng = axmax - axmin
    new_min = axmin - 0.03 * axrng
    new_max = axmax + 0.03 * axrng
    return new_min,new_max

def fix_xlim(ax):
  ax.set_xlim( larger_axlim( ax.get_xlim() ) )

def fix_ylim(ax):
  ax.set_ylim( larger_axlim( ax.get_ylim() ) )

def fix_xylims(ax):
  fix_xlim(ax)
  fix_ylim(ax)

def uxt2str(uxt):
  try:
    pyt = datetime(1970,1,1) + timedelta(0,uxt)
    return pyt.strftime('%Y-%m-%d %H:%M:%S')
  except:
    return 'NaN'

def mymkdir(mydir):
  try: 
    os.makedirs(mydir) # like mkdir -p
  except OSError:
    if not os.path.isdir(mydir):
      print('cannot make directory:',mydir)
      exit(1)

def getmatfiles(idir,typ):
  allfiles = sorted(listdir(idir))
  matfiles = []
  hpids = []
  for ifile in allfiles:
    if ifile.find('~') >= 0:
      if options.verbose:
        print('skipped backup ifile=',ifile)
      continue
    if not all(c in printable for c in ifile):
      if options.verbose >= 0:
        print('skipped non-printable ifile=',ifile)
      continue
    toks = ifile.split('-')
    if toks[-1] == typ + '.mat':
      matfiles.append(ifile)
      hpids.append(int(toks[2]))
  return matfiles, hpids

def writepdf(pltdir, namewoext):
  mymkdir(pltdir)
  pdffile = os.path.join(pltdir,namewoext+'.pdf')
  if options.verbose:
    print('  pdffile=',pdffile)
  plt.savefig(pdffile)
  os.system('/home/dunlap/bin/updateframe.run ' + pltdir)

def main():
  parser = OptionParser()

  parser.add_option("-v", "--verbose", dest="verbose", 
    action="count", default=0,
    help="print status messages to stdout")

  parser.add_option("--hpid", dest="hpid", metavar='HPID', 
    type="int", default=None, 
    help="half profile id [default: %default]")

  parser.add_option('-j', '--just_all', 
    action='store_true', dest='just_all', default=False,
    help='plot just overall figs')

  global options
  (options, args) = parser.parse_args()

  if len(args) < 1:
    print('usage: pltema runid(s)')
    exit(1)

  if options.just_all:
    do_plt_ctd = False
    do_plt_pvt = False
    do_plt_vel = False
    do_plt_Psfc = False
    do_plt_axyz = False
    do_plt_hxy = False
    do_plt_e12 = False
    do_plt_batv = True
    do_plt_pvtoa = True # pressure top & bottom over all profiles
  else:
    do_plt_ctd = True
    do_plt_pvt = True
    do_plt_vel = True
    do_plt_Psfc = True
    do_plt_axyz = True
    do_plt_hxy = True
    do_plt_e12 = True
    do_plt_batv = True
    do_plt_pvtoa = True

  for runid in args:

    uxt_pr_all = []
    uxt_prtop_all = []
    uxt_prbot_all = []
    pr_all = []
    prtop_all = []
    prbot_all = []
    uxt_hol_all = []
    pr_hol_all = []

    uxt_gps_all = []
    lat_all = []
    lon_all = []
    alt_all = []

    uxt_ema_all  = []
    bat_ema_all  = []

    uxt_vit_all  = []
    bat_vit_all = []


    pltdir = '/home/emapex/proc/plt/' + runid
    decdir = '/home/emapex/proc/dec/' + runid
    veldir = '/home/emapex/proc/vel/' + runid

    ctd_files, ctd_hpids = getmatfiles(decdir,'ctd')
    vel_files, vel_hpids = getmatfiles(veldir,'vel')
    eoa_files, eoa_hpids = getmatfiles(decdir,'eoa')
    efp_files, efp_hpids = getmatfiles(decdir,'efp')
    gps_files, gps_hpids = getmatfiles(decdir,'gps')
    scp_files, scp_hpids = getmatfiles(decdir,'scp')
    hol_files, hol_hpids = getmatfiles(decdir,'hol')
    vit_files, vit_hpids = getmatfiles(decdir,'vit')

#   hpids = np.array(list(set(ctd_hpids + vel_hpids + eoa_hpids + efp_hpids)))
    hpids = np.array(list(set(ctd_hpids)))

    if options.hpid:
      hpids = np.tile(options.hpid,1)

    for hpid_index in range(len(hpids)):
      hpid = hpids[hpid_index]
      if options.verbose:
        print('\nhpid=',hpid)

      jctd = np.nonzero(np.array(ctd_hpids) == hpid)[0]
      if len(jctd) == 0:
        got_ctd = False
        print('no CTD data -- very curious... what to do? exit for now')
        print('runid=',runid)
        print('hpid=',hpid)
        print('hpids=',hpids)
        exit(1)
      else:
        got_ctd = True
        ctdfile = '{0:s}/ema-{1:s}-{2:04d}-ctd.mat'.format(decdir,runid,hpid)
        if options.verbose:
          print('ctdfile=',ctdfile)
        CTD = loadmat(ctdfile)

        uxt_ctd = CTD['UXT'][0]
        Pctd = CTD['P'][0]
        Tctd = CTD['T'][0]
        Sctd = CTD['S'][0]
        pc_ctd = CTD['pc'][0]

      jscp = np.nonzero(np.array(scp_hpids) == hpid)[0]
      if len(jscp) == 0:
        got_scp = False
      else:
        got_scp = True
        scpfile = '{0:s}/ema-{1:s}-{2:04d}-scp.mat'.format(decdir,runid,hpid)
        if options.verbose:
          print('scpfile=',scpfile)
        SCP = loadmat(scpfile)

        Pscp = SCP['P'][0]
        Tscp = SCP['T'][0]
        Sscp = SCP['S'][0]

      jhol = np.nonzero(np.array(hol_hpids) == hpid)[0]
      if len(jhol) == 0:
        got_hol = False
      else:
        got_hol = True
        holfile = '{0:s}/ema-{1:s}-{2:04d}-hol.mat'.format(decdir,runid,hpid)
        if options.verbose:
          print('holfile=',holfile)
        HOL = loadmat(holfile)
        nobs_hol = HOL['nobs'][0]
        if nobs_hol:
          uxt_hol = HOL['UXT'][0]
          Phol    = HOL['P'][0]
          Thol    = HOL['T'][0]
          Shol    = HOL['S'][0]
          pc_hol  = HOL['pc'][0]
        else:
          got_hol = False

      jefp = np.nonzero(np.array(efp_hpids) == hpid)[0]
      if len(jefp) == 0:
        got_efp = False
      else:
        got_efp = True
        efpfile = '{0:s}/ema-{1:s}-{2:04d}-efp.mat'.format(decdir,runid,hpid)
        if options.verbose:
          print('efpfile=',efpfile)
        EFP = loadmat(efpfile)
        uxt_efp = EFP['UXT'][0]
        e1_mean = EFP['E1MEAN4'][0]
        e2_mean = EFP['E2MEAN4'][0]
        e1_sdev = EFP['E1SDEV4'][0]
        e2_sdev = EFP['E2SDEV4'][0]
        hx_mean = EFP['HX_MEAN'][0]
        hy_mean = EFP['HY_MEAN'][0]
        hx_sdev = EFP['HX_SDEV'][0]
        hy_sdev = EFP['HY_SDEV'][0]
        rotp_hx = EFP['ROTP_HX'][0]
        rotp_hy = EFP['ROTP_HY'][0]
        ax_mean = EFP['AX_MEAN'][0]
        ay_mean = EFP['AY_MEAN'][0]
        az_mean = EFP['AZ_MEAN'][0]
        ax_sdev = EFP['AX_SDEV'][0]
        ay_sdev = EFP['AY_SDEV'][0]
        bt_mean = EFP['BT_MEAN'][0] * 0.009668 + 0.2

      jvel = np.nonzero(np.array(vel_hpids) == hpid)[0]
      if len(jvel) == 0:
        got_vel = False
      else:
        got_vel = True
        velfile = '{0:s}/ema-{1:s}-{2:04d}-vel.mat'.format(veldir,runid,hpid)
        if options.verbose:
          print('velfile=',velfile)
        VEL = loadmat(velfile)

        uxt_vel = VEL['uxt'][0]
        Pvel = VEL['P'][0]
        Tvel = VEL['T'][0]
        Svel = VEL['S'][0]
        dpdt_vel = VEL['W'][0]
        pc_efp = VEL['pc_efp'][0]
        u1 = VEL['u1'][0]
        u2 = VEL['u2'][0]
        v1 = VEL['v1'][0]
        v2 = VEL['v2'][0]
        verr1 = VEL['verr1'][0]
        verr2 = VEL['verr2'][0]

      jeoa = np.nonzero(np.array(eoa_hpids) == hpid)[0]
      if len(jeoa) == 0:
        got_eoa = False
      else:
        got_eoa = True
        eoafile = '{0:s}/ema-{1:s}-{2:04d}-eoa.mat'.format(decdir,runid,hpid)
        if options.verbose:
          print('eoafile=',eoafile)
        EOA = loadmat(eoafile)
        Psfc = EOA['P'][0]
        uxt_eoa = EOA['UXT'][0]
        tsfc = uxt_eoa - uxt_eoa[0]

      if hpid % 2 == 1:
        hpid_gps = hpid + 1  # GPS data after sat comms (gpa) is in following ascent file
      else:            
        hpid_gps = hpid      # ascent

      jgps = np.nonzero(np.array(gps_hpids) == hpid_gps)[0]
      if len(jgps) == 0:
        got_gps = False
      else:
        got_gps = True
        gpsfile = '{0:s}/ema-{1:s}-{2:04d}-gps.mat'.format(decdir,runid,hpid_gps)
        if options.verbose:
          print('gpsfile=',gpsfile)
        GPS = loadmat(gpsfile)
        uxt_gps = GPS['UXT_GPS'][0]
        lat = GPS['LAT'][0]
        lon = GPS['LON'][0]
        alt = GPS['ALT'][0]
        nsat = GPS['NSAT'][0]

        if len(uxt_gps):
          uxt_gps_all = np.append(uxt_gps_all, uxt_gps)
          lat_all = np.append(lat_all, lat)
          lon_all = np.append(lon_all, lon)
          alt_all = np.append(alt_all, alt)

      jvit = np.nonzero(np.array(vit_hpids) == hpid)[0]
      if len(jvit) == 0:
        got_vit = False
      else:
        got_vit = True
        vitfile = '{0:s}/ema-{1:s}-{2:04d}-vit.mat'.format(decdir,runid,hpid)
        if options.verbose:
          print('vitfile=',vitfile)
        VIT = loadmat(vitfile)
        uxt_vit = VIT['DateVit'][0]
        bat_vit = VIT['AirPumpVolts'][0] * 16.0 * 3.3 * 5.99 / 4095.0
        if options.verbose:
          print('uxt_vit=',uxt_vit,'bat_vit=',bat_vit)

# finished reading files

      uxt_ref = None
      if got_ctd:
        uxt_ref = uxt_ctd[0]
      if got_efp and uxt_efp[0] < uxt_ref:
        uxt_ref = uxt_efp[0]
      if got_vel and uxt_vel[0] < uxt_ref:
        uxt_ref = uxt_vel[0]

      if uxt_ref == None:
        print('uxt_ref is None')
        exit(1)

      uxt_fin = None
      if got_ctd:
        uxt_fin = uxt_ctd[-1]
      if got_efp and uxt_efp[-1] > uxt_fin:
        uxt_fin = uxt_efp[-1]
      if got_vel and uxt_vel[-1] > uxt_fin:
        uxt_fin = uxt_vel[-1]

      x = np.array(uxt_ctd)
      x = np.append(x,uxt_efp)
      x = np.append(x,uxt_vel)
      j = np.nonzero(np.isfinite(x))
      x = x[j]
      x = np.sort(x)
      uxt_ref = np.min(x)
      uxt_fin = np.max(x)

      if got_gps:
        if hpid % 2 == 1:      # descent
          j = np.nonzero(uxt_gps < uxt_ref)
          uxt_gps_ref = uxt_ref
        else:                  # ascent
          j = np.nonzero(uxt_gps > uxt_fin)
          uxt_gps_ref = uxt_fin
        uxt_gps = uxt_gps[j]
        lat = lat[j]
        lon = lon[j]
        alt = alt[j]
        nsat = nsat[j]
        tgps = uxt_gps - uxt_gps_ref

      if got_gps:
        j = np.nonzero(np.isfinite(lat) & (nsat >= 4) & (np.abs(alt) < 50))[0]
        if len(j):
          uxtavg = np.mean(uxt_gps[j])
          latavg = np.mean(lat[j])
          lonavg = np.mean(lon[j])
          altavg = np.mean(alt[j])
          posstr = 'lat={0:.4f} lon={1:.4f}'.format(latavg,lonavg)
        else:
          latavg = np.nan
          lonavg = np.nan
          posstr = ''
          got_gps = False
      else:
        posstr = ''

      if got_gps:
        uxt_gps_all = np.append(uxt_gps_all, uxt_gps)
        lat_all = np.append(lat_all, latavg)
        lon_all = np.append(lon_all, lonavg)
        alt_all = np.append(alt_all, altavg)

      if got_efp:
        uxt_ema_all  = np.append(uxt_ema_all,np.mean(uxt_efp))
        bat_ema_all  = np.append(bat_ema_all,np.mean(bt_mean))

      if got_vit:
        uxt_vit_all  = np.append(uxt_vit_all,uxt_vit)
        bat_vit_all  = np.append(bat_vit_all,bat_vit)

      # collect pressure versus time for overall plot
      if got_ctd:
        j = np.nonzero(np.isfinite(Pctd))[0]
        jtop = np.argmin(Pctd[j])
        jbot = np.argmax(Pctd[j])
        uxt_top = uxt_ctd[j[jtop]]
        uxt_bot = uxt_ctd[j[jbot]]
        P_top = Pctd[j[jtop]]
        P_bot = Pctd[j[jbot]]
        if False:
          if uxt_top < uxt_bot:
            uxt_pr_all = np.append(uxt_pr_all,uxt_top)
            uxt_pr_all = np.append(uxt_pr_all,uxt_bot)
            pr_all = np.append(pr_all,P_top)
            pr_all = np.append(pr_all,P_bot)
          else:
            uxt_pr_all = np.append(uxt_pr_all,uxt_bot)
            uxt_pr_all = np.append(uxt_pr_all,uxt_top)
            pr_all = np.append(pr_all,P_bot)
            pr_all = np.append(pr_all,P_top)
          uxt_pr_all = np.append(uxt_pr_all,np.nan)
          pr_all = np.append(pr_all,np.nan)
        else:
          uxt_pr_all = np.append(uxt_pr_all,uxt_ctd)
          pr_all     = np.append(pr_all,    Pctd)

        uxt_prtop_all = np.append(uxt_prtop_all,uxt_top)
        uxt_prbot_all = np.append(uxt_prbot_all,uxt_bot)
        prtop_all = np.append(prtop_all,P_top)
        prbot_all = np.append(prbot_all,P_bot)

      if got_hol:
        uxt_hol_all = np.append(uxt_hol_all,uxt_hol)
        uxt_hol_all = np.append(uxt_hol_all,np.nan)
        pr_hol_all = np.append(pr_hol_all,Phol)
        pr_hol_all = np.append(pr_hol_all,np.nan)

      timpos = '\n' + uxt2str(uxt_ref) + ' to ' + uxt2str(uxt_fin)
      if len(posstr):
        timpos = timpos + '\n' + posstr
      if options.verbose:
        print('timpos=',timpos)

      tctd = None
      thol = None
      tefp = None
      tvel = None
      
      if got_ctd:
        tctd = uxt_ctd - uxt_ref
      if got_hol:
        thol = uxt_hol - uxt_ref
      if got_efp:
        tefp = uxt_efp - uxt_ref
      if got_vel:
        tvel = uxt_vel - uxt_ref

      if got_ctd:
        dpdt_ctd = np.diff(Pctd) / np.diff(tctd)
        tctdmid = (tctd[1:] + tctd[0:-1]) * 0.5

      if got_hol:
        dpdt_hol =  np.diff(Phol) / np.diff(thol)
        tholmid = (thol[1:] + thol[0:-1]) * 0.5

      if do_plt_ctd and got_ctd:
        pltnam = 'ema-{0}-{1:04d}-ctd'.format(runid,hpid)
        fig = plt.figure(num=1,figsize=(6,8))
        fig.clf()
        fig.suptitle(pltnam + '  v:b s:p h:v c:r' + timpos)

        ax = fig.add_subplot(3,1,1)
        ax.hold(True)
        if got_vel:
          ax.plot(Pvel,Tvel,'b.') # ,marker='o',markeredgecolor='b')
        if got_scp:
          ax.plot(Pscp,Tscp,color='purple',marker='o',markeredgecolor='purple')
        if got_hol:
          ax.plot(Phol,Thol,color='violet',marker='.')
        ax.plot(Pctd,Tctd,'r.')
        ax.hold(False)
        ax.grid(True)
        ax.set_ylabel('T, degC')
        ax.xaxis.set_ticklabels([])

        ax = fig.add_subplot(3,1,2)
        ax.hold(True)
        if got_vel:
          ax.plot(Pvel,Svel,'b.') # ,marker='o',markeredgecolor='b')
        if got_scp:
          ax.plot(Pscp,Sscp,color='purple',marker='o',markeredgecolor='purple')
        if got_hol:
          ax.plot(Phol,Shol,color='violet',marker='.')
        ax.plot(Pctd,Sctd,'r.')
        ax.hold(False)
        ax.grid(True)
        ax.set_ylabel('S, psu')
        ax.xaxis.set_ticklabels([])

        ax = fig.add_subplot(3,1,3)
        ax.hold(True)
        if got_vel:
          ax.plot(Pvel,pc_efp,'b.')
        if got_hol:
          ax.plot(Phol,pc_hol,color='violet',marker='.')
        ax.plot(Pctd,pc_ctd,'r.')
        ax.hold(False)
        fix_ylim(ax)
        ax.grid(True)
        ax.set_ylabel('piston')
        ax.set_xlabel('P, dbar')

        writepdf(pltdir, pltnam)

      if do_plt_pvt and (got_ctd or got_vel):
        pltnam = 'ema-{0}-{1:04d}-pvt'.format(runid,hpid)
        fig = plt.figure(num=1,figsize=(6,8))
        fig.clf()
        fig.suptitle(pltnam + '  v:b h:v c:r' + timpos)

        ax = fig.add_subplot(3,1,1); ax1 = ax
        ax.hold(True)
        if got_vel:
          ax.plot(tvel,Pvel,'b.') # ,marker='o',markeredgecolor='b')
        if got_hol:
          ax.plot(thol,Phol,color='violet',marker='.')
        if got_ctd:
          ax.plot(tctd,Pctd,'r.')
        ax.hold(False)
        ax.invert_yaxis()
        ax.grid(True)
        ax.xaxis.set_ticklabels([])
        ax.set_ylabel('P')

        ax = fig.add_subplot(3,1,2,sharex=ax1)
        ax.hold(True)
        if got_vel:
          ax.plot(tvel,dpdt_vel,'b.') # ,marker='o',markeredgecolor='b')
        if got_ctd:
          ax.plot(tctdmid,dpdt_ctd,'r.') # ,marker='.')
        if got_hol:
          ax.plot(tholmid,dpdt_hol,color='violet',marker='.')
        ax.hold(False)
        ax.invert_yaxis()
        ax.grid(True)
        ax.xaxis.set_ticklabels([])
        ax.set_ylabel('dP/dt')

        ax = fig.add_subplot(3,1,3)
        ax.hold(True)
        if got_vel:
          ax.plot(tvel,pc_efp,'b.') # ,marker='o',markeredgecolor='b')
        if got_ctd:
          ax.plot(tctd,pc_ctd,'r.')
        if got_hol:
          ax.plot(thol,pc_hol,color='violet',marker='.')
        ax.hold(False)
        fix_ylim(ax)
        ax.grid(True)
        ax.set_xlabel('time, s')
        ax.set_ylabel('piston')

        writepdf(pltdir, pltnam)

      if do_plt_vel and got_vel:
        pltnam = 'ema-{0}-{1:04d}-vel'.format(runid,hpid)
        fig = plt.figure(num=1,figsize=(6,8))
        fig.clf()
        fig.suptitle(pltnam + '  1:b 2:r' + timpos)

        ax = fig.add_subplot(3,1,1)
        ax.hold(True)
        ax.plot(Pvel,u1,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(Pvel,u2,'r')
        ax.hold(False)
        ax.grid(True)
        ax.xaxis.set_ticklabels([])
        ax.set_ylabel('u, m/s')

        ax = fig.add_subplot(3,1,2)
        ax.hold(True)
        ax.plot(Pvel,v1,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(Pvel,v2,'r')
        ax.hold(False)
        ax.grid(True)
        ax.xaxis.set_ticklabels([])
        ax.set_ylabel('v, m/s')

        ax = fig.add_subplot(3,1,3)
        ax.hold(True)
        ax.plot(Pvel,verr1,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(Pvel,verr2,'r')
        ax.hold(False)
        fix_ylim(ax)
        ax.grid(True)
        ax.set_ylabel('verr, m/s')
        ax.set_xlabel('P, dbar')

        writepdf(pltdir, pltnam)

      if do_plt_Psfc and (got_eoa or got_gps):
        pltnam = 'ema-{0}-{1:04d}-surface'.format(runid,hpid)
        fig = plt.figure(num=1,figsize=(6,8))
        fig.clf()
        fig.suptitle(pltnam + timpos)

        if got_eoa:
          ax = fig.add_subplot(4,1,1)
          ax.plot(tsfc,Psfc,'b.-') # ,marker='o',markeredgecolor='b')
          fix_ylim(ax)
          ax.grid(True)
          ax.set_ylabel('Psfc, dbar')
          ax.set_xlabel('time, seconds')

        if got_gps:
          dLat = (lat - latavg) * 1852 * 60
          dLon = (lon - lonavg) * 1852 * 60 * np.cos(latavg * np.pi / 180.0)

          ax = fig.add_subplot(4,1,2)
          ax.plot(tgps,dLat,'b.-',markeredgecolor='b')
          ax.grid(True)
          ax.xaxis.set_ticklabels([])
          ax.set_ylabel('dLat, m')

          ax = fig.add_subplot(4,1,3)
          ax.plot(tgps,dLon,'b.-',markeredgecolor='b')
          ax.grid(True)
          ax.xaxis.set_ticklabels([])
          ax.set_ylabel('dLon, m')

          ax = fig.add_subplot(4,1,4)
          ax.plot(tgps,alt,'b.-',markeredgecolor='b')
          fix_ylim(ax)
          ax.grid(True)
          ax.set_xlabel('time, seconds')
          ax.set_ylabel('Alt, m')

        writepdf(pltdir, pltnam)

      if do_plt_axyz and got_efp:
        pltnam = 'ema-{0}-{1:04d}-axyz'.format(runid,hpid)
        fig = plt.figure(num=1,figsize=(6,8))
        fig.clf()
        fig.suptitle(pltnam + '  x:b y:r z:g' + timpos)

        ax = fig.add_subplot(2,1,1)
        ax.hold(True)
        ax.plot(tefp,ax_mean,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(tefp,ay_mean,'r') # ,marker='o',markeredgecolor='r')
        ax.plot(tefp,az_mean,'g') # ,marker='o',markeredgecolor='g')
        ax.hold(False)
        fix_ylim(ax)
        ax.grid(True)
        ax.xaxis.set_ticklabels([])
        ax.set_ylabel('mean')

        ax = fig.add_subplot(2,1,2)
        ax.hold(True)
        ax.plot(tefp,ax_sdev,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(tefp,ay_sdev,'r') # ,marker='o',markeredgecolor='r')
        ax.hold(False)
        ax.grid(True)
        fix_ylim(ax)
        ax.set_ylabel('rms')
        ax.set_xlabel('time, seconds')

        writepdf(pltdir, pltnam)

      if do_plt_hxy and got_efp:
        pltnam = 'ema-{0}-{1:04d}-hxy'.format(runid,hpid)
        fig = plt.figure(num=1,figsize=(6,8))
        fig.clf()
        fig.suptitle(pltnam + '  x:b y:r' + timpos)

        ax = fig.add_subplot(3,1,1)
        ax.hold(True)
        ax.plot(tefp,hx_mean,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(tefp,hy_mean,'r') # ,marker='o',markeredgecolor='r')
        ax.hold(False)
        fix_ylim(ax)
        ax.grid(True)
        ax.set_ylabel('mean')
        ax.xaxis.set_ticklabels([])

        ax = fig.add_subplot(3,1,2)
        ax.hold(True)
        ax.plot(tefp,hx_sdev,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(tefp,hy_sdev,'r') # ,marker='o',markeredgecolor='r')
        ax.hold(False)
        ax.grid(True)
        fix_ylim(ax)
        ax.set_ylabel('rms')
        ax.xaxis.set_ticklabels([])

        ax = fig.add_subplot(3,1,3)
        ax.hold(True)
        ax.plot(tefp,rotp_hx,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(tefp,rotp_hy,'r') # ,marker='o',markeredgecolor='r')
        ax.hold(False)
        ax.set_ylim([0,30])
        fix_ylim(ax)
        ax.grid(True)
        ax.set_ylabel('rotp, s')
        ax.set_xlabel('time, seconds')

        writepdf(pltdir, pltnam)

      if do_plt_e12 and got_efp:
        pltnam = 'ema-{0}-{1:04d}-e12'.format(runid,hpid)
        fig = plt.figure(num=1,figsize=(6,8))
        fig.clf()
        fig.suptitle(pltnam + '  1:b 2:r' + timpos)

        uvpc = 1.0e6 * 10.0e-3 / 2**24
        off = 2**23

        ax = fig.add_subplot(2,1,1)
        ax.hold(True)
        ax.plot(tefp,(e1_mean - off) * uvpc,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(tefp,(e2_mean - off) * uvpc,'r') # ,marker='o',markeredgecolor='r')
        ax.hold(False)
        ax.grid(True)
        ax.xaxis.set_ticklabels([])
        ax.set_ylabel('mean, uV')

        ax = fig.add_subplot(2,1,2)
        ax.hold(True)
        ax.plot(tefp,e1_sdev * uvpc,'b') # ,marker='o',markeredgecolor='b')
        ax.plot(tefp,e2_sdev * uvpc,'r') # ,marker='o',markeredgecolor='r')
        ax.hold(False)
        ax.grid(True)
        fix_ylim(ax)
        ax.set_ylabel('sdev, uV')
        ax.set_xlabel('time, seconds')

        writepdf(pltdir, pltnam)

    # end of for hpid_index

    if do_plt_batv:
      pltnam = 'ema-{0}-batv'.format(runid)
      fig = plt.figure(num=1,figsize=(6,8))
      fig.clf()
      fig.suptitle(pltnam)

      uxr = uxt_ema_all[0]

      ax = fig.add_subplot(2,1,1); ax1 = ax
      ax.plot((uxt_vit_all-uxr)/86400,bat_vit_all,'b.-')
      fix_ylim(ax)
      ax.grid(True)
      ax.set_ylabel('APF9 bat, V')

      ax = fig.add_subplot(2,1,2,sharex=ax1)
      ax.plot((uxt_ema_all-uxr)/86400,bat_ema_all,'b.-')
      fix_ylim(ax)
      ax.grid(True)
      ax.set_ylabel('EMA bat, V')
      ax.set_xlabel('Days')

      writepdf(pltdir, pltnam)

    if do_plt_pvtoa and got_ctd:
      pltnam = 'ema-{0}-pvtoa'.format(runid)
      fig = plt.figure(num=2,figsize=(10,7))
      fig.clf()
      fig.suptitle(pltnam)

      ref = uxt_pr_all[0]
      t_all    = (uxt_pr_all    - ref) / 86400
      ttop_all = (uxt_prtop_all - ref) / 86400
      tbot_all = (uxt_prbot_all - ref) / 86400
      t_hol_all = (uxt_hol_all - ref) / 86400

      ax = fig.add_subplot(1,1,1)
      ax.hold(True)
      ax.plot(t_all,pr_all,color='purple',marker='.',linewidth=0,markersize=1)
      if len(t_hol_all):
        ax.plot(t_hol_all,pr_hol_all,color='violet',marker='.',linewidth=0,markersize=1)
      ax.plot(ttop_all,prtop_all,'b.')
      ax.plot(tbot_all,prbot_all,'r.')
      ax.hold(False)
      ax.invert_yaxis()
      fix_ylim(ax)
      ax.grid(True)
      ax.set_ylabel('Pressure, dbar')
      ax.set_xlabel('Days')

      writepdf(pltdir, pltnam)

  # end of for runid

if __name__ == '__main__':
  main()

