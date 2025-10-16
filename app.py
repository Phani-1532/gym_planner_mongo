import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
import bcrypt
from functools import wraps
from datetime import date, timedelta
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 1. Initialize Flask App
app = Flask(__name__)
app.secret_key = os.urandom(24) # Generate a secret key for session management

# 2. Configure MongoDB
# Get the MongoDB URI from environment variables, with a default for local development
MONGO_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.gym_planner_db # Database name
users_collection = db.users # Collection for users
workout_days_collection = db.workout_days # Collection for workout days
exercises_collection = db.exercises # Collection for exercises

# Seed the database with default exercises if none exist
def seed_exercises():
    """Seeds the database with some default exercises if the collection is empty."""
    if exercises_collection.count_documents({}) == 0:
        print("No exercises found. Seeding database with default exercises...")
        default_exercises = [
            {'name': 'Bench Press', 'muscle_group': 'Chest'},
            {'name': 'Squat', 'muscle_group': 'Legs'},
            {'name': 'Deadlift', 'muscle_group': 'Back'},
            {'name': 'Overhead Press', 'muscle_group': 'Shoulders'},
            {'name': 'Barbell Row', 'muscle_group': 'Back'},
            {'name': 'Pull Ups', 'muscle_group': 'Back'},
            {'name': 'Bicep Curls', 'muscle_group': 'Arms'},
            {'name': 'Tricep Dips', 'muscle_group': 'Arms'},
            {'name': 'Leg Press', 'muscle_group': 'Legs'},
        ]
        exercises_collection.insert_many(default_exercises)
        print(f"Seeded {len(default_exercises)} exercises.")

# Call the seed function when the application starts
seed_exercises()

# 3. Helper function for protected routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        # Fetch user for every request
        kwargs['user'] = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not kwargs['user']: return redirect(url_for('logout'))
        return f(*args, **kwargs)
    return decorated_function

# 4. Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = users_collection.find_one({'email': email})

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            # Passwords match, log user in
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            # Invalid credentials
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if user already exists
        if users_collection.find_one({'email': email}):
            flash('An account with this email already exists.', 'warning')
            return redirect(url_for('signup'))

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Insert new user into the database
        users_collection.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password,
            # Add role for RBA later
            'role': 'USER' 
        })

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard(user):
    # Get the current week's data
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday()) # Monday
    end_of_week = start_of_week + timedelta(days=6) # Sunday

    # Fetch workout days for the current user for the current week
    query = {
        'user_id': user['_id'],
        'date': {'$gte': start_of_week.isoformat(), '$lte': end_of_week.isoformat()}
    }
    user_workouts = list(workout_days_collection.find(query).sort('date', 1))

    # Create a dictionary for easy access in the template
    # Days: Monday (0) to Sunday (6)
    week_plan = { (start_of_week + timedelta(days=i)).strftime('%A'): None for i in range(7) }
    for workout in user_workouts:
        day_name = date.fromisoformat(workout['date']).strftime('%A')
        week_plan[day_name] = workout

    # Fetch all exercises to populate the dropdown in the modal
    # In a larger app, you might want to filter this by user-created exercises vs global ones
    all_exercises = list(exercises_collection.find({}))

    return render_template('weekly_planner.html', week_plan=week_plan, start_of_week=start_of_week, timedelta=timedelta, all_exercises=all_exercises)

@app.route('/monthly-plan')
@login_required
def monthly_view(user):
    return render_template('monthly_plan.html')

@app.route('/exercise-library')
@login_required
def exercise_library(user):
    return render_template('exercise_library.html')

@app.route('/progress-tracker')
@login_required
def progress_tracker(user):
    return render_template('progress_tracker.html')

@app.route('/goal-setting')
@login_required
def goal_setting(user):
    return render_template('goal_setting.html')

@app.route('/diet-plan')
@login_required
def diet_plan(user):
    return render_template('diet_plan.html')

@app.route('/backup-restore')
@login_required
def backup_restore(user):
    return render_template('backup_restore.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/edit-workout-day', methods=['POST'])
@login_required
def edit_workout_day(user):
    try:
        workout_date_str = request.form['edit_workout_date']
        title = request.form.get('day_title', '') # Default to empty string if not provided
        notes = request.form.get('day_notes', '') # Get notes from the form
        is_rest_day = 'is_rest_day' in request.form

        if not workout_date_str:
            flash('Missing date for workout day.', 'danger')
            return redirect(url_for('dashboard'))

        # Find the workout day or create a new one if it doesn't exist
        workout_days_collection.find_one_and_update(
            {'user_id': user['_id'], 'date': workout_date_str},
            {
                '$set': {'title': title, 'is_rest_day': is_rest_day, 'notes': notes},
                '$setOnInsert': {'user_id': user['_id'], 'date': workout_date_str, 'tasks': [], 'notes': ''}
            },
            upsert=True
        )

        flash('Workout day updated successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/toggle-set', methods=['POST'])
@login_required
def toggle_set_completion(user):
    try:
        data = request.get_json()
        workout_day_id = data.get('workout_day_id')
        task_id = data.get('task_id')
        set_id = data.get('set_id')
        is_completed = data.get('is_completed')

        if not all([workout_day_id, task_id, set_id, isinstance(is_completed, bool)]):
            return {'status': 'error', 'message': 'Missing required data.'}, 400

        # The path to the 'completed' field of the specific set
        update_path = 'tasks.$[task].sets.$[set].completed'

        result = workout_days_collection.update_one(
            {'_id': ObjectId(workout_day_id), 'user_id': user['_id']},
            {'$set': {update_path: is_completed}},
            array_filters=[{'task._id': ObjectId(task_id)}, {'set._id': ObjectId(set_id)}]
        )

        if result.modified_count > 0:
            return {'status': 'success', 'message': 'Set updated.'}, 200
        return {'status': 'error', 'message': 'Set not found or not updated.'}, 404
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/delete-task', methods=['POST'])
@login_required
def delete_task(user):
    try:
        data = request.get_json()
        workout_day_id = data.get('workout_day_id')
        task_id = data.get('task_id')

        if not all([workout_day_id, task_id]):
            return {'status': 'error', 'message': 'Missing required data.'}, 400

        result = workout_days_collection.update_one(
            {'_id': ObjectId(workout_day_id), 'user_id': user['_id']},
            {'$pull': {'tasks': {'_id': ObjectId(task_id)}}}
        )

        if result.modified_count > 0:
            return {'status': 'success', 'message': 'Task deleted.'}, 200
        return {'status': 'error', 'message': 'Task not found or not deleted.'}, 404
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/update-set-details', methods=['POST'])
@login_required
def update_set_details(user):
    try:
        data = request.get_json()
        workout_day_id = data.get('workout_day_id')
        task_id = data.get('task_id')
        set_id = data.get('set_id')
        weight = data.get('weight_kg')
        reps = data.get('actual_reps')

        if not all([workout_day_id, task_id, set_id]):
            return {'status': 'error', 'message': 'Missing required data.'}, 400

        update_fields = {}
        # We check for `is not None` to allow saving empty strings
        if weight is not None:
            update_fields['tasks.$[task].sets.$[set].weight_kg'] = weight
        if reps is not None:
            update_fields['tasks.$[task].sets.$[set].actual_reps'] = reps

        if not update_fields:
            return {'status': 'info', 'message': 'No fields to update.'}, 200

        result = workout_days_collection.update_one(
            {'_id': ObjectId(workout_day_id), 'user_id': user['_id']},
            {'$set': update_fields},
            array_filters=[{'task._id': ObjectId(task_id)}, {'set._id': ObjectId(set_id)}]
        )

        if result.modified_count > 0 or result.matched_count > 0:
            return {'status': 'success', 'message': 'Set details updated.'}, 200
        return {'status': 'error', 'message': 'Set not found or not updated.'}, 404
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/edit-exercise', methods=['POST'])
@login_required
def edit_exercise(user):
    try:
        workout_day_id = request.form.get('edit_workout_day_id')
        task_id = request.form.get('edit_task_id')
        exercise_id = request.form.get('edit_exercise_id')
        sets_str = request.form.get('edit_sets')
        reps = request.form.get('edit_reps')

        if not all([workout_day_id, task_id, exercise_id, sets_str, reps]):
            flash('Missing required fields for editing.', 'danger')
            return redirect(url_for('dashboard'))

        # Fetch the selected exercise details
        exercise = exercises_collection.find_one({'_id': ObjectId(exercise_id)})
        if not exercise:
            flash('Selected exercise not found.', 'danger')
            return redirect(url_for('dashboard'))

        # Regenerate the sets list based on the new count
        num_sets = int(sets_str)
        new_set_list = [{"_id": ObjectId(), "set_number": i + 1, "completed": False, "weight_kg": "", "actual_reps": ""}
                        for i in range(num_sets)]

        # Prepare the fields to be updated in the specific task
        update_fields = {
            'tasks.$[task].exercise_id': ObjectId(exercise_id),
            'tasks.$[task].exercise_name': exercise['name'],
            'tasks.$[task].target_reps': reps,
            'tasks.$[task].sets': new_set_list
        }

        # Use arrayFilters to target the specific task within the workout day
        result = workout_days_collection.update_one(
            {'_id': ObjectId(workout_day_id), 'user_id': user['_id']},
            {'$set': update_fields},
            array_filters=[{'task._id': ObjectId(task_id)}]
        )

        if result.modified_count > 0:
            flash('Exercise updated successfully!', 'success')
        else:
            # This could happen if no data was actually changed
            flash('No changes were made to the exercise.', 'info')

    except ValueError:
        flash('Invalid number of sets provided.', 'danger')
    except Exception as e:
        flash(f'An error occurred while updating the exercise: {e}', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/toggle-task', methods=['POST'])
@login_required
def toggle_task_completion(user):
    try:
        data = request.get_json()
        workout_day_id = data.get('workout_day_id')
        task_id = data.get('task_id')
        is_completed = data.get('is_completed')

        if not all([workout_day_id, task_id, isinstance(is_completed, bool)]):
            return {'status': 'error', 'message': 'Missing required data.'}, 400

        # Use arrayFilters to update the specific task in the embedded array
        result = workout_days_collection.update_one(
            {'_id': ObjectId(workout_day_id), 'user_id': user['_id']},
            {'$set': {'tasks.$[elem].completed': is_completed}},
            array_filters=[{'elem._id': ObjectId(task_id)}]
        )

        if result.modified_count > 0:
            return {'status': 'success', 'message': 'Task updated.'}, 200
        return {'status': 'error', 'message': 'Task not found or not updated.'}, 404
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/add-exercise', methods=['POST'])
@login_required
def add_exercise_to_day(user):
    try:
        workout_date_str = request.form.get('workout_date')
        exercise_id = request.form.get('exercise_id')
        sets = request.form.get('sets')
        reps = request.form.get('reps')

        if not all([workout_date_str, exercise_id, sets, reps]):
            flash('Missing required fields.', 'danger')
            return redirect(url_for('dashboard'))

        exercise = exercises_collection.find_one({'_id': ObjectId(exercise_id)})
        if not exercise:
            flash('Selected exercise not found.', 'danger')
            return redirect(url_for('dashboard'))

        # Find the workout day or create a new one
        workout_day = workout_days_collection.find_one_and_update(
            {'user_id': user['_id'], 'date': workout_date_str},
            {'$setOnInsert': {'user_id': user['_id'], 'date': workout_date_str, 'is_rest_day': False, 'tasks': [], 'title': '', 'notes': ''}},
            upsert=True,
            return_document=True
        )

        # Create a list of set documents
        num_sets = int(sets)
        set_list = [{"_id": ObjectId(), "set_number": i + 1, "completed": False, "weight_kg": "", "actual_reps": ""}
                    for i in range(num_sets)]

        # Create the new exercise task
        new_task = {
            '_id': ObjectId(), # PyMongo needs an ObjectId for embedded docs if you want to reference them
            'exercise_id': ObjectId(exercise_id),
            'exercise_name': exercise['name'], # Denormalizing for easier display
            'target_reps': reps,
            'sets': set_list # Embed the list of sets
        }

        # Add the new task to the workout day's tasks list
        workout_days_collection.update_one(
            {'_id': workout_day['_id']},
            {'$push': {'tasks': new_task}}
        )
        flash('Exercise added successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
    return redirect(url_for('dashboard'))

# Run the App
if __name__ == '__main__':
    app.run(debug=True)