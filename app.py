from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import os
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from ocr_utils import extract_expense_data_from_image, add_expense_from_image





# Import our BillSplitter class
from bill_splitter import BillSplitter

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Create a bill splitter instance for each group
bill_splitters = {}

# User credentials storage
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

# Initialize users data
users = load_users()

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Get user's groups
    user_groups = []
    for group_id, group_info in users.get(session['username'], {}).get('groups', {}).items():
        user_groups.append({
            'id': group_id,
            'name': group_info.get('name', 'Unnamed Group')
        })
    
    return render_template('home.html', groups=user_groups)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and check_password_hash(users[username]['password'], password):
            session['username'] = username
            flash('Logged in successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        if username in users:
            flash('Username already exists', 'danger')
        else:
            users[username] = {
                'password': generate_password_hash(password),
                'email': email,
                'groups': {}
            }
            save_users(users)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        group_name = request.form['group_name']
        group_id = f"group_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create storage file for this group
        storage_file = f"{group_id}.json"
        bill_splitters[group_id] = BillSplitter(storage_file=storage_file)
        
        # Add current user to the group
        bill_splitters[group_id].add_user(session['username'])
        
        # Add group to user's profile
        if session['username'] not in users:
            users[session['username']] = {'groups': {}}
        
        if 'groups' not in users[session['username']]:
            users[session['username']]['groups'] = {}
            
        users[session['username']]['groups'][group_id] = {
            'name': group_name,
            'role': 'admin'
        }
        save_users(users)
        
        flash(f'Group "{group_name}" created successfully!', 'success')
        return redirect(url_for('group_dashboard', group_id=group_id))
    
    return render_template('create_group.html')

@app.route('/group/<group_id>')
def group_dashboard(group_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Check if user has access to this group
    if group_id not in users.get(session['username'], {}).get('groups', {}):
        flash('You do not have access to this group', 'danger')
        return redirect(url_for('home'))
    
    # Initialize bill splitter for this group if not already initialized
    if group_id not in bill_splitters:
        storage_file = f"{group_id}.json"
        bill_splitters[group_id] = BillSplitter(storage_file=storage_file)
    
    bs = bill_splitters[group_id]
    
    # Get expense summary
    expense_summary = bs.get_expense_summary()
    
    # Get settlements
    settlements = bs.calculate_balances()
    
    # Get user-specific info
    user_info = bs.get_user_expenses(session['username'])
    if isinstance(user_info, str):  # Error message
        user_info = None
    
    # Get all expenses
    expenses = bs.expenses
    
    # Get all users in the group
    group_users = list(bs.users)
    
    group_name = users[session['username']]['groups'][group_id]['name']
    
    return render_template(
        'group_dashboard.html',
        group_id=group_id,
        group_name=group_name,
        expense_summary=expense_summary,
        settlements=settlements,
        user_info=user_info,
        expenses=expenses,
        group_users=group_users
    )

@app.route('/group/<group_id>/add_user', methods=['POST'])
def add_user_to_group(group_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Check if user has admin access to this group
    if group_id not in users.get(session['username'], {}).get('groups', {}) or \
       users[session['username']]['groups'][group_id]['role'] != 'admin':
        flash('You do not have admin access to this group', 'danger')
        return redirect(url_for('group_dashboard', group_id=group_id))
    
    username = request.form['username']
    
    # Check if the user exists
    if username not in users:
        flash(f'User "{username}" does not exist', 'danger')
        return redirect(url_for('group_dashboard', group_id=group_id))
    
    # Add user to the group
    if group_id not in bill_splitters:
        storage_file = f"{group_id}.json"
        bill_splitters[group_id] = BillSplitter(storage_file=storage_file)
    
    bs = bill_splitters[group_id]
    message = bs.add_user(username)
    
    # Add group to user's profile
    if 'groups' not in users[username]:
        users[username]['groups'] = {}
        
    users[username]['groups'][group_id] = {
        'name': users[session['username']]['groups'][group_id]['name'],
        'role': 'member'
    }
    save_users(users)
    
    flash(message, 'success')
    return redirect(url_for('group_dashboard', group_id=group_id))

@app.route('/group/<group_id>/add_expense', methods=['POST'])
def add_expense(group_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Check if user has access to this group
    if group_id not in users.get(session['username'], {}).get('groups', {}):
        flash('You do not have access to this group', 'danger')
        return redirect(url_for('home'))
    
    # Initialize bill splitter for this group if not already initialized
    if group_id not in bill_splitters:
        storage_file = f"{group_id}.json"
        bill_splitters[group_id] = BillSplitter(storage_file=storage_file)
    
    bs = bill_splitters[group_id]
    
    # Get form data
    paid_by = request.form['paid_by']
    amount = request.form['amount']
    description = request.form['description']
    category = request.form.get('category', '')
    
    # Get participants
    participants = request.form.getlist('participants')
    
    # Add expense
    message = bs.add_expense(paid_by, amount, description, participants)
    
    # Add category if provided
    if category and message.startswith("Expense"):
        expense_id = len(bs.expenses)  # The latest expense ID
        bs.categorize_expense(expense_id, category)
    
    flash(message, 'success')
    return redirect(url_for('group_dashboard', group_id=group_id))

@app.route('/group/<group_id>/categorize_expense', methods=['POST'])
def categorize_expense(group_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Check if user has access to this group
    if group_id not in users.get(session['username'], {}).get('groups', {}):
        flash('You do not have access to this group', 'danger')
        return redirect(url_for('home'))
    
    # Initialize bill splitter for this group if not already initialized
    if group_id not in bill_splitters:
        storage_file = f"{group_id}.json"
        bill_splitters[group_id] = BillSplitter(storage_file=storage_file)
    
    bs = bill_splitters[group_id]
    
    # Get form data
    expense_id = int(request.form['expense_id'])
    category = request.form['category']
    
    # Categorize expense
    message = bs.categorize_expense(expense_id, category)
    
    flash(message, 'success')
    return redirect(url_for('group_dashboard', group_id=group_id))
@app.route('/group/<group_id>/upload_receipt', methods=['POST'])
def upload_receipt(group_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    if group_id not in users.get(session['username'], {}).get('groups', {}):
        flash('You do not have access to this group', 'danger')
        return redirect(url_for('home'))

    if 'receipt_image' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('group_dashboard', group_id=group_id))

    image = request.files['receipt_image']
    if image.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('group_dashboard', group_id=group_id))

    # Save image temporarily
    image_path = os.path.join('uploads', image.filename)
    os.makedirs('uploads', exist_ok=True)
    image.save(image_path)

    # Extract multiple expenses from OCR
    from ocr_utils import extract_expense_data_from_image
    expenses = extract_expense_data_from_image(image_path)

    if not expenses:
        flash('Could not extract expense details from image.', 'danger')
        return redirect(url_for('group_dashboard', group_id=group_id))

    bs = bill_splitters[group_id]
    paid_by = session['username']
    participants = list(bs.users)

    for expense in expenses:
        description = expense.get("description", "Scanned Item")
        amount = expense.get("amount", 0)
        category = expense.get("category", "Uncategorized")

        message = bs.add_expense(paid_by, amount, description, participants)
        if message.startswith("Expense"):
            expense_id = len(bs.expenses) - 1
            bs.categorize_expense(expense_id, category)

        flash(f"{message} - {description} ({category})", 'success')

    return redirect(url_for('group_dashboard', group_id=group_id))




if __name__ == '__main__':
    app.run(debug=True)
    