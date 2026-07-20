import os

from app import create_app
from app.extensions import db
from app.models.law import Law

app = create_app()

with app.app_context():
    upload_dir = os.path.join(app.config['UPLOAD_PATH'], 'laws')

    # all files on disk
    disk_files = set(os.listdir(upload_dir)) if os.path.isdir(upload_dir) else set()

    # all secure_name in DB
    db_files = {r[0] for r in db.session.query(Law.secure_name).filter(Law.secure_name.isnot(None)).all()}

    dangling = disk_files - db_files

    if dangling:
        print(f'{len(dangling)} 悬垂文件:')
        for f in sorted(dangling):
            path = os.path.join(upload_dir, f)
            size = os.path.getsize(path)
            print(f'  {f} ({size} bytes)')
    else:
        print('无悬垂文件')