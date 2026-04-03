from datetime import datetime, timedelta
import os
import json
from pathlib import Path
import sys
from src.acquisition.acquisition import InfluxConfig, run_acquisition
from src.acquisition.endis_api import fetch_consumption_range as get_el_consumption_from_enedis
from src.transform_and_metrics.prix_MWh_elec_TTC import prix_MWh_elec_TTC
from src.transform_and_metrics.prix_MWh_elec_TTC_ENEFFIC import prix_MWh_elec_TTC_ENEFFIC
import numpy as np
import pandas as pd


def get_and_save_site_data_to_csv(startdate):
    # CELL 1: Import Libraries and Configure Project Paths
    # This cell imports all necessary libraries (pandas, numpy, matplotlib) and custom modules
    # for data acquisition, API access, and pricing calculations. It also sets up the project
    # root path to enable proper module imports from the src/ directory.



    # Add project root to sys.path for module imports
    PROJECT_ROOT = Path.cwd()
    sys.path.append(str(PROJECT_ROOT))

    DATA_DIR = PROJECT_ROOT / "data"
    ENEDIS_DIR = DATA_DIR / "ENEDIS"
    SITEDATA_DIR = PROJECT_ROOT / "ResultsData_site"
    PILOTAGE_DIR = PROJECT_ROOT / "ResultsData_pilotage"
    #SITEDATADIR_PILOTAGE = PILOTAGE_DIR / "ResultsData_site"

    startdate_str = startdate.strftime("%Y-%m-%d")
    enddate = startdate + timedelta(days=1)
    enddate_str = enddate.strftime("%Y-%m-%d")
    
    csv_path = DATA_DIR / f"data_AllData_combined_{startdate_str}_to_{enddate_str}.csv"
    csv_output_path = SITEDATA_DIR / f"ResultsTable_{startdate.strftime('%d%b%y').upper()}_site.csv"
    csv_output_path_pilotage = PILOTAGE_DIR / f"ResultsTable_{startdate.strftime('%d%b%y').upper()}_site_ssbsl.csv"
    json_path = ENEDIS_DIR / f"metering_data_{startdate_str}_to_{enddate_str}.json"

    # CELL 2: Data Acquisition from InfluxDB and ENEDIS API
    # This cell handles data import from two sources:
    # 1. System data (temperature, energy, heat pump status) from InfluxDB database
    # 2. Electricity consumption data from ENEDIS API (French grid operator)
    # Both datasets are cached as CSV/JSON files to avoid redundant API calls.
    # ENEDIS data is resampled from 5-minute intervals to hourly aggregations.

    # IMPORT DATA FROM DATABASE AND ENEDIS API
    print(f"Acquisition de données pour la période : {startdate_str} au {enddate_str}")
    # print(f"Fichier de données InfluxDB : {csv_path.name}")
    # print(f"Fichier de données ENEDIS : {json_path.name}")
    print()

    # Import system data from database

    if os.path.exists(csv_path):
        #print(f"Le fichier données existe déjà. Chargement des données existantes...")
        df = pd.read_csv(csv_path)
    else:
        #print(f"Fichier données non trouvé. Lancement de l'acquisition...")
        
        intervals = [{"start_date": startdate_str, "end_date": enddate_str, "description": "Semaine"}]

        result = run_acquisition(
            date_intervals=intervals,
            fields=[
                    "TT_ext", "RH_ext", "price",
                    "dis_mode", "Temp_SC_Charge",
                    "DIS_STS_A_TT1", "DIS_STS_R_TT1",
                    "sharky_energy",
                    "DIS2_CHD_A_TT1", "DIS2_CHD_R_TT1", "Pchd_flow",
                    "DIS_VRD_retour_position_opt", "DIS_CH_A_TT1", "DIS_CH_R_TT1",
                    "DIS_BEL_energy_heating",
                    "PAC1_energy", "PAC2_energy", "SKID_energy",
                    "PAC1_power", "PAC2_power",
                    "PAC1_cond_inlet", "PAC1_cond_outlet", "PAC1_modstatus",
                    "PAC2_cond_inlet", "PAC2_cond_outlet", "PAC2_modstatus",
                    "PAC1_user_pump", "PAC2_user_pump", "PAC1_domestic_pump", "PAC2_domestic_pump",
                    "PAC1_general_alarm2", "PAC2_general_alarm2",
                    "PAC1_DHW_stp", "PAC2_DHW_stp",
                    ],
            use_specific_fields=True,
            output_dir=DATA_DIR,
            query_mode="daily",
            data_step="1m",
            influx=InfluxConfig(),
        )
        
        # Load the newly created file
        df = pd.read_csv(csv_path)
        #print("Acquisition de données terminée et chargée.")

    if os.path.exists(json_path):
        #print(f"Le fichier données ENEDIS existe déjà. Chargement des données existantes...")
        a = 1
    else:
        #print(f"Fichier données ENEDIS non trouvé. Récupération des données depuis ENEDIS...")
        result = get_el_consumption_from_enedis(startdate_str, enddate_str, output_dir=ENEDIS_DIR)
        #print(result["file"])
    # Load the JSON file
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Extract the interval readings
    interval_readings = data['meter_reading']['interval_reading']

    # Or if you want to expand the arrays:
    rows = []
    for reading in interval_readings:
        rows.append({
            'date': reading['date'][0],
            'power_W': int(reading['value'][0]),
            'reactive_VAr': int(reading['value'][1])
        })
    df_enedis = pd.DataFrame(rows)

    df_enedis['el_energy_kWh'] = df_enedis['power_W'] * (5*60/3600) / 1000  # Assuming 5-minute intervals

    df_enedis['date'] = pd.to_datetime(df_enedis['date'])

    df_enedis.set_index('date', inplace=True)

    df_resampled_enedis = df_enedis.resample('h').agg({
        'power_W': 'max',
        'reactive_VAr': 'max',
        'el_energy_kWh': 'sum'
    }).round(2)

    # CELL 3: Data Processing, Metrics Calculation, and Aggregation
    # This cell performs the core data processing pipeline:
    # 1. Fill missing 1-minute data gaps with NaN values (for power outages)
    # 2. Calculate performance metrics: COP (Coefficient of Performance), thermal energy, SPF (Seasonal Performance Factor)
    # 3. Aggregate data from 1-minute to hourly and daily intervals
    # 4. Merge electricity consumption data and calculate costs using French tariff structure
    # 5. Generate daily statistics including temperature ranges, energy consumption, and system performance

    timeStep_hours  = 60/3600

    # Convert _time to datetime and remove timezone awareness
    df['_time'] = pd.to_datetime(df['_time']).dt.tz_convert('Europe/Paris')
    df['_time'] = pd.to_datetime(df['_time']).dt.tz_localize(None)


    # Filter data to keep only dates strictly before enddate
    df = df[df['_time'] < enddate]

    # Set _time as index temporarily
    df = df.set_index('_time')

    # Create a complete datetime index with 1-minute intervals
    full_time_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq='1min')

    # Count missing data points
    original_count = len(df)
    expected_count = len(full_time_index)
    missing_count = expected_count - original_count

    # Reindex to fill gaps with NaN
    df = df.reindex(full_time_index)

    # Reset index to make _time a column again
    df = df.reset_index().rename(columns={'index': '_time'})

    # Print the number of lines added
    print(f"Points de données d'origine : {original_count}")
    print(f"Points de données attendus : {expected_count}")
    print(f"Points de données manquants remplis : {missing_count}")

    # Print sample of added lines (first few NaN rows)
    # Print sample of added lines (first few NaN rows)
    if missing_count > 0:
        nan_rows = df[df.iloc[:, 1:].isnull().all(axis=1)]
        if len(nan_rows) > 0:
            print("\nPoints de données manquants ajoutés à ces horodatages :")
            unique_dates = {}
            for i, (idx, row) in enumerate(nan_rows.iterrows()):
                # Format datetime to Y-m-d h:00:00
                formatted_time = row['_time'].strftime('%Y-%m-%d %H:00:00')
                if formatted_time in unique_dates:
                    unique_dates[formatted_time] += 1
                else:
                    unique_dates[formatted_time] = 1
            
            # Print unique dates sorted with occurrence counts
            for date in sorted(unique_dates.keys()):
                print(f"  {date} ({unique_dates[date]} occurrences)")

    #Add metrics columns
    df['PAC1_HW'] = (df['PAC1_modstatus'] == 14)
    df['PAC1_WW'] = (df['PAC1_modstatus'] == 15)
    df['PAC1_defr'] = (df['PAC1_modstatus'] == 9)

    df['PAC2_HW'] = (df['PAC2_modstatus'] == 14)
    df['PAC2_WW'] = (df['PAC2_modstatus'] == 15)
    df['PAC2_defr'] = (df['PAC2_modstatus'] == 9)


    df['PAC1_th_energy'] = df.apply(lambda row: 1.16 * 14.593 * (row['PAC1_cond_outlet'] - row['PAC1_cond_inlet']) * timeStep_hours if row['PAC1_modstatus'] >= 7 else 0, axis=1)
    ### due to PAC2_modtatus = 13 which means "some alarms are present" the thermal energy will be calculated considerng PAC2_domestic_pump staus and not modstatus. This is because when the domestic pump is on, it means that the system is still trying to operate and provide heating, even if some alarms are present. Therefore, we will consider the thermal energy produced during these periods as well, rather than setting it to zero based on the modstatus alone.
    df['PAC2_th_energy'] = df.apply(lambda row: 1.16 * 14.593 * (row['PAC2_cond_outlet'] - row['PAC2_cond_inlet']) * timeStep_hours if row['PAC2_domestic_pump'] == 1 else 0, axis=1)
    df['CHD_th_energy'] = df.apply(lambda row: max(0, 1.16 * 6.1 * (row['DIS2_CHD_A_TT1'] - row['DIS2_CHD_R_TT1']) * timeStep_hours) if row['Pchd_flow'] > 4 else 0,  axis=1)
    df['COP_PAC1_HW'] = df.apply(lambda row: row['PAC1_HW'] * row['PAC1_th_energy'] / (row['PAC1_power'] * timeStep_hours) if row['PAC1_power'] > 0 else 0, axis=1)
    df['COP_PAC2_HW'] = df.apply(lambda row: row['PAC2_HW'] * row['PAC2_th_energy'] / (row['PAC2_power'] * timeStep_hours) if row['PAC2_power'] > 0 else 0, axis=1)
    df['COP_PAC1_WW'] = df.apply(lambda row: row['PAC1_WW'] * row['PAC1_th_energy'] / (row['PAC1_power'] * timeStep_hours) if row['PAC1_power'] > 0 else 0, axis=1)
    df['COP_PAC2_WW'] = df.apply(lambda row: row['PAC2_WW'] * row['PAC2_th_energy'] / (row['PAC2_power'] * timeStep_hours) if row['PAC2_power'] > 0 else 0, axis=1)

    df['PAC1_th_power'] = df.apply(lambda row: 1.16 * 14.593 * (row['PAC1_cond_outlet'] - row['PAC1_cond_inlet']) if row['PAC1_modstatus'] >= 7 else 0, axis=1)
    ### due to PAC2_modtatus = 13 which means "some alarms are present" the thermal energy will be calculated considerng PAC2_domestic_pump staus and not modstatus. This is because when the domestic pump is on, it means that the system is still trying to operate and provide heating, even if some alarms are present. Therefore, we will consider the thermal energy produced during these periods as well, rather than setting it to zero based on the modstatus alone.
    df['PAC2_th_power'] = df.apply(lambda row: 1.16 * 14.593 * (row['PAC2_cond_outlet'] - row['PAC2_cond_inlet']) if row['PAC2_domestic_pump'] == 1 else 0, axis=1)


    df['recharge'] = (df['dis_mode'] == 3)
    df['decharge'] = (df['dis_mode'] == 2)
    df['direct'] = (df['dis_mode'] == 1)
    df['T_stock'] = (df['recharge'] * df['DIS_STS_R_TT1'] + df['decharge'] * df['DIS_STS_A_TT1'])

    # df['el_power_tot'] = df['el_energy_kWh'] / timeStep_hours
    # df['el_power_PAC'] = (df['PAC1_energy'] + df['PAC2_energy']) / timeStep_hours
    # df['conso_annexe_kW'] = df['el_power_tot'] - df['el_power_PAC']

    # Forward fill price column if it exists
    if 'price' in df.columns:
        df['price'] = df['price'].ffill()

    # Fill T_stock based on dis_mode
    df['T_stock'] = df['T_stock'].replace(0, np.nan)
    # Fill only the first NaN value with the minimum of the two thermal sensors
    if pd.isna(df['T_stock'].iloc[0]):
        df.loc[df.index[0], 'T_stock'] = df[['DIS_STS_R_TT1', 'DIS_STS_A_TT1']].iloc[0].min()
    # Forward fill the entire table
    df['T_stock'] = df['T_stock'].ffill()

    df_resampled = df.set_index('_time')
    # Explicitly infer object types and convert to appropriate dtypes before interpolation
    df_resampled = df_resampled.infer_objects(copy=False)
    # Only interpolate numeric columns to avoid FutureWarning with object dtype
    numeric_cols = df_resampled.select_dtypes(include=[np.number]).columns
    df_resampled[numeric_cols] = df_resampled[numeric_cols].interpolate(method='linear').round(2)

    # Resample df_resampled to hourly aggregations
    hourly_stats = df_resampled[["TT_ext", "RH_ext", "price",
                                "dis_mode", "Temp_SC_Charge",
                                "DIS_STS_A_TT1", "DIS_STS_R_TT1",
                                'recharge', 'decharge', 'T_stock',
                                'sharky_energy', 
                                'PAC1_energy', 'PAC2_energy', 'SKID_energy',
                                'DIS_BEL_energy_heating','CHD_th_energy',
                                'PAC1_user_pump', 'PAC2_user_pump', 'PAC1_domestic_pump', 'PAC2_domestic_pump',
                                'PAC1_th_energy', 'PAC2_th_energy',
                                'PAC1_cond_inlet', 'PAC1_cond_outlet', 'PAC2_cond_inlet', 'PAC2_cond_outlet',
                                'PAC1_DHW_stp', 'PAC2_DHW_stp',
                                ]].resample('h').agg({
                                
        'sharky_energy': lambda x: x.iloc[-1] - x.iloc[0],
        'DIS_BEL_energy_heating': lambda x: x.iloc[-1] - x.iloc[0],
        'CHD_th_energy': 'sum',
        'PAC1_energy': lambda x: x.iloc[-1] - x.iloc[0],
        'PAC2_energy': lambda x: x.iloc[-1] - x.iloc[0],
        'SKID_energy': lambda x: x.iloc[-1] - x.iloc[0],
        'PAC1_user_pump': lambda x: x.sum() * timeStep_hours,
        'PAC2_user_pump': lambda x: x.sum() * timeStep_hours,
        'PAC1_domestic_pump': lambda x: x.sum() * 2.2 * timeStep_hours,
        'PAC2_domestic_pump': lambda x: x.sum() * 2.2 * timeStep_hours,
        'PAC1_th_energy': lambda x: x.sum(),
        'PAC2_th_energy': lambda x: x.sum(),
        'TT_ext': 'mean',
        'RH_ext': 'mean',
        'price': 'mean' ,
        'recharge': ['first', 'mean'],
        'decharge': ['first', 'mean'],
        'Temp_SC_Charge':['first'],
        'T_stock': [lambda x: x.iloc[5] if len(x) > 5 else x.iloc[0], 'last'],
        'PAC1_cond_inlet': 'mean','PAC1_cond_outlet': 'mean', 'PAC2_cond_inlet':'mean', 'PAC2_cond_outlet': 'mean',
        'PAC1_DHW_stp': 'max', 'PAC2_DHW_stp': 'max',

    }).round(2)

    # Flatten column names
    hourly_stats.columns = ['sharky_energy',
        'DIS_BEL_energy_heating',
        'CHD_th_energy',
        'PAC1_energy',
        'PAC2_energy',
        'SKID_energy',
        'PAC1_user_pump',
        'PAC2_user_pump',
        'PAC1_domestic_pump',
        'PAC2_domestic_pump',
        'PAC1_th_energy',
        'PAC2_th_energy',
        'TT_ext',
        'RH_ext',
        'price_mean' ,
        'recharge_first', 'recharge_mean',
        'decharge_first', 'decharge_mean',
        'Temp_SC_Charge_first',
        'T_stock_first', 'T_stock_last',
        'PAC1_cond_inlet', 'PAC1_cond_outlet', 'PAC2_cond_inlet', 'PAC2_cond_outlet',
        'PAC1_DHW_stp', 'PAC2_DHW_stp',
        ]
    #display(hourly_stats)

    # Flatten MultiIndex columns
    #hourly_stats.columns = ['_'.join(col).strip('_') for col in hourly_stats.columns.values]

    # Merge energy_kWh from ENEDIS data
    hourly_stats = hourly_stats.merge(df_resampled_enedis[['el_energy_kWh']], left_index=True, right_index=True, how='left')

    # Some NaN values are present, for now the solution is to fill them through interpolation. 
    # Should be discussed
    hourly_stats = hourly_stats.interpolate(method='linear').round(2)


    hourly_stats.columns.tolist()
    # Apply prix_MWh_elec_TTC function to calculate electricity prices
    # Use prix_MWh_elec_TTC_ENEFFIC for dates after 21/12/2026
    hourly_stats[['el_price_fixed', 'el_price_variable']] = hourly_stats.apply(
    lambda row: pd.Series(
        prix_MWh_elec_TTC_ENEFFIC(row.name, row['price_mean'])
        if row.name >= pd.Timestamp('2025-12-21')
        else prix_MWh_elec_TTC(row.name, row['price_mean']) 
    ), axis=1
    )

    #df_resampled_enedis.to_csv("test.csv")
    hourly_stats['el_price_variable'] = hourly_stats['el_price_variable']/1000
    hourly_stats['el_energy_cost'] = (hourly_stats['el_price_fixed'] + hourly_stats['el_price_variable'] * hourly_stats['el_energy_kWh']).round(2)
    

    # Initialisation du DataFrame de synthèse avec le même index
    df_synthese_visu = pd.DataFrame(index=hourly_stats.index)

    # --- Informations de temps ---
    df_synthese_visu['Heure'] = hourly_stats.index.hour
    #df_synthese_visu['time'] = hourly_stats['_time']

    # --- Températures et Stock ---
    df_synthese_visu['T_ext'] = hourly_stats['TT_ext']
    df_synthese_visu['Tst'] = hourly_stats['T_stock_first']
    # Moyenne des entrées/sorties condenseurs
    df_synthese_visu['Tcond'] = hourly_stats[['PAC1_DHW_stp', 'PAC2_DHW_stp']].max(axis=1)
    df_synthese_visu['Cond_prod'] = -1.6 * hourly_stats['TT_ext'] + 49
    # Calcul de l'énergie stockée (formule : 1.16 * Volume * deltaT)
    df_synthese_visu['S_stock'] = 1.16 * 5 * (hourly_stats['T_stock_first'] - 15)

    # --- Flux et Puissances Thermiques ---
    df_synthese_visu['Q_base'] = hourly_stats['sharky_energy']
    df_synthese_visu['Qdis'] = hourly_stats['decharge_mean'] * hourly_stats['sharky_energy']
    df_synthese_visu['Quse'] = hourly_stats['sharky_energy'] - df_synthese_visu['Qdis']
    df_synthese_visu['Qch'] = hourly_stats['recharge_mean'] * (df_synthese_visu['Q_base'] - hourly_stats['sharky_energy'])
    df_synthese_visu['Qww'] = 0
    df_synthese_visu['Qpin'] = 0

    # --- Mode select ---
    df_synthese_visu['m_pac_ch'] = hourly_stats['recharge_first'].astype(int)
    df_synthese_visu['m_dis'] = hourly_stats['decharge_first'].astype(int)
    df_synthese_visu['m_ww'] = 0

    # --- Puissances Électriques ---
    df_synthese_visu['P_ww'] = 0
    df_synthese_visu['P_pin'] = 0
    df_synthese_visu['Elec_tot'] = hourly_stats['el_energy_kWh']
    df_synthese_visu['Conso'] =  hourly_stats['el_energy_kWh'] * hourly_stats['el_price_variable']


    # --- Cas baseline ---
    df_synthese_visu['P_base'] = 0
    df_synthese_visu['Elec_base'] = 0
    df_synthese_visu['Conso_base'] = 0
    df_synthese_visu['P_chrg'] = df_synthese_visu['Elec_tot'] - df_synthese_visu['Elec_base']
    df_synthese_visu['NegaWatts'] = 0
    df_synthese_visu['Gain_spot'] = 0


    # --- Prix et Gains ---
    df_synthese_visu['EURMWH_SPOT'] = hourly_stats['price_mean']
    df_synthese_visu['EURKWH_variable'] = hourly_stats['el_price_variable']
    df_synthese_visu['Cost_hour'] = hourly_stats['el_energy_cost']

    
    # Reorder columns to match the required format
    column_order = ['Heure', 'T_ext', 'Q_base', 'EURMWH_SPOT', 'EURKWH_variable', 'Tst', 'Tcond', 
                    'Cond_prod', 'S_stock', 'm_pac_ch', 'm_dis', 'm_ww', 'Quse', 'Qdis', 'Qch', 
                    'Qww', 'Qpin', 'P_base', 'P_chrg', 'P_ww', 'P_pin', 'Elec_tot', 'Conso', 
                    'Elec_base', 'Conso_base', 'NegaWatts', 'Gain_spot', 'Cost_hour']

    df_synthese_visu_export = df_synthese_visu[column_order].copy().round(2)
    df_synthese_visu_export.to_csv(csv_output_path, index=False, sep=';')
    df_synthese_visu_export.to_csv(csv_output_path_pilotage, index=False, sep=';')

    print(f"df_synthese_visu sauvegardé dans : {csv_output_path}")
    print(f"df_synthese_visu sauvegardé dans : {csv_output_path_pilotage}")