#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug  1 15:18:29 2019

@author: psakicki
"""

########## BEGIN IMPORT ##########
#### External modules
import datetime as dt
import dateutil
import glob
import numpy as np
import os 
import pandas as pd
import scipy
import re

#### geodeZYX modules
from geodezyx import conv
from geodezyx import files_rw
from geodezyx import reffram
from geodezyx import time_series
from geodezyx import utils

#### Import star style
from geodezyx import *                   # Import the GeodeZYX modules
from geodezyx.externlib import *         # Import the external modules
from geodezyx.megalib.megalib import *   # Import the legacy modules names

##########  END IMPORT  ##########


def read_all_points(filein):
    """selectionne automatiquement le type de fichier brut en entrée
       INPUT  : chemin du fichier brut de POINTS
       OUTPUT : Une TimeSeriePoint """

    firstline = open(filein).readline()

    if re.compile('RTKLIB').search(firstline):
        tsout = read_rtklib(filein)

    elif re.compile('Kinematic Processing').search(firstline):
        tsout = read_gipsy_apps(filein)

    elif re.compile('tdp.llh').search(filein):
        tsout = read_gipsy_bosser(filein)

    elif re.compile('STA').search(firstline) or re.compile('tdp').search(filein) or re.compile('TRPAZ').search(firstline):
        tsout = read_tdp(filein)

    elif re.compile('YY  MM DD HR MIN').search(firstline):
        tsout = read_track(filein)

    elif re.compile('Latitude').search(firstline):
        tsout = read_sonardyne_posi(filein)

    elif re.compile('Heading').search(firstline):
        tsout = read_sonardyne_attitude(filein)

    elif re.compile('\*\*\* warning').search(firstline):
        tsout = read_gins(filein,'kine')

    elif re.compile('#GINS_VERSION').search(firstline):
        tsout = read_gins_solution(filein)

    elif re.compile('OCTANS_ATTITUDE').search(firstline):
        tsout = read_qinsy(filein,2014,0o4,0o4)

    elif re.compile('PBO Station Position Time Series').search(firstline):
        tsout= read_pbo_pos(filein)

    elif re.compile('latitude_degre_decimal').search(firstline):
        tsout= read_nrcan_csv(filein)

    elif re.compile('--------------------------------------------------').search(firstline): # NDLR : Best parser ever
        tsout= read_nrcan_pos(filein)

    else:
        print("ERR : read_all : pas de motif valide pour lect. auto")
        print(filein)
        print(firstline)

    return tsout

def read_all_obs(filein):

    """selectionne automatiquement le type de fichier brut en entrée
       INPUT  : chemin du fichier brut de observations génériques
       OUTPUT : Une LISTE de TimeSerieObs """

    firstline = open(filein).readline()

    if re.compile('Heading').search(firstline):
        tsout = read_sonardyne_attitude(filein)

    else:
        print("ERR : read_all : pas de motif valide pour lect. auto")

    return tsout

def read_rtklib(filein):

    """lit un fichier de type RTKLIB
       INPUT  : chemin du fichier brut
       OUTPUT : Une TimeSeriePoint """

    tsout = time_series.TimeSeriePoint()

    for line in open(filein):

        if re.compile('e-baseline').search(line):
            initype='ENU'
        elif re.compile('x-ecef').search(line):
            initype='XYZ'
        elif 'latitude(deg)' in line:
            initype='FLH'

        if re.compile('%  UTC').search(line):
            dUTCGPS = 16
            print('WARN : MAYBE A WRONG LEAP SECOND !!!!')
        elif re.compile('%  GPST').search(line):
            dUTCGPS = 0

        if line[0] == '%':
            continue

        fields = line.split()
        date1 = re.findall(r"[\w']+",fields[0] + ':' + fields[1])
        date2 = tuple([int(d) for d in date1])

        T = (dt.datetime(date2[0],date2[1],date2[2],date2[3],date2[4],date2[5],date2[6]*1000) + dt.timedelta(seconds=dUTCGPS))
        A = (float(fields[2]))
        B = (float(fields[3]))
        C = (float(fields[4]))
        if initype == 'XYZ':
            sA = (float(fields[7]))
            sB = (float(fields[8]))
            sC = (float(fields[9]))
        elif initype == 'FLH':
            sA = (float(fields[7]))
            sB = (float(fields[8]))
            sC = (float(fields[9]))
            sA,sB,sC = conv.sENU2sFLH(A,B,C,sA,sB,sC)


        point = time_series.Point(A,B,C,T,initype,sA,sB,sC)
        point.anex['sdAB'] = float(fields[10])
        point.anex['sdBC'] = float(fields[11])
        point.anex['sdAC'] = float(fields[12])

        tsout.add_point(point)

    tsout.meta_set(filein)

    if initype == 'ENU':
        tsout.boolENU = True


    try:
        inpfilis = utils.grep(filein,'inp file')
        tsout.anex['rover'] = os.path.basename(inpfilis[0].split()[-1])[0:4].upper()
        tsout.anex['base']  = os.path.basename(inpfilis[1].split()[-1])[0:4].upper()
    except:
        pass

    return tsout

def read_tdp(filein):

    print('TDPclassic')

    X,Y,Z = 0,0,0
    Tx , Ty , Tz, T = 111,222,333,0
    sX,sY,sZ = 0,0,0

    tsout = time_series.TimeSeriePoint()

    for line in open(filein):

        fields = line.split()

        if fields[4] == 'STA' and fields[5] == 'Z':
            Tz = conv.tgipsy2dt(fields[0])
            Z = (float(fields[2])* 1000)
            sZ = (float(fields[3])* 1000)

        if fields[4] == 'STA' and fields[5] == 'Y':
            Ty = conv.tgipsy2dt(fields[0])
            Y = (float(fields[2])* 1000)
            sY = (float(fields[3])* 1000)

        if fields[4] == 'STA' and fields[5] == 'X':
            Tx = conv.tgipsy2dt(fields[0])
            X = (float(fields[2])* 1000)
            sX = (float(fields[3])* 1000)
            STAT = fields[6]

        if  Tx == Ty == Tz :
            T = Tx
            point = time_series.Point(X,Y,Z,T,'XYZ',sX,sY,sZ)
            tsout.add_point(point)

            Tx = 111
            Ty = 222
            Tz = 333

    tsout.meta_set(filein,stat=STAT)

    return tsout


def read_gipsy_tdp(filein):
    """
    wrapper de read_tdp pour un nom plus explicite (et qui evitera de recoder la fct ...)
    """
    return read_tdp(filein)


def read_gipsy_tdp_list(filelistin):
    tslist = []
    for fil in filelistin:
        ts = read_gipsy_tdp(fil)
        tslist.append(ts)

    tsout = time_series.merge_ts(tslist)

    return tsout

def read_gipsy_bosser(filein):
    print('TDPBOSSER')
    F,L,H = 0,0,0
    T = 0
    sF,sL,sH = 0,0,0

    tsout = time_series.TimeSeriePoint()

    for line in open(filein):

        f = line.split()

        y = int(f[0])
        doydec = float(f[1])
        doy = int(doydec)

        T = conv.doy2dt(y,doy) + dt.timedelta(days=(doydec - doy))

        F = np.rad2deg(float(f[2]))
        L = np.rad2deg(float(f[3]))
        H = float(f[4])
        RMS = float(f[8])

        point = time_series.Point(F,L,H,T,'FLH')
        point.anex['RMS'] = RMS
        tsout.add_point(point)


    tsout.meta_set(filein,stat='STAT')

    return tsout

def read_gipsy_apps(filein):
    """ WARN : not optimized for > 1Hz !!! """
    print("GIPSY APPS")

    tsout = time_series.TimeSeriePoint()

    for l in open(filein):
        if l[0] == '#' or ('Kinematic Processing' in l):
            continue
        f = l.split()

        date_lis = [int(float(e)) for e in f[1].split(':')]

        T = dt.datetime(*date_lis)

        X  = float(f[2])
        sX = float(f[3])
        Y  = float(f[4])
        sY = float(f[5])
        Z  = float(f[6])
        sZ = float(f[7])

        point = time_series.Point(X,Y,Z,T,'XYZ',sX,sY,sZ)
        tsout.add_point(point)

    tsout.meta_set(filein)
    return tsout




def read_track(filein):

    tsout = time_series.TimeSeriePoint()

    for line in open(filein):

        if re.compile('dNorth').search(line):
            initype='ENU'
        elif re.compile('dX').search(line):
            initype='XYZ'

        if line[0] != ' ':
            continue

        fields = line.split()

        T = (dt.datetime(int(fields[0]),
                         int(fields[1]),
                         int(fields[2]),
                         int(fields[3]),
                         int(fields[4]),
                         int(fields[5].split('.')[0]),
                         int(np.round(float(fields[5].split('.')[1]),4))))
        A = (float(fields[6]))
        B = (float(fields[8]))
        C = (float(fields[10]))

        sA = (float(fields[7]))
        sB = (float(fields[9]))
        sC = (float(fields[11]))

        # On inverse A et B car NEU => ENU
        if initype == 'ENU':
            point = time_series.Point(B,A,C,T,initype,sB,sA,sC)
        elif initype == 'XYZ':
            point = time_series.Point(A,B,C,T,initype,sA,sB,sC)
        else:
            "ERR : track_read : mauvais initype"

        tsout.add_point(point)

    if initype == 'ENU':
        tsout.boolENU = True

    tsout.meta_set(filein)

    tsout.anex['rover'] = tsout.name.split('.')[-2].upper()

    # recherche de la base
    try:
        if '.LC' in filein:
            stat_n_base_lc_files = glob.glob(filein[:-8] + '*')
            stat_n_base_lc_files.remove(filein)
            statbase = os.path.basename(stat_n_base_lc_files[0])[-7:-3]
            tsout.anex['base'] = statbase
        elif '.L1+L2' in filein:
            stat_n_base_l1l2_files = glob.glob(filein[:-11] + '*')
            stat_n_base_l1l2_files.remove(filein)
            statbase = os.path.basename(stat_n_base_l1l2_files[0])[-10:-6]
            tsout.anex['base'] = statbase
    except:
        print('WARN : unable to find the base for the TRACK experience')
        print(filein)
        pass

    return tsout

def read_gins_solution(filein,mode="cinematic"):
    """
    mode = cinematic : retrun a TimeSerie
    mode = static : retrun a point
    """

    F = open(filein)

    Pts_list_tmp = []

    for l in F:
        f = l.split()

        if 'STATION_NAME' in l:
            if len(f) > 1:
                namestat = f[1]
            else:
                namestat = f[-1]


        if l[0] == '#':
            continue

        Traw = float(f[2])

        if 'XYZ_SOL' in l:
            coordstype = 'XYZ'
            X =  float(f[4])
            Y =  float(f[6])
            Z =  float(f[8])

            sX =  np.sqrt(float(f[9]))
            sY =  np.sqrt(float(f[10]))
            sZ =  np.sqrt(float(f[11]))

            if "T24:00:00.000" in f[1]: # Manage the special case if we are at the border bw 2 days
                Txyz = conv.string_date2dt(f[1][:10])  + dt.timedelta(days=+1) + dt.timedelta(seconds=-19)
            else:
                Txyz = conv.string_date2dt(f[1]) + dt.timedelta(seconds=-19)

            point = time_series.Point(X,Y,Z,Txyz,coordstype,sX,sY,sZ,name=namestat)

            point.anex['sdXY'] = float(f[10])
            point.anex['sdXZ'] = float(f[11])
            point.anex['sdYZ'] = float(f[12])

        elif 'FLH_SOL' in l:
            coordstype = 'FLH'
            F =  float(f[4])
            L =  float(f[6])
            H =  float(f[8])

            sF =  np.rad2deg(np.sqrt(float(f[9])))
            sL =  np.rad2deg(np.sqrt(float(f[10])))
            sH =  np.sqrt(float(f[11]))

            point.F , point.L , point.H = F,L,H
            point.sF , point.sL , point.sH = sF,sL,sH

            #point.X , point.Y , point.Z = X,Y,Z

            point.anex['sdFL'] = float(f[10])
            point.anex['sdFH'] = float(f[11])
            point.anex['sdLH'] = float(f[12])

            Pts_list_tmp.append(point)

    #### End of reading, export
    if not Pts_list_tmp:
        print("WARN : no point found in :")
        print(filein)
        print("returns None")
        return None

    if mode == "cinematic":
        tsout = time_series.TimeSeriePoint()
        for point in Pts_list_tmp:
            tsout.add_point(point)
        tsout.meta_set(filein,namestat)
        return tsout

    elif mode == "static":
        pt_out = Pts_list_tmp[0]
        return pt_out


def read_gins_solution_multi(filein_list,return_dict = True):

    filein_list  = sorted(filein_list)
    Points_list  = []
    statname_stk = []

    for fil in filein_list:
        point_daily   = read_gins_solution(fil,mode="static")
        if not point_daily:
            continue
        Points_list.append(point_daily)
        statname_stk.append(point_daily.name)

    statname_uniq = sorted(list(set(statname_stk)))

    ts_dict = dict()

    for point in Points_list:
        if not point.name in ts_dict.keys():
            ts_dict[point.name] = time_series.TimeSeriePoint(stat=point.name)
        ts_dict[point.name].add_point(point)

    if return_dict:
        return ts_dict
    else:
        ts_list = []
        for k , val in ts_dict.items():
            ts_list.append(val)
        return ts_list


def read_epos_sta_kinematics(filein):
    """
    read an EPOS kinematic solutions
    """

    F = open(filein)
    Lines_4_DF_stk = []
    for l in F:
        fields = l.split()
        if l[0] != "K" and l[0] != "U" and l[0] != "X":
            continue
        if l[0] == "K" or l[0] == "U" or l[0] == "X":
            namstat = fields[2]
            numstat = int(fields[1])
            MJD_epo = float(fields[3])
            numobs = int(fields[4])

            X = float(fields[6])
            Y = float(fields[7])
            Z = float(fields[8])
            sX = float(fields[10])
            sY = float(fields[11])
            sZ = float(fields[12])

            N = float(fields[14])
            E = float(fields[15])
            U = float(fields[16])
            sN = float(fields[18])
            sE = float(fields[19])
            sU = float(fields[20])

            tup_4_df = (namstat,numstat,MJD_epo,numobs,X,Y,Z,sX,sY,sZ,
                        N,E,U,sN,sE,sU)
            Lines_4_DF_stk.append(tup_4_df)

    columns = ("site","site_num",
                   "MJD_epo","numobs",
                   "x","y","z","sx","sy","sz",
                   "N","E","U","sN","sE","sU")

    DFout = pd.DataFrame(Lines_4_DF_stk,
                     columns=columns)
    return DFout

def read_epos_sta_coords_mono(filein,return_df=True):
    """
    read an EPOS's YYYY_DDD_XX_sta_coordinates coordinates files
    and return a list of Points objects

    ... TBC ...
    """
    F = open(filein)

    Points_list_stk = []
    Lines_4_DF_stk = []

    for l in F:
        fields = l.split()
        if l[0] != " ":
            continue
        if "SITE" in fields[0]:
            namestat = fields[8]
            numstat  = int(fields[2])
            tecto_plate = fields[4]
            MJD_ref  = int(fields[5])
            MJD_strt = int(fields[6])
            MJD_end  = int(fields[7])
            MJD_mid = np.mean([MJD_strt , MJD_end])
            T = conv.MJD2dt(MJD_mid)

        if "POS_VEL:XYZ" in fields[0]:
            X  = float(fields[4])
            Y  = float(fields[5])
            Z  = float(fields[6])
            Vx = float(fields[7])
            Vy = float(fields[8])
            Vz = float(fields[9])

        if "SIG_PV_XYZ" in fields[0]:
            sX  = float(fields[4].replace("D","E"))
            sY  = float(fields[5].replace("D","E"))
            sZ  = float(fields[6].replace("D","E"))
            sVx = float(fields[7])
            sVy = float(fields[8])
            sVz = float(fields[9])
        
            #### Last useful line for the point, store it
            if not return_df:
                point = time_series.Point(X,Y,Z,T,"XYZ",sX,sY,sZ,name=namestat)
                point.anex["Vx"] = sVx
                point.anex["Vy"] = sVy
                point.anex["Vz"] = sVz
                Points_list_stk.append(point)
            

            #### And store for the DataFrame
            else:
                tup_4_DF = (namestat,numstat,tecto_plate,
                            MJD_ref,MJD_strt,MJD_end,
                            X,Y,Z,sX,sY,sZ,
                            Vx,Vy,Vz,sVx,sVy,sVz)

                Lines_4_DF_stk.append(tup_4_DF)


    if return_df:
        
        columns = ("site","site_num","tecto_plate",
           "MJD_ref","MJD_start","MJD_end",
           "x","y","z","sx","sy","sz",
           "Vx","Vy","Vz","sVx","sVy","sVz")

        DFout = pd.DataFrame(Lines_4_DF_stk,
             columns=columns)

        return DFout
    else:
        return Points_list_stk

def read_epos_sta_coords_multi(filein_list,return_dict = True):

    filein_list  = sorted(filein_list)
    Points_list  = []
    statname_stk = []

    for fil in filein_list:
        Points_daily_list = read_epos_sta_coords_mono(fil,return_df=False)
        Points_list   = Points_list + Points_daily_list
        statname_stk  = statname_stk + [e.name for e in Points_daily_list]

    statname_uniq = sorted(list(set(statname_stk)))

    ts_dict = dict()

    for point in Points_list:
        if not point.name in ts_dict.keys():
            ts_dict[point.name] = time_series.TimeSeriePoint(stat=point.name)
        ts_dict[point.name].add_point(point)

    if return_dict:
        return ts_dict
    else:
        ts_list = []
        for k , val in ts_dict.items():
            ts_list.append(val)
        return ts_list


def read_epos_slv_times(p,convert_to_time=False):
    """
    convert_to_time : divide by the speed of light. Values in meter instead 
    """
    L = utils.extract_text_between_elements_2(p,"\+sum_times/estimates",
                                                "\-sum_times/estimates")

    Lgood = []
    
    for l in L[1:-1]:
        if "EPOCHE" in l:
            cur_epoc_line = l
            cur_epoc_f = cur_epoc_line.split()
            cur_epoc   = conv.MJD2dt(int(cur_epoc_f[1])) +  dt.timedelta(seconds=int(86400*float(cur_epoc_f[2])))

        if re.match("^   [0-9]{4}.*",l):
            Lgood.append([cur_epoc] + [float(e) for e in l.split()])


    DF = pd.DataFrame(Lgood,columns=["epoch","stat","offset","offset_sig"])

    DF["stat"] = DF["stat"].astype('int')
    
    if convert_to_time:
        DF[["offset","offset_sig"]] = DF[["offset","offset_sig"]] / 299792458.

    return DF



def write_epos_sta_coords(DF_in,file_out,sort_wrt="site",
                          no_time_limit_for_first_period = True,
                          no_time_limit_for_last_period = True):
    """
    sort_wrt="site" or "site_num"
    """

    DF_work = DF_in.sort_values([sort_wrt,"MJD_start"])


    Stat_lines_blk_stk = []

    generic_header = """+info
 FLATTENING                  298.2550
 MAJOR_AXIS              6378140.0000
 REFERENCE_FRAME                IGS14
 NUMBER_OF_STATIONS             {:5d}
 REF_MJD                        {:5d}
-info
"""

    generic_header = generic_header.format(len(DF_work),
                                           int(utils.most_common(DF_work["MJD_ref"])))

    Stat_lines_blk_stk.append(generic_header)

    Stat_lines_blk_stk.append("+station_coordinates")

    for site in DF_work[sort_wrt].unique():

        Stat_lines_blk_stk.append("*------------------------- ---- ----- -beg- -end- -**- ------------------------------------------------\n*")

        DF_SiteBlock = DF_work[DF_work[sort_wrt] == site]

        for i_l ,(_ , l) in enumerate(DF_SiteBlock.iterrows()):

            iope = i_l + 1
            
            if no_time_limit_for_first_period and i_l == 0:
                MJD_start = 0
            else:
                MJD_start = l["MJD_start"]
                                            
            if no_time_limit_for_last_period and iope == len(DF_SiteBlock):
                MJD_end = 0
            else:
                MJD_end = l["MJD_end"]
                
                
            
            line_site_fmt = " SITE            m {:4d}  {:1d} {:} {:5d} {:5d} {:5d} {:}   A  {:1d}      LOG_CAR       LOG_CAR"
            line_posi_fmt = " POS_VEL:XYZ     m {:4d}  {:1d} {:+15.4f} {:+15.4f} {:+15.4f}      {:+6.4f} {:+6.4f} {:+6.4f}"
            line_velo_fmt = " SIG_PV_XYZ      m {:4d}  {:1d} {:+15.4f} {:+15.4f} {:+15.4f}      {:+6.4f} {:+6.4f} {:+6.4f}"

            line_site = line_site_fmt.format(int(l["site_num"]),
                                             int(iope),
                                             l["tecto_plate"].upper(),
                                             int(l["MJD_ref"]),
                                             int(MJD_start),
                                             int(MJD_end),
                                             int(l["site"]),
                                             int(iope))
            
            line_posi = line_posi_fmt.format(int(l["site_num"]),
                                             int(iope),
                                             l["x"],
                                             l["y"],
                                             l["z"],
                                             l["Vx"],
                                             l["Vy"],
                                             l["Vz"])
            
            line_velo = line_velo_fmt.format(int(l["site_num"]),
                                             int(iope),
                                             l["sx"],
                                             l["sy"],
                                             l["sz"],
                                             l["sVx"],
                                             l["sVy"],
                                             l["sVz"])

            Stat_lines_blk_stk.append(line_site)
            Stat_lines_blk_stk.append(line_posi)
            Stat_lines_blk_stk.append(line_velo)
            Stat_lines_blk_stk.append("*")


    Stat_lines_blk_stk.append("-station_coordinates")


    final_str = "\n".join(Stat_lines_blk_stk)


    with open(file_out,"w+") as f:
        f.write(final_str)

    return final_str


def prn_int_2_prn_str(prn_int,full_out=False):
    """
    for read_combi_sum_full

    if full_out : return e.g. "G04","G",4
    """
    const = "X"

    prn_int = int(prn_int)

    prn_int_out = prn_int

    if prn_int >= 400:
        prn_int_out = prn_int - 400
        const = "J"
    elif 300 <= prn_int < 400:
        prn_int_out = prn_int - 300
        const = "C"
    elif 200 <= prn_int < 300:
        prn_int_out = prn_int - 200
        const = "E"
    elif 100 <= prn_int < 200:
        prn_int_out = prn_int - 100
        const = "R"
    else:
        prn_int_out = prn_int
        const = "G"

    prn_str = const + str(prn_int_out).zfill(2)

    if not full_out:
        return prn_str
    else:
        return prn_str , const , prn_int_out

def read_combi_sum_full(sum_full_file,RMS_lines_output=True,
                        set_PRN_as_index=True):
    Vals_stk = []

    for l in open(sum_full_file):

        F = l.split()
        if "|" in F:
            F.remove("|")

        ### Find date line
        if "MJD:" in l:
            date_line  = l

        ### Skip useless lines
        if not "|" in l or "------" in l:
            continue

        ### Find AC list
        if "PRN" in l:
            ACs_list  = F
            ACs_list.append("RMS_sat")
            ACs_list.append("PRN_str")
            ACs_list.append("CONST")


        elif F[0].isnumeric():
            Fout = [float(f) for f in F]
            Fout[0] = int(Fout[0])
            #Add the PRN string and the constellation
            Fout.append(prn_int_2_prn_str(int(Fout[0])))
            Fout.append(Fout[-1][0])

            Vals_stk.append(Fout)

        elif "RMS" in F[0] and RMS_lines_output:
            Fout = [float(f) for f in F[1:]]
            Fout.append(np.nan)
            Fout.insert(0,F[0])
            #Add FAKE the PRN string and the constellation
            Fout.append(F[0])
            Fout.append(None)

            Vals_stk.append(Fout)


    DF = pd.DataFrame(Vals_stk,columns=ACs_list)

    ### Date management
    mjd = float(date_line.split("MJD:")[1].split()[0])
    date_dt = conv.MJD2dt(mjd)

    DF.date_mjd = mjd
    DF.date_dt  = date_dt

    DF.date_gps = utils.join_improved("",conv.dt2gpstime(date_dt))

    if set_PRN_as_index:
        DF.set_index("PRN_str",inplace=True)

    return DF


def read_combi_sum_exclu(sum_file,return_as_df=True,
                         use_intuitive_bool = True):


    t_dt = conv.sp3name2dt(sum_file)

    with open(sum_file) as f:
        cont = f.readlines()


    excluded_dic = dict()
    useful_ssection = False
    useful_ssection_k = 0
    for l in cont:
        f = l.split()
        if "---|---" in l and useful_ssection_k < 2:
            useful_ssection = not useful_ssection
            useful_ssection_k +=1
            continue

        if not useful_ssection:
            continue

        prn_raw = f[0]

        if "X" in prn_raw:
            exclu = True
        else:
            exclu = False

        if use_intuitive_bool:
            exclu = not exclu

        prn_int = int(f[0].replace("X","").split()[0])

        prn_good = prn_int_2_prn_str(prn_int)

        excluded_dic[prn_good] = exclu

    if return_as_df:
        return pd.DataFrame(excluded_dic,index=[t_dt])
    else:
        return excluded_dic


def read_combi_clk_rms(sum_file,return_as_df=True,
                       clk_ref_cen_gal = "com"):
    """
    based on : read_good_clk_rms_one
    """

    strt = " RESULTS OF FINAL WEIGHTED COMBINATION"
    end  = " CLK_REF_CEN_GAL: " + clk_ref_cen_gal

    L = utils.extract_text_between_elements_2(sum_file,strt,end)

    L = L[:-2]

    Lres = [e for e in L if re.search("^ [a-z]{3} \|",e)]

    Lres_splited = [e.split() for e in Lres]

    filnam = os.path.basename(sum_file)
    if "log" in filnam:
        week = int(filnam[4:8])
        dow  = int(filnam[9])
        tdt = conv.gpstime2dt(week,dow)
    elif "cls" in filnam:
        week = int(filnam[3:7])
        dow  = int(filnam[7])
        tdt = conv.gpstime2dt(week,dow)

    rms_dict = dict()

    for e in Lres_splited:
        try:
            rms_dict[e[0]] = int(e[-4])
        except:
            print("WARN : ", e[-4],"not handeled")
            print("replaced with NaN")
            rms_dict[e[0]] = np.nan

    if return_as_df:
        return pd.DataFrame(rms_dict,index=[tdt])
    else:
        return tdt,rms_dict


def read_combi_clk_rms_full_table(path_in):
    """
    recommended for .out file
    """
    strt = "RMS \(ps\) OF AC CLOCK COMPARED TO COMBINATION"
    end  = "---+---"

    Lines = utils.extract_text_between_elements_2(path_in,strt,end,nth_occur_elt_end=1)

    Lines_good = []

    for l in Lines[1:]:
        if "---+---" in l or "bad" in l:
            continue
        else:
            Lines_good.append(l)


    Lines_good = [e.replace("|","") for e in Lines_good]
    Lines_good = [e.replace("         ","  SAT    ") for e in Lines_good]

    STR = "".join(Lines_good)

    import io

    DF = pd.read_table(io.StringIO(STR),
                      na_values = ["-","X",">>>"] ,
                      delim_whitespace = True ,
                      error_bad_lines=False)

    DF = DF.set_index("SAT")

    return DF


def read_combi_REPORT(Path_list):
    STK = []
    for p in Path_list:
        F = open(p)
        for l in F:
            f = l.split()
            if "epoch" in l:
                epoch = conv.gpstime2dt(int(f[2]),int(f[3]))
            if "orb_flag_x" in l:
                prn_str , const , prn_int = prn_int_2_prn_str((f[2]),True)
                STK.append((epoch,prn_str,const , prn_int,"all"))
            if "orb_excl_sat" in l:
                prn_str , const , prn_int = prn_int_2_prn_str((f[3]),True)
                STK.append((epoch,prn_str,const , prn_int,f[2]))

    DF = pd.DataFrame(STK,columns=("epoch","PRN_str","CONST","PRN","AC"))

    return DF




def read_gins(filein,kineorstatic='kine',flh_in_rad=True,
              force_get_convergence=False,kf_result=False):

    '''
    Static : donne un point
    Kinematic : donne une TS

    force_get_convergence : if there is a bug about
    'COORDONNEES DES STATIONS AJUSTEES EN HAUTE FREQUENCE' field, it is in the listing
    but empty ... so we force the retreive of the 'c o n v e r g e n c e' part
    '''

    if '.prepars' in filein:
        print('WARN :',filein, 'seems to be a prepars file, are you sure of what you are doing ?')

    # Pour le static, il y a des blancs en fin de ligne ...

    if kineorstatic == 'kine':
        #regex = '\[S[PLHXYZ] .*\]$'
        regex = '\[S[PLHXYZ] .*\]$'
        tsout = time_series.TimeSeriePoint()
        if kf_result:
            regex = '\[S[PLHXYZ][E ].*\]     $'
    elif kineorstatic == 'static':
        #regex = '\[S[PLHXYZ] .*\]     $'
        regex = '\[S[PLHXYZ][E ].*\]     $'
        tsout = time_series.TimeSeriePoint()
    else:
        print("ERR")

    A,B,C = 0,0,0
    Ta , Tb , Tc, T = 111,222,333,0
    sA,sB,sC = 0,0,0

    if kf_result:
        regex = '\[S[PLHXYZ][E ].*\]     $'


    # Specific si 2ble convergence
    grep_conv = utils.grep(filein,'c o n v e r g e n c e')
    if len(grep_conv) == 2:
        IPPmode = True
        converg_compt = 0
        print("INFO : ", os.path.basename(filein) , 'have 2  c o n v e r g e n c e  fields')
        print("     keeping the last one")
    else:
        IPPmode = False

    # Specific si Ajustement Final
    greped_adj = utils.grep(filein,'COORDONNEES DES STATIONS AJUSTEES EN HAUTE FREQUENCE')
    if force_get_convergence:
        FinalAdj_mode = False
    elif len(greped_adj) != 0:
        FinalAdj_mode = True
        FinalAdj_found = False
        print("INFO : ", os.path.basename(filein) , 'have a COORD STAT AJ EN HTE FREQ  field')
        print("     keeping this one (and not the convergence)")
    else:
        FinalAdj_mode = False

    fileopened = open(filein,encoding = "ISO-8859-1")

    regex_valid_line_count = 0

    for line in fileopened:

        if re.compile('__Nom__').search(line):
            nextline = next(fileopened).split()
            namestat = nextline[3]
            Xref = float(nextline[4])
            Yref = float(nextline[5])
            Zref = float(nextline[6])

            Fref , Lref , Href = conv.XYZ2GEO(Xref,Yref,Zref)

#        if 'angles en deg' in line:
#            flh_in_rad = False

        # Specific search
        if IPPmode and re.compile('c o n v e r g e n c e').search(line):
            converg_compt = converg_compt + 1
        if FinalAdj_mode and re.compile('COORDONNEES DES STATIONS AJUSTEES EN HAUTE FREQUENCE').search(line):
            FinalAdj_found = True

        # Specific skip
        if FinalAdj_mode and not FinalAdj_found:
            continue
        if IPPmode and converg_compt != 2:
            continue

        if "real" in line:
            rawexectime = line.split()[-1]

        if re.compile(regex).search(line):
            regex_valid_line_count += 1
            fields = line.split()

            if re.compile('[XYZ]').search(line):
                initype = 'XYZ'
                Aref , Bref ,Cref = Xref,Yref,Zref
            elif re.compile('[PLH]').search(line):
                initype = 'FLH'
                Aref , Bref ,Cref = Fref,Lref,Href
            else:
                print("ERR : read gins : wrong initype")

            if (float(fields[2]) == 0):
                continue

            if (fields[0] == 'stations'):
                print('yyyyy')

            # securité pour les lignes du type
            #  ------------------------------------------------------------------------------------------------------
            # stations      175  -0.574353783560234E+07  +/-   0.000000000000000E+00   1  [SX  1212001892701M005071]

            jour = int(line[108:110])
            h    = int(line[110:112])
            m    = int(line[112:114])
            s    = int(line[114:116])
            yy   = int(line[125:127])

            # gestion des années
            if 80 < yy <= 99:
                yy = yy + 1900
            else:
                yy = yy + 2000

            # pour le mois, si > sept (9), alors lettre ...
            mm = line[127]

            if mm == 'O':
                mm = 10
            elif mm == 'N':
                mm = 11
            elif mm == 'D':
                mm = 12
            else:
                mm = int(mm)

            try:
                if h == 24:
                    # cas exceptionnel ou on doit gerer minuit
                    # on retranche l'heure dans l'int en input et on l'ajoute dans le dt
                    Ttemp = (dt.datetime(yy,mm,jour,h-1,m,s) + dt.timedelta(seconds=-19) + dt.timedelta(hours=1))
                else:
                    Ttemp = (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))

                if  line[105] == 'X' or line[105] == 'P':
                    Ta = Ttemp
                    A = (float(fields[3]))
                    sA = (float(fields[4]))

                if  line[105] == 'Y' or line[105] == 'L':
                    Tb = Ttemp
                    B = (float(fields[3]))
                    sB = (float(fields[4]))

                if  line[105] == 'Z' or line[105] == 'H':
                    Tc = Ttemp
                    C = (float(fields[3]))
                    sC = (float(fields[4]))
            except ValueError as err:
                print('ERR :')
                print('yy,mm,jour,h,m,s ',yy,mm,jour,h,m,s)
                raise err

            if  Ta == Tb == Tc :
                T = Ta
                if initype == 'FLH' and not FinalAdj_mode:
                    if flh_in_rad:
                        A = np.rad2deg(A)
                        B = np.rad2deg(B)
                        sA = np.rad2deg(sA)
                        sB = np.rad2deg(sB)
                if kf_result and 0:
                    A = A + Aref
                    B = B + Bref
                    C = C + Cref
                point = time_series.Point(A,B,C,T,initype,sA,sB,sC,name=namestat)

                Ta = 111
                Tb = 222
                Tc = 333

                if kineorstatic == 'static':
                    return point
                elif kineorstatic == 'kine':
                    tsout.add_point(point)
                else:
                    print("ERR")

    if  regex_valid_line_count == 0:
        print("WARN : no valid line (with regex check) was found !!!")


    tsout.anex['exec_time'] = rawexectime
    tsout.meta_set(filein,namestat)
    return tsout


def gins_read_time(line):
    jour = int(line[108:110])
    h    = int(line[110:112])
    m    = int(line[112:114])
    s    = int(line[114:116])
    yy   = int(line[125:127])

    # gestion des années
    if 80 < yy <= 99:
        yy = yy + 1900
    else:
        yy = yy + 2000

    # pour le mois, si > sept (9), alors lettre ...
    mm = line[127]

    if mm == 'O':
        mm = 10
    elif mm == 'N':
        mm = 11
    elif mm == 'D':
        mm = 12
    else:
        mm = int(mm)

    try:
        if h == 24:
            # cas exceptionnel ou on doit gerer minuit
            # on retranche l'heure dans l'int en input et on l'ajoute dans le dt
            Ttemp = (dt.datetime(yy,mm,jour,h-1,m,s) +
                     dt.timedelta(seconds=-19) + dt.timedelta(hours=1))
        else:
            Ttemp = (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))
    except:
        Ttemp = dt.datetime(1970,1,1)

    T = Ttemp

    return T


def gins_read_MZB(filein):

    F = open(filein)

    regex = '\[MZB.*\]     $'

    Tstk    = []
    MZBstk  = []
    sMZBstk = []

    for line in F:
        if re.compile('__Nom__').search(line):
            nextline = next(F).split()
            namestat = nextline[3]
            Xref = float(nextline[4])
            Yref = float(nextline[5])
            Zref = float(nextline[6])

        if re.compile(regex).search(line):
            fields = line.split()

            #[MZB  801980015051301 GPS]

            Traw = fields[6][-8:]
            yy = int(Traw[0:2])
            mm = int(Traw[2:4])
            dd = int(Traw[4:6])
            hh = int(Traw[6:8])

            if 80 < yy <= 99:
                yy = yy + 1900
            else:
                yy = yy + 2000

            T = dt.datetime(yy,mm,dd,hh)

            MZB  = float(fields[3])
            sMZB = float(fields[4])

            Tstk.append(T)
            MZBstk.append(MZB)
            sMZBstk.append(sMZB)

    return Tstk , MZBstk , sMZBstk , namestat


def write_ATM_GAMIT(Tstk , MZBstk , sMZBstk ,
                    namestat , file_out):
    Fout = open(file_out,'w+')
    for T,mzb , smzb in zip(Tstk , MZBstk , sMZBstk):
        yy = T.year
        mm = T.month
        dd = T.day
        hh = T.hour
        Line = 'ATM_ZEN X {}  1 {:4} {:2} {:2} {:2}  0  {:6.4f} +-   {:6.4f}    {:6.4f}\n'.format(namestat.upper(),yy,mm,dd,hh,mzb,smzb,mzb)
        Fout.write(Line)
    Fout.close()
    return file_out


def MZB_GINS_2_ATM_GAMIT(listing_in,path_out):
    Tstk , MZBstk , sMZBstk , namestat = gins_read_MZB(listing_in)
    doy,yy = conv.dt2doy_year(Tstk[0],str)
    file_out = os.path.join(path_out,'_'.join(('MZB_GINS_2_ATM_GAMIT',namestat,doy,yy,'.txt')))
    write_ATM_GAMIT(Tstk , MZBstk , sMZBstk ,
                    namestat , file_out)

    return file_out

def read_gins_wrapper(input_list_or_path,flh_in_rad=True):
    """
    pour une liste de paths renvoie une liste de timeseries
    AUTANT DE TIMESERIES QUE DE LISTINGS

    INPUT :
    Une liste de fichiers
    Un path compatible avec glob

    les fichiers sans extensions .gins
    sont automatiquement exclus
    """

    if type(input_list_or_path) is str:
        gins_listings_list = glob.glob(input_list_or_path)
    else:
        gins_listings_list = input_list_or_path

    tslis = []
    for f in gins_listings_list:
        if not '.gins' in f:
            print('WARN : no .gins ext, skipping')
            continue

        ts = read_gins(f,flh_in_rad=flh_in_rad)
        tslis.append(ts)

    return tslis


def convert_sp3_clk_2_GINS_clk(sp3_path_in,
                               clk_gins_out,
                               interpo_30sec = True,
                               return_as_DF = True):
    DF = files_rw.read_sp3(sp3_path_in)

    Fout = open(clk_gins_out,"w+")

    def write_GINS_signaletic_elt_clk(dt_in,sv,
                                      signaletic_name="MNG",
                                      add_19sec_to_dt_in = True):
        """
        very beta, only for GPS clk
        """

        if add_19sec_to_dt_in:
            dt_work = dt_in + dt.timedelta(seconds=19)
        else:
            dt_work = dt_in

        jjul = conv.dt2jjulCNES(dt_work)
        sec_in_day = (dt_work - conv.jjulCNES2dt(jjul) ).seconds

        #MNG0000000jjjjjcccccnnnn

        outstr = "[MNG0000000" + str(jjul) + str(sec_in_day).zfill(5) + "GP" + str(sv).zfill(2) + "]"

        return outstr

    c = 299792458

    if interpo_30sec:
        Epoc_work = []
        Sv_work   = []
        Clk_work  = []

        for sv in sorted(DF["sv"].unique()):
            DFsv = DF[DF["sv"] == sv]

            Epoc_inp = np.array(conv.dt2posix(DFsv["epoch"]))
            Clk_inp  = np.array(DFsv["clk"])

            Epoc_interp = np.arange(np.min(Epoc_inp),np.max(Epoc_inp),30)
            Epoc_interp_dt = conv.posix2dt(Epoc_interp)

            I = scipy.interpolate.interp1d(Epoc_inp,Clk_inp)

            Clk_interp = I(Epoc_interp)

            Sv_work   = Sv_work   + [sv] * len(Epoc_interp)
            Epoc_work = Epoc_work + list(Epoc_interp_dt)
            Clk_work  = Clk_work  + list(Clk_interp)

    else:
        Epoc_work = DF["epoch"]
        Sv_work   = DF["sv"]
        Clk_work  = DF["clk"]


    DF_work = pd.DataFrame(list(zip(Epoc_work,Sv_work,Clk_work)),
                            columns=("epoch","sv","clk"))

    DF_work.sort_values(["epoch","sv"],inplace=True)

    print("tot",DF_work)

    for epoc , sv , clk in zip(DF_work["epoch"],DF_work["sv"],DF_work["clk"]):
        signaletik = write_GINS_signaletic_elt_clk(epoc,sv,clk)

        str_final = " 0 0 {:}  {:+17.15e} {:+17.15e}\n".format(signaletik,clk* 10**-6 * c,0)

        Fout.write(str_final)

    if not return_as_DF:
        return clk_gins_out
    else:
        return DF_work



#def read_gins_kinematic(filein):
#
#    ''' retourne une TSPoint '''
#
#    tsout = time_series.TimeSeriePoint()
#
#    X,Y,Z = 0,0,0
#    Tx , Ty , Tz, T = 111,222,333,0
#    sX,sY,sZ = 0,0,0
#
#    for line in open(filein):
#
#        if re.compile('\[S[XYZ] .*\]$').search(line):
#            fields = line.split()
#
#            if (float(fields[2]) == 0):
#                continue
#
#            if (fields[0] == 'stations'):
#                continue
#            # securité pour les lignes du type
#            #  ------------------------------------------------------------------------------------------------------
#            # stations      175  -0.574353783560234E+07  +/-   0.000000000000000E+00   1  [SX  1212001892701M005071]
#
#            jour = int(line[108:110])
#            h = int(line[110:112])
#            m = int(line[112:114])
#            s = int(line[114:116])
#            yy = int(line[125:127]) + 2000
#            mm = int(line[127])
#
#            if line[105] == 'X':
#                Tx = (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))
#                X = (float(fields[3]))
#                sX = (float(fields[4]))
#
#            if  line[105] == 'Y':
#                Ty = (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))
#                Y = (float(fields[3]))
#                sY = (float(fields[4]))
#
#            if  line[105] == 'Z':
#                Tz = (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))
#                Z = (float(fields[3]))
#                sZ = (float(fields[4]))
#
#
#            if  Tx == Ty == Tz :
#                T = Tx
#                point = time_series.Point(X,Y,Z,T,'XYZ',sX,sY,sZ)
#                tsout.add_point(point)
#                Tx = 111
#                Ty = 222
#                Tz = 333
#
#    tsout.meta_set(filein)
#
#    return tsout
#
#
#def read_gins_static_solo(filein):
#
#    X,Y,Z = 0,0,0
#    Tx , Ty , Tz, T = 111,222,333,0
#    sX,sY,sZ = 0,0,0
#    namestat='NULL'
#
#    fileopened = open(filein)
#
#    for line in fileopened:
#
#        if re.compile('__Nom__').search(line):
#            namestat = next(fileopened).split()[3]
#
#        # Pour le static, il y a des blancs en fin de ligne ...
#        if re.compile('\[S[XYZ] .*\]     $').search(line):
#
#            fields = line.split()
#
#            if (float(fields[2]) == 0):
#                continue
#
#            if (fields[0] == 'stations'):
#                continue
#            # securité pour les lignes du type
#            #  ------------------------------------------------------------------------------------------------------
#            # stations      175  -0.574353783560234E+07  +/-   0.000000000000000E+00   1  [SX  1212001892701M005071]
#
#            jour = int(line[108:110])
#            h = int(line[110:112])
#            m = int(line[112:114])
#            s = int(line[114:116])
#            yy = int(line[125:127])
#
#            # gestion des annÃ©es
#            if 80 < yy <= 99:
#                yy = yy + 1900
#            else:
#                yy = yy + 2000
#
#            # pour le mois, si > sept (9), alors lettre ...
#            mm = line[127]
#
#            if mm == 'O':
#                mm = 10
#            elif mm == 'N':
#                mm = 11
#            elif mm == 'D':
#                mm = 12
#            else:
#                mm = int(mm)
#
#            if line[105] == 'X':
#                Tx = (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))
#                X = (float(fields[3]))
#                sX = (float(fields[4]))
#
#            if  line[105] == 'Y':
#                Ty = (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))
#                Y = (float(fields[3]))
#                sY = (float(fields[4]))
#
#            if  line[105] == 'Z':
#                Tz = (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))
#                Z = (float(fields[3]))
#                sZ = (float(fields[4]))
#
#
#            if  Tx == Ty == Tz :
#                T = Tx
#                point = time_series.Point(X,Y,Z,T,'XYZ',sX,sY,sZ,name=namestat)
#
#                Tx = 111
#                Ty = 222
#                Tz = 333
#
#                return point

#read_gins_static_solo('/media/DDannex/GINS_AKRIM/listing/listing_NRMD/DIR_sortie_2007_20830_nrmd.140513_060821.gins')

def read_gins_multi_raw_listings(filelistin,kineorstatic='static',flh_in_rad=True):
    """
    traite une liste de listing bruts
    pour obtenir UNE SEULE timeserie
    """

    tsout = time_series.TimeSeriePoint()
    refname = 'RIEN'
    if kineorstatic == 'static':
        for filein in filelistin:
            print(filein)
            if not utils.check_regex(filein,'c o n v e r g e n c e'):
                continue
            pt = read_gins(filein,kineorstatic='static',flh_in_rad=flh_in_rad)
            if refname == 'RIEN':
                refname = pt.name
            if refname != pt.name:
                print("WARN : read_gins_multi : nom de stat. != reference")
            tsout.add_point(pt)
        tsout.meta_set(stat=refname)


    elif kineorstatic == 'kine':
        tsoutlis = []
        for filein in filelistin:
            print(filein)
            if not utils.check_regex(filein,'c o n v e r g e n c e'):
                continue
            ts = read_gins(filein,kineorstatic='kine',flh_in_rad=flh_in_rad)
            tsoutlis.append(ts)
        tsout = merge_ts(tsoutlis)

    else:
        print("ERR : check kineorstatic keyword")

    tsout.sort()
    return tsout

def read_gins_multi_extracted(filelistin,flh_in_rad=True):
    """
    traite les extractions de listings
    sous la forme par ex. S<HLP>__ddhhiissxxxxxxxxxyym.HOUE
    La liste doit contenir exactement 3 fichiers (pour chacune des composantes)
    """
    tsout = time_series.TimeSeriePoint()
    if len(filelistin) != 3:
        print("ERR : read_gins_multi_extracted : listfilein != 3 elts")
        return None
    statnameset = list(set([ f.split('.')[-1] for f in filelistin ]))
    statname = statnameset[0]
    if len(statnameset) != 1:
        print("WARN : read_gins_multi_extracted : len(statnameset) != 1")
    fileopenedlist = [ open(f,'r+') for f in filelistin ]
    coortypelist = [ os.path.basename(f)[1] for f in filelistin ]
    print(coortypelist,filelistin)
    if 'X' in coortypelist:
        initype='XYZ'
        ia = coortypelist.index('X')
        ib = coortypelist.index('Y')
        ic = coortypelist.index('Z')
    elif 'P' in coortypelist:
        initype = 'FLH'
        ia = coortypelist.index('P')
        ib = coortypelist.index('L')
        ic = coortypelist.index('H')

    for lf in zip(*fileopenedlist):
        # OLD MODE : MAVAIS GESTION DE LA DATE
#        t1 = lf[0].split()[0]
#        t2 = lf[1].split()[0]
#        t3 = lf[2].split()[0]
#        if not (t1 == t2 == t3):
#            print "WARN : read_gins_multi_extracted : not (t1 == t2 == t3)"
#
        fields = lf[0].split()
        line = lf[0]
        blok = fields[-1]
        jour = int(blok[0:2])
        h = int(blok[2:4])
        m = int(blok[4:6])
        s = int(blok[6:8])
        yy = int(blok[-4:-2])
        # gestion des années
        if 80 < yy <= 99:
            yy = yy + 1900
        else:
            yy = yy + 2000

        # pour le mois, si > sept (9), alors lettre ...
        mm = blok[-2]

        if mm == 'O':
            mm = 10
        elif mm == 'N':
            mm = 11
        elif mm == 'D':
            mm = 12
        else:
            mm = int(mm)

        t1  =  (dt.datetime(yy,mm,jour,h,m,s) + dt.timedelta(seconds=-19))

        lfiasplit = lf[ia].split()
        lfibsplit = lf[ib].split()
        lficsplit = lf[ic].split()

        A  = float(lfiasplit[4])
        B  = float(lfibsplit[4])
        C  = float(lficsplit[4])
        sA = float(lfiasplit[5])
        sB = float(lfibsplit[5])
        sC = float(lficsplit[5])
        T = t1

        if initype == 'FLH' and flh_in_rad:
            A  = np.rad2deg(A)
            B  = np.rad2deg(B)
            sA = np.rad2deg(sA)
            sB = np.rad2deg(sB)

        pt = time_series.Point(A,B,C,T,initype,sA,sB,sC)

        tsout.add_point(pt)
    tsout.meta_set(stat=statname)
    tsout.sort()

    return tsout

def read_gins_double_diff(filein):
    """
    return a list of Point object for a double diff listing
    """

    if utils.grep(filein , 'c o n v e r g e n c e') == '':
        print('ERR : ' , filein , 'have no convergence, return None')
        return None

    fileopened = open(filein)

    statlist    = []
    rawdatalist = []
    timelist    = []

    regstat   = re.compile(r'[0-9]{5}[A-Z][0-9]{3}  [0-9]{7} .*$')
    regresult = re.compile(r'\[S[PLHXYZ][E ].*\]     $')


    for line in fileopened:
        # finding
        if regstat.search(line):
            stat = line.split()[3]
            statlist.append(stat)

        if regresult.search(line):
            fields = line.split()
            rawdatalist.append([float(e) for e in fields[:-2]])
            timelist.append(gins_read_time(line))


    rawdatatab = np.vstack(rawdatalist)

    Pstk = []

    for istat,stat in enumerate(statlist):
        P = time_series.Point(rawdatatab[3*istat,3],
                       rawdatatab[3*istat+1,3],
                       rawdatatab[3*istat+2,3],
                       timelist[3*istat],'XYZ',
                       rawdatatab[3*istat,4],
                       rawdatatab[3*istat,4],
                       rawdatatab[3*istat,4],name=stat)

        Pstk.append(P)

    return Pstk

def read_gins_double_diff_multi(filelistin):
    """
    return a dictionnary with station names as keys and timeseries as values
    """

    Ptsstk = []
    for filein in filelistin:
        Pstk = read_gins_double_diff(filein)
        if Pstk != None:
            Ptsstk = Ptsstk + Pstk

    statlist = set([e.name for e in Ptsstk])

    tsdico = dict()

    for stat in statlist:
        tsdico[stat] = time_series.TimeSeriePoint(stat=stat)

    for pt in Ptsstk:
        tsdico[pt.name].add_point(pt)

    for ts in tsdico.values():
        ts.sort()

    return tsdico




def read_jpl_timeseries_solo(latlonrad_files_list):

    tsout = time_series.TimeSeriePoint()

    latpath = [f for f in latlonrad_files_list if '.lat' in f][0]
    lonpath = [f for f in latlonrad_files_list if '.lon' in f][0]
    radpath = [f for f in latlonrad_files_list if '.rad' in f][0]

    latfile = open(latpath)
    lonfile = open(lonpath)
    radfile = open(radpath)

    for llat , llon , lrad in zip(latfile,lonfile,radfile):
        flat = [float(e) for e in llat.split()[0:3]]
        flon = [float(e) for e in llon.split()[0:3]]
        frad = [float(e) for e in lrad.split()[0:3]]

        if not ( flat[0] == flon[0] == frad[0]):
            print(flat[0] , flon[0] , frad[0])
            raise Exception('ERR : read_jpl_timeseries_solo : Time dont corresponds !!!')

        statlat = os.path.basename(latpath).split('.')[0]
        statlon = os.path.basename(lonpath).split('.')[0]
        statrad = os.path.basename(radpath).split('.')[0]

        if not ( statlat == statlon == statrad):
            print(statlat , statlon , statrad)
            raise Exception('ERR : read_jpl_timeseries_solo : station name dont corresponds !!!')

        T = conv.year_decimal2dt(flat[0])

        N = flat[1] * 10**-2
        E = flon[1] * 10**-2
        U = frad[1] * 10**-2

        sN = flat[2] * 10**-2
        sE = flon[2] * 10**-2
        sU = frad[2] * 10**-2

        point = time_series.Point(E,N,U,T,'ENU',sE,sN,sU)

        tsout.boolENU = True
        tsout.add_point(point)

    tsout.stat = statlat

    return tsout

def read_nevada(filein,input_coords="enu"):
    """
    input_coords="enu" or "xyz"
    """

    tsout = time_series.TimeSeriePoint()

    envfile = open(filein)

    if input_coords=="enu":
        for l in envfile:
            f = l.split()

            if "site YYMMMDD" in l:
                continue
            if len(l) == 0:
                continue

            stat = f[0]

            T = conv.year_decimal2dt(float(f[2]))

            N = float(f[10])
            E = float(f[8])
            U = float(f[12])

            sN = float(f[15])
            sE = float(f[14])
            sU = float(f[16])

            point = time_series.Point(E,N,U,T,'ENU',sE,sN,sU)

            #tsout.refENU = time_series.Point()

            tsout.boolENU = True
            tsout.add_point(point)


    if input_coords=="xyz":
        for l in envfile:
            f = l.split()

            if "site YYMMMDD" in l:
                continue
            if len(l) == 0:
                continue

            stat = f[0]

            T = conv.year_decimal2dt(float(f[2]))

            X = float(f[3])
            Y = float(f[4])
            Z = float(f[5])

            sX = float(f[6])
            sY = float(f[7])
            sZ = float(f[8])

            point = time_series.Point(X,Y,Z,T,'XYZ',sX,sY,sZ)

            point.anex['Rxy'] = float(f[9])
            point.anex['Rxz'] = float(f[10])
            point.anex['Ryz'] = float(f[11])

            tsout.add_point(point)

    tsout.stat = stat

    return tsout

def read_IGS_coords(filein,initype='auto'):
    Tstk , Astk, Bstk, Cstk = [] , [] , [] , []
    tsout = time_series.TimeSeriePoint()
    for l in open(filein):
        f = l.split()

        if initype == 'auto':
            if "plh" in os.path.basename(filein):
                initype = 'FLH'
            elif "xyz" in os.path.basename(filein):
                initype = 'XYZ'

        T = conv.MJD2dt(float(f[3]))
        A = float(f[6])
        B = float(f[7])
        C = float(f[8])
        sA = float(f[9])
        sB = float(f[10])
        sC = float(f[11])

        initype = "FLH"

        pt = time_series.Point(A,B,C,T,initype,sA,sB,sC,f[0])
        tsout.add_point(pt)

    tsout.meta_set(filein,f[0])
    return tsout

def sorting_a_calais_file(openedfile):
    openedfile.seek(0)
    T , A, sA , STAT = [] , [] , [] , []
    for l in openedfile:
        f = l.split()
        T.append(float(f[0]))
        A.append(float(f[1]))
        sA.append(float(f[2]))
        STAT.append(str(f[3]))

    DATA = [ T , A, sA , STAT ]
    DATA2 = utils.sort_table(DATA,0)

    return DATA2

def read_calais(filelist):
    """ filelistin est une liste de 3 fichier E N & U """

    if filelist == []:
        print('WARN : read_calais : files list empty , exiting ...')
        return None
    filelist.sort()

    fileopenedlist = [open(f) for f in filelist]

    sorted_data_lis = [sorting_a_calais_file(fil) for fil in fileopenedlist]

    statnameset = list(set([ f.split('.')[0] for f in filelist ]))
    statname = os.path.basename(statnameset[0])

    # LOADING ALL DATA IN A BIG MATRIX
    bigT = np.array(sorted(set(np.hstack([np.array(sd[0]) for sd in sorted_data_lis]))))
    bigDATA = np.empty((len(bigT),3))
    bigDATA.fill(np.nan)
    bigDATAsigma = np.empty((len(bigT),3))
    bigDATAsigma.fill(np.nan)

    for i,bt in enumerate(bigT):
        for j,data in enumerate(sorted_data_lis):
            for t , d ,sd, stat in zip(*data):
                if t == bt:
                    bigDATA[i,j] = d
                    bigDATAsigma[i,j] = sd

    DATA = np.hstack((bigDATA / 1000. ,bigDATAsigma / 100.))

    ptslist = []

    # MAKING POINTS
    for i in range(DATA.shape[0]):
        pt = time_series.Point(conv.convert_partial_year(bigT[i])
        ,'ENU',DATA[i,3],DATA[i,4],DATA[i,5])
        ptslist.append(pt)

    tsout = time_series.TimeSeriePoint()

    for pt in ptslist:
        tsout.add_point(pt)

    #FINDING DISCONT
    # finding discont directly in files

    # Finding the composant with max of data
    lendata = [len(sd[0]) for sd in sorted_data_lis]
    ii = lendata.index(max(lendata))

    discont = []
    T = sorted_data_lis[ii][0]
    STAT = sorted_data_lis[ii][-1]
    for i in range(len(STAT)-1):
        if STAT[i+1] != STAT[i]:
            discont.append(T[i+1])

    tsout.set_discont(discont)
    tsout.meta_set(stat=statname)
    tsout.boolENU = True
    tsout.sort()

    return tsout

def read_renag_synthetic(filein , discont_file_in = None):

    tsout = time_series.TimeSeriePoint()

    fil = open(filein)

    for l in fil:

        if l[0] == "#":
            continue

        f = l.split()

        T = conv.year_decimal2dt(float(f[0]))

        N = float(f[1])
        E = float(f[2])
        U = float(f[3])

        sN = float(f[4])
        sE = float(f[5])
        sU = float(f[6])

        point = time_series.Point(E,N,U,T,'ENU',sE,sN,sU)

        #tsout.refENU = time_series.Point()

        tsout.boolENU = True
        tsout.add_point(point)


    if discont_file_in:
        DiscontInp = open(discont_file_in)

        Discont = []
        for l in DiscontInp:
            if l[0] == "#":
                continue
            f = l.split()
            try:
                Discont.append(conv.doy2dt(int(f[0]),int(f[1])))
            except:
                print("WARN : something went wrong during discont. file reading")
                pass

        Discont = sorted(Discont)
        tsout.set_discont(Discont)

    stat_name = os.path.basename(filein).split(".")[0].split(".")[0]
    print(stat_name)
    tsout.meta_set(path=filein,stat=stat_name,name=stat_name)


    return tsout


def read_jump_file(filein,returned_events=('S','E','D')):
    """
    From a "Jump" File (P. Sakic internal file)
    Return a dictionnairy with events

    Parameters
    ----------
    filein : str
        path of the Jump File

    returned_events : tuple or list
        contains the inital letter of the event type which will be stored in the dico
        (See below)

    Returns
    -------
    jump_dico : dict of dict of datetime
        outputed events, in the form jump_dico["STAT"]["L"] = datetime
        where L is the inital letter of the event type

    Note
    ----
    A jump file contains infos like this :

    >>> STAT S 2000 001
    >>> STAT E 2001 001
    >>> STAT D 2000 06 01

    it can manage YEAR DOY or YEAR MM DD or DECIMAL YEAR

    A non-blank 1st column is a commented line

    After a #, it is a commentary

    event type letters :
        S : Start

        E : End

        D : Discontinuity

    """
    import pytz

    F = open(filein)
    jump_dico = dict()
    for l in F:
        l =  l.split("#")[0]
        f =  l.split()
        print(f)
        ## Skip comment lines
        if (not f) or (l[0] != " ") or ("#" in l):
            continue
        else:
            stat  = f[0]
            event = f[1]
            ## Create the key for the station
            if not f[0] in jump_dico.keys():
                jump_dico[stat] = dict()
                for rtn_evt in returned_events:
                    jump_dico[stat][rtn_evt] = []

            ## Fill the dico
            if event in returned_events:
                if    len(f) == 4: ### DOY
                    date = conv.doy2dt(int(f[2]),int(f[3]))
                elif  len(f) == 5: ### YYYY MM DD
                    date = dt.datetime(*[int(e) for e in f[2:]])
                elif  len(f) == 3: ### DECIMAL YEAR
                    date = conv.year_decimal2dt(float(f[2]))

                date_tz = date.replace(tzinfo=pytz.UTC)
                jump_dico[stat][event].append(date_tz)
    return jump_dico

def read_nav_step1_geodesea(filein):
    M = np.loadtxt(filein)
    tsout = time_series.TimeSeriePoint()

    for m in M:
        pt = time_series.Point(np.rad2deg(m[1]),np.rad2deg(m[2]),m[3],m[0],initype='FLH')
        tsout.add_point(pt)

    return tsout


def read_nrcan_csv(filein , associated_ps_file = '', statname = ''):
    """
    associated_ps_file is highly recommanded
    because of the time managing

    WARN : Must be avoided b/c of the weak decimal precision of the angles !!!
    """

    if statname == '':
        statname = os.path.basename(filein)[0:4]

    pdcsv = pd.read_csv(filein)

    F     = np.array(pdcsv['latitude_degre_decimal'])
    L     = np.array(pdcsv['longitude_degre_decimal'])
    H     = np.array(pdcsv['hauteur_ellipsoidale_m'])
    heure = np.array(pdcsv['heure_decimal'])
    doy   = np.array(pdcsv['jour_de_l_annee'])
    year  = np.array(pdcsv['annee'])

    T = conv.doy2dt(year,doy,heure)

    if associated_ps_file != '':
        T = []
        for l in open(associated_ps_file):
            if "BWD" in l:
                f = l.split()
                t = conv.date_string_2_dt(f[4] + ' ' + f[5])
                T.append(t)
        if statname == '':
            statname = f[2]

    tsout = time_series.TimeSeriePoint()
    for f,l,h,t in zip(F,L,H,T):
        point = time_series.Point(f,l,h,t,'FLH',name = statname)
        tsout.add_point(point)

    tsout.meta_set(filein,statname)

    return tsout

def read_nrcan_pos(filein):
    """
    .pos file are more precise than .csv, should be used !
    """
    tsout = time_series.TimeSeriePoint()
    start_read = False

    for l in open(filein):
        if l[0:3] == 'DIR':
            start_read = True
            continue
        elif not start_read:
            continue
        else:
            f = l.split()
            lat = (np.abs(float(f[20])) + 1/60. * float(f[21]) + 1/3600. * float(f[22])) * np.sign(float(f[20]))
            lon = (np.abs(float(f[23])) + 1/60. * float(f[24]) + 1/3600. * float(f[25])) * np.sign(float(f[23]))
            sE = float(f[15])
            sN = float(f[16])
            sU = float(f[17])
            h   = float(f[26])
            slat , slon , sh = conv.sENU2sFLH(lat,lon,h,sE,sN,sU)

            t   = conv.date_string_2_dt(f[4] + ' ' + f[5])

            pt = time_series.Point(lat,lon,h,t,'FLH',slat,slon,sh,name = f[2])
            tsout.add_point(pt)

    tsout.meta_set(filein,f[2])
    return tsout


def read_qinsy(filein,yy,mm,dd):
    reader = pd.read_csv(open(filein))
    T = [ dateutil.parser.parse(e).replace(year=yy, month=mm, day=dd) + dt.timedelta(seconds=dUTCGPS) for e in list(reader.icol(0))]
    (X,Y,Z) = np.array(conv.GEO2XYZ(reader.icol(12),reader.icol(13),reader.icol(14)))
    #sX,sY,sZ = [] , [] , []
    initype = 'XYZ'
    tsout = time_series.TimeSeriePoint()
    for i in range(len(T)):
        point = time_series.Point(X[i],Y[i],Z[i],T[i],initype,sA=np.nan,sB=np.nan,sC=np.nan)
        tsout.add_point(point)
    tsout.meta_set(filein)
    return tsout

def read_sonardyne_posi(filein):
    reader = pd.read_csv(open(filein),skip_footer=1)
    T = [ dateutil.parser.parse(e) + dt.timedelta(seconds=dUTCGPS) for e in list(reader['UTCTime'])]
    (L,F,H) = (reader['Longitude'],reader['Latitude'],reader['Altitude'])
    sX,sY,sZ = [] , [] , []
    initype = 'FLH'
    tsout = time_series.TimeSeriePoint()
    for i in range(len(T)):
        point = time_series.Point(F[i],L[i],H[i],T[i],initype,sA=np.nan,sB=np.nan,sC=np.nan)
        tsout.add_point(point)

    tsout.meta_set(filein)
    return tsout

def read_pbo_pos(filein):
    filobj = open(filein,'r')
    tsout = time_series.TimeSeriePoint()
    header = True
    for line in filobj:
        if not header:
            f = line.split()
            f2 = [float(e) for e in f[:-1]]
            t = dt.datetime(int(f[0][0:4]),int(f[0][4:6]),int(f[0][6:]),int(f[1][0:2]),int(f[1][2:4]),int(f[1][4:]))
            pt = time_series.Point(f2[3],f2[4],f2[5],t,'XYZ',f2[6],f2[7],f2[8])
            pt.FLHset(f2[12],f2[13],f2[14])
            pt.ENUset(f2[16],f2[15],f2[17],f2[19],f2[18],f2[20])
            pt.anex['Rxy'] = f2[9]
            pt.anex['Rxz'] = f2[10]
            pt.anex['Ryz'] = f2[11]
            pt.anex['Rne'] = f2[-4]
            pt.anex['Rnu'] = f2[-3]
            pt.anex['Reu'] = f2[-2]
            tsout.add_point(pt)
        if line[0] == '*':
            header = False
    tsout.boolENU = True
    tsout.meta_set(filein)
    tsout.stat = os.path.basename(filein)[0:4]
    return tsout


def read_sonardyne_attitude(filein):
    reader = pd.read_csv(open(filein),skip_footer=1)

    T = [ dateutil.parser.parse(e) + dt.timedelta(seconds=dUTCGPS) for e in list(reader['PTPTime'])]

    pitch = np.array(reader['Pitch'])
    roll  = np.array(reader['Roll'])
    head  = np.array(reader['Heading'])

    initype = 'FLH'

    AHRS = list(reader['AHRS Id'])
    nbunit = reffram.guess_seq_len(AHRS)
    print("nbre de devices ID : " ,nbunit)
    AHRS = reader['AHRS Id']

    tsout_list = []

    for n in range(nbunit):
        tsout = TimeSerieObs()
        tsout.typeobs = 'RPY'
        tsout_list.append(tsout)

    i = 0
    for p,r,h,t,a in zip(roll,pitch,head,T,AHRS):
        att = Attitude(p,r,h,t,devID=a)
        n = np.mod(i,nbunit)
        tsout_list[n].add_obs(att)
        i=i+1

    for ts in tsout_list:
        ts.meta_set(filein,devID=list(set([e.devID for e in ts.obs])))
        ts.interp_set()

    return tsout_list


def interp_sndy_SYS_UTC(time_conv_file_in):
    timeConv = utils.read_mat_file(time_conv_file_in)
    timeSYS  = timeConv[0,:]
    timeUTC  = timeConv[1,:]
    IntSYSUTC = scipy.interpolate.interp1d(timeSYS,timeUTC,kind='slinear',
                                           bounds_error=0)
    TSout = time_series.TimeSerieObs(time_conv_file_in)

    return IntSYSUTC


def read_sndy_mat_att(filein,IntSYSUTCin=None):
    if IntSYSUTCin == None:
        print("WARN : read_sndy_mat_att : No Interpolator")
    attmat  = utils.read_mat_file(filein)
    Tsys_att = attmat[0,:]
    Tposix_att = IntSYSUTCin(Tsys_att)
#    Tdt_att = np.array(conv.posix2dt(Tposix_att))
    roll  = attmat[1,:]
    pitch = attmat[2,:]
    head  = attmat[3,:]

    TSout = time_series.TimeSerieObs('RPY',filein)

    for r,p,h,t in zip(roll,pitch,head,Tposix_att):
        att = time_series.Attitude(r,p,h,t)
        TSout.add_obs(att)
    return TSout


def read_sndy_mat_nav(filein,IntSYSUTCin=None):
    if IntSYSUTCin == None:
        print("WARN : read_sndy_mat_att : No Interpolator")
    navmat  = utils.read_mat_file(filein)
    Tsys_nav = navmat[0,:]
    Tposix_nav = IntSYSUTCin(Tsys_nav)
#    Tdt_att = np.array(conv.posix2dt(Tposix_att))
    lat = navmat[2,:]
    lon = navmat[3,:]
    h   = navmat[4,:]

    TSout = time_series.TimeSeriePoint()

    for f,l,h,t in zip(lat,lon,h,Tposix_nav):
        pt = time_series.Point(f,l,h,t,initype='FLH')
        TSout.add_point(pt)
    return TSout

def read_hector_neu(filein):
    print("WARN : XYZ/FLH conversion not implemented")
    M = np.loadtxt(filein)
    stat = utils.grep(filein,'Site :',only_first_occur=True).split()[3]
    tsout = time_series.ts_from_list(M[:,2],M[:,1],M[:,3],conv.year_decimal2dt(M[:,0]),
                         'ENU',M[:,4],M[:,5],M[:,6],stat=stat,name=stat)

    return tsout
