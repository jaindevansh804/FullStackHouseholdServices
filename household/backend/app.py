from flask import Flask, render_template
from flask_login import LoginManager
from models import db, Admin, Professional, Customer, ServiceRequest
from routes import init_routes
from flask_jwt_extended import JWTManager
from celery.schedules import crontab
from email_config import send_email
from models import Professional, Customer
from celery import Celery
from cache import cache
from datetime import datetime, timedelta


app = Flask(__name__)
app.secret_key = 'your_random_secret_key_here'
app.config['JWT_SECRET_KEY'] = "thisissecret"
jwt_mgr = JWTManager(app)
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/1'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/2'

app.config['CACHE_TYPE'] = 'RedisCache'
app.config['CACHE_REDIS_URL'] = 'redis://localhost:6379/3'
app.config['DEFAULT_CACHE_TIMEOUT'] = 200
app.config['REDIS_URL'] = 'redis://localhost:6379'
app.config['broker_url'] = 'redis://localhost:6379/0'
app.config['result_backend'] = 'redis://localhost:6379/0'
app.config['broker_connection_retry_on_startup']=True


app.app_context().push()

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db?timeout=10'
# app.config['SECRET_KEY'] = 'thisissecret'

# initialize database
db.init_app(app)

init_routes(app)

celery = Celery("Application Jobs")
class ContextTask(celery.Task):
    def __call__(self, *args, **kwargs):
        with app.app_context():
            return self.run(*args, **kwargs)
celery.conf.update(broker_url=app.config['CELERY_BROKER_URL'], result_backend=app.config['CELERY_RESULT_BACKEND'])
celery.Task = ContextTask

@celery.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        #initaiate crontab daily at 4pm
        crontab(hour=16, minute=0),
        # crontab(),
        daily_reminder.s(),
        name='Daily Reminder'
    )
    sender.add_periodic_task(
        crontab(0, 0, day_of_month='1'),
        monthly_reminder.s(),
        name='Monthly Reminder'
    )

@celery.task
def daily_reminder():
    service_request = ServiceRequest.query.all()
    for req in service_request:
        print(req)
        if req.professional:
            to_email = req.professional.email
            msg = (
            f"Hello {req.professional.name},\n\n"
            f"A new service request for '{req.service.name}' has been created.\n"
            f"Date Scheduled: {req.date_scheduled}\n"
            f"Remarks: {req.remarks or 'None'}\n\n"
            f"Please ensure you are prepared for this service request.\n\n"
            f"Best regards,\n "
            )
            html_content = render_template(
            'monthly_report.html')
        else:
            continue
        send_email(to_email, 'Daily Reminder', msg, html_content)
        # print(f'Sent email to {req.professional.name}')
    return 'DAILY REMINDER SENT'

@celery.task
def monthly_reminder():
    today = datetime.utcnow()
    first_day_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_day_of_last_month = today.replace(day=1) - timedelta(days=1)

    customers = Customer.query.filter_by(flagged=False).all()

    for cust in customers:
        services_requested = ServiceRequest.query.filter(
            ServiceRequest.customer_id == cust.id,
            ServiceRequest.date_created.between(first_day_of_last_month, last_day_of_last_month)
        ).count()

        services_completed = ServiceRequest.query.filter(
            ServiceRequest.customer_id == cust.id,
            ServiceRequest.status == 'Closed',
            ServiceRequest.date_created.between(first_day_of_last_month, last_day_of_last_month)
        ).count()

        services_pending = ServiceRequest.query.filter(
            ServiceRequest.customer_id == cust.id,
            ServiceRequest.status != 'Closed',
            ServiceRequest.date_created.between(first_day_of_last_month, last_day_of_last_month)
        ).count()

        # Generate the HTML content
        html_content = render_template(
            'monthly_report.html',
            username=cust.username,
            services_requested=services_requested,
            services_completed=services_completed,
            services_pending=services_pending,
            month=first_day_of_last_month.strftime('%B %Y')
        )

        # Send the email with the HTML report
        send_email(
            cust.email,
            subject=f"Monthly Activity Report - {first_day_of_last_month.strftime('%B %Y')}",
            body='your report is attached',
            html=html_content  # Use HTML content
        )

        print(f"Sent monthly report to {cust.username}")

    return 'MONTHLY REMINDER SENT'



app.app_context().push()


cache.init_app(app)
app.app_context().push()
# create initial admin user
with app.app_context():
    db.create_all()

    if not db.session.query(Professional).first():
        first_professional = Professional(
            id=10000,
            name='First Pro',
            username='firstpro',
            password='password',
            description='Example',
            service_type='Type',
            experience='5 years',
            service_id=1
        )
        db.session.add(first_professional)
        db.session.commit()

    admin_exist = Admin.query.filter_by(name='admin').first()
    if not admin_exist:
        admin_exist = Admin(name='admin', password='admin')
        db.session.add(admin_exist)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)