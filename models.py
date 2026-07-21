from extensions import db

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    can_manage_system = db.Column(db.Boolean, default=False)
    can_manage_areas = db.Column(db.Boolean, default=False)
    can_manage_games = db.Column(db.Boolean, default=False)
    can_view_reports = db.Column(db.Boolean, default=True)

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
