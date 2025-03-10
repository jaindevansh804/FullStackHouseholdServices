from flask import render_template, request, redirect, url_for, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.wrappers import Response as HTTPResponse
from datetime import datetime
import pytz
import io
from functools import wraps
from models import db, Admin, Customer, Professional, Service, ServiceRequest, Review
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, get_jwt, verify_jwt_in_request
from cache import cache
from flask_cors import CORS
from flask_cors import cross_origin
import os
from openpyxl import Workbook


def init_routes(app):

    #-------------------------------- ADMIN ROUTES --------------------------------
    #allow cors from all sources

    CORS(app, resources={r"/*": {"origins": ["http://localhost:8080"]}})

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if request.method == 'POST':
            data = request.get_json()
            name = data['name']
            password = data['password']
            admin = Admin.query.filter_by(name=name).first()
            if admin and admin.password == password:
                token = create_access_token(identity=admin.name, additional_claims={"type":"admin", "id":admin.id})
                return {"access_token": token}, 200
            else:
                return ValueError({'message': 'Invalid username or password'}, 400)
        return jsonify({'message': 'Invalid request'}, 400)

    @app.route('/admin/dashboard', methods=['GET', 'POST'])
    @jwt_required()
    @cache.memoize(timeout=50)
    def admin_dashboard():
        list_of_services = [service.to_json() for service in Service.query.all()]
        
        not_approved_professionals = [professional.to_json() for professional in Professional.query.filter_by(approved=False).all()]
        # Professional.query.filter_by(approved=False).all()
        
        #approved professionals
        list_of_professionals = [professional.to_json() for professional in Professional.query.filter_by(approved=True).all()]

        list_of_customers = [customer.to_json() for customer in Customer.query.all()]

        list_of_service_requests = [service_request.to_json() for service_request in ServiceRequest.query.all()]

        list_of_reviews = [review.to_json() for review in Review.query.join(ServiceRequest).order_by(ServiceRequest.id.asc()).all()]

        return jsonify({
    'services': list_of_services,
    'professionals': list_of_professionals,
    'customers': list_of_customers,
    'service_requests': list_of_service_requests,
    'reviews': list_of_reviews,
    'not_approved_professionals': not_approved_professionals
}), 200

    @jwt_required()
    @app.route('/admin/addservice', methods=['POST'])
    def addservice():
        verify_jwt_in_request()
        if request.method == 'POST':
            data = request.get_json()
            name = data['name']
            description = data['description']
            price = data['price']
            time_required = data['time_required']
            service = Service(name=name, description=description, price=price, time_required=time_required)
            db.session.add(service)
            db.session.commit()
            return jsonify({'message': 'Service added successfully!'}, 200)
        return jsonify({'message': 'Invalid request'}, 400)

    @app.route('/admin/editservice', methods=['GET', 'POST'])
    @jwt_required()
    def editservice():
        verify_jwt_in_request()
        id = request.args.get('id')
        print(id)
        service_id = id
        service = Service.query.filter_by(id=service_id).first()

        data = request.get_json()
        print(data)

        service.name = data["name"]
        service.description = data["description"]
        service.price = data["price"]
        service.time_required = data["time_required"]
        db.session.commit()
        return jsonify({'message': 'Service updated successfully!'}, 200)
        # return jsonify({'message': 'Invalid request'}, 400)

    @app.route('/admin/deleteservice', methods=['GET', 'POST'])
    @jwt_required()
    def deleteservice():
        data = request.get_json()
        service_id = data['id']
        service = Service.query.get(service_id)

        #if that service exists then find the corresponding professionals and service requests
        #for those professionals and service requests, delete review and service request and the professional itself
        if service:
            professionals = Professional.query.filter_by(service_id=service_id).all()
            service_requests = ServiceRequest.query.filter_by(service_id=service_id).all()
        
            reviews = Review.query.join(ServiceRequest).filter(ServiceRequest.service_id == service_id).all()
        
            for review in reviews:
                db.session.delete(review)
            
            for service_request in service_requests:
                db.session.delete(service_request)
            
            for professional in professionals:
                db.session.delete(professional)

            db.session.delete(service)
            db.session.commit()
        return jsonify({'message': 'Service deleted successfully!'}, 200)

    @app.route('/download_document/<int:professional_id>')
    def download_document(professional_id):
        professional = Professional.query.get(professional_id)
        
        if professional and professional.document_content:
            return send_file(
                io.BytesIO(professional.document_content),
                download_name='document.pdf',
                as_attachment=True
            )
        return "Document not found", 404


    @app.route('/admin/approve_professional', methods=['GET', 'POST'])
    def approve_professional():
        data = request.get_json()
        professional_id = data['id']
        professional = Professional.query.get(professional_id)
        professional.approved = True
        db.session.commit()
        return jsonify({'message': 'Professional approved successfully!'}, 200)

    @app.route('/admin/view_professional', methods=['GET'])
    def view_professional():
    # Retrieve 'id' from query parameters
        professional_id = request.args.get('id')
        if not professional_id:
            return jsonify({"error": "Professional ID is required"}), 400

        # Query the database
        this_professional = Professional.query.get(professional_id)
        if not this_professional:
            return jsonify({"error": "Professional not found"}), 404

        review_for_professional = Review.query.filter_by(professional_review_id=this_professional.id).all()

        # Return JSON response
        return jsonify({
            'professional': this_professional.to_json(),
            'review_for_professional': [review.to_json() for review in review_for_professional]
        }), 200
    #   render_template('Professional/view_professional.html', props={'professional': this_professional, 'review_for_professional': review_for_professional})

    @app.route('/admin/flag_professional', methods=['GET', 'POST'])
    def flag_professional():
        data = request.get_json()
        professional_id = data['id']
        professional = Professional.query.get(professional_id)
        professional.approved = False
        db.session.commit()
        return jsonify({'message': 'Professional flagged successfully!'}, 200)

    @app.route('/admin/view_customer', methods=['GET'])
    def view_customer():
        customer_id = request.args.get('id')
        
        # Ensure the ID is provided
        if not customer_id:
            return jsonify({"error": "Customer ID is required"}), 400
        
        # Query the database for the customer
        this_customer = Customer.query.get(customer_id)
        
        # Handle case where customer does not exist
        if not this_customer:
            return jsonify({"error": "Customer not found"}), 404
        
        # Return customer data in JSON format
        return jsonify({'customer': this_customer.to_json()}), 200
    # render_template('customer/view_customer.html', props={'customer': this_customer})

    @app.route('/admin/flag_customer', methods=['GET', 'POST'])
    def flag_customer():
        data = request.get_json()
        customer_id = data['id']
        customer = Customer.query.get(customer_id)
        customer.flagged = True
        db.session.commit()
        return jsonify({'message': 'Customer flagged successfully!'}, 200)

    @app.route('/admin/unflag_customer', methods=['GET', 'POST'])
    def unflag_customer():
        data = request.get_json()
        customer_id = data['id']
        customer = Customer.query.get(customer_id)
        customer.flagged = False
        db.session.commit()
        return jsonify({'message': 'Customer unflagged successfully!'}, 200)

    #-------------------------------- Professional ROUTES --------------------------------

    @app.route('/professional/register', methods=['GET', 'POST'])
    def register_professional():
        
        service_types_offered = Service.query.all()

        if request.method == 'POST':
            data = request.get_json()
            name = data['name']
            email = data['email']
            username = data['username']
            password = data['password']
            description = data['description']
            service_type = data['service_type']
            experience = data['experience']
            pincode = data['pincode']
            # document = data['document']
            # document_content = document
            if Professional.query.filter_by(username=username).first():
                return jsonify({'message': 'Username already exists. Please choose a different username.'}, 400)

            # Get the service ID
            service = Service.query.filter_by(name=service_type).first()
            if not service:
                return jsonify({'message': 'Invalid service type selected.'}, 400)
            service_id = service.id

            # Set the date created to the current timestamp in Indian timezone
            india_tz = pytz.timezone('Asia/Kolkata')
            date_created = datetime.now(india_tz)

            # Create a new Professional object
            new_professional = Professional(
                name=name,
                email=email,
                username=username,
                password=generate_password_hash(password),
                date_created=date_created,
                description=description,
                experience=experience,
                service_id=service_id,
                service_type=service_type,
                approved=False,
                pincode=pincode
                # document_content = document_content
            )

            db.session.add(new_professional)
            db.session.commit()

            return jsonify({'message': 'Registration successful!'}, 200)

        return jsonify({'message': 'Invalid request'}, 400)
        # render_template('Professional/professional_register.html', props={'services_types_offered': service_types_offered})

    CORS(app)
    @app.route('/professional/login', methods=['GET', 'POST'])
    def professional_login():
        if request.method == 'POST':
            data = request.get_json()
            username = data['username']
            password = data['password']
            professional = Professional.query.filter_by(username=username).first()
            if professional and check_password_hash(professional.password, password):
                token = create_access_token(identity=professional.username, additional_claims={"type":"professional", "id":professional.id})
                return {"access_token": token}, 200
            else:
                return ValueError({'message': 'Invalid username or password'}, 400)
            
        return jsonify({'message': 'Invalid request'}, 400)

    @app.route('/professional/dashboard', methods=['GET', 'POST'])
    @jwt_required()
    def professional_dashboard():
        print(f"JWT Payload: {get_jwt()}")
        if get_jwt()['type'] != 'professional':
            return jsonify({'message': 'You do not have permission to access this page.'}), 403
        
        user_identity = get_jwt_identity()
        print(f"User Identity: {user_identity}")
        
        current = Professional.query.filter_by(username=user_identity).first()
        if not current.approved:
            return jsonify({'message': 'Your account is not approved yet. Please wait for the admin to approve your account.'}), 403
        
        # Modify the query to get related data
        pending_service_requests = ServiceRequest.query.join(Service).filter(
            Service.name == current.service.name, 
            ServiceRequest.status == 'Pending'
        ).all()
        
        accepted_service_requests = ServiceRequest.query.join(Service).filter(
            Service.name == current.service.name, 
            ServiceRequest.status == 'Accepted'
        ).all()
        
        closed_service_requests = ServiceRequest.query.join(Service).filter(
            Service.name == current.service.name, 
            ServiceRequest.status == 'Closed'
        ).all()
        
        review_of_professional = Review.query.filter_by(professional_review_id=current.id).all()
        
        # Custom JSON serialization
        return jsonify({
            'professional_info': {
                'username': current.username,
                'service_type': current.service.name,
                'description': current.description,
                'pincode': current.pincode
            },
            'pending_service_requests': [
                {
                    'id': req.id,
                    'customer': {
                        'username': req.customer.username,
                        'email': req.customer.email
                    },
                    'service': {
                        'name': req.service.name,
                        'price': req.service.price
                    },
                    'date_scheduled': req.date_scheduled.isoformat() if req.date_scheduled else None,
                    'remarks': req.remarks
                } for req in pending_service_requests
            ],
            'accepted_service_requests': [
                {
                    'id': req.id,
                    'customer': {
                        'username': req.customer.username,
                        'email': req.customer.email
                    },
                    'service': {
                        'name': req.service.name,
                        'price': req.service.price
                    },
                    'date_scheduled': req.date_scheduled.isoformat() if req.date_scheduled else None,
                    'remarks': req.remarks
                } for req in accepted_service_requests
            ],
            'closed_service_requests': [
                {
                    'id': req.id,
                    'customer': {
                        'username': req.customer.username,
                        'email': req.customer.email
                    },
                    'service': {
                        'name': req.service.name
                    },
                    'date_scheduled': req.date_scheduled.isoformat() if req.date_scheduled else None,
                    'remarks': req.remarks
                } for req in closed_service_requests
            ],
            'review_of_professional': [
                {
                    'id': review.id,
                    'service_request': {
                        'id': review.service_request.id,
                        'service': {
                            'name': review.service_request.service.name
                        },
                        'date_scheduled': review.service_request.date_scheduled.isoformat() if review.service_request.date_scheduled else None
                    },
                    'customer': {
                        'username': review.customer.username,
                        'email': review.customer.email
                    },
                    'rating': review.rating,
                    'description': review.description
                } for review in review_of_professional
            ]
        }), 200
       # return render_template('Professional/professional_dashboard.html', props={'professional_info': professional_info, 'pending_service_requests': pending_service_requests, 'accepted_service_requests': accepted_service_requests, 'rejected_service_requests': rejected_service_requests, 'closed_service_requests': closed_service_requests, 'review_of_professional': review_of_professional})


    @app.route('/professional/acceptrequest', methods=['POST'])
    @jwt_required()
    def accept_request():
        current = Professional.query.filter_by(username=get_jwt_identity()).first()
        if not current:
            return jsonify({"message": "User not found"}), 404
        
        # Get the data from the request
        data = request.get_json()
        request_id = data.get('id')
        if not request_id:
            return jsonify({"message": "Request ID is missing"}), 400
        
        # Fetch the service request from the database
        service_request = ServiceRequest.query.get(request_id)
        if not service_request:
            return jsonify({"message": "Service request not found"}), 404
        
        # Update the service request and commit changes
        service_request.status = 'Accepted'
        service_request.professional_id = current.id
        db.session.commit()
        
        return jsonify({'message': 'Request accepted successfully!'}), 200

    @jwt_required()
    @app.route('/professional/rejectrequest', methods=['GET', 'POST'])
    def reject_request():
        verify_jwt_in_request()
        if get_jwt()['type'] != 'professional':
            return jsonify({'message': 'You do not have permission to access this page.'}, 403)
        current = Professional.query.filter_by(username=get_jwt_identity()).first()

        data = request.get_json()
        request_id = data['id']
        
        service_request = ServiceRequest.query.get(request_id)
        service_request.status = 'Rejected'
        service_request.professional_id = current.id
        db.session.commit()
        return jsonify({'message': 'Request rejected successfully!'}, 200)

    @app.route('/professional/close_request', methods=['GET', 'POST'])
    def close_request():
        data = request.get_json()
        request_id = data['id']
        service_request = ServiceRequest.query.get(request_id)
        service_request.status = 'Closed'
        db.session.commit()
        return jsonify({'message': 'Request closed successfully!'}, 200)

    # -------------------------------- Customer ROUTES --------------------------------

    @app.route('/customer/register', methods=['GET', 'POST'])
    def register_customer():
        if request.method == 'POST':
            data = request.get_json()
            username = data['username']
            password = data['password']
            email = data['email']
            if Customer.query.filter_by(username=username).first():
                return jsonify({'message': 'Username already exists. Please choose a different username.'}, 400)

            new_customer = Customer(username=username, email = email, password=generate_password_hash(password))
            db.session.add(new_customer)
            db.session.commit()

            return jsonify({'message': 'Registration successful!'}, 200)
        return jsonify({'message': 'Invalid request'}, 400)

    @app.route('/customer/login', methods=['GET', 'POST'])
    def customer_login():
        if request.method == 'POST':
            data = request.get_json()

            username = data['username']
            password = data['password']
            customer = Customer.query.filter_by(username=username).first()
            if customer and check_password_hash(customer.password, password):
                token = create_access_token(identity=customer.username, additional_claims={"type":"customer", "id":customer.id})
                return {"access_token": token}, 200
            else:
                # flash('Invalid username or password')
                return ValueError({'message': 'Invalid username or password'}, 400)
        return jsonify({'message': 'Invalid request'}, 400)

    @app.route('/customer/dashboard', methods=['GET', 'POST'])
    @jwt_required()
    def customer_dashboard():
        if get_jwt()['type'] != 'customer':
            return jsonify({'message': 'You do not have permission to access this page.'}, 403)
        
        user_identity = get_jwt_identity()
        current = Customer.query.filter_by(username=user_identity).first()
        if current.flagged:
            return HTTPResponse('Your account has been flagged. Please contact the admin for more information.', status=403)

        #show all services for which professionals are available for
        available_services = db.session.query(Service).join(Professional)
        
        #join returns multiple entries, thus find the unique of them all
        all_services = available_services.distinct().all()

        #getting all service_request of the customer id currently logged in
        service_requests = ServiceRequest.query.filter_by(customer_id=current.id).all()
        closed_service_requests = ServiceRequest.query.filter_by(customer_id=current.id, status='Closed').all()
        customer_info = current
        return jsonify({'customers': [customer_info.to_json()], 'service_requests': [service_request.to_json() for service_request in service_requests], 'closed_service_requests': [closed_service_requests.to_json() for closed_service_requests in closed_service_requests], 'services': [service.to_json() for service in all_services]}, 200)

    @app.route('/customer/edit_service_request', methods=['GET', 'POST'])
    @jwt_required()
    def edit_service_request():
        if get_jwt_identity() != 'customer':
            return jsonify({'message': 'You do not have permission to access this page.'}, 403)
        current = Customer.query.filter_by(username=get_jwt_identity()).first()

        services = Service.query.all()

        if request.method == 'POST':
            data = request.get_json()

            request_id = data['id']
            this_service_request = ServiceRequest.query.filter_by(id=request_id, customer_id=current.id).first()

            service_id = data['service_id']
            date_scheduled_raw = data['date_scheduled']
            date_scheduled = datetime.strptime(date_scheduled_raw, '%Y-%m-%d').date()
            remarks = data['remarks']

            this_service_request.service_id = service_id
            this_service_request.date_scheduled = date_scheduled
            this_service_request.remarks = remarks

            db.session.commit()
            return jsonify({'message': 'Service request updated successfully!'}, 200)
            # return redirect(url_for('customer_dashboard'))

        return jsonify({'message': 'Invalid request'}, 400)
        # return render_template('customer/edit_service_request.html', props={'this_service_request': this_service_request, 'services': services})

    @jwt_required()
    @cross_origin(origins="http://localhost:8080")
    @app.route('/customer/requestservice', methods=['GET', 'POST'])
    def request_service():
        # if get_jwt()['type'] != 'customer':
        #     return jsonify({'message': 'You do not have permission to access this page.'}, 403)
        verify_jwt_in_request()
        current = Customer.query.filter_by(username=get_jwt_identity()).first()

        services = Service.query.all()
        professionals = Professional.query.all()
        service_requests = ServiceRequest.query.filter_by(customer_id=current.id).all()
        if request.method == 'POST':
            data = request.get_json()
            service_name = data['service_name']
            date_scheduled_raw = data['schedule_date']
            remarks = data['remarks']

            #only fetching the date
            date_scheduled = datetime.strptime(date_scheduled_raw, '%Y-%m-%d').date()  
            service_name = Service.query.filter_by(name=service_name).first()

            service_id = service_name.id

            professionals = Professional.query.filter_by(service_id=service_id).all()
            
            if not professionals:
                # flash('No professionals are registered for the selected service. Please choose a different service.', 'danger')
                return jsonify({'message': 'No professionals are registered for the selected service. Please choose a different service.'}, 400)

            customer = current
            new_request = ServiceRequest(
                date_scheduled=date_scheduled,
                status='Pending',
                service_id=service_id,
                customer_id=customer.id,
                remarks=remarks
            )
            db.session.add(new_request)
            db.session.commit()
            # flash('Service request sent successfully!', 'success')
            return jsonify({'message': 'Service request sent successfully!'}, 200)
        return jsonify({'message': 'Invalid request'}, 400)
        # return render_template('customer/request_service.html', props={'services': services, 'professionals': professionals, 'service_requests': service_requests})

    @app.route('/customer/review', methods=['GET', 'POST'])
    def review():
        # get the service request ID from query parameters
        # service_request_id = request.args.get('id', type=int)
        if request.method == 'POST':
            data = request.get_json()
            service_request_id = request.args.get('id')
            service_request = ServiceRequest.query.get(service_request_id)

            rating = data['rating']
            description = data['comment']
            professional_id = service_request.professional_id
            customer_id = service_request.customer_id

            new_review = Review(
                rating=rating,
                description=description,
                service_request_id=service_request.id,
                professional_review_id=professional_id,
                customer_review_id=customer_id
            )

                #change the status of the service request to reviewed
            service_request.status = 'Reviewed'
                
            db.session.add(new_review)
            db.session.commit()
            return jsonify({'message': 'Review added successfully!'}, 200)
            
        return jsonify({'message': 'Invalid request'}, 400)

    @app.route('/customer/closerequest', methods=['GET', 'POST'])
    def customer_close_request():
        data = request.get_json()
        request_id = data['id']
        service_request = ServiceRequest.query.get(request_id)
        service_request.status = 'Closed'
        db.session.commit()
        return jsonify({'message': 'Request closed successfully!'}, 200)

    @app.route('/customer/view_reviews', methods=['GET', 'POST'])
    def view_review():
        # data = request.get_json()
        service_request_id = request.args.get('id')
        service_request = ServiceRequest.query.get(service_request_id)
        reviews = Review.query.filter(Review.service_request.has(id=service_request_id)).first()
        print(reviews)
        return jsonify({'service_request': service_request.to_json(), 'reviews': [reviews.to_json()]}, 200)
    


    @app.route('/search_services', methods=['GET', 'POST'])
    def search_services():
        pincode = request.args.get('pincode')

        available = db.session.query(Service).join(Professional)
        
        if pincode:
            query = available.filter(Professional.pincode == pincode)
        
        services = query.distinct().all()
        return jsonify({'services': [service.to_json() for service in services]}, 200)
        # render_template('Customer/services_list.html', services=services, pincode=pincode, service_name=service_name)

    # -------------------------------- GENERIC ROUTES --------------------------------

    @app.route('/')
    def home():
        return jsonify({'message': 'Welcome to the home page!'}, 200)

    @app.route('/about')
    def about():
        return jsonify({'message': 'Welcome to the about page!'}, 200)

    @app.route('/login')
    def login():
        return jsonify({'message': 'Welcome to the login page!'}, 200)

    @app.route('/register')
    def register():
        return jsonify({'message': 'Welcome to the register page!'}, 200)



    @app.route('/api/services', methods=['GET'])
    def get_services():
        try:
            # Fetch all services from the database
            services = Service.query.all()
            # Convert each service to a dictionary
            services_list = [{"id": service.id, "name": service.name} for service in services]

            return jsonify({"services_types_offered": services_list}), 200
        except Exception as e:
            print(f"Error fetching services: {e}")
            return jsonify({"message": "Error fetching services."}), 500

    @jwt_required()    
    @app.route('/api/servicesbyid', methods=['GET'])
    def servicebyid():
        service_id = request.args.get('id')
        service = Service.query.get(service_id)
        return jsonify({'service': service.to_json()}), 200
    
    @app.route('/admin/export_service_requests', methods=['GET'])
    @jwt_required()  # Ensures only authenticated admins can trigger this
    def export_service_requests_excel():
        try:
            service_requests = ServiceRequest.query.all()
            print("Fetched service requests:", service_requests)

            if not service_requests:
                return jsonify({'message': 'No service requests found'}), 404

            # Create an Excel workbook
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Service Requests"

            # Write headers
            headers = ["Request ID", "Customer", "Professional", "Service", "Remarks"]
            sheet.append(headers)

            # Write service request data
            for request in service_requests:
                print(f"Processing request: {request}")  # Log each request for debugging
                sheet.append([
                    request.id,
                    request.customer.username if request.customer else 'N/A',
                    request.professional.name if request.professional else 'N/A',
                    request.service.name if request.service else 'N/A',
                    request.remarks or 'N/A'
                ])

            # Save the Excel file
            file_path = f'service_requests.xlsx'
            workbook.save(file_path)

            # Send the file to the user for download
            return send_file(file_path, as_attachment=True, download_name="service_requests.xlsx")

        except Exception as e:
            print(f"Error: {e}")  # Log the actual error
            return jsonify({'error': str(e)}), 500
        # finally:
        #     # Clean up the file after serving (optional)
        #     if os.path.exists(file_path):
        #         os.remove(file_path)