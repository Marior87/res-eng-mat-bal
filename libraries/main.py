#import libraries.initialising as init
import libraries.iterations as itera
import libraries.matbal as mb
import plotly
import json
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit



def matbal_run2(dict_tank, df_prod, dict_pvtmaster, df_pvt_oil, df_pvt_gas, regress, regress_config=None):
    #####Material Balance
    data_dict = {
        'df_prod': df_prod,
        'dict_pvtmaster': dict_pvtmaster,
        'df_pvt_oil': df_pvt_oil,
        'df_pvt_gas': df_pvt_gas,
        'dict_tank': dict_tank
    }

    df_prod = data_dict['df_prod']
    # Pres_calc, ts_obs, reservoir_pressure_obs, ts = eval_mbal_input2(data_dict)
    DDI = [None] * len(df_prod['np'])
    SDI = [None] * len(df_prod['np'])
    WDI = [None] * len(df_prod['np'])
    CDI = [None] * len(df_prod['np'])
    if regress is False:
        Pres_calc, ts_obs, reservoir_pressure_obs, ts = itera.eval_mbal_input2(data_dict)
    else:
        popt, sd = mbal_fit(data_dict)
        dict_tank['initial_inplace'][0] = popt[0]
        dict_tank['wei'][0] = popt[1]
        dict_tank['J'][0] = popt[2]
        data_dict['dict_tank'] = dict_tank
        Pres_calc, ts_obs, reservoir_pressure_obs, ts = itera.eval_mbal_input2(data_dict)

    data_dict['Pres_calc'] = Pres_calc
    DDI, SDI, WDI, CDI = drive_indices(data_dict)
    # plot = match_plot(ts, Pres_calc, ts_obs, reservoir_pressure_obs)
    return ts, Pres_calc, ts_obs, reservoir_pressure_obs, DDI, SDI, WDI, CDI, \
        dict_tank['initial_inplace'], dict_tank['wei'], dict_tank['J']


def match_plot(ts, Pres_calc, ts_obs, reservoir_pressure_obs):
    dataseries = []
    act1 = dict(
        name='Observed Data',
        # fill='tozeroy',
        # stackgaps='infer zero',
        # orientation = 'vertical',
        mode='line',
        type='scatter',
        x=Pres_calc,
        y=ts,
        # stackgroup='one',
    )
    act2 = dict(
        name='Calculated Data',
        # fill='tozeroy',
        # stackgaps='infer zero',
        # orientation = 'vertical',
        mode='line',
        type='scatter',
        x=reservoir_pressure_obs,
        y=ts_obs,
        # stackgroup='one',
    )
    dataseries.append(act1)
    dataseries.append(act2)
    graphs = [
        dict(
            data=dataseries
        )
    ]

    graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)

    # forecast_kpi = pd.DataFrame(rows_list)

    # df_json = forecast_kpi.to_json(orient='records')
    # data = {'graphJSON': graphJSON}
    return graphJSON


def drive_indices(dict):

    df_prod = dict['df_prod']
    dict_tank = dict['dict_tank']
    dict_pvtmaster = dict['dict_pvtmaster']
    df_pvt_gas = dict['df_pvt_gas']
    df_pvt_oil = dict['df_pvt_oil']

    dates = df_prod['datestamp']
    ts = pd.to_numeric(dates - df_prod['datestamp'].min()) / 864e11
    Np = df_prod['np']
    Gp = df_prod['gp']
    # Gp = Gp * 1000.0
    Wp = df_prod['wp']
    reservoir_pressure_obs = df_prod['pressure']
    ts_obs = ts[reservoir_pressure_obs.notnull()]
    Pres_calc = dict['Pres_calc']
    reservoir_pressure_obs = reservoir_pressure_obs[reservoir_pressure_obs.notnull()]
    reservoir_pressure_obs = reservoir_pressure_obs * 1.0
    N = float(dict_tank['initial_inplace'])
    Wei = float(dict_tank['wei'])
    Swi = float(dict_tank['swi'])
    cw = float(dict_tank['cw'])
    cf = float(dict_tank['cf'])
    # N = 1.00E+07
    # Wei = 5.00E+07
    J = float(dict_tank['J'])
    m = float(dict_tank['initial_gascap'])
    # We = 0
    Winj = df_prod['wi']
    Winj = Winj.fillna(0)
    Ginj = df_prod['gi']
    Ginj = Ginj.fillna(0)
    We = [None] * len(Np)
    We[0] = 0
    #####General PVT
    # Tsc = 60  # F
    # Psc = 15.025  # psia
    # Tres = 219  # F
    # Pbp = df_pvtmaster['sat_press']  # psia
    Rsi = dict_pvtmaster['gor']  # scf/stb

    Pi = float(dict_tank['initial_pressure'])
    Boi = np.interp(Pi, df_pvt_oil['pressure'], df_pvt_oil['oil_fvf'])
    Bgi = np.interp(Pi, df_pvt_gas['pressure'], df_pvt_gas['gas_fvf']) / 1000
    Rsb = dict_pvtmaster['gor']
    Bti = mb.formation_total_volume_factor(Boi, Bgi, Rsb, Rsi)
    #####Water PVT
    Bw = 1.0  # dict_tank['Bw']
    Bwinj = 1.0
    #####Oil PVT
    pvt_oil_pressure = df_pvt_oil['pressure']
    pvt_oil_Bo = df_pvt_oil['oil_fvf']
    pvt_oil_Rs = df_pvt_oil['solution_gas']
    #####Gas PVT
    pvt_gas_pressure = df_pvt_gas['pressure']
    pvt_gas_Bg = df_pvt_gas['gas_fvf']
    pvt_gas_Bg = pvt_gas_Bg / 1000
    arr = np.array(pvt_oil_pressure)
    interpol = lambda P: np.interp(P, pvt_gas_pressure, pvt_gas_Bg)
    pvt_oil_Bg = interpol(arr)
    # pvt_oil_Bg = np.interp(P, pvt_gas_pressure, pvt_gas_Bg)

    aquifer_pres = [None] * len(Np)
    aquifer_pres[0] = Pi
    Pres_calc_empty = [None] * len(Np)
    DDI = [None] * len(Np)
    SDI = [None] * len(Np)
    WDI = [None] * len(Np)
    CDI = [None] * len(Np)

    for x in range(len(Np)):
        if x == 0:
            DDI[x] = 0
            SDI[x] = 0
            WDI[x] = 0
            CDI[x] = 0
        else:
            P = Pres_calc[x]
            Bo = np.interp(P, pvt_oil_pressure, pvt_oil_Bo)

            Bg = np.interp(P, pvt_oil_pressure, pvt_oil_Bg)
            Bginj = Bg
            Rs = np.interp(P, pvt_oil_pressure, pvt_oil_Rs)
            Bt = mb.formation_total_volume_factor(Bo, Bg, Rsb, Rs)
            Eo = mb.dissolved_oil_and_gas_expansion(Bt, Bti)
            Eg2 = mb.gas_cap_expansion2(Bti, Bg, Bgi)
            Eg = mb.gas_cap_expansion(Bti, Bg, Bgi)
            dP = Pi - P
            Efw = mb.pore_volume_reduction_connate_water_expansion(m, Boi, cw, Swi, cf, dP)
            F, produced_oil_and_gas, produced_water, injected_gas, injected_water = \
                mb.production_injection_balance(Np[x],Bt, Rs, Rsi, Bg, Wp[x], Bw, Winj[x], Bwinj, Ginj[x], Bginj, Gp[x])
            Wex, aq_pres = itera.aquifer_influx(x, P, Wei, We, ts, Pres_calc, Pi, J, aquifer_pres)
            We[x] = Wex
            aquifer_pres[x] = aq_pres

            Ncalc = mb.oil_in_place(F, Eo, m, Eg, Efw, We[x], Bw, Bti)
            DDI[x] = Ncalc * Eo / F
            SDI[x] = Ncalc * m * Eg2 * (Boi / Bgi) / F
            WDI[x] = (We[x] * Bw - Wp[x] * Bw) / F
            CDI[x] = Ncalc * (1 + m) * Efw * Boi / F
            # of = (N - Ncalc)


    return DDI, SDI, WDI, CDI


def mbal_fit(dict):
    def fit_mbal_input(ts_obs, N, Wei, J):
        Pres_calc2 = []
        # Pres_calc.clear()
        dict_tank = dict['dict_tank']
        dict_tank['initial_inplace'][0] = N
        dict_tank['wei'][0] = Wei
        dict_tank['J'][0] = J
        dict['dict_tank'] = dict_tank
        Pres_calc2, ts_obs, reservoir_pressure_obs, ts = mb.eval_mbal_input2(dict)
        Pres_calc_obs = []
        ts_obs_vals = ts_obs.values
        for x in range(len(ts_obs_vals)):
            Pres_calc_obs.append(np.interp(ts_obs_vals[x], ts, Pres_calc2))
        return Pres_calc_obs

    df_prod = dict['df_prod']
    dates = df_prod['datestamp']
    ts = pd.to_numeric(dates - df_prod['datestamp'].min()) / 864e11
    reservoir_pressure_obs = df_prod['pressure']
    ts_obs = ts[reservoir_pressure_obs.notnull()]
    reservoir_pressure_obs = reservoir_pressure_obs[reservoir_pressure_obs.notnull()]
    reservoir_pressure_obs = reservoir_pressure_obs * 1.0
    popt, pcov = curve_fit(fit_mbal_input, ts_obs, reservoir_pressure_obs, bounds=([1E6, 0.00001, 0.0001], [1E9, 10E9, 10.0]))
    sd = np.sqrt(np.diag(pcov))
    return popt, sd




# def mbal_run_simulation():
#     regress = False
#     regress_config = None
#     instance_tank = dict(request.POST.lists())
#     prod_fk = instance_tank['production_fk'][0]
#     pvt_fk = instance_tank['pvt_fk'][0]
#     # aqu_fk = instance_tank['aquifer_fk']
#
#     instance_prod = ProductionDataSet_MatBal.objects.filter(definition_fk=prod_fk)
#     instance_pvt_o = Pvt_table_oil.objects.filter(definition_table=pvt_fk)
#     instance_pvt_g = Pvt_Table_Gas.objects.filter(definition_table=pvt_fk)
#     instance_pvt_master = PvtMaster.objects.get(pk=pvt_fk)
#     # instance_aquifer = AquiferMaster.objects.get(pk=aqu_fk)
#
#     df_prod = pd.DataFrame(read_frame(instance_prod))
#     df_pvt_o = pd.DataFrame(read_frame(instance_pvt_o))
#     df_pvt_g = pd.DataFrame(read_frame(instance_pvt_g))
#     # df_tank_master = pd.DataFrame(read_frame(instance_tank))
#     # df_pvt_master = pd.DataFrame(read_frame(instance_pvt_master))
#     regress_config = {}
#     list_regress = ['initial_inplace_regress', 'aquifer_size_regress', 'aquifer_pi_regress']
#     for var in list_regress:
#         try:
#             regress_config[var] = instance_tank[var][0]
#             regress = True
#         except:
#             pass
#
#     #regress = True
#     ts, Pres_calc, ts_obs, reservoir_pressure_obs, DDI, SDI, WDI, CDI, N, Wei, J = mbal2.matbal_run2(instance_tank, df_prod,
#                             instance_pvt_master, df_pvt_o, df_pvt_g, regress, regress_config)
#
#     return ts, Pres_calc, ts_obs, reservoir_pressure_obs, DDI, SDI, WDI, CDI, N, Wei, J
#
# if __name__ == 'main':
#     mbal_run_simulation()