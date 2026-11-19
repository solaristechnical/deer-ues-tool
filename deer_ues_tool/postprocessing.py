'''
Description: This script will run the SQL files and perform calculations used in the DEER-EnergyPlus Models post-processing steps,
             effectively expediting the SQL and energy savings workbook steps.
Author: Kelsey Yen, Solaris Technical LLC
Date: 10-01-2025
'''
'''
Revision Log:
10-21-2025 - converted simdata from wide to long table
11-05-2025 - added calculated columns to simdata input file for SQL queries
11-11-2025 - added weighted Com SQL queries
11-13-2025 - created Res SQLs
11-20-2025 - updated Res SQLs and applied changes to Com SQLs
01-14-2026 - updated script with terminal user inputs for future UI development
02-19-2026 - removed excess simdata files from being written and simplified normunits function
02-25-2026 - added lookup table files and functions
11-19-2026 - revised input from csv to long table
'''

import pandas as pd
import sqlite3
import io

try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import files

def load_simdata_long(Simdata_file, peak_version="CZ2025"):
    """
    Read simdata.sqlite and combine simulation metadata, annual results,
    and DEER peak results into one long-format DataFrame.
    """

    with sqlite3.connect(Simdata_file) as connection:

        # Annual/query results
        df_sim = pd.read_sql_query(
            """
            SELECT
                m.simID,
                m.BldgLoc,
                m.BldgType,
                m.Story,
                m.BldgHVAC,
                m.BldgVint,
                m.TechGroup,
                m.TechType,
                m.TechID,
                d.VarName AS "Value Name",
                d.Value AS Value
            FROM sim_metadata AS m
            INNER JOIN sim_data AS d
                ON m.simID = d.simID
            """,
            connection
        )

        # DEER peak results
        df_peak = pd.read_sql_query(
            """
            SELECT
                m.simID,
                m.BldgLoc,
                m.BldgType,
                m.Story,
                m.BldgHVAC,
                m.BldgVint,
                m.TechGroup,
                m.TechType,
                m.TechID,
                p.VarName AS "Value Name",
                p.Version,
                p.PeakDemand_kW AS Value
            FROM sim_metadata AS m
            INNER JOIN sim_deerpeak AS p
                ON m.simID = p.simID
            WHERE p.Version = ?
            """,
            connection,
            params=(peak_version,)
        )

    return df_sim, df_peak


def postprocessing(
    Measure_name,
    Measure_type,
    Sector,
    Norm_unit,
    Simdata_file,
    MeasDef_file,
    BT_option
):

    # ============================================================
    # UNIT CONVERSIONS
    # ============================================================
    kWh_to_therms = 0.0341295763495688

    # ============================================================
    # READ SIMDATA.SQLITE
    # ============================================================
    df_simdata, df_deerpeak = load_simdata_long(
        Simdata_file=Simdata_file,
        peak_version="CZ2025"
    )

    # Make sure the stored result values are numeric.
    df_simdata["Value"] = pd.to_numeric(
        df_simdata["Value"],
        errors="coerce"
    )

    df_deerpeak["PeakDemand_kW"] = pd.to_numeric(
        df_deerpeak["PeakDemand_kW"],
        errors="coerce"
    )

    # Identify one simulation.
    id_columns = [
        "simID",
        "BldgLoc",
        "BldgType",
        "Story",
        "BldgHVAC",
        "BldgVint",
        "TechGroup",
        "TechType",
        "TechID"
    ]

    # Assign user selected norm unit name
    df['MeasureName'] = Measure_name
    df['NormUnit'] = Norm_unit
    df['MeasureType'] = Measure_type

    # Convert revised simdata to long format
    df_long = pd.melt(df, id_vars = ["MeasureName", "MeasureType", "BldgLoc", "BldgType", "Story", "BldgHVAC" ,
                                        "BldgVint", "TechGroup", "TechType", "TechID","NormUnit"], var_name = "Value Name", value_name = "Value")

    print("simdata processed")

    # Connect to the database (or create it if it doesn't exist) 
    connection = sqlite3.connect('postprocessing.db')

    # Create a cursor object 
    cursor = connection.cursor()

    # Read in lookup tables and simdata to database
    df_long.to_sql('simdata', connection, if_exists="replace", index=False)

    df_measdef = pd.read_csv(MeasDef_file)
    df_measdef.to_sql('MeasDef', connection, if_exists="replace",index=False)

    df_numstor = pd.read_csv(io.StringIO(files('deer_ues_tool.lookup').joinpath('NumStor.csv').read_text()))
    df_numstor.to_sql('NumStor', connection, if_exists="replace",index=False)

    df_normunits = pd.read_csv(io.StringIO(files('deer_ues_tool.lookup').joinpath('NormUnits.csv').read_text()))
    df_normunits.to_sql('NormUnits', connection, if_exists="replace",index=False)

    # Read the SQL script 
    if Sector == "Residential":
        df_res = pd.read_csv(io.StringIO(files('deer_ues_tool.lookup').joinpath('wts_res_bldg.csv').read_text()))
        df_res.to_sql('wts_res_bldg', connection, if_exists="replace")

        try:
            # Condition for using Norm unit lookup table
            if Measure_type in ["Wall Insulation", "Ceiling Insulation", "Refrigerator/Freezer", "PTAC/PTHP", "WholeHouseFan"]:
                sql_script = files('deer_ues_tool.residential').joinpath('NormUnitLookup.sql').read_text()
                cursor.executescript(sql_script)
                print("Norm units lookup script executed successfully.")
            else: 
                sql_script = files('deer_ues_tool.residential').joinpath('NormUnit.sql').read_text()
                cursor.executescript(sql_script)
                print("Norm units script executed successfully.")
                
            sql_script = files('deer_ues_tool.residential').joinpath('Story_Wts.sql').read_text()
            cursor.executescript(sql_script)
            print("Story_Wts executed successfully.")
            
            sql_script = files('deer_ues_tool.residential').joinpath('Permutations.sql').read_text()
            cursor.executescript(sql_script)
            print("Permutations script executed successfully.")

            sql_script = files('deer_ues_tool.residential').joinpath('UEC.sql').read_text()
            cursor.executescript(sql_script)
            print("UEC script executed successfully.")

            sql_script = files('deer_ues_tool.residential').joinpath('UES.sql').read_text()
            cursor.executescript(sql_script)
            print("UES script executed successfully.")

            if BT_option == True:
                sql_script = files('deer_ues_tool.residential').joinpath('Bldg_Wts.sql').read_text()
                cursor.executescript(sql_script)
                print("Bldg_Wts script executed successfully.")

                sql_script = files('deer_ues_tool.residential').joinpath('Res.sql').read_text()
                cursor.executescript(sql_script)
                print("Res script executed successfully.")

        except sqlite3.Error as e: 
            print(f"An error occurred: {e}")

    elif Sector == "Commercial":
        df_com = pd.read_csv(io.StringIO(files('deer_ues_tool.lookup').joinpath('wts_com_bldg_2026.csv').read_text()))
        df_com.to_sql('wts_com_bldg_2026', connection, if_exists="replace")

        try:     
            sql_script = files('deer_ues_tool.commercial').joinpath('Permutations.sql').read_text()
            cursor.executescript(sql_script)
            print("Permutations script executed successfully.")
            # Condition for using Norm unit lookup table
            if Norm_unit == "Area-ft2-BA":
                sql_script = files('deer_ues_tool.commercial').joinpath('NormUnitLookUp.sql').read_text()
                cursor.executescript(sql_script)
                print("Norm units lookup script executed successfully.")
            else: 
                sql_script = files('deer_ues_tool.commercial').joinpath('NormUnit.sql').read_text()
                cursor.executescript(sql_script)
                print("Norm units script executed successfully.")

            sql_script = files('deer_ues_tool.commercial').joinpath('UEC.sql').read_text()
            cursor.executescript(sql_script)
            print("UEC script executed successfully.")

            sql_script = files('deer_ues_tool.commercial').joinpath('UES.sql').read_text()
            cursor.executescript(sql_script)
            print("UES script executed successfully.")

            if BT_option == True:
                sql_script = files('deer_ues_tool.commercial').joinpath('Bldg_Wts.sql').read_text()
                cursor.executescript(sql_script)
                print("Bldg_Wts script executed successfully.")

                sql_script = files('deer_ues_tool.commercial').joinpath('Com.sql').read_text()
                cursor.executescript(sql_script)
                print("Com script executed successfully.")

        except sqlite3.Error as e: 
            print(f"An error occurred: {e}")

    # Output results as csv
    df_output = pd.read_sql_query(f"SELECT * FROM {'UES'}", connection)
    df_output.to_csv(f'energysavings_{Measure_name}.csv', index=False)
    print(f"Savings calcs completed for {Measure_name}.")

    # Commit changes and close the connection 
    connection.commit()
    connection.close()
