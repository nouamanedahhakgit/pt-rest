import os
import shutil


def delete_contents_in_folders(folder_list):
    for folder_path in folder_list:
        try:
            # التحقق من وجود المجلد
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                # مسح جميع الملفات والمجلدات الفرعية داخل المجلد الأساسي
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)

                    # إذا كان ملفًا، نحذفه
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        print(f"تم حذف الملف: {item_path}")

                    # إذا كان مجلدًا فرعيًا، نحذفه مع جميع محتوياته
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        print(f"تم حذف المجلد الفرعي: {item_path}")

                print(f"📂 تم مسح جميع المحتويات داخل: {folder_path}")
            else:
                print(f"⚠️ المجلد غير موجود: {folder_path}")

        except Exception as e:
            print(f"❌ خطأ أثناء حذف المحتويات داخل {folder_path}: {e}")


# 📌 قائمة المجلدات التي نريد مسح محتوياتها فقط دون حذفها
folder_list = [
    "../Pinterest_01-out",
    "../Pinterest_02-out",
    "../Pinterest_03-out",
    "../Pinterest_04-out",
    "../Pinterest_05-out",
    "../Pinterest_06-out",
    "../Pinterest_07-out",
    "../Pinterest_08-out",
    "../Pinterest_09-out",
    "../Pinterest_10-out",
    "../Pinterest_11-out",
    "../Pinterest_12-out",
    "../Pinterest_13-out",
    "../Pinterest_14-out",
    "../Pinterest_15-out",
    "../Pinterest_16-out",
    "../Pinterest_17-out",
    "../Pinterest_18-out",
    "../Pinterest_19-out",
    "../Pinterest_20-out",
    "../Pinterest_21-out",
    "../Pinterest_22-out",
    "../Pinterest_23-out",
    "../Pinterest_24-out",
    "../Pinterest_25-out",
    "../Pinterest_26-out",
    "../Pinterest_27-out",
    "../Pinterest_28-out",
    "../Pinterest_29-out",
    "../Pinterest_30-out",
    "../Pinterest_31-out",
    "../Pinterest_32-out",
    "../Pinterest_33-out",
    "../Pinterest_34-out",
    "../Pinterest_35-out",
    "../Pinterest_36-out"

]

# 🔄 تشغيل الدالة لمسح جميع المحتويات داخل المجلدات
delete_contents_in_folders(folder_list)
