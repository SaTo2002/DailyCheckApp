from app import app
import models
from extensions import db


def update_database():
    with app.app_context():
        # db.create_all() يقوم بإنشاء أي جداول جديدة غير موجودة في قاعدة البيانات
        # ولا يقوم بمسح أو تعديل الجداول القديمة الموجودة بالفعل
        db.create_all()
        print("✅ تم تحديث قاعدة البيانات بنجاح!")
        print(
            "✅ تم إنشاء الجداول الجديدة (مثل daily_sessions) بدون المساس بالبيانات القديمة."
        )


if __name__ == "__main__":
    update_database()
