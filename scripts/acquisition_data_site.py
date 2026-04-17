if __name__ == "__main__":

    import pandas as pd
    from pathlib import Path
    import sys

    SCRIPT_DIR = Path.cwd()
    PROJECT_ROOT = SCRIPT_DIR.parent
    sys.path.append(str(SCRIPT_DIR))

    from src.acquisition.get_and_save_site_data_to_csv import get_and_save_site_data_to_csv
    from datetime import datetime, timedelta

    startdate = pd.Timestamp("2026-04-08")
    enddate   = pd.Timestamp("2026-04-09")
    nowdate = pd.Timestamp.now().normalize()

    startdate_str = startdate.strftime("%Y-%m-%d")
    enddate_str   = enddate.strftime("%Y-%m-%d")
    nowdate_str   = nowdate.strftime("%Y-%m-%d")

    # Add project root to sys.path for module imports
    current_date = startdate
    while current_date <= enddate:
        # 3. Format it using the 11FEB2026 style
        print(current_date.strftime('%d%b%Y').upper())
        get_and_save_site_data_to_csv(current_date)

        # 4. Increment by 1 day
        current_date += timedelta(days=1)

        
