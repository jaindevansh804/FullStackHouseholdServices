from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import base64

db = SQLAlchemy()

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True, default=-1)
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'password': self.password
        }

class Customer(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100))
    password = db.Column(db.String(100))
    flagged = db.Column(db.Boolean, default=False)

    # establishing a relationship with the ServiceRequest table
    service_requests_sent = db.relationship('ServiceRequest', backref='customer', lazy=True)
    customer_reviews = db.relationship('Review', backref='customer', lazy=True)

    def to_json(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'password': self.password,
            'flagged': self.flagged
        }

class Professional(UserMixin, db.Model):
    #start primary key from 10000
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    username = db.Column(db.String(100))
    password = db.Column(db.String(100))
    date_created = db.Column(db.String(100))
    description = db.Column(db.String(100))
    service_type = db.Column(db.String(100))
    experience = db.Column(db.String(100))
    approved = db.Column(db.Boolean, default=False)
    

    pincode = db.Column(db.String(100), nullable=True)
    document_content = db.Column(db.String(100), nullable=True, default=9999)
    
    service_id = db.Column(db.Integer, db.ForeignKey('service.id', ondelete='CASCADE'), nullable=False)
    service_requests_recd = db.relationship('ServiceRequest', backref='professional', lazy=True)
    reviews = db.relationship('Review', backref='professional', lazy=True)

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'username': self.username,
            'password': self.password,
            'date_created': self.date_created,
            'description': self.description,
            'service_type': self.service_type,
            'experience': self.experience,
            'approved': self.approved,
            'service_name': self.service.name,
            'pincode': self.pincode,
            # 'document_content': "none" if self.document_content else None
        }

class Service(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(100))
    price = db.Column(db.String(100))
    time_required = db.Column(db.String(100))
    
    professionals = db.relationship('Professional', backref='service', lazy=True)
    service_requests = db.relationship('ServiceRequest', backref='service', lazy=True)

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'time_required': self.time_required
        }

class ServiceRequest(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_created = db.Column(db.Date, default=datetime.utcnow)
    date_scheduled = db.Column(db.Date, nullable=False) 
    status = db.Column(db.String(100))
    remarks = db.Column(db.String(300), nullable=True)

    service_id = db.Column(db.Integer, db.ForeignKey('service.id', ondelete='CASCADE'), nullable=False)
    professional_id = db.Column(db.Integer, db.ForeignKey('professional.id', ondelete='CASCADE'), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)

    reviews = db.relationship('Review', backref='service_request', lazy=True)

    def to_json(self):
        return {
            'id': self.id,
            'date_created': self.date_created,
            'date_scheduled': self.date_scheduled,
            'status': self.status,
            'remarks': self.remarks,
            'service_name': self.service.name,
            'professional_name': self.professional.name if self.professional else None,
            'customer_name': self.customer.username,
            # 'professional_email': self.professional.email,
            'service_location': self.professional.pincode if self.professional else None
            # 'customer_id': self.customer.id
        }

class Review(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer)
    description = db.Column(db.String(100))
    service_request_id = db.Column(db.Integer, db.ForeignKey('service_request.id', ondelete='CASCADE'), nullable=False)
    professional_review_id = db.Column(db.Integer, db.ForeignKey('professional.id', ondelete='CASCADE'), nullable=True)
    customer_review_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)

    def to_json(self):
        return {
            'id': self.id,
            'rating': self.rating,
            'description': self.description,
            'service_request_id': self.service_request_id,
            'professional_name': self.professional.name if self.professional_review_id else None,
            'customer_name': self.customer.username if self.customer_review_id else None,
            'date_scheduled': self.service_request.date_scheduled,
            'service_name': self.service_request.service.name


        }