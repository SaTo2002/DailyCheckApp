import os
from flask import Flask
from dotenv import load_dotenv
from extensions import db
from models import User, Area, GameModel, GameReport
from routes.monitor import monitor_bp
from routes.admin import admin_bp
from routes.manage import manage_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'gravity_code_secret_key_fallback')

DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Register Blueprints
app.register_blueprint(monitor_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manage_bp)

from sqlalchemy import text

with app.app_context():
    db.create_all()
    # Migration helper for User permission columns
    for col, default_val in [('can_manage_system', 0), ('can_manage_areas', 0), ('can_manage_games', 0), ('can_view_reports', 1)]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} TINYINT(1) DEFAULT {default_val}"))
                conn.commit()
        except Exception:
            pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)