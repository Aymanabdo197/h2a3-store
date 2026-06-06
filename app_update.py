import sys
sys.path.insert(0, '.')
from app import app, db, Product

with app.app_context():
    product = Product.query.filter_by(name='HASNAA PRO v6.0').first()
    if not product:
        product = Product.query.filter_by(name='HASNAA PRO v11.0').first()
    if not product:
        product = Product.query.filter_by(name='HASNAA PRO v14.1').first()
    if not product:
        product = Product(
            name='HASNAA PRO v14.1 Ultimate',
            description='أداة اختبار الاختراق المتكاملة – استكشاف شامل لجميع الأنظمة (Linux/Windows/macOS)، مولد حمولات ديناميكي، فحص تلقائي بدون FUZZ، تجاوز WAF، تقارير CVSS احترافية.',
            price=49,
            category='pentest',
            plan='enterprise'
        )
        db.session.add(product)
    else:
        product.name = 'HASNAA PRO v14.1 Ultimate'
        product.description = 'أداة اختبار الاختراق المتكاملة – استكشاف شامل لجميع الأنظمة (Linux/Windows/macOS)، مولد حمولات ديناميكي، فحص تلقائي بدون FUZZ، تجاوز WAF، تقارير CVSS احترافية.'
        product.price = 49
    db.session.commit()
    print("✅ تم تحديث منتج HASNAA PRO في المتجر")
