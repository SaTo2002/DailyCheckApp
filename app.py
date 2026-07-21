# ==============================================================================
# الملف الرئيسي لتشغيل تطبيق Flask (DailyCheckApp)
# المصمم لإدارة الفحوصات اليومية للمناطق والألعاب
# ==============================================================================

import os
from flask import Flask
from dotenv import load_dotenv
from sqlalchemy import text

# استدعاء كائن قاعدة البيانات الامتدادي والماكينات
from extensions import db
from models import User, Area, GameModel, GameReport

# استدعاء الـ Blueprints مباشرة من حزمة المسارات (routes)
from routes import monitor_bp, admin_bp, manage_bp

# 1. تحميل متغيرات البيئة من ملف .env
load_dotenv()

# 2. إنشاء وتكوين تطبيق فلاسك
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'gravity_code_secret_key_fallback')

# إعدادات الاتصال بقاعدة بيانات MySQL
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. ربط قاعدة البيانات بتطبيق فلاسك
db.init_app(app)

# 4. تسجيل الـ Blueprints (تقسيم المسارات برمجياً)
app.register_blueprint(monitor_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manage_bp)

# 5. تهيئة جداول قاعدة البيانات والترحيل التلقائي للأعمدة الجديدة (Migrations)
with app.app_context():
    # إنشاء الجداول الأساسية إن لم تكن موجودة
    db.create_all()
    
    # فحص وإضافة أعمدة الصلاحيات الجديدة لجداول المستخدمين إن لم تكن موجودة
    for col, default_val in [('can_manage_system', 0), ('can_manage_areas', 0), ('can_manage_games', 0), ('can_view_reports', 1)]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} TINYINT(1) DEFAULT {default_val}"))
                conn.commit()
        except Exception:
            pass  # العمود موجود بالفعل
            
    # فحص وإضافة عمود ترتيب الألعاب (sort_order) لجداول الألعاب إن لم يكن موجوداً
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE games ADD COLUMN sort_order INT DEFAULT 0"))
            conn.commit()
    except Exception:
        pass  # العمود موجود بالفعل

    # فحص وإضافة عمود ترتيب المناطق (sort_order) لجداول المناطق إن لم يكن موجوداً
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE areas ADD COLUMN sort_order INT DEFAULT 0"))
            conn.commit()
    except Exception:
        pass  # العمود موجود بالفعل

    # فحص وإضافة عمود صورة المنطقة (image) لجداول المناطق إن لم يكن موجوداً
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE areas ADD COLUMN image VARCHAR(255) DEFAULT NULL"))
            conn.commit()
    except Exception:
        pass  # العمود موجود بالفعل

# 6. نقطة الانطلاق والتشغيل الخادم المحلي
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)