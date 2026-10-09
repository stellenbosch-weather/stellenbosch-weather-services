#!/usr/bin/env python3
import os
import sys
import csv
import mysql.connector
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings_loader import load_database_settings

if len(sys.argv) < 2:
    print(f"Usage: python3 {sys.argv[0]} <filename.csv>")
    sys.exit(1)

table_name = "SB_TMin"
data_file = sys.argv[1]
db_config = load_database_settings()

def values_match(csv_val, db_val):
    """Helper to compare CSV string values with DB values (handling NULLs and floats)"""
    csv_val = csv_val.strip()
    if csv_val == "NA" or csv_val == "NAN":
        return db_val is None
    if db_val is None:
        return csv_val == "NA" or csv_val == "NAN"

    try:
        # Numerical comparison handles cases like 13.7 vs 13.7000
        return abs(float(csv_val) - float(db_val)) < 1e-7
    except (ValueError, TypeError):
        return str(csv_val) == str(db_val)

def main():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        with open(data_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)

            # Skip line 1 (Site info)
            _ = next(reader)
            # Line 2: The actual field names
            fields = next(reader)
            # Line 3 & 4: Units and Processing info (skip)
            next(reader)
            next(reader)

            # Map field names to DB names
            db_columns = []
            for x in fields:
                x = x.strip()
                if x == "TmStamp": x = "TimeStamp"
                elif x == "RecNum": x = "Record"
                db_columns.append(x)

            countlines = 4
            for row in reader:
                countlines += 1
                if not row or not row[0]:
                    continue

                # Convert CSV format (01/06/2023 00:00:00) to DB format (2023-06-01 00:00:00)
                csv_timestamp = row[0]
                try:
                    dt_obj = datetime.strptime(csv_timestamp, '%d/%m/%Y %H:%M:%S')
                    db_timestamp = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    print(f"Line {countlines}: Invalid timestamp format '{csv_timestamp}'")
                    continue

                # Query database using the converted TimeStamp
                sql = f"SELECT * FROM `{table_name}` WHERE `TimeStamp` = %s"
                cursor.execute(sql, (db_timestamp,))
                db_rows = cursor.fetchall()

                if not db_rows:
                    print(f"Line {countlines}: Record for {db_timestamp} not found in database.")
                else:
                    if len(db_rows) > 1:
                        print(f"Line {countlines}: WARNING! Multiple records ({len(db_rows)}) found for {db_timestamp}.")
                    
                    db_row = db_rows[0]
                    # Compare columns (skipping TmStamp at index 0)
                    for i in range(1, len(db_columns)):
                        col_name = db_columns[i]
                        csv_val = row[i]
                        db_val = db_row.get(col_name)

                        if not values_match(csv_val, db_val):
                            diff_str = ""
                            try:
                                c_float = float(csv_val)
                                d_float = float(db_val)
                                if d_float != 0:
                                    perc = ((c_float - d_float) / abs(d_float)) * 100
                                    diff_str = f" (Diff: {perc:.2f}%)"
                                elif c_float != 0:
                                    diff_str = " (Diff: 100%)"
                            except (ValueError, TypeError):
                                pass

                            print(f"Line {countlines} ({db_timestamp}): Mismatch in {col_name}. "
                                  f"CSV: {csv_val}, DB: {db_val}{diff_str}")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
