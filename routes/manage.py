# ==============================================================================
# مسارات الإدارة وبناء النظام (routes/manage.py)
# مسئول عن: إضافة/تعديل/حذف المناطق، إدارة الألعاب وترتيبها، وإدارة المستخدمين
# ==============================================================================

import os
import json
import uuid
from flask import Blueprint, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from extensions import db, UPLOAD_FOLDER
from models import User, Area, GameModel

# إنشاء Blueprint لإدارة وتشكيل النظام
manage_bp = Blueprint('manage', __name__)

# ------------------------------------------------------------------------------
# دالة مساعدة للتحقق من صلاحية تعديل النظام (المناطق والألعاب)
# ------------------------------------------------------------------------------
def check_system_permission():
    return session.get('is_admin') and (session.get('is_master_admin') or session.get('can_manage_system') or session.get('can_manage_areas') or session.get('can_manage_games'))

# ------------------------------------------------------------------------------
# 1. الصفحة الرئيسية لإدارة مناطق الفحص (GET)
# ------------------------------------------------------------------------------
@manage_bp.route('/manage_system', methods=['GET', 'POST'])
def manage_system():
    if not session.get('is_admin') or not check_system_permission():
        return redirect(url_for('admin.admin_login'))
    return render_template('manage_system.html', areas=Area.query.order_by(Area.sort_order.asc(), Area.id.asc()).all())

# ------------------------------------------------------------------------------
# 2. إضافة منطقة جغرافية جديدة (POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/add_area', methods=['POST'])
def add_area():
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    name = request.form.get('area_name')
    
    image_path = None
    if 'area_image' in request.files:
        file = request.files['area_image']
        if file and file.filename != '':
            ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'png'
            filename = f"area_cover_{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            image_path = f"/{filepath}".replace("\\", "/")

    if name:
        max_order = db.session.query(db.func.max(Area.sort_order)).scalar() or 0
        db.session.add(Area(name=name, sort_order=max_order + 1, image=image_path))
        db.session.commit()
    return redirect(url_for('manage.manage_system'))

# ------------------------------------------------------------------------------
# 2.5 الترتيب المخصص للمناطق بالسحب والإفلات (Drag & Drop) (POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/update_areas_order', methods=['POST'])
def update_areas_order():
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    area_ids = request.form.getlist('area_ids[]')
    for idx, a_id in enumerate(area_ids, start=1):
        area = Area.query.get(a_id)
        if area:
            area.sort_order = idx
    db.session.commit()
    return redirect(url_for('manage.manage_system'))

# ------------------------------------------------------------------------------
# 3. تعديل اسم منطقة موجودة (GET & POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/edit_area/<int:area_id>', methods=['GET', 'POST'])
def edit_area(area_id):
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    area = Area.query.get_or_404(area_id)
    if request.method == 'POST':
        new_name = request.form.get('area_name')
        if new_name:
            area.name = new_name
            
        if 'area_image' in request.files:
            file = request.files['area_image']
            if file and file.filename != '':
                # مسح الصورة القديمة إن وُجدت
                if area.image:
                    old_path = area.image.lstrip('/')
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception as e:
                            print(f"Error deleting old area image: {e}")
                
                ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'png'
                filename = f"area_cover_{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                area.image = f"/{filepath}".replace("\\", "/")
                
        db.session.commit()
        return redirect(url_for('manage.manage_system'))
    return render_template('edit_area.html', area=area)

# ------------------------------------------------------------------------------
# 4. حذف منطقة بكافة ألعابها المترتبة عليها (GET/POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/delete_area/<int:area_id>')
def delete_area(area_id):
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    area = Area.query.get_or_404(area_id)
    if area:
        db.session.delete(area)
        db.session.commit()
    return redirect(url_for('manage.manage_system'))

# ==============================================================================
# --- مسارات إدارة وتشكيل الألعاب داخل المناطق ---
# ==============================================================================

# ------------------------------------------------------------------------------
# 5. عرض ألعاب المنطقة بترتيبها الحالي المخصص (GET)
# ------------------------------------------------------------------------------
@manage_bp.route('/area_games/<int:area_id>')
def area_games(area_id):
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    area = Area.query.get_or_404(area_id)
    sorted_games = GameModel.query.filter_by(area_id=area_id).order_by(GameModel.sort_order.asc(), GameModel.id.asc()).all()
    return render_template('area_games.html', area=area, games=sorted_games)

# ------------------------------------------------------------------------------
# 6. الترتيب المخصص للألعاب بالسحب والإفلات (Drag & Drop) (POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/update_games_order/<int:area_id>', methods=['POST'])
def update_games_order(area_id):
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    game_ids = request.form.getlist('game_ids[]')
    for idx, g_id in enumerate(game_ids, start=1):
        g = GameModel.query.get(g_id)
        if g and g.area_id == area_id:
            g.sort_order = idx
    db.session.commit()
    return redirect(url_for('manage.area_games', area_id=area_id))

# ------------------------------------------------------------------------------
# 7. إضافة لعبة جديدة للمنطقة وتحديد إعداداتها (POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/add_game_to_area/<int:area_id>', methods=['POST'])
def add_game_to_area(area_id):
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    
    name = request.form.get('game_name')
    check_names = request.form.getlist('check_names[]')
    structured_checks = [{"name": c.strip(), "is_mandatory": bool(request.form.get(f'check_mandatory_{i}'))} for i, c in enumerate(check_names) if c.strip()]
    
    # رفع ومعالجة صورة الخريطة الأساسية إن وُجدت
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
        max_order = db.session.query(db.func.max(GameModel.sort_order)).filter_by(area_id=area_id).scalar() or 0
        db.session.add(GameModel(
            name=name, 
            area_id=area_id,
            sort_order=max_order + 1,
            has_map=bool(request.form.get('has_map')), 
            map_mandatory=bool(request.form.get('map_mandatory')),
            map_image=map_image_path,
            allow_photos=bool(request.form.get('allow_photos')), 
            requires_photo=bool(request.form.get('requires_photo')),
            notes_mandatory=bool(request.form.get('notes_mandatory')), 
            checks=json.dumps(structured_checks, ensure_ascii=False)
        ))
        db.session.commit()
        
    return redirect(url_for('manage.area_games', area_id=area_id))

# ------------------------------------------------------------------------------
# 8. تعديل إعدادات وأسئلة لعبة موجودة (GET & POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/edit_game/<int:game_id>', methods=['GET', 'POST'])
def edit_game(game_id):
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    game = GameModel.query.get_or_404(game_id)
    
    if request.method == 'POST':
        game.name = request.form.get('name')
        game.area_id = request.form.get('area_id')
        game.has_map = bool(request.form.get('has_map'))
        game.map_mandatory = bool(request.form.get('map_mandatory'))
        game.allow_photos = bool(request.form.get('allow_photos'))
        game.requires_photo = bool(request.form.get('requires_photo'))
        game.notes_mandatory = bool(request.form.get('notes_mandatory'))
        
        check_names = request.form.getlist('check_names[]')
        game.checks = json.dumps([{"name": c.strip(), "is_mandatory": bool(request.form.get(f'check_mandatory_{i}'))} for i, c in enumerate(check_names) if c.strip()], ensure_ascii=False)
        
        # استبدال الخريطة القديمة بالجديدة وتوسيع الملف القديم
        if 'map_image' in request.files:
            file = request.files['map_image']
            if file and file.filename != '':
                old_map_path = getattr(game, 'map_image_path', None)
                if old_map_path and os.path.exists(old_map_path):
                    try:
                        os.remove(old_map_path)
                    except Exception as e:
                        print(f"Error deleting old map: {e}")
                
                filename = secure_filename(file.filename)
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                game.map_image_path = filepath

        db.session.commit()
        return redirect(url_for('manage.area_games', area_id=game.area_id))
        
    return render_template('edit_game.html', game=game, areas=Area.query.order_by(Area.sort_order.asc(), Area.id.asc()).all(), checks=json.loads(game.checks) if game.checks else [])

# ------------------------------------------------------------------------------
# 9. حذف لعبة من منطقة (GET)
# ------------------------------------------------------------------------------
@manage_bp.route('/delete_game_from_area/<int:area_id>/<int:game_id>')
def delete_game_from_area(area_id, game_id):
    if not check_system_permission(): return redirect(url_for('admin.admin_login'))
    game = GameModel.query.get(game_id)
    if game:    
        db.session.delete(game)
        db.session.commit()
    return redirect(url_for('manage.area_games', area_id=area_id))

# ==============================================================================
# --- مسارات إدارة المستخدمين والصلاحيات ---
# ==============================================================================

# ------------------------------------------------------------------------------
# 10. عرض وإنشاء حسابات المستخدمين الجدد (GET & POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    if not session.get('is_admin'): return redirect(url_for('admin.admin_login'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'Team Leader')
        can_manage_system = bool(request.form.get('can_manage_system'))

        if username and password:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role=role,
                can_manage_system=can_manage_system,
                can_manage_areas=can_manage_system,
                can_manage_games=can_manage_system,
                can_view_reports=True
            )
            db.session.add(user)
            db.session.commit()
        return redirect(url_for('manage.manage_users'))
    return render_template('manage_users.html', users=User.query.all())

# ------------------------------------------------------------------------------
# 11. تحديث صلاحية حساب قائم (POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/update_user_permissions/<int:user_id>', methods=['POST'])
def update_user_permissions(user_id):
    if not session.get('is_admin'): return redirect(url_for('admin.admin_login'))
    user = User.query.get_or_404(user_id)
    can_manage_system = bool(request.form.get('can_manage_system'))
    user.can_manage_system = can_manage_system
    user.can_manage_areas = can_manage_system
    user.can_manage_games = can_manage_system
    user.can_view_reports = True
    db.session.commit()
    return redirect(url_for('manage.manage_users'))

# ------------------------------------------------------------------------------
# 12. حذف حساب مستخدم (POST)
# ------------------------------------------------------------------------------
@manage_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('is_admin'): return redirect(url_for('admin.admin_login'))
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('manage.manage_users'))
