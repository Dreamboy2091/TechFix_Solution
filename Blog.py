from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_mail import Mail, Message
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-key-change-later'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///techfix.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email config (optional)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-techfix-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-app-password'
app.config['MAIL_DEFAULT_SENDER'] = ('U. TechFix Solutions', 'noreply@techfix.com')

mail = Mail(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ==================== MODELS ====================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_helper = db.Column(db.Boolean, default=False)
    reputation = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Problem(db.Model):
    __tablename__ = 'problems'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    device_type = db.Column(db.String(50))
    operating_system = db.Column(db.String(50))
    urgency = db.Column(db.String(20), default='medium')
    is_solved = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    solution_count = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    author = db.relationship('User', backref='user_problems')
    solutions = db.relationship('Solution', backref='problem', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Problem {self.title}>'

class Solution(db.Model):
    __tablename__ = 'solutions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    steps = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), default='Beginner')
    estimated_time = db.Column(db.String(20))
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    is_verified = db.Column(db.Boolean, default=False)
    problem_id = db.Column(db.Integer, db.ForeignKey('problems.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='user_solutions')

    @property
    def helpful_score(self):
        total = self.upvotes + self.downvotes
        return round((self.upvotes / total * 100), 1) if total > 0 else 0

# ==================== INITIALIZATION ====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    print("✅ Database ready!")

# ==================== CONTEXT PROCESSOR ====================
@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# ==================== ROUTES ====================
@app.route('/')
def home():
    recent_problems = Problem.query.filter_by(is_solved=True).order_by(Problem.created_at.desc()).limit(4).all()
    return render_template('index.html', title='Home', recent_problems=recent_problems)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        flash('✅ Registration successful! Welcome to TechFix!', 'success')
        return redirect(url_for('welcome_page', username=username))

    return render_template('auth/register.html', title='Register')

@app.route('/welcome/<username>')
@login_required
def welcome_page(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user.id != current_user.id:
        return redirect(url_for('home'))
    return render_template('welcome.html', title=f'Welcome {username}!', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('auth/login.html', title='Login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    user_problems = Problem.query.filter_by(user_id=user.id).all()
    user_solutions = Solution.query.filter_by(user_id=user.id).all()
    
    return render_template('profile.html',
                           title=f"{username}'s Profile",
                           user=user,
                           problems=user_problems,
                           solutions=user_solutions)
import os
from werkzeug.utils import secure_filename

# Add configuration for uploads
app.config['UPLOAD_FOLDER'] = 'static/uploads/profile_pics'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload-profile-pic', methods=['POST'])
@login_required
def upload_profile_pic():
    if 'profile_pic' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('profile', username=current_user.username))
    
    file = request.files['profile_pic']
    
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('profile', username=current_user.username))
    
    print(f"DEBUG: Uploading file: {file.filename}")  # For debugging
    
    if file and allowed_file(file.filename):
        # Create uploads directory if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        print(f"DEBUG: Saving to: {file_path}")  # For debugging
        
        # Save file
        file.save(file_path)
        
        # Check if file was saved
        if os.path.exists(file_path):
            print(f"DEBUG: File saved successfully! Size: {os.path.getsize(file_path)} bytes")
        else:
            print("DEBUG: ERROR - File not saved!")
            flash('Error saving file', 'danger')
            return redirect(url_for('profile', username=current_user.username))
        
        # Update user profile_pic in database
        current_user.profile_pic = unique_filename
        db.session.commit()
        
        print(f"DEBUG: Database updated with: {current_user.profile_pic}")  # For debugging
        
        flash('✅ Profile picture updated successfully!', 'success')
    else:
        flash('Invalid file type. Allowed: PNG, JPG, JPEG, GIF', 'danger')
    
    return redirect(url_for('profile', username=current_user.username))
@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_problem():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        device_type = request.form.get('device_type', '')
        operating_system = request.form.get('operating_system', '')
        urgency = request.form.get('urgency', 'medium')

        new_problem = Problem(
            title=title,
            description=description,
            category=category,
            device_type=device_type,
            operating_system=operating_system,
            urgency=urgency,
            user_id=current_user.id
        )

        try:
            db.session.add(new_problem)
            db.session.commit()
            flash('🎉 Problem submitted successfully!', 'success')
            return redirect(url_for('problem_detail', problem_id=new_problem.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('submit_problem.html', title='Submit Problem')

@app.route('/problem/<int:problem_id>')
def problem_detail(problem_id):
    problem = Problem.query.get_or_404(problem_id)
    problem.views += 1
    db.session.commit()
    return render_template('problem_detail.html', title=problem.title, problem=problem)

# ==================== BROWSE WITH SEARCH & FILTERS ====================
@app.route('/browse')
def browse():
    # Get query parameters
    search_query = request.args.get('search', '')
    category = request.args.get('category', '')
    sort_by = request.args.get('sort', 'newest')
    
    # Start with base query
    query = Problem.query
    
    # Apply search filter
    if search_query:
        query = query.filter(
            (Problem.title.ilike(f'%{search_query}%')) |
            (Problem.description.ilike(f'%{search_query}%'))
        )
    
    # Apply category filter
    if category:
        query = query.filter_by(category=category)
    
    # Apply sorting
    if sort_by == 'views':
        query = query.order_by(Problem.views.desc())
    elif sort_by == 'solutions':
        query = query.order_by(Problem.solution_count.desc())
    elif sort_by == 'unsolved':
        query = query.filter_by(is_solved=False).order_by(Problem.created_at.desc())
    else:  # newest
        query = query.order_by(Problem.created_at.desc())
    
    problems = query.all()
    
    # Get unique categories for filter
    categories = db.session.query(Problem.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('browse.html',
                          title='Browse Problems',
                          problems=problems,
                          search_query=search_query,
                          current_category=category,
                          sort_by=sort_by,
                          categories=categories)

# ==================== SOLUTION SYSTEM ====================
@app.route('/problem/<int:problem_id>/add-solution', methods=['GET', 'POST'])
@login_required
def add_solution(problem_id):
    problem = Problem.query.get_or_404(problem_id)
    
    if request.method == 'POST':
        title = request.form.get('title', f'Solution by {current_user.username}')
        steps = request.form['steps']
        difficulty = request.form.get('difficulty', 'Beginner')
        estimated_time = request.form.get('estimated_time', '')
        
        new_solution = Solution(
            title=title,
            steps=steps,
            difficulty=difficulty,
            estimated_time=estimated_time,
            problem_id=problem_id,
            user_id=current_user.id
        )
        
        try:
            db.session.add(new_solution)
            problem.solution_count = Solution.query.filter_by(problem_id=problem_id).count()
            problem.is_solved = True if problem.solution_count > 0 else False
            db.session.commit()
            flash('✅ Solution added successfully!', 'success')
            return redirect(url_for('problem_detail', problem_id=problem_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('add_solution.html', 
                          title=f'Add Solution: {problem.title}',
                          problem=problem)

# ==================== QUICK SOLUTION (COMMENT-STYLE) ====================
@app.route('/problem/<int:problem_id>/quick-solution', methods=['POST'])
@login_required
def quick_solution(problem_id):
    problem = Problem.query.get_or_404(problem_id)
    
    if problem.user_id == current_user.id:
        flash("You can't add a solution to your own problem.", 'warning')
        return redirect(url_for('problem_detail', problem_id=problem_id))
    
    steps = request.form.get('steps', '').strip()
    if not steps:
        flash('Please provide solution steps.', 'danger')
        return redirect(url_for('problem_detail', problem_id=problem_id))
    
    new_solution = Solution(
        title=f'Solution by {current_user.username}',
        steps=steps,
        difficulty=request.form.get('difficulty', 'Beginner'),
        estimated_time=request.form.get('estimated_time', ''),
        problem_id=problem_id,
        user_id=current_user.id
    )
    
    try:
        db.session.add(new_solution)
        problem.solution_count = Solution.query.filter_by(problem_id=problem_id).count()
        problem.is_solved = True
        db.session.commit()
        flash('✅ Your solution has been posted!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('problem_detail', problem_id=problem_id))

# ==================== VOTING SYSTEM ====================
@app.route('/solution/<int:solution_id>/upvote')
@login_required
def upvote_solution(solution_id):
    solution = Solution.query.get_or_404(solution_id)
    solution.upvotes += 1
    db.session.commit()
    flash('👍 Thanks for your vote!', 'success')
    return redirect(url_for('problem_detail', problem_id=solution.problem_id))

@app.route('/solution/<int:solution_id>/downvote')
@login_required
def downvote_solution(solution_id):
    solution = Solution.query.get_or_404(solution_id)
    solution.downvotes += 1
    db.session.commit()
    flash('👎 Vote recorded.', 'info')
    return redirect(url_for('problem_detail', problem_id=solution.problem_id))

# ==================== SAMPLE DATA ====================
@app.route('/add-real-solutions')
def add_real_solutions():
    """Add real tech solutions with actual steps"""
    try:
        # Clear existing data
        Solution.query.delete()
        Problem.query.delete()
        User.query.filter_by(username='techhelper').delete()
        User.query.filter_by(username='testuser').delete()
        db.session.commit()
        
        # Create helper user
        helper = User(username='techhelper', email='helper@techfix.com', is_helper=True, reputation=100)
        helper.set_password('help123')
        db.session.add(helper)
        
        # Create test user
        test_user = User(username='testuser', email='test@techfix.com')
        test_user.set_password('test123')
        db.session.add(test_user)
        
        db.session.commit()
        
        # Sample problems with solutions
        problems_data = [
            {
                'title': 'Python 3.11 Installation Guide for Windows 11',
                'description': 'Complete step-by-step guide to install Python on Windows 11 with troubleshooting tips.',
                'category': 'Software',
                'device_type': 'Laptop/Desktop',
                'os': 'Windows 11',
                'urgency': 'medium',
                'solution': '''Step 1: Download Python Installer
• Visit python.org/downloads
• Click "Download Python 3.11.x"

Step 2: Run Installer
• Double-click the installer
• Check "Add python.exe to PATH"

Step 3: Verify Installation
• Open Command Prompt
• Type: python --version'''
            },
            {
                'title': 'Fix "No Internet" on Connected WiFi',
                'description': 'WiFi shows connected but websites won\'t load.',
                'category': 'Network',
                'device_type': 'Any Device',
                'os': 'Windows/Mac/Android',
                'urgency': 'high',
                'solution': '''Step 1: Restart Devices
• Restart router
• Restart computer/phone

Step 2: Check Other Devices
• Try another device on same WiFi

Step 3: Flush DNS Cache
• Open Command Prompt as Admin
• Type: ipconfig /flushdns'''
            },
            {
                'title': 'Speed Up Slow Windows Computer',
                'description': 'Windows running very slow after update.',
                'category': 'Performance',
                'device_type': 'Desktop',
                'os': 'Windows 10/11',
                'urgency': 'medium',
                'solution': '''Step 1: Clean Disk Space
• Open Disk Cleanup
• Select C: drive

Step 2: Disable Startup Programs
• Open Task Manager
• Go to Startup tab

Step 3: Update Drivers
• Open Device Manager
• Update display drivers'''
            },
            {
                'title': 'Install Printer Without Installation CD',
                'description': 'Need to install HP printer but lost installation CD.',
                'category': 'Hardware',
                'device_type': 'Printer',
                'os': 'Windows',
                'urgency': 'medium',
                'solution': '''Step 1: Connect Printer
• Turn on printer
• Connect to WiFi

Step 2: Download Drivers
• Go to HP.com/support
• Download drivers

Step 3: Add Printer in Windows
• Open Settings → Devices
• Click "Add printer"'''
            }
        ]
        
        for i, prob_data in enumerate(problems_data):
            problem = Problem(
                title=prob_data['title'],
                description=prob_data['description'],
                category=prob_data['category'],
                device_type=prob_data['device_type'],
                operating_system=prob_data['os'],
                urgency=prob_data['urgency'],
                user_id=helper.id if i % 2 == 0 else test_user.id
            )
            db.session.add(problem)
            db.session.commit()
            
            solution = Solution(
                title=f'Solution for {prob_data["title"]}',
                steps=prob_data['solution'],
                difficulty='Beginner',
                estimated_time='10-20 minutes',
                upvotes=20 + i*5,
                downvotes=i,
                is_verified=True,
                problem_id=problem.id,
                user_id=helper.id
            )
            db.session.add(solution)
            problem.solution_count = 1
            problem.is_solved = True
        
        db.session.commit()
        flash('✅ 4 real problems with solutions added!', 'success')
        flash('👤 Test accounts: techhelper/help123 and testuser/test123', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('home'))

# ==================== ABOUT & CONTACT ====================
@app.route('/about')
def about():
    return render_template('about.html', title='About Us')

@app.route('/contact')
def contact():
    return render_template('contact.html', title='Contact Us')

# ==================== RUN SERVER ====================
if __name__ == '__main__':
    print("🚀 TechFix Solutions - Step-by-Step Tech Help")
    print("🌐 http://127.0.0.1:5000")
    print("\n📊 Quick Commands:")
    print("• /add-real-solutions - Add 4 real problems with solutions")
    print("• /browse - Browse problems with search & filters")
    print("• /submit - Submit new problem")
    print("\n👤 Test Accounts:")
    print("• techhelper / help123")
    print("• testuser / test123")
    print("\n" + "="*50)
    app.run(debug=True)
