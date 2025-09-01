from flask import Blueprint, render_template, g
import sqlite3
import os

def get_db_schema(db_path):
    """Get the schema for a SQLite database."""
    schema = {}
    try:
        # Connect to the database with proper encoding
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        conn.text_factory = lambda x: str(x, 'utf-8', 'replace')
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Get schema for each table
        for table in tables:
            # Skip sqlite_ system tables
            if table.startswith('sqlite_'):
                continue
                
            # Get table info
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            
            # Get foreign key info
            cursor.execute(f"PRAGMA foreign_key_list({table});")
            foreign_keys = cursor.fetchall()
            
            # Get indexes
            cursor.execute(f"PRAGMA index_list({table});")
            indexes = []
            for idx in cursor.fetchall():
                idx_name = idx[1]
                cursor.execute(f"PRAGMA index_info({idx_name});")
                idx_columns = [row[2] for row in cursor.fetchall()]
                indexes.append({
                    'name': idx_name,
                    'unique': idx[2] == 1,
                    'columns': idx_columns
                })
            
            schema[table] = {
                'columns': columns,
                'foreign_keys': foreign_keys,
                'indexes': indexes
            }
        
        return schema
    except Exception as e:
        return {'error': str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

def get_all_database_schemas(app):
    """Get schemas for all SQLite databases in the app config."""
    schemas = {}
    
    try:
        # Get main database
        main_db = app.config.get('DATABASE')
        if main_db and os.path.exists(main_db):
            try:
                schemas['main'] = get_db_schema(main_db)
            except Exception as e:
                schemas['main'] = {'error': f'Error reading main database: {str(e)}'}
        
        # Check for attendance database
        if main_db:
            attendance_db = os.path.join(os.path.dirname(os.path.abspath(main_db)), 'attendance.db')
            if os.path.exists(attendance_db):
                try:
                    schemas['attendance'] = get_db_schema(attendance_db)
                except Exception as e:
                    schemas['attendance'] = {'error': f'Error reading attendance database: {str(e)}'}
        
        # Check for any other .db files in the instance folder
        instance_path = os.path.abspath(os.path.join(app.root_path, 'instance'))
        if os.path.exists(instance_path):
            for filename in os.listdir(instance_path):
                if filename.endswith('.db') and filename not in ['tournament.db', 'attendance.db']:
                    db_path = os.path.join(instance_path, filename)
                    db_name = os.path.splitext(filename)[0]
                    try:
                        schemas[db_name] = get_db_schema(db_path)
                    except Exception as e:
                        schemas[db_name] = {'error': f'Error reading {filename}: {str(e)}'}
    except Exception as e:
        return {'error': f'Error getting database schemas: {str(e)}'}
    
    return schemas

def init_dev_routes(app):
    """Initialize development routes."""
    # Create a blueprint for development routes
    dev_bp = Blueprint('dev', __name__, url_prefix='/dev')
    
    @dev_bp.route('/schema')
    def show_schema():
        """Display database schemas for all databases."""
            
        schemas = get_all_database_schemas(app)
        return render_template('dev/schema.html', schemas=schemas)
    
    # Register the blueprint with the app
    app.register_blueprint(dev_bp)
    
    # Create template directory if it doesn't exist
    template_dir = os.path.join(app.root_path, 'templates', 'dev')
    os.makedirs(template_dir, exist_ok=True)
    
    # Create schema template if it doesn't exist
    schema_template = os.path.join(template_dir, 'schema.html')
    if not os.path.exists(schema_template):
        with open(schema_template, 'w', encoding='utf-8') as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Database Schemas</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .database { margin-bottom: 40px; }
        .database h2 { color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 5px; }
        .table { margin-bottom: 30px; }
        .table h3 { color: #3498db; margin-bottom: 10px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .foreign-key { color: #e74c3c; font-style: italic; }
        .index { margin-top: 10px; }
        .index-name { font-weight: bold; color: #27ae60; }
        .unique { color: #f39c12; }
    </style>
</head>
<body>
    <h1>Database Schemas</h1>
    
    {% for db_name, tables in schemas.items() %}
    <div class="database">
        <h2>Database: {{ db_name }}</h2>
        
        {% if tables is mapping %}
            {% for table_name, table_info in tables.items() %}
            <div class="table">
                <h3>Table: {{ table_name }}</h3>
                
                <h4>Columns:</h4>
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Not Null</th>
                        <th>Default</th>
                        <th>Primary Key</th>
                    </tr>
                    {% for col in table_info.columns %}
                    <tr>
                        <td>{{ col[0] }}</td>
                        <td>{{ col[1] }}</td>
                        <td>{{ col[2] }}</td>
                        <td>{% if col[3] %}✓{% endif %}</td>
                        <td>{{ col[4] or '' }}</td>
                        <td>{% if col[5] %}✓{% endif %}</td>
                    </tr>
                    {% endfor %}
                </table>
                
                {% if table_info.foreign_keys %}
                <h4>Foreign Keys:</h4>
                <table>
                    <tr>
                        <th>ID</th>
                        <th>From</th>
                        <th>To Table</th>
                        <th>To Column</th>
                        <th>On Update</th>
                        <th>On Delete</th>
                    </tr>
                    {% for fk in table_info.foreign_keys %}
                    <tr>
                        <td>{{ fk[0] }}</td>
                        <td>{{ fk[3] }}</td>
                        <td>{{ fk[2] }}</td>
                        <td>{{ fk[4] }}</td>
                        <td>{{ fk[5] or 'NO ACTION' }}</td>
                        <td>{{ fk[6] or 'NO ACTION' }}</td>
                    </tr>
                    {% endfor %}
                </table>
                {% endif %}
                
                {% if table_info.indexes %}
                <h4>Indexes:</h4>
                {% for idx in table_info.indexes %}
                <div class="index">
                    <span class="index-name">{{ idx.name }}</span>
                    {% if idx.unique %}<span class="unique"> (UNIQUE)</span>{% endif %}
                    <ul>
                        {% for col in idx.columns %}
                        <li>{{ col }}</li>
                        {% endfor %}
                    </ul>
                </div>
                {% endfor %}
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <p>Error: {{ tables.error }}</p>
        {% endif %}
    </div>
    {% endfor %}
</body>
</html>
""")
    
    return dev_bp
