from flask import Flask, render_template

# تهيئة تطبيق فلاسك
app = Flask(__name__)

# قاعدة البيانات المبدئية (قاموس) تحتوي على إعدادات كل لعبة
# أي لعبة جديدة سيتم إضافتها هنا مستقبلاً
GAMES_CONFIG = {
    "Dodge-ball": {
        "name": "Dodge ball",
        "has_map": True, # يحدد إذا كانت اللعبة تحتاج لمخطط رسم أم لا
        "map_image": "Dodge_ball.png",  # اسم صورة المخطط في مجلد static
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك", "حالة السجادة (Mat)", "الوسادات (Pad)", "السوست (Spring)"] # عناصر الفحص
    },
    "Ninja-Course": {
        "name": "Ninja Course",
        "has_map": False, # هذه اللعبة لا تحتاج لمخطط رسم
        "checks": ["النظافة", "الإضاءة", "غطاء الحديد (PVC)", "حالة الشبك"]
    },
    "Matrix": {
        "name": "Matrix",
        "has_map": True,          
        "map_image": "matrix_map.png", 
        "checks": ["النظافة", "الإضاءة"]
    }
}

# المسار الرئيسي للموقع (الصفحة الرئيسية)
@app.route('/')
def home():
    # يعرض ملف index.html الموجود في مجلد templates
    return render_template('index.html')

# مسار ديناميكي يتغير حسب اللعبة التي يختارها الموظف
@app.route('/check/<game_id>')
def check_game(game_id):
    # سحب بيانات اللعبة من القاموس بناءً على الرابط
    game_data = GAMES_CONFIG.get(game_id)
    
    # تأمين: إذا تم إدخال رابط للعبة غير موجودة
    if not game_data:
        return "هذه اللعبة غير موجودة في النظام!"

    # إرسال بيانات اللعبة إلى صفحة الفورمة لعرضها
    return render_template('form.html', game=game_data)

# نقطة تشغيل السيرفر
if __name__ == '__main__':
    # host='0.0.0.0' تسمح للأجهزة الأخرى على نفس شبكة الواي فاي بالاتصال بالسيرفر
    app.run(host='0.0.0.0', port=5000, debug=True)