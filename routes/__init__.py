# ==============================================================================
# ملف تهيئة حزمة المسارات (routes/__init__.py)
# يُعرف المجلد كـ Python Package ويُتيح استدعاء جميع الـ Blueprints مباشرة
# ==============================================================================

from .monitor import monitor_bp
from .admin import admin_bp
from .manage import manage_bp
