import os, uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ---------- Models ----------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    plan = db.Column(db.String(50))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    reference_number = db.Column(db.String(100))
    paid = db.Column(db.Boolean, default=False)
    license_key = db.Column(db.String(100), unique=True)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not Product.query.first():
        products = [
            Product(name='H2A3 DataVault Core', description='محرك التشفير المركزي AES-256-GCM مع حماية الذاكرة', price=0, category='core', plan='community'),
            Product(name='H2A3 Encrypted Database Types', description='أنواع SQLAlchemy مشفرة شفافة مع دعم البحث', price=25, category='database', plan='professional'),
            Product(name='H2A3 InsiderShield', description='نظام كشف التهديدات الداخلية بالذكاء السلوكي', price=25, category='insider', plan='professional'),
            Product(name='H2A3 AutoShield', description='نظام استجابة تلقائية فورية للتهديدات', price=49, category='auto', plan='enterprise'),
        ]
        db.session.add_all(products)
        db.session.commit()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='H2A3@Fortress2026', is_admin=True)
        db.session.add(admin)
        db.session.commit()

# ---------- Routes ----------
@app.route('/')
def home():
    products = Product.query.all()
    return render_template('home.html', products=products)

@app.route('/products')
def products():
    products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    products = []
    total = 0
    for item in cart_items:
        product = Product.query.get(item['product_id'])
        if product:
            products.append({'product': product, 'quantity': item['quantity']})
            total += product.price * item['quantity']
    return render_template('cart.html', cart_items=products, total=total)

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    cart = session.get('cart', [])
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += 1
            break
    else:
        cart.append({'product_id': product_id, 'quantity': 1})
    session['cart'] = cart
    flash('تمت الإضافة إلى السلة', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        cart = session.get('cart', [])
        if not cart:
            flash('السلة فارغة', 'danger')
            return redirect(url_for('cart'))
        total = 0
        items = []
        for item in cart:
            product = Product.query.get(item['product_id'])
            if product:
                total += product.price * item['quantity']
                items.append((product, item['quantity']))
        order = Order(user_id=current_user.id if current_user.is_authenticated else None,
                     total=total, payment_method=payment_method)
        db.session.add(order)
        for product, qty in items:
            oi = OrderItem(order=order, product_id=product.id, quantity=qty, price=product.price)
            db.session.add(oi)
        db.session.commit()
        session['cart'] = []
        if payment_method in ('vodafone_cash', 'etisalat_wallet'):
            return redirect(url_for('payment_page', order_id=order.id))
        else:
            order.paid = True
            order.license_key = str(uuid.uuid4())
            db.session.commit()
            return redirect(url_for('order_success', order_id=order.id))
    cart = session.get('cart', [])
    products = []
    total = 0
    for item in cart:
        product = Product.query.get(item['product_id'])
        if product:
            products.append({'product': product, 'quantity': item['quantity']})
            total += product.price * item['quantity']
    return render_template('checkout.html', cart_items=products, total=total)

@app.route('/payment/<int:order_id>')
def payment_page(order_id):
    order = Order.query.get_or_404(order_id)
    wallet_number = "01001234567" if order.payment_method == 'vodafone_cash' else "01123456789"
    return render_template('payment.html', order=order, wallet_number=wallet_number)

@app.route('/confirm_payment/<int:order_id>', methods=['POST'])
def confirm_payment(order_id):
    order = Order.query.get_or_404(order_id)
    order.reference_number = request.form.get('reference_number')
    db.session.commit()
    flash('تم تسجيل المرجع. في انتظار التأكيد.', 'success')
    return redirect(url_for('order_success', order_id=order.id))

@app.route('/order/<int:order_id>')
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_success.html', order=order)

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    return render_template('admin/dashboard.html')

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/confirm_payment/<int:order_id>')
@login_required
def admin_confirm_payment(order_id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    order = Order.query.get_or_404(order_id)
    order.paid = True
    order.license_key = str(uuid.uuid4())
    db.session.commit()
    flash('تم تأكيد الدفع ومنح الترخيص.', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        flash('بيانات غير صحيحة', 'danger')
    return render_template('admin/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
