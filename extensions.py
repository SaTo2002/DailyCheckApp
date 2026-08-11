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

# 3. الباسورد المشفّر للـ Master Admin الرئيسي (يُقرأ من ملف .env فقط — لا يُكتب في الكود أبداً)
MASTER_ADMIN_HASH = os.getenv('MASTER_ADMIN_HASH')
if not MASTER_ADMIN_HASH:
    raise RuntimeError("❌ MASTER_ADMIN_HASH is missing from .env file! The app cannot start without it.")

