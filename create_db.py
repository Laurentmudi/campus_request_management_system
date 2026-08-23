"""
Run this once to create the database and a default admin account.
Usage: python create_db.py
"""
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()

    if not User.query.filter_by(email='admin@gmail.com').first():
        admin = User(
            full_name='System Administrator',
            email='admin@gmail.com',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Database created.')
        print('Default admin login -> email: admin@gmail | password: admin123')
    else:
        print('Database already exists. No changes made.')
