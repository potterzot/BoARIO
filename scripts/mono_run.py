import os
import sys
module_path = os.path.abspath(os.path.join('../'))
if module_path not in sys.path:
    sys.path.append(module_path)

module_path = os.path.abspath(os.path.join('./'))
if module_path not in sys.path:
    sys.path.append(module_path)

from ario3.simulation import Simulation
from ario3.indicators import Indicators
from ario3.logging_conf import DEBUGFORMATTER
import json
import pandas as pd
import numpy as np
import pathlib
import csv
import logging
import coloredlogs
import pickle
import argparse
from datetime import datetime

parser = argparse.ArgumentParser(description="Produce indicators from one run folder")
parser.add_argument('region', type=str, help='The region to run')
parser.add_argument('params', type=str, help='The params file')
parser.add_argument('psi', type=str, help='The psi parameter')
parser.add_argument('inv_tau', type=str, help='The inventory restoration parameter')
parser.add_argument('stype', type=str, help='The type (RoW or Full) simulation to run')
parser.add_argument('flood_int', type=str, help='The flood intensity to run')
parser.add_argument('input_dir', type=str, help='The input directory')
parser.add_argument('output_dir', type=str, help='The output directory')
parser.add_argument('flood_gdp_file', type=str, help='The share of gdp impacted according to flood distribution file')
parser.add_argument('event_file', type=str, help='The event template file')
parser.add_argument('mrio_params', type=str, help='The mrio parameters file')

logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] %(name)s %(message)s", datefmt="%H:%M:%S")
scriptLogger = logging.getLogger("generic_run")
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)

scriptLogger.addHandler(consoleHandler)
scriptLogger.setLevel(logging.INFO)
scriptLogger.propagate = False

def run(region, params, psi, inv_tau, stype, flood_int, input_dir, output_dir, flood_gdp_file, event_file, mrio_params):
    with open(params) as f:
        params_template = json.load(f)
    params_template['input_dir'] = input_dir
    params_template['output_dir'] = output_dir
    params_template['mrio_params_file'] = mrio_params
    with open(flood_gdp_file) as f:
        flood_gdp_share = json.load(f)

    with open(event_file) as f:
        event_template = json.load(f)

    if stype == "RoW":
        mrio_path = list(pathlib.Path(input_dir).glob('mrio_'+region+'*.pkl'))
        scriptLogger.info("Trying to load {}".format(mrio_path))
        assert len(mrio_path)==1
        mrio_path = list(mrio_path)[0]
    else:
        mrio_path = pathlib.Path(input_dir+"mrio_full.pkl")

    with mrio_path.open('rb') as f:
        mrio = pickle.load(f)

    value_added = (mrio.x.T - mrio.Z.sum(axis=0))
    value_added = value_added.reindex(sorted(value_added.index), axis=0) #type: ignore
    value_added = value_added.reindex(sorted(value_added.columns), axis=1)
    value_added[value_added < 0] = 0.0
    gdp_df = value_added.groupby('region',axis=1).sum().T['indout']
    gdp_df_pct = gdp_df*1000000
    scriptLogger.info('Done !')
    scriptLogger.info("Main storage dir is : {}".format(pathlib.Path(params_template['output_dir']).resolve()))
    v = flood_gdp_share[region][flood_int]
    dmg = gdp_df_pct[region] * v
    event = event_template.copy()
    sim_params = params_template.copy()
    sim_params['psi_param'] = float(psi.replace("_","."))
    print(sim_params['psi_param'])
    sim_params['inventory_restoration_time'] = inv_tau
    event['r_dmg'] = v
    event['aff-regions'] = region
    event['q_dmg'] = dmg
    sim_params["output_dir"] = output_dir
    sim_params["results_storage"] = region+'_type_'+stype+'_qdmg_'+flood_int+'_Psi_'+psi+"_inv_tau_"+str(sim_params['inventory_restoration_time'])
    model = Simulation(sim_params, mrio_path)
    model.read_events_from_list([event])
    try:
        scriptLogger.info("Model ready, looping")
        model.loop(progress=False)
    except Exception:
        scriptLogger.exception("There was a problem:")

if __name__ == "__main__":
    scriptLogger.info("=============== STARTING RUN ================")
    args = parser.parse_args()
    run(args.region, args.params, args.psi, int(args.inv_tau), args.stype, args.flood_int, args.input_dir, args.output_dir, args.flood_gdp_file, args.event_file, args.mrio_params)