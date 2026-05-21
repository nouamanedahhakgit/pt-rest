import pandas as pd
import os

def merge_excel_files(file_paths, output_file):
    """
    Merge specific Excel files (by full path) into one Excel file.
    No extra columns or changes are added.
    Returns the number of successfully merged files.
    """
    dfs = []
    total_files = 0

    for file in file_paths:
        if os.path.exists(file):
            try:
                df = pd.read_excel(file)
                dfs.append(df)
                total_files += 1
            except Exception as e:
                print(f"⚠️ Error reading {file}: {e}")
        else:
            print(f"⚠️ File not found: {file}")

    if dfs:
        merged_df = pd.concat(dfs, ignore_index=True)
        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        merged_df.to_excel(output_file, index=False)

    return total_files  # ⬅️ يرجع عدد الملفات المدموجة


# =========================
# إعداد المسارات
# =========================

BASE = os.path.join(os.path.expanduser("~"), "Desktop", "PINTEREST", "ALL")

# 🔹 المجموعة الأولى
files_group_1 = [
    os.path.join(BASE, "A1-Pinterest_01-out", "Pin_01.xlsx"),
    os.path.join(BASE, "A2-Pinterest_02-out", "Pin_02.xlsx"),
    os.path.join(BASE, "A3-Pinterest_03-out", "Pin_03.xlsx"),
    os.path.join(BASE, "A4-Pinterest_04-out", "Pin_04.xlsx"),
    os.path.join(BASE, "A5-Pinterest_05-out", "Pin_05.xlsx"),
    os.path.join(BASE, "A6-Pinterest_06-out", "Pin_06.xlsx"),
    os.path.join(BASE, "A7-Pinterest_07-out", "Pin_07.xlsx"),
    os.path.join(BASE, "A8-Pinterest_08-out", "Pin_08.xlsx"),
    os.path.join(BASE, "A9-Pinterest_09-out", "Pin_09.xlsx"),
    os.path.join(BASE, "A10-Pinterest_10-out", "Pin_10.xlsx"),
    os.path.join(BASE, "A11-Pinterest_11-out", "Pin_11.xlsx"),
    os.path.join(BASE, "A12-Pinterest_12-out", "Pin_12.xlsx"),
    os.path.join(BASE, "A13-Pinterest_13-out", "Pin_13.xlsx"),
    os.path.join(BASE, "A14-Pinterest_14-out", "Pin_14.xlsx"),
    os.path.join(BASE, "A15-Pinterest_15-out", "Pin_15.xlsx"),
    os.path.join(BASE, "A16-Pinterest_16-out", "Pin_16.xlsx"),
    os.path.join(BASE, "A17-Pinterest_17-out", "Pin_17.xlsx"),
    os.path.join(BASE, "A18-Pinterest_18-out", "Pin_18.xlsx"),
    os.path.join(BASE, "A19-Pinterest_19-out", "Pin_19.xlsx"),
    os.path.join(BASE, "A20-Pinterest_20-out", "Pin_20.xlsx"),
    os.path.join(BASE, "A21-Pinterest_21-out", "Pin_21.xlsx"),
    os.path.join(BASE, "A22-Pinterest_22-out", "Pin_22.xlsx"),
    os.path.join(BASE, "A23-Pinterest_23-out", "Pin_23.xlsx"),
    os.path.join(BASE, "A24-Pinterest_24-out", "Pin_24.xlsx"),
    os.path.join(BASE, "A25-Pinterest_25-out", "Pin_25.xlsx"),
    os.path.join(BASE, "A26-Pinterest_26-out", "Pin_26.xlsx"),
    os.path.join(BASE, "A27-Pinterest_27-out", "Pin_27.xlsx"),
    os.path.join(BASE, "A28-Pinterest_28-out", "Pin_28.xlsx"),
    os.path.join(BASE, "A29-Pinterest_29-out", "Pin_29.xlsx"),
    os.path.join(BASE, "A30-Pinterest_30-out", "Pin_30.xlsx"),
    os.path.join(BASE, "A31-Pinterest_31-out", "Pin_31.xlsx"),
    os.path.join(BASE, "A32-Pinterest_32-out", "Pin_32.xlsx"),
    os.path.join(BASE, "A33-Pinterest_33-out", "Pin_33.xlsx"),
    os.path.join(BASE, "A34-Pinterest_34-out", "Pin_34.xlsx"),
    os.path.join(BASE, "A35-Pinterest_35-out", "Pin_35.xlsx"),
    os.path.join(BASE, "A36-Pinterest_36-out", "Pin_36.xlsx"),
    os.path.join(BASE, "A37-Pinterest_37-out", "Pin_37.xlsx"),
    os.path.join(BASE, "A38-Pinterest_38-out", "Pin_38.xlsx"),
    os.path.join(BASE, "A39-Pinterest_39-out", "Pin_39.xlsx"),
    os.path.join(BASE, "A40-Pinterest_40-out", "Pin_40.xlsx"),
    os.path.join(BASE, "A41-Pinterest_41-out", "Pin_41.xlsx"),
    os.path.join(BASE, "A42-Pinterest_42-out", "Pin_42.xlsx"),
    os.path.join(BASE, "A43-Pinterest_43-out", "Pin_43.xlsx"),
    os.path.join(BASE, "A44-Pinterest_44-out", "Pin_44.xlsx"),
    os.path.join(BASE, "A45-Pinterest_45-out", "Pin_45.xlsx"),
    os.path.join(BASE, "A46-Pinterest_46-out", "Pin_46.xlsx"),
    os.path.join(BASE, "A47-Pinterest_47-out", "Pin_47.xlsx"),
    os.path.join(BASE, "A48-Pinterest_48-out", "Pin_48.xlsx"),
    os.path.join(BASE, "A49-Pinterest_49-out", "Pin_49.xlsx"),
    os.path.join(BASE, "A50-Pinterest_50-out", "Pin_50.xlsx"),
]
output_1 = os.path.join(BASE, "Merge", "print_merged1.xlsx")

# 🔹 المجموعة الثانية
files_group_2 = [
    os.path.join(BASE, "B1-Pinterest_51-out", "Pin_51.xlsx"),
    os.path.join(BASE, "B2-Pinterest_52-out", "Pin_52.xlsx"),
    os.path.join(BASE, "B3-Pinterest_53-out", "Pin_53.xlsx"),
    os.path.join(BASE, "B4-Pinterest_54-out", "Pin_54.xlsx"),
    os.path.join(BASE, "B5-Pinterest_55-out", "Pin_55.xlsx"),
    os.path.join(BASE, "B6-Pinterest_56-out", "Pin_56.xlsx"),
    os.path.join(BASE, "B7-Pinterest_57-out", "Pin_57.xlsx"),
    os.path.join(BASE, "B8-Pinterest_58-out", "Pin_58.xlsx"),
    os.path.join(BASE, "B9-Pinterest_59-out", "Pin_59.xlsx"),
    os.path.join(BASE, "B10-Pinterest_60-out", "Pin_60.xlsx"),
    os.path.join(BASE, "B11-Pinterest_61-out", "Pin_61.xlsx"),
    os.path.join(BASE, "B12-Pinterest_62-out", "Pin_62.xlsx"),
    os.path.join(BASE, "B13-Pinterest_63-out", "Pin_63.xlsx"),
    os.path.join(BASE, "B14-Pinterest_64-out", "Pin_64.xlsx"),
    os.path.join(BASE, "B15-Pinterest_65-out", "Pin_65.xlsx"),
    os.path.join(BASE, "B16-Pinterest_66-out", "Pin_66.xlsx"),
    os.path.join(BASE, "B17-Pinterest_67-out", "Pin_67.xlsx"),
    os.path.join(BASE, "B18-Pinterest_68-out", "Pin_68.xlsx"),
    os.path.join(BASE, "B19-Pinterest_69-out", "Pin_69.xlsx"),
    os.path.join(BASE, "B20-Pinterest_70-out", "Pin_70.xlsx"),
    os.path.join(BASE, "B21-Pinterest_71-out", "Pin_71.xlsx"),
    os.path.join(BASE, "B22-Pinterest_72-out", "Pin_72.xlsx"),
    os.path.join(BASE, "B23-Pinterest_73-out", "Pin_73.xlsx"),
    os.path.join(BASE, "B24-Pinterest_74-out", "Pin_74.xlsx"),
    os.path.join(BASE, "B25-Pinterest_75-out", "Pin_75.xlsx"),
    os.path.join(BASE, "B26-Pinterest_76-out", "Pin_76.xlsx"),
    os.path.join(BASE, "B27-Pinterest_77-out", "Pin_77.xlsx"),
    os.path.join(BASE, "B28-Pinterest_78-out", "Pin_78.xlsx"),
    os.path.join(BASE, "B29-Pinterest_79-out", "Pin_79.xlsx"),
    os.path.join(BASE, "B30-Pinterest_80-out", "Pin_80.xlsx"),
    os.path.join(BASE, "B31-Pinterest_81-out", "Pin_81.xlsx"),
    os.path.join(BASE, "B32-Pinterest_82-out", "Pin_82.xlsx"),
    os.path.join(BASE, "B33-Pinterest_83-out", "Pin_83.xlsx"),
    os.path.join(BASE, "B34-Pinterest_84-out", "Pin_84.xlsx"),
    os.path.join(BASE, "B35-Pinterest_85-out", "Pin_85.xlsx"),
    os.path.join(BASE, "B36-Pinterest_86-out", "Pin_86.xlsx"),
    os.path.join(BASE, "B37-Pinterest_87-out", "Pin_87.xlsx"),
    os.path.join(BASE, "B38-Pinterest_88-out", "Pin_88.xlsx"),
    os.path.join(BASE, "B39-Pinterest_89-out", "Pin_89.xlsx"),
    os.path.join(BASE, "B40-Pinterest_90-out", "Pin_90.xlsx"),
    os.path.join(BASE, "B41-Pinterest_91-out", "Pin_91.xlsx"),
    os.path.join(BASE, "B42-Pinterest_92-out", "Pin_92.xlsx"),
    os.path.join(BASE, "B43-Pinterest_93-out", "Pin_93.xlsx"),
    os.path.join(BASE, "B44-Pinterest_94-out", "Pin_94.xlsx"),
    os.path.join(BASE, "B45-Pinterest_95-out", "Pin_95.xlsx"),
    os.path.join(BASE, "B46-Pinterest_96-out", "Pin_96.xlsx"),
    os.path.join(BASE, "B47-Pinterest_97-out", "Pin_97.xlsx"),
    os.path.join(BASE, "B48-Pinterest_98-out", "Pin_98.xlsx"),
    os.path.join(BASE, "B49-Pinterest_99-out", "Pin_99.xlsx"),
    os.path.join(BASE, "B50-Pinterest_100-out", "Pin_100.xlsx"),
]
output_2 = os.path.join(BASE, "Merge", "print_merged2.xlsx")

# =========================
# 🚀 التشغيل
# =========================
merged_A = merge_excel_files(files_group_1, output_1)
merged_B = merge_excel_files(files_group_2, output_2)

total_merged_all = merged_A + merged_B

# 🟩 آخر 3 سطور فقط فالكونسول
print()
print(f"✅ Merged {merged_A} files into '{output_1}'.")
print(f"✅ Merged {merged_B} files into '{output_2}'.")
print(f"📊 Total merged projects: {total_merged_all}")
