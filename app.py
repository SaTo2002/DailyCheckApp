import os
import json
import base64
import uuid
from datetime import datetime
import time
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# ==========================================
# --- إعدادات البيئة ---
# ==========================================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'gravity_code_secret_key_fallback')

DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ==========================================
# --- كلاسات قاعدة البيانات (Models) ---
# ==========================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class Area(db.Model):
    __tablename__ = 'areas'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    games = db.relationship('GameModel', backref='area', lazy=True, cascade="all, delete-orphan")

class GameModel(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    area_id = db.Column(db.Integer, db.ForeignKey('areas.id'), nullable=False)
    has_map = db.Column(db.Boolean, default=False)
    map_image = db.Column(db.String(255), nullable=True)
    map_mandatory = db.Column(db.Boolean, default=False)
    allow_photos = db.Column(db.Boolean, default=True)
    requires_photo = db.Column(db.Boolean, default=False)
    notes_mandatory = db.Column(db.Boolean, default=False)
    checks = db.Column(db.Text, nullable=False) 

class GameReport(db.Model):
    __tablename__ = 'game_reports'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    monitor_name = db.Column(db.String(100), nullable=False)
    area_id = db.Column(db.String(50), nullable=False) 
    game_id = db.Column(db.String(50), nullable=False)
    checks_data = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    map_image_path = db.Column(db.String(255), nullable=True)
    photos_paths = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.now())

MASTER_ADMIN_HASH = "scrypt:32768:8:1$o2sRQJ3CVeIvLBFk$630226ad3aa44801001362c89ca76753c7ae6900c4f8395cbe90cf89a657dd6d544988584d0ab9e667571be840294f8290e4c87cb47d5d4f6a2acb0075e2bb1e"

with app.app_context():
    db.create_all()

# ==========================================
# --- مسارات التطبيق الرئيسية (للمراقب) ---
# ==========================================
@app.route('/', methods=['GET', 'POST'])
def home():
    try:
        reports = GameReport.query.with_entities(GameReport.map_image_path, GameReport.photos_paths).all()
        valid_filenames = set()
        for r in reports:
            if r.map_image_path: valid_filenames.add(os.path.basename(r.map_image_path))
            if r.photos_paths:
                for p in json.loads(r.photos_paths): valid_filenames.add(os.path.basename(p))
        current_time = time.time()
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath) and (current_time - os.path.getmtime(filepath)) > 86400:
                if filename not in valid_filenames: os.remove(filepath)
    except Exception as e:
        pass

    if request.method == 'POST':
        session['monitor_name'] = request.form.get('monitor_name')
        selected_area = request.form.get('area')
        session['area_id'] = selected_area 
        session['completed_games'] = []
        session['game_data'] = {}
        return redirect(url_for('show_games', area_id=selected_area))
    
    areas = Area.query.all()
    return render_template('index.html', areas=areas)

@app.route('/games/<area_id>')
def show_games(area_id):
    if 'monitor_name' not in session: return redirect(url_for('home'))
    area = Area.query.get(area_id)
    if not area: return "هذه المنطقة غير موجودة!"
    games = GameModel.query.filter_by(area_id=area.id).all()
    completed = session.get('completed_games', [])
    all_completed = len(games) > 0 and all(str(g.id) in completed for g in games)
    return render_template('games.html', area_name=area.name, games=games, monitor_name=session['monitor_name'], completed_games=completed, all_completed=all_completed)

@app.route('/check/<game_id>', methods=['GET', 'POST'])
def check_game(game_id):
    game = GameModel.query.get(game_id)
    if not game: return "هذه اللعبة غير موجودة في النظام!"
    game_checks = json.loads(game.checks) if game.checks else []
    next_game_id = None
    area_id = session.get('area_id')
    
    if area_id:
        area_games = GameModel.query.filter_by(area_id=area_id).all()
        game_ids = [str(g.id) for g in area_games]
        if game_id in game_ids:
            current_index = game_ids.index(game_id)
            if current_index + 1 < len(game_ids): next_game_id = game_ids[current_index + 1]

    saved_data = session.get('game_data', {}).get(game_id, {})
        
    if request.method == 'POST':
        if 'completed_games' not in session: session['completed_games'] = []
        if game_id not in session['completed_games']: session['completed_games'].append(game_id)
        if 'game_data' not in session: session['game_data'] = {}
            
        current_answers = {}
        for i in range(1, len(game_checks) + 1):
            check_name = f'check_{i}'
            current_answers[check_name] = request.form.get(check_name)
        current_answers['notes'] = request.form.get('notes', '')
        current_answers['photos'] = session.get('game_data', {}).get(game_id, {}).get('photos', [])

        map_drawing_data = request.form.get('map_drawing', '')
        old_map_path = session.get('game_data', {}).get(game_id, {}).get('map_drawing', '')

        if map_drawing_data == '': current_answers['map_drawing'] = ''
        elif map_drawing_data.startswith('data:image'):
            _, encoded = map_drawing_data.split(',', 1)
            filename = f"map_{game_id}_{uuid.uuid4().hex}.png"
            filepath = os.path.join('static', 'uploads', filename)
            with open(filepath, "wb") as fh: fh.write(base64.b64decode(encoded))
            current_answers['map_drawing'] = f"/{filepath}".replace("\\", "/") 
        else: current_answers['map_drawing'] = old_map_path

        session['game_data'][game_id] = current_answers
        session.modified = True
        
        user_action = request.form.get('action')
        if user_action == 'next' and next_game_id: return redirect(url_for('check_game', game_id=next_game_id))
        else: return redirect(url_for('show_games', area_id=session.get('area_id')))

    return render_template('form.html', game=game, checks=game_checks, next_game_id=next_game_id, saved_data=saved_data, game_id=game_id)

@app.route('/upload_photo_ajax', methods=['POST'])
def upload_photo_ajax():
    game_id = request.form.get('game_id')
    uploaded_files = request.files.getlist('issue_photos')
    new_photos = []
    if 'game_data' not in session: session['game_data'] = {}
    if game_id not in session['game_data']: session['game_data'][game_id] = {}
    if 'photos' not in session['game_data'][game_id]: session['game_data'][game_id]['photos'] = []

    for file in uploaded_files:
        if file and file.filename != '':
            photo_ext = file.filename.split('.')[-1]
            photo_filepath = os.path.join('static', 'uploads', f"photo_{game_id}_{uuid.uuid4().hex}.{photo_ext}")
            file.save(photo_filepath)
            photo_url = f"/{photo_filepath}".replace("\\", "/")
            new_photos.append(photo_url)
            session['game_data'][game_id]['photos'].append(photo_url)
    session.modified = True
    return {"status": "success", "photos": new_photos}

@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    data = request.json
    game_id = data.get('game_id')
    photo_url = data.get('photo_url')
    if 'game_data' in session and game_id in session['game_data']:
        photos = session['game_data'][game_id].get('photos', [])
        if photo_url in photos:
            photos.remove(photo_url)
            session['game_data'][game_id]['photos'] = photos
            session.modified = True
            if os.path.exists(photo_url.lstrip('/')): os.remove(photo_url.lstrip('/'))
            return {"status": "success"}
    return {"status": "error"}, 400

@app.route('/submit_report', methods=['POST'])
def submit_report():
    if 'monitor_name' not in session or 'area_id' not in session: return redirect(url_for('home'))
    monitor_name, area_id = session['monitor_name'], session['area_id']
    area = Area.query.get(area_id)
    area_name = area.name if area else "منطقة غير معروفة"
    completed_games = session.get('completed_games', [])
    game_data = session.get('game_data', {})
    session_id = uuid.uuid4().hex

    for game_id in completed_games:
        data = game_data.get(game_id, {})
        checks = {k: v for k, v in data.items() if k.startswith('check_')}
        db.session.add(GameReport(
            session_id=session_id, monitor_name=monitor_name, area_id=area_name,
            game_id=game_id, checks_data=json.dumps(checks, ensure_ascii=False),
            notes=data.get('notes', ''), map_image_path=data.get('map_drawing', ''),
            photos_paths=json.dumps(data.get('photos', []), ensure_ascii=False)
        ))
    db.session.commit()
    session.pop('completed_games', None)
    session.pop('game_data', None)
    session.pop('area_id', None) 
    return "<div style='text-align:center; margin-top:100px; direction:rtl;'><h1 style='color:green;'>تم إرسال تقرير المنطقة بنجاح! 🎉</h1><a href='/'>العودة للصفحة الرئيسية</a></div>"

@app.route('/cancel_game/<game_id>')
def cancel_game(game_id):
    if game_id in session.get('completed_games', []): return redirect(url_for('show_games', area_id=session.get('area_id')))
    game_data = session.get('game_data', {}).get(game_id, {})
    for photo in game_data.get('photos', []):
        if os.path.exists(photo.lstrip('/')): os.remove(photo.lstrip('/'))
    map_drawing = game_data.get('map_drawing', '')
    if map_drawing and os.path.exists(map_drawing.lstrip('/')): os.remove(map_drawing.lstrip('/'))
    if 'game_data' in session and game_id in session['game_data']:
        del session['game_data'][game_id]
        session.modified = True
    return redirect(url_for('show_games', area_id=session.get('area_id')))

@app.route('/cancel_area')
def cancel_area():
    for _, data in session.get('game_data', {}).items():
        for photo in data.get('photos', []):
            if os.path.exists(photo.lstrip('/')): os.remove(photo.lstrip('/'))
        map_drawing = data.get('map_drawing', '')
        if map_drawing and os.path.exists(map_drawing.lstrip('/')): os.remove(map_drawing.lstrip('/'))
    session.pop('completed_games', None)
    session.pop('game_data', None)
    session.pop('area_id', None)
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    cancel_area()
    session.clear()
    return redirect(url_for('home'))

# ==========================================
# --- مسارات الإدارة والداشبورد ---
# ==========================================
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        if username == 'admin' and check_password_hash(MASTER_ADMIN_HASH, password):
            session['is_admin'], session['admin_role'] = True, 'admin'
            return redirect(url_for('dashboard'))
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['is_admin'], session['admin_role'] = True, user.role
            return redirect(url_for('dashboard'))
        return render_template('admin_login.html', error="اسم المستخدم أو كلمة المرور غير صحيحة!")
    return render_template('admin_login.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_role', None)
    return redirect(url_for('home'))

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    selected_area, selected_date, selected_monitor = request.args.get('area', ''), request.args.get('date', ''), request.args.get('monitor_name', '')
    query = GameReport.query
    if selected_area: query = query.filter(GameReport.area_id == selected_area)
    if selected_date: query = query.filter(func.date(GameReport.timestamp) == selected_date)
    if selected_monitor: query = query.filter(GameReport.monitor_name == selected_monitor)
    reports = query.order_by(GameReport.timestamp.desc()).all()
    areas = [r[0] for r in db.session.query(GameReport.area_id).distinct().all()]
    dates = [str(r[0]) for r in db.session.query(func.date(GameReport.timestamp)).distinct().all() if r[0]]
    monitors = [r[0] for r in db.session.query(GameReport.monitor_name).distinct().all()]
    
    grouped_reports = {}
    for r in reports:
        if r.session_id not in grouped_reports:
            grouped_reports[r.session_id] = {'monitor_name': r.monitor_name, 'area_id': r.area_id, 'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S'), 'games': []}
        game_model = GameModel.query.get(r.game_id) if r.game_id.isdigit() else None
        actual_check_names = [c['name'] for c in json.loads(game_model.checks)] if game_model and game_model.checks else []
        checks = json.loads(r.checks_data) if r.checks_data else {}
        mapped_checks = {}
        for k, v in checks.items():
            if k.startswith('check_'):
                try:
                    idx = int(k.split('_')[1]) - 1
                    mapped_checks[actual_check_names[idx] if idx < len(actual_check_names) else k] = 'OK' if v == 'سليم' else 'Not OK'
                except: mapped_checks[k] = v
            else: mapped_checks[k] = v
        grouped_reports[r.session_id]['games'].append({'game_id': game_model.name if game_model else r.game_id, 'checks': mapped_checks, 'notes': r.notes, 'map_drawing': r.map_image_path, 'base_map': game_model.map_image if game_model else "", 'photos': json.loads(r.photos_paths) if r.photos_paths else []})
    return render_template('dashboard.html', reports=grouped_reports, areas=areas, dates=dates, monitors=monitors, selected_area=selected_area, selected_date=selected_date, selected_monitor=selected_monitor)

@app.route('/print_report/<session_id>')
def print_report(session_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    reports = GameReport.query.filter_by(session_id=session_id).all()
    if not reports: return "التقرير غير موجود"
    report_data = {'monitor_name': reports[0].monitor_name, 'area_id': reports[0].area_id, 'timestamp': reports[0].timestamp.strftime('%Y-%m-%d %H:%M:%S'), 'games': []}
    for r in reports:
        game_model = GameModel.query.get(r.game_id) if r.game_id.isdigit() else None
        actual_check_names = [c['name'] for c in json.loads(game_model.checks)] if game_model and game_model.checks else []
        mapped_checks = {}
        for k, v in (json.loads(r.checks_data) if r.checks_data else {}).items():
            if k.startswith('check_'):
                try: mapped_checks[actual_check_names[int(k.split('_')[1]) - 1] if int(k.split('_')[1]) - 1 < len(actual_check_names) else k] = 'OK' if v == 'سليم' else 'Not OK'
                except: mapped_checks[k] = v
            else: mapped_checks[k] = v
        report_data['games'].append({'game_id': game_model.name if game_model else r.game_id, 'checks': mapped_checks, 'notes': r.notes, 'map_drawing': r.map_image_path, 'base_map': game_model.map_image if game_model else "", 'photos': json.loads(r.photos_paths) if r.photos_paths else []})
    return render_template('print_report.html', report=report_data)

@app.route('/delete_report/<session_id>', methods=['POST'])
def delete_report(session_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    for r in GameReport.query.filter_by(session_id=session_id).all():
        if r.map_image_path and os.path.exists(r.map_image_path.lstrip('/')): os.remove(r.map_image_path.lstrip('/'))
        if r.photos_paths:
            try:
                for p in json.loads(r.photos_paths):
                    if os.path.exists(p.lstrip('/')): os.remove(p.lstrip('/'))
            except: pass
        db.session.delete(r)
    db.session.commit()
    return redirect(url_for('dashboard'))

# ==========================================
# --- مسارات بناء وإدارة النظام للـ Admin ---
# ==========================================
@app.route('/manage_system', methods=['GET', 'POST'])
def manage_system():
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    return render_template('manage_system.html', areas=Area.query.all())

@app.route('/add_area', methods=['POST'])
def add_area():
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    name = request.form.get('area_name')
    if name:
        db.session.add(Area(name=name))
        db.session.commit()
    return redirect(url_for('manage_system'))

@app.route('/edit_area/<int:area_id>', methods=['GET', 'POST'])
def edit_area(area_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    area = Area.query.get_or_404(area_id)
    if request.method == 'POST':
        new_name = request.form.get('area_name')
        if new_name:
            area.name = new_name
            db.session.commit()
        return redirect(url_for('manage_system'))
    return render_template('edit_area.html', area=area)

@app.route('/delete_area/<int:area_id>')
def delete_area(area_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    area = Area.query.get_or_404(area_id)
    if area:
        db.session.delete(area)
        db.session.commit()
    return redirect(url_for('manage_system'))

# --- إدارة الألعاب داخل المنطقة ---
@app.route('/area_games/<int:area_id>')
def area_games(area_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    return render_template('area_games.html', area=Area.query.get_or_404(area_id))

@app.route('/add_game_to_area/<int:area_id>', methods=['POST'])
def add_game_to_area(area_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    
    name = request.form.get('game_name')
    check_names = request.form.getlist('check_names[]')
    structured_checks = [{"name": c.strip(), "is_mandatory": bool(request.form.get(f'check_mandatory_{i}'))} for i, c in enumerate(check_names) if c.strip()]
    
    # معالجة صورة الخريطة الأساسية
    map_image_path = None
    if 'map_image' in request.files:
        file = request.files['map_image']
        if file and file.filename != '':
            ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'png'
            filename = f"base_map_area{area_id}_{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            map_image_path = f"/{filepath}".replace("\\", "/")

    if name:
        db.session.add(GameModel(
            name=name, 
            area_id=area_id,
            has_map=bool(request.form.get('has_map')), 
            map_mandatory=bool(request.form.get('map_mandatory')),
            map_image=map_image_path,  # تم إضافة مسار الصورة هنا
            allow_photos=bool(request.form.get('allow_photos')), 
            requires_photo=bool(request.form.get('requires_photo')),
            notes_mandatory=bool(request.form.get('notes_mandatory')), 
            checks=json.dumps(structured_checks, ensure_ascii=False)
        ))
        db.session.commit()
        
    return redirect(url_for('area_games', area_id=area_id))



@app.route('/edit_game/<int:game_id>', methods=['GET', 'POST'])
def edit_game(game_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    game = GameModel.query.get_or_404(game_id)
    
    if request.method == 'POST':
        # فصلت السطور شوية عشان تبقى أسهل في القراءة والتعديل
        game.name = request.form.get('game_name')
        game.area_id = request.form.get('area_id')
        game.has_map = bool(request.form.get('has_map'))
        game.map_mandatory = bool(request.form.get('map_mandatory'))
        game.allow_photos = bool(request.form.get('allow_photos'))
        game.requires_photo = bool(request.form.get('requires_photo'))
        game.notes_mandatory = bool(request.form.get('notes_mandatory'))
        
        check_names = request.form.getlist('check_names[]')
        game.checks = json.dumps([{"name": c.strip(), "is_mandatory": bool(request.form.get(f'check_mandatory_{i}'))} for i, c in enumerate(check_names) if c.strip()], ensure_ascii=False)
        
        # --- الجزء الجديد الخاص بتحديث الخريطة ومسح القديمة ---
        if 'map_image' in request.files:
            file = request.files['map_image']
            # لو المستخدم اختار ملف فعلاً
            if file and file.filename != '':
                # 1. مسح الصورة القديمة لو موجودة
                # (استخدمنا getattr عشان لو العمود مش موجود ما يضربش إيرور)
                old_map_path = getattr(game, 'map_image_path', None)
                if old_map_path and os.path.exists(old_map_path):
                    try:
                        os.remove(old_map_path)
                    except Exception as e:
                        print(f"Error deleting old map: {e}")
                
                # 2. حفظ الصورة الجديدة
                filename = secure_filename(file.filename)
                os.makedirs(UPLOAD_FOLDER, exist_ok=True) # بيكريت الفولدر لو مش موجود
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                # 3. تحديث مسار الصورة في الداتابيز
                game.map_image_path = filepath
        # --------------------------------------------------

        db.session.commit()
        return redirect(url_for('area_games', area_id=game.area_id))
        
    return render_template('edit_game.html', game=game, areas=Area.query.all(), checks=json.loads(game.checks) if game.checks else [])


@app.route('/delete_game_from_area/<int:area_id>/<int:game_id>')
def delete_game_from_area(area_id, game_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    game = GameModel.query.get(game_id)
    if game:    
        db.session.delete(game)
        db.session.commit()
    return redirect(url_for('area_games', area_id=area_id))

@app.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    if request.method == 'POST':
        username, password, role = request.form.get('username'), request.form.get('password'), request.form.get('role', 'monitor')
        if username and password:
            db.session.add(User(username=username, password_hash=generate_password_hash(password), role=role))
            db.session.commit()
        return redirect(url_for('manage_users'))
    return render_template('manage_users.html', users=User.query.all())

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('manage_users'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)