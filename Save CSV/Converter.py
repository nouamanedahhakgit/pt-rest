import pandas as pd
import os
from urllib.parse import unquote
import html

def _clean(val):
    if isinstance(val, str):
        val = unquote(val)
        val = html.unescape(val)
        return val.strip()
    return val

def convert_xlsx_to_csv(file_list, output_folder):

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for input_file in file_list:

        file_name = os.path.basename(input_file)
        output_file = os.path.join(output_folder, file_name.replace(".xlsx", ".csv"))

        try:

            df = pd.read_excel(input_file, engine="openpyxl")

            # تنظيف جميع الأعمدة ماعدا Board
            for col in df.columns:
                if col.lower() != "board" and df[col].dtype == object:
                    df[col] = df[col].apply(_clean)

            df.to_csv(output_file, index=False, encoding="utf-8-sig")

            print(f"✅ تم تحويل {input_file} إلى {output_file}")

        except Exception as e:
            print(f"⚠️ خطأ أثناء تحويل {input_file}: {e}")

file_list = [
    r"../ALL/Merge/print_merged1.xlsx",
    r"../ALL/Merge/print_merged2.xlsx"
]

output_folder = "./Converted_Csv"

convert_xlsx_to_csv(file_list, output_folder)