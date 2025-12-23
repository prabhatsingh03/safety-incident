"""
Migration script to transfer data from SQLite3 to MySQL database.
Run this script BEFORE the first run of the application with MySQL.

This script will:
1. Connect to the existing SQLite3 database
2. Connect to MySQL database (using credentials from .env)
3. Create tables in MySQL if they don't exist
4. Transfer all data from SQLite3 to MySQL
"""

import os
import sqlite3
from dotenv import load_dotenv
from urllib.parse import quote_plus
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

# Initialize Flask app for SQLAlchemy
app = Flask(__name__)

# MySQL Database Configuration from environment variables
mysql_host = os.getenv('MYSQL_HOST', 'localhost')
mysql_port = os.getenv('MYSQL_PORT', '3306')
mysql_user = os.getenv('MYSQL_USER', 'root')
mysql_password = os.getenv('MYSQL_PASSWORD', '')
mysql_database = os.getenv('MYSQL_DATABASE', 'safety_app')

# URL-encode password to handle special characters like @, #, etc.
encoded_password = quote_plus(mysql_password) if mysql_password else ''
# Configure MySQL connection
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{mysql_user}:{encoded_password}@{mysql_host}:{mysql_port}/{mysql_database}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models (must match app.py)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)

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
    observationPhoto = db.Column(db.Text)
    contractor = db.Column(db.String(100), nullable=False, default='SIL')
    subContractor = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Open')
    compliance = db.Column(db.Text)
    complianceDate = db.Column(db.String(20))
    compliancePhoto = db.Column(db.Text)


def migrate_data():
    """Migrate data from SQLite3 to MySQL"""
    basedir = os.path.abspath(os.path.dirname(__file__))
    sqlite_db_path = os.path.join(basedir, 'safety_app.db')
    
    # Check if SQLite database exists
    if not os.path.exists(sqlite_db_path):
        print(f"ERROR: SQLite database not found at {sqlite_db_path}")
        print("Please ensure safety_app.db exists in the project directory.")
        return False
    
    print(f"Found SQLite database at: {sqlite_db_path}")
    
    # Connect to SQLite database
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    try:
        # Create tables in MySQL
        print("\nCreating tables in MySQL database...")
        with app.app_context():
            db.create_all()
            print("Tables created successfully.")
        
        # Check if MySQL database already has data
        with app.app_context():
            if User.query.first() or Project.query.first() or Observation.query.first():
                response = input("\nWARNING: MySQL database already contains data. Continue migration? (yes/no): ")
                if response.lower() != 'yes':
                    print("Migration cancelled.")
                    return False
        
        # Migrate Users
        print("\nMigrating Users...")
        sqlite_cursor.execute("SELECT * FROM user")
        users = sqlite_cursor.fetchall()
        with app.app_context():
            for user_row in users:
                # Check if user already exists
                existing_user = User.query.filter_by(username=user_row['username']).first()
                if not existing_user:
                    user = User(
                        id=user_row['id'],
                        username=user_row['username'],
                        password_hash=user_row['password_hash'],
                        role=user_row['role']
                    )
                    db.session.add(user)
            db.session.commit()
            print(f"Migrated {len(users)} users.")
        
        # Migrate Projects
        print("\nMigrating Projects...")
        sqlite_cursor.execute("SELECT * FROM project")
        projects = sqlite_cursor.fetchall()
        with app.app_context():
            for project_row in projects:
                # sqlite3.Row doesn't support .get(), so convert to a plain dict
                pr = dict(project_row)
                # Check if project already exists
                existing_project = Project.query.filter_by(projectCode=pr['projectCode']).first()
                if not existing_project:
                    project = Project(
                        id=pr['id'],
                        projectCode=pr['projectCode'],
                        projectName=pr['projectName'],
                        projectManagerContractor=pr.get('projectManagerContractor'),
                        projectManagerClient=pr.get('projectManagerClient'),
                        clientName=pr.get('clientName'),
                        contractor=pr.get('contractor')
                    )
                    db.session.add(project)
            db.session.commit()
            print(f"Migrated {len(projects)} projects.")
        
        # Migrate SubContractors
        print("\nMigrating SubContractors...")
        sqlite_cursor.execute("SELECT * FROM sub_contractor")
        subcontractors = sqlite_cursor.fetchall()
        with app.app_context():
            for sc_row in subcontractors:
                # Check if subcontractor already exists
                existing_sc = SubContractor.query.filter_by(
                    name=sc_row['name'],
                    project_code=sc_row['project_code']
                ).first()
                if not existing_sc:
                    subcontractor = SubContractor(
                        id=sc_row['id'],
                        name=sc_row['name'],
                        project_code=sc_row['project_code']
                    )
                    db.session.add(subcontractor)
            db.session.commit()
            print(f"Migrated {len(subcontractors)} subcontractors.")
        
        # Migrate Observations
        print("\nMigrating Observations...")
        sqlite_cursor.execute("SELECT * FROM observation")
        observations = sqlite_cursor.fetchall()
        with app.app_context():
            for obs_row in observations:
                orow = dict(obs_row)
                # Check if observation already exists
                existing_obs = Observation.query.filter_by(id=orow['id']).first()
                if not existing_obs:
                    observation = Observation(
                        id=orow['id'],
                        projectCode=orow['projectCode'],
                        date=orow['date'],
                        raisedBy=orow['raisedBy'],
                        issueType=orow['issueType'],
                        safetyCategory=orow['safetyCategory'],
                        observation=orow['observation'],
                        observationPhoto=orow.get('observationPhoto'),
                        contractor=orow.get('contractor', 'SIL'),
                        subContractor=orow.get('subContractor'),
                        status=orow.get('status', 'Open'),
                        compliance=orow.get('compliance'),
                        complianceDate=orow.get('complianceDate'),
                        compliancePhoto=orow.get('compliancePhoto')
                    )
                    db.session.add(observation)
            db.session.commit()
            print(f"Migrated {len(observations)} observations.")
        
        print("\n" + "="*50)
        print("Migration completed successfully!")
        print("="*50)
        print(f"\nSummary:")
        print(f"  - Users: {len(users)}")
        print(f"  - Projects: {len(projects)}")
        print(f"  - SubContractors: {len(subcontractors)}")
        print(f"  - Observations: {len(observations)}")
        print("\nYou can now run the application with MySQL.")
        return True
        
    except Exception as e:
        print(f"\nERROR during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        with app.app_context():
            db.session.rollback()
        return False
    finally:
        sqlite_conn.close()


if __name__ == '__main__':
    print("="*50)
    print("SQLite3 to MySQL Migration Script")
    print("="*50)
    print("\nThis script will migrate all data from SQLite3 to MySQL.")
    print("Make sure you have:")
    print("  1. Created the MySQL database")
    print("  2. Set up .env file with MySQL credentials")
    print("  3. Installed required packages (pymysql, python-dotenv)")
    print("\nMySQL Configuration:")
    print(f"  Host: {mysql_host}")
    print(f"  Port: {mysql_port}")
    print(f"  Database: {mysql_database}")
    print(f"  User: {mysql_user}")
    
    response = input("\nContinue with migration? (yes/no): ")
    if response.lower() == 'yes':
        success = migrate_data()
        if not success:
            exit(1)
    else:
        print("Migration cancelled.")
        exit(0)

