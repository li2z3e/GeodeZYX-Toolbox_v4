#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 16 11:54:28 2019

@author: psakicki
"""

########## BEGIN IMPORT ##########
#### External modules
import datetime as dt
import os 
import subprocess

#### geodeZYX modules
from geodezyx import files_rw
from geodezyx import operational
from geodezyx import utils


##########  END IMPORT  ##########

def rtklib_run_from_rinex(rnx_rover,rnx_base,generik_conf,working_dir,
                          experience_prefix="",rover_auto_conf=False,
                          base_auto_conf=True,XYZbase=[0,0,0],outtype = 'auto',
                          calc_center='igs'):

    """
    auto_conf :
        read the header of the rinex and write the conf. file according to it
        if the mode is disabled, the antenna/rec part of the
        conf. file will be the same as the generic one

        NB : RTKLIB "core" have it's own reading header option.
        Thus, my advice is to disable the auto mode for the rover and leave
        ``ant1-postype=rinexhead`` in the generic conf file
        and enable it for the base with a XYZbase vector initialized or
        the good XYZ in header on the rinex (the XYZbase vector is prioritary
        over the base RINEX header)

        (but in anycase, prepars good rinex's headers ;) )

    outtype :
        'auto' (as defined in the generic config file) or
        'dms' 'deg' 'xyz' 'enu'
        can manage the upper case XYZ or FLH
    """

    # paths & files
    working_dir = utils.create_dir(working_dir)
    temp_dir    = utils.create_dir(os.path.join(working_dir,'TEMP_' + utils.get_timestamp()))
    out_dir     = utils.create_dir(os.path.join(working_dir,'OUTPUT'))

    # uncompressing rinex if compressed
    if operational.check_if_compressed_rinex(rnx_rover):
        rnx_rover = operational.crz2rnx(rnx_rover,temp_dir)
    if operational.check_if_compressed_rinex(rnx_base):
        rnx_base  = operational.crz2rnx(rnx_base,temp_dir)

    # RINEX START & END
    rov_srt, rov_end , rov_itv = operational.rinex_start_end(rnx_rover,1)
    bas_srt, bas_end , bas_itv = operational.rinex_start_end(rnx_base,1)

    # RINEX NAMES
    rov_name = os.path.basename(rnx_rover)[0:4]
    bas_name = os.path.basename(rnx_base)[0:4]

    # paths & files
    #temp_dir = os.path.join(working_dir,'TEMP')
    #if clean_temp_dir:
    #    shutil.rmtree(temp_dir)
    #    temp_dir = os.path.join(working_dir,'TEMP')
    #out_dir  = os.path.join(working_dir,'OUTPUT')

    srt_str = rov_srt.strftime("%Y_%j")
    exp_full_name = '_'.join((experience_prefix,rov_name,bas_name,srt_str))

    out_conf_fil   = os.path.join(out_dir,exp_full_name + '.conf')
    out_result_fil = os.path.join(out_dir,exp_full_name + '.out' )

    dicoconf = operational.read_conf_file(generik_conf)

    if rover_auto_conf:
        Antobj_rov , Recobj_rov , Siteobj_rov , Locobj_rov = \
        files_rw.read_rinex_2_dataobjts(rnx_rover)
        dicoconf['ant1-postype'] ='xyz'
        dicoconf['ant1-anttype'] = Antobj_rov.Antenna_Type
        dicoconf['ant1-pos1'] = Locobj_rov.X_coordinate_m
        dicoconf['ant1-pos2'] = Locobj_rov.Y_coordinate_m
        dicoconf['ant1-pos3'] = Locobj_rov.Z_coordinate_m
        dicoconf['ant1-antdelu'] = Antobj_rov.Up_Ecc
        dicoconf['ant1-antdeln'] = Antobj_rov.North_Ecc
        dicoconf['ant1-antdele'] = Antobj_rov.East_Ecc

    if not outtype.lower() == 'auto':
        dicoconf['out-solformat'] = outtype.lower()
        print('out-solformat' , dicoconf['out-solformat'])


    if base_auto_conf:
        Antobj_bas , Recobj_bas , Siteobj_bas , Locobj_bas = \
        files_rw.read_rinex_2_dataobjts(rnx_base)
        dicoconf['ant2-postype'] ='xyz'
        dicoconf['ant2-anttype'] = Antobj_bas.Antenna_Type
        if XYZbase[0] != 0:
            dicoconf['ant2-pos1'] = XYZbase[0]
            dicoconf['ant2-pos2'] = XYZbase[1]
            dicoconf['ant2-pos3'] = XYZbase[2]
        else:
            dicoconf['ant2-pos1'] = Locobj_bas.X_coordinate_m
            dicoconf['ant2-pos2'] = Locobj_bas.Y_coordinate_m
            dicoconf['ant2-pos3'] = Locobj_bas.Z_coordinate_m
        dicoconf['ant2-antdelu'] = Antobj_bas.Up_Ecc
        dicoconf['ant2-antdeln'] = Antobj_bas.North_Ecc
        dicoconf['ant2-antdele'] = Antobj_bas.East_Ecc


    if not (bas_srt <= rov_srt <= rov_end <= bas_end):
        print('WARN : not bas_srt <= rov_srt <= rov_end <= bas_end !!!')

    outconffilobj = open(out_conf_fil,'w+')
    for k,v in dicoconf.items():
        lin = k.ljust(20)+'='+str(v)+'\n'
        outconffilobj.write(lin)
    outconffilobj.close()

    # ORBITS
    # SP3
    orblis = operational.multi_downloader_orbs_clks( temp_dir , bas_srt , bas_end , archtype='/',
                                        calc_center = calc_center)
    sp3Z = orblis[0]
    sp3 = utils.uncompress(sp3Z)

    # BRDC
    statdic = dict()
    statdic['nav'] = ['BRDC']
    nav_srt = dt.datetime(bas_srt.year, bas_srt.month , bas_srt.day )
    orblis = operational.multi_downloader_rinex(statdic,temp_dir , nav_srt , bas_end ,
                                    archtype='/', sorted_mode=0)
    navZ = orblis[0]
    nav = utils.uncompress(navZ)

    # Command
    com_config  = "-k " + out_conf_fil
    com_interval="-ti " + str(rov_itv)
    com_mode = ""
    #com_mode="-p 4"
    com_resultfile="-o " + out_result_fil
    #com_combinsol="-c"

    exe_path = "rnx2rtkp"
#    exe_path = "/home/pierre/install_softs/RTKLIB/rnx2rtkp"

    bigcomand = ' '.join((exe_path,com_config,com_interval,com_mode,
                          com_resultfile,rnx_rover,rnx_base,nav,sp3))

    print(bigcomand)

    subprocess.call([bigcomand], executable='/bin/bash', shell=True)
    print("RTKLIB RUN FINISHED")

    return None
