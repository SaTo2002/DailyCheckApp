import os
import json
from flask import Blueprint, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash
from sqlalchemy import func
from extensions import db, MASTER_ADMIN_HASH
from models import User, GameModel, GameReport

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        if username == 'admin' and check_password_hash(MASTER_ADMIN_HASH, password):
            session['is_admin'], session['admin_role'] = True, 'admin'
            return redirect(url_for('admin.dashboard'))
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['is_admin'], session['admin_role'] = True, user.role
            return redirect(url_for('admin.dashboard'))
        return render_template('admin_login.html', error="اسم المستخدم أو كلمة المرور غير صحيحة!")
    return render_template('admin_login.html')

@admin_bp.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_role', None)
    return redirect(url_for('monitor.home'))

@admin_bp.route('/dashboard', methods=['GET'])
def dashboard():
    if not session.get('is_admin'): return redirect(url_for('admin.admin_login'))
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

@admin_bp.route('/print_report/<session_id>')
def print_report(session_id):
    if not session.get('is_admin'): return redirect(url_for('admin.admin_login'))
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

@admin_bp.route('/delete_report/<session_id>', methods=['POST'])
def delete_report(session_id):
    if not session.get('is_admin'): return redirect(url_for('admin.admin_login'))
    for r in GameReport.query.filter_by(session_id=session_id).all():
        if r.map_image_path and os.path.exists(r.map_image_path.lstrip('/')): os.remove(r.map_image_path.lstrip('/'))
        if r.photos_paths:
            try:
                for p in json.loads(r.photos_paths):
                    if os.path.exists(p.lstrip('/')): os.remove(p.lstrip('/'))
            except: pass
        db.session.delete(r)
    db.session.commit()
    return redirect(url_for('admin.dashboard'))
