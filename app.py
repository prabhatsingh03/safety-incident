from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from uuid import uuid4
import base64
import os

# --- App Configuration ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'safety_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False) # 'admin', 'safety'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    projectCode = db.Column(db.String(50), unique=True, nullable=False)
    projectName = db.Column(db.String(200), nullable=False)
    projectManagerContractor = db.Column(db.String(100))
    projectManagerClient = db.Column(db.String(100))
    clientName = db.Column(db.String(100))
    contractor = db.Column(db.String(100))

class SubContractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    project_code = db.Column(db.String(50), nullable=False)

class Observation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    projectCode = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    raisedBy = db.Column(db.String(100), nullable=False)
    issueType = db.Column(db.String(50), nullable=False)
    safetyCategory = db.Column(db.String(50), nullable=False)
    observation = db.Column(db.Text, nullable=False)
    observationPhoto = db.Column(db.Text) # Base64 string
    contractor = db.Column(db.String(100), nullable=False, default='SIL')
    subContractor = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Open')
    compliance = db.Column(db.Text)
    complianceDate = db.Column(db.String(20))
    compliancePhoto = db.Column(db.Text) # Base64 string

# --- Helper Functions ---
def setup_database(app):
    with app.app_context():
        db.create_all()
        
        # Check if users exist, if not, create default admin/safety users
        if not User.query.first():
            admin_pass = generate_password_hash('Simon@54321', method='pbkdf2:sha256')
            safety_pass = generate_password_hash('Simon@54321', method='pbkdf2:sha256')
            admin = User(username='admin@simonindia.ai', password_hash=admin_pass, role='admin')
            safety = User(username='safety@simonindia.ai', password_hash=safety_pass, role='safety')
            db.session.add(admin)
            db.session.add(safety)
            print("Created default admin and safety users.")
            db.session.commit()
        
        # Initialize projects if they don't exist
        if not Project.query.first():
            projects_data = [
                {
                    'projectCode': 'I-30059',
                    'projectName': '5th Evaporator',
                    'projectManagerContractor': 'Biswa Ranjan Dash',
                    'projectManagerClient': 'PPL Manager',
                    'clientName': 'PPL',
                    'contractor': 'SIL'
                },
                {
                    'projectCode': 'I-2501F001',
                    'projectName': 'Sulphur Melting & Filtration Facility',
                    'projectManagerContractor': 'Biswa Ranjan Dash',
                    'projectManagerClient': 'PPL Manager',
                    'clientName': 'PPL',
                    'contractor': 'SIL'
                },
                {
                    'projectCode': 'I-2501F002',
                    'projectName': '23MW Power Plant TG-4, PPL',
                    'projectManagerContractor': 'Biswa Ranjan Dash',
                    'projectManagerClient': 'PPL Manager',
                    'clientName': 'PPL',
                    'contractor': 'SIL'
                },
                {
                    'projectCode': 'I-2503F002',
                    'projectName': '8000T Phosphoric Acid Tank, MCFL',
                    'projectManagerContractor': 'Biswa Ranjan Dash',
                    'projectManagerClient': 'MCFL Manager',
                    'clientName': 'MCFL',
                    'contractor': 'SIL'
                }
            ]
            
            for project_data in projects_data:
                project = Project(**project_data)
                db.session.add(project)
            
            print("Created default projects.")
            db.session.commit()
        
        # Initialize contractors for I-30059 if they don't exist
        if not SubContractor.query.first():
            contractors_data = [
                {'name': 'RRPL', 'project_code': 'I-30059'},
                {'name': 'CHEMDIST', 'project_code': 'I-30059'},
                {'name': 'KRUPANJAL', 'project_code': 'I-30059'},
                {'name': 'BBGC', 'project_code': 'I-30059'},
                {'name': 'FRIENDS', 'project_code': 'I-30059'},
                {'name': 'RK ENGG', 'project_code': 'I-30059'},
                {'name': 'BIMAL', 'project_code': 'I-30059'},
                {'name': 'M SQUARE', 'project_code': 'I-30059'},
                {'name': 'CUMI', 'project_code': 'I-30059'},
                {'name': 'SAMANTARAY', 'project_code': 'I-30059'}
            ]
            
            for contractor_data in contractors_data:
                contractor = SubContractor(**contractor_data)
                db.session.add(contractor)
            
            print("Created default contractors for I-30059.")
            db.session.commit()
        
        print("Database setup complete. The database is ready.")

def save_base64_image(data_url: str, prefix: str) -> str:
    """Save a base64 data URL image to disk and return public URL path."""
    if not data_url or not isinstance(data_url, str):
        return ''
    if not data_url.startswith('data:'):
        # Assume it's already a URL
        return data_url
    try:
        header, b64data = data_url.split(',', 1)
        # header example: data:image/png;base64
        mime = header.split(';')[0].split(':', 1)[1] if ';' in header else 'application/octet-stream'
        ext = 'bin'
        if '/' in mime:
            ext = mime.split('/')[-1]
            # normalize common ext
            if ext == 'jpeg':
                ext = 'jpg'
        filename = f"{prefix}_{uuid4().hex}.{ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(file_path, 'wb') as f:
            f.write(base64.b64decode(b64data))
        return f"/uploads/{filename}"
    except Exception:
        return ''


# --- API Routes ---
@app.route('/')
def serve_index():
    return render_template('index.html')

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    # Serve files saved in uploads folder
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"message": "Invalid username or password"}), 401
    
    return jsonify({"username": user.username, "role": user.role})

@app.route('/api/data', methods=['GET'])
def get_initial_data():
    # Helper to convert SQLAlchemy objects to dictionaries
    def to_dict(obj):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    
    projects = Project.query.all()
    observations = Observation.query.order_by(Observation.id.desc()).all()
    sub_contractors_list = SubContractor.query.all()
    
    sub_contractors_map = {}
    for sc in sub_contractors_list:
        if sc.project_code not in sub_contractors_map:
            sub_contractors_map[sc.project_code] = []
        sub_contractors_map[sc.project_code].append(to_dict(sc))

    return jsonify({
        "projects": [to_dict(p) for p in projects],
        "observations": [to_dict(o) for o in observations],
        "sub_contractors": sub_contractors_map
    })
    
@app.route('/api/projects', methods=['POST'])
def add_project():
    data = request.get_json()
    # TODO: Add validation and role check (only admin)
    
    if Project.query.filter_by(projectCode=data.get('projectCode')).first():
        return jsonify({"message": "Project code already exists."}), 409

    new_project = Project(**data)
    db.session.add(new_project)
    db.session.commit()
    
    def to_dict(obj):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    return jsonify(to_dict(new_project)), 201

@app.route('/api/subcontractors', methods=['POST'])
def add_subcontractor():
    data = request.get_json()
    project_code = data.get('project_code')
    name = data.get('name')

    if not project_code or not name:
        return jsonify({"message": "Project code and name are required."}), 400

    # Optional: Check if the project exists
    if not Project.query.filter_by(projectCode=project_code).first():
         return jsonify({"message": "Project not found."}), 404

    new_subcontractor = SubContractor(project_code=project_code, name=name)
    db.session.add(new_subcontractor)
    db.session.commit()
    
    def to_dict(obj):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        
    return jsonify(to_dict(new_subcontractor)), 201


@app.route('/api/observations', methods=['POST'])
def add_observation():
    try:
        data = request.get_json()
        print(f"Received observation data: {data}")  # Debug logging
        
        # Validate required fields
        required_fields = ['projectCode', 'date', 'raisedBy', 'issueType', 'safetyCategory', 'observation']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"message": f"Missing required field: {field}"}), 400
        
        # Save photos to disk if they are base64 data URLs
        if data.get('observationPhoto'):
            data['observationPhoto'] = save_base64_image(data.get('observationPhoto'), 'observation')
        if data.get('compliancePhoto'):
            data['compliancePhoto'] = save_base64_image(data.get('compliancePhoto'), 'compliance')
        
        # Create new observation with only valid fields
        observation_data = {}
        valid_fields = ['projectCode', 'date', 'raisedBy', 'issueType', 'safetyCategory', 'observation', 
                       'observationPhoto', 'contractor', 'subContractor', 'status', 'compliance', 'complianceDate', 'compliancePhoto']
        
        for field in valid_fields:
            if field in data and data[field] is not None:
                observation_data[field] = data[field]
        
        new_obs = Observation(**observation_data)
        db.session.add(new_obs)
        db.session.commit()
        
        def to_dict(obj):
            return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        
        return jsonify(to_dict(new_obs)), 201
        
    except Exception as e:
        print(f"Error creating observation: {str(e)}")  # Debug logging
        db.session.rollback()
        return jsonify({"message": f"Failed to create observation: {str(e)}"}), 500

@app.route('/api/observations/<int:obs_id>', methods=['PUT'])
def update_observation(obs_id: int):
    try:
        data = request.get_json()
        print(f"Updating observation {obs_id} with data: {data}")  # Debug logging
        
        obs = Observation.query.get_or_404(obs_id)
        
        # Save photos to disk if updated as base64 data URLs
        if 'observationPhoto' in data and data.get('observationPhoto'):
            data['observationPhoto'] = save_base64_image(data.get('observationPhoto'), 'observation')
        if 'compliancePhoto' in data and data.get('compliancePhoto'):
            data['compliancePhoto'] = save_base64_image(data.get('compliancePhoto'), 'compliance')
        
        # Update only valid fields
        valid_fields = ['projectCode', 'date', 'raisedBy', 'issueType', 'safetyCategory', 'observation', 
                       'observationPhoto', 'contractor', 'subContractor', 'status', 'compliance', 'complianceDate', 'compliancePhoto']
        
        for key, value in data.items():
            if key in valid_fields and hasattr(obs, key):
                setattr(obs, key, value)
        
        db.session.commit()
        
        def to_dict(obj):
            return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        
        return jsonify(to_dict(obs))
        
    except Exception as e:
        print(f"Error updating observation: {str(e)}")  # Debug logging
        db.session.rollback()
        return jsonify({"message": f"Failed to update observation: {str(e)}"}), 500

# Project Management APIs
@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id: int):
    try:
        data = request.get_json()
        project = Project.query.get_or_404(project_id)
        
        # Update project fields
        for key, value in data.items():
            if hasattr(project, key):
                setattr(project, key, value)
        
        db.session.commit()
        
        def to_dict(obj):
            return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        
        return jsonify(to_dict(project))
        
    except Exception as e:
        print(f"Error updating project: {str(e)}")
        db.session.rollback()
        return jsonify({"message": f"Failed to update project: {str(e)}"}), 500

@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id: int):
    try:
        project = Project.query.get_or_404(project_id)
        
        # Check if project has observations
        observations_count = Observation.query.filter_by(projectCode=project.projectCode).count()
        if observations_count > 0:
            return jsonify({"message": f"Cannot delete project. It has {observations_count} observations."}), 400
        
        db.session.delete(project)
        db.session.commit()
        
        return jsonify({"message": "Project deleted successfully"})
        
    except Exception as e:
        print(f"Error deleting project: {str(e)}")
        db.session.rollback()
        return jsonify({"message": f"Failed to delete project: {str(e)}"}), 500

# SubContractor Management APIs
@app.route('/api/subcontractors/<int:subcontractor_id>', methods=['PUT'])
def update_subcontractor(subcontractor_id: int):
    try:
        data = request.get_json()
        subcontractor = SubContractor.query.get_or_404(subcontractor_id)
        
        # Update subcontractor fields
        for key, value in data.items():
            if hasattr(subcontractor, key):
                setattr(subcontractor, key, value)
        
        db.session.commit()
        
        def to_dict(obj):
            return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        
        return jsonify(to_dict(subcontractor))
        
    except Exception as e:
        print(f"Error updating subcontractor: {str(e)}")
        db.session.rollback()
        return jsonify({"message": f"Failed to update subcontractor: {str(e)}"}), 500

@app.route('/api/subcontractors/<int:subcontractor_id>', methods=['DELETE'])
def delete_subcontractor(subcontractor_id: int):
    try:
        subcontractor = SubContractor.query.get_or_404(subcontractor_id)
        
        # Check if subcontractor has observations
        observations_count = Observation.query.filter_by(subContractor=subcontractor.name).count()
        if observations_count > 0:
            return jsonify({"message": f"Cannot delete subcontractor. It has {observations_count} observations."}), 400
        
        db.session.delete(subcontractor)
        db.session.commit()
        
        return jsonify({"message": "Subcontractor deleted successfully"})
        
    except Exception as e:
        print(f"Error deleting subcontractor: {str(e)}")
        db.session.rollback()
        return jsonify({"message": f"Failed to delete subcontractor: {str(e)}"}), 500


if __name__ == '__main__':
    setup_database(app)
app.run(debug=True, host='0.0.0.0', port=5000)

