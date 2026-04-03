if __name__ == "__main__":

    import pandas as pd
    from pathlib import Path
    import sys

    SCRIPT_DIR = Path.cwd()
    PROJECT_ROOT = SCRIPT_DIR
    sys.path.append(str(SCRIPT_DIR))

    from datetime import datetime, timedelta

    startdate = pd.Timestamp("2026-03-27")
    enddate   = pd.Timestamp("2026-04-02")
    nowdate = pd.Timestamp.now().normalize()

    startdate_str = startdate.strftime("%Y-%m-%d")
    enddate_str   = enddate.strftime("%Y-%m-%d")
    nowdate_str   = nowdate.strftime("%Y-%m-%d")

    DATA_DIR = PROJECT_ROOT / "data"
    SITEDATA_DIR = PROJECT_ROOT / "ResultsData_site"
    JUMEAUNUM_DATA_DIR = PROJECT_ROOT / "ResultsData_jumeau_num"
    PILOTAGE_DIR = PROJECT_ROOT.parent
    SITEDATADIR_PILOTAGE = PROJECT_ROOT / "ResultsData_pilotage"

    # Add project root to sys.path for module imports
    current_date = startdate
    while current_date <= enddate:
        site_file = SITEDATA_DIR / f"ResultsTable_{current_date.strftime('%d%b%y').upper()}_site.csv"
        jumeaunum_ref_site_file = JUMEAUNUM_DATA_DIR / f"ResultsTable_{current_date.strftime('%d%b%y').upper()}_JN_ref_SITE.csv"
        csv_output_path = SITEDATA_DIR / f"ResultsTable_{current_date.strftime('%d%b%y').upper()}_site.csv"
        csv_output_path_pilotage_delete = SITEDATADIR_PILOTAGE / f"ResultsTable_{current_date.strftime('%d%b%y').upper()}_site_ssbsl.csv"
        csv_output_path_pilotage = SITEDATADIR_PILOTAGE / f"ResultsTable_{current_date.strftime('%d%b%y').upper()}_site.csv"

        
        if site_file.exists() and jumeaunum_ref_site_file.exists():
            df_synthese_visu = pd.read_csv(site_file, sep=';')
            df_jn_ref_site = pd.read_csv(jumeaunum_ref_site_file, sep=';')
            
            df_synthese_visu["P_base"] = df_jn_ref_site["P_base"].round(2)
            df_synthese_visu["Elec_base"] = df_jn_ref_site["Elec_base"].round(2)
            df_synthese_visu["Conso_base"] = df_jn_ref_site["Conso_base"].round(2)
            df_synthese_visu["NegaWatts"] = 0 + (
                (df_synthese_visu["m_dis"] == 1) * 
                (df_synthese_visu["Elec_base"] - df_synthese_visu["Elec_tot"])).round(2)
            df_synthese_visu["Gain_spot"] = 0 + (df_synthese_visu["NegaWatts"] * df_synthese_visu["EURKWH_variable"]).round(2)
            df_synthese_visu["P_chrg"] = 0 + (
                (df_synthese_visu["m_pac_ch"] == 1) * 
                (df_synthese_visu["Elec_tot"] - df_synthese_visu["Elec_base"])).round(2)

            column_order = ['Heure', 'T_ext', 'Q_base', 'EURMWH_SPOT', 'EURKWH_variable', 'Tst', 'Tcond', 
                    'Cond_prod', 'S_stock', 'm_pac_ch', 'm_dis', 'm_ww', 'Quse', 'Qdis', 'Qch', 
                    'Qww', 'Qpin', 'P_base', 'P_chrg', 'P_ww', 'P_pin', 'Elec_tot', 'Conso', 
                    'Elec_base', 'Conso_base', 'NegaWatts', 'Gain_spot', 'Cost_hour']
            
            df_synthese_visu_export = df_synthese_visu[column_order].copy()
            df_synthese_visu_export.to_csv(csv_output_path, float_format='%.2f',
                                           index=False, sep=';')
            df_synthese_visu_export.to_csv(csv_output_path_pilotage, float_format='%.2f',
                                           index=False, sep=';')
            
            if csv_output_path_pilotage.exists() and csv_output_path_pilotage_delete.exists():
                csv_output_path_pilotage_delete.unlink()
            
        else: 
            print(f"Warning: Missing file for date {current_date.strftime('%d%b%y').upper()}. Skipping.")
        # 4. Increment by 1 day
        current_date += timedelta(days=1)




        
