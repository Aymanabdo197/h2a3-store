import os, uuid, socket
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    paid = db.Column(db.Boolean, default=False)
    license_key = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not Product.query.first():
        db.session.add_all([
            Product(name='H2A3 DataVault Core', description='محرك التشفير المركزي', price=0),
            Product(name='H2A3 Encrypted Database', description='قواعد بيانات مشفرة', price=25),
            Product(name='H2A3 InsiderShield', description='كشف التهديدات الداخلية', price=25),
            Product(name='H2A3 AutoShield', description='استجابة تلقائية', price=49),
        ])
        db.session.commit()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', is_admin=True)
        admin.password_hash = generate_password_hash('H2A3@Fortress2026')
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def home():
    products = Product.query.all()
    cards = ''.join([f'<div style="background:#1e293b;padding:20px;margin:10px;border-radius:10px;display:inline-block;width:200px"><h3>{p.name}</h3><p>{p.description[:80]}...</p><span style="color:#10b981;font-size:1.4em">{"مجاني" if p.price==0 else f"${p.price}/شهر"}</span></div>' for p in products])
    return f'<html dir="rtl"><head><meta charset="UTF-8"><title>متجر H2A3 Fortress</title><style>body{{font-family:Arial;background:#0f172a;color:#f1f5f9;padding:20px}}a{{color:#10b981}}</style></head><body><h1>🛡️ متجر H2A3 Fortress</h1><div>{cards}</div><p><a href="/admin">لوحة التحكم</a></p></body></html>'

@app.route('/admin')
@login_required
def admin():
    return '<h1>لوحة التحكم</h1><p>مرحباً بك في لوحة تحكم H2A3 Fortress</p>'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect('/admin')
    return '<form method="POST"><input name="username" placeholder="المستخدم"><input name="password" type="password" placeholder="كلمة المرور"><button>دخول</button></form>'

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
