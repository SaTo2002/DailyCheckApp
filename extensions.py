import os
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

MASTER_ADMIN_HASH = os.getenv(
    'MASTER_ADMIN_HASH',
    'scrypt:32768:8:1$o2sRQJ3CVeIvLBFk$630226ad3aa44801001362c89ca76753c7ae6900c4f8395cbe90cf89a657dd6d544988584d0ab9e667571be840294f8290e4c87cb47d5d4f6a2acb0075e2bb1e'
)
