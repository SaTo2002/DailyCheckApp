# ==============================================================================
# ملف الامتدادات والإعدادات الثابتة المشتركة (extensions.py)
# يحتوي على كائن قاعدة البيانات والمجلدات الثابتة والتشفيرات الرئيسية
# ==============================================================================

import os
from flask_sqlalchemy import SQLAlchemy

# 1. إنشاء كائن قاعدة البيانات الوحيد لمنع التعارضات الدائرية (Circular Imports)
db = SQLAlchemy()

# 2. إعداد مجلد المرفقات والصور المرفوعة من قبل المونيتورز والأدمن
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 3. الباسورد المشفّر للـ Master Admin الرئيسي (يُقرأ من ملف .env أو النواة الاحتياطية)
MASTER_ADMIN_HASH = os.getenv(
    'MASTER_ADMIN_HASH',
    'scrypt:32768:8:1$o2sRQJ3CVeIvLBFk$630226ad3aa44801001362c89ca76753c7ae6900c4f8395cbe90cf89a657dd6d544988584d0ab9e667571be840294f8290e4c87cb47d5d4f6a2acb0075e2bb1e'
)
