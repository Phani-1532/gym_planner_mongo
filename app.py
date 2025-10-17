import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
import bcrypt
from functools import wraps
from datetime import date, timedelta
from bson import ObjectId
from dotenv import load_dotenv
from monthly_handler import get_monthly_plan_context
from json_util import dumps as json_dumps
from exercise_handler import get_exercise_library_context, add_custom_exercise, edit_exercise_in_library, delete_exercise_from_library
from progress_handler import get_progress_data
from goal_setting_handler import get_goal_setting_context, set_exercise_goal
from diet_plan_handler import get_diet_plan_context, add_diet_entry, delete_diet_entry

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
goals_collection = db.goals # Collection for user goals
diet_entries_collection = db.diet_entries # Collection for diet entries

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
    today = date.today()

    # --- New Navigation Logic ---
    # Get year, month, and week from query parameters, defaulting to the current date
    selected_year = request.args.get('year', default=today.year, type=int)
    selected_month = request.args.get('month', default=today.month, type=int)

    # Determine the week of the month for today's date
    first_day_of_month = today.replace(day=1)
    start_of_first_week = first_day_of_month - timedelta(days=first_day_of_month.weekday())
    today_week_in_month = (today - start_of_first_week).days // 7 + 1

    selected_week_in_month = request.args.get('week', default=today_week_in_month, type=int)

    # Calculate the start date of the selected week
    first_day_of_selected_month = date(selected_year, selected_month, 1)
    start_of_first_week_of_month = first_day_of_selected_month - timedelta(days=first_day_of_selected_month.weekday())
    start_of_week = start_of_first_week_of_month + timedelta(weeks=selected_week_in_month - 1)
    end_of_week = start_of_week + timedelta(days=6)

    # --- Dropdown Population Logic ---
    # Year range: from first workout year to current year + 1
    first_workout = workout_days_collection.find_one(
        {'user_id': user['_id']},
        sort=[('date', 1)]
    )
    start_year = date.fromisoformat(first_workout['date']).year if first_workout else today.year
    year_range = range(start_year, today.year + 2)

    # Month range is always 1-12
    month_names = [date(2000, i, 1).strftime('%B') for i in range(1, 13)]

    # Calculate the number of weeks to show for the selected month
    # This is the number of weeks that have at least one day in the month
    if selected_month == 12:
        first_day_of_next_month = date(selected_year + 1, 1, 1)
    else:
        first_day_of_next_month = date(selected_year, selected_month + 1, 1)
    
    start_of_last_week_of_month = first_day_of_next_month - timedelta(days=first_day_of_next_month.weekday())
    # If the first of the next month is a Monday, the previous week is the last one.
    if first_day_of_next_month.weekday() == 0:
        start_of_last_week_of_month -= timedelta(weeks=1)

    num_weeks_in_month = ((start_of_last_week_of_month - start_of_first_week_of_month).days // 7) + 1

    # The old week_number can be deprecated or recalculated if needed, but the new UI doesn't use it.
    # For now, we'll remove it to simplify.

    # --- Check for previous week's workouts to enable/disable copy button ---
    previous_week_start = start_of_week - timedelta(days=7)
    previous_week_end = previous_week_start + timedelta(days=6)
    has_previous_week_workouts = workout_days_collection.count_documents({
        'user_id': user['_id'],
        'date': {'$gte': previous_week_start.isoformat(), '$lte': previous_week_end.isoformat()}
    }) > 0


    # Fetch workout days for the current user for the target week
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

    return render_template('weekly_planner.html', 
                           week_plan=week_plan, 
                           start_of_week=start_of_week, 
                           timedelta=timedelta,
                           all_exercises=all_exercises,
                           # New navigation context
                           selected_year=selected_year,
                           selected_month=selected_month,
                           selected_week_in_month=selected_week_in_month,
                           year_range=year_range,
                           month_names=month_names,
                           num_weeks_in_month=num_weeks_in_month,
                           has_previous_week_workouts=has_previous_week_workouts)

@app.route('/monthly-plan')
@login_required
def monthly_view(**kwargs):
    # Delegate the logic to the handler function
    user = kwargs.get('user')
    context = get_monthly_plan_context(request, user, workout_days_collection)
    return render_template('monthly_plan.html', json_dumps=json_dumps, **context)

@app.route('/exercise-library', methods=['GET', 'POST'])
@login_required
def exercise_library(**kwargs):
    user = kwargs.get('user')
    if request.method == 'POST':
        add_custom_exercise(request, user, exercises_collection)
        return redirect(url_for('exercise_library'))

    # For GET request
    context = get_exercise_library_context(exercises_collection)
    return render_template('exercise_library.html', **context)

@app.route('/edit-exercise-library/<exercise_id>', methods=['POST'])
@login_required
def edit_exercise_library(exercise_id, **kwargs):
    edit_exercise_in_library(request, exercise_id, exercises_collection)
    return redirect(url_for('exercise_library'))

@app.route('/delete-exercise-library/<exercise_id>', methods=['POST'])
@login_required
def delete_exercise_library(exercise_id, **kwargs):
    user = kwargs.get('user')
    delete_exercise_from_library(exercise_id, exercises_collection, workout_days_collection, goals_collection)
    return redirect(url_for('exercise_library'))

@app.route('/progress-tracker')
@login_required
def progress_tracker(**kwargs):
    user = kwargs.get('user')
    context = get_progress_data(user, workout_days_collection)
    return render_template('progress_tracker.html', json_dumps=json_dumps, **context)

@app.route('/goal-setting', methods=['GET', 'POST'])
@login_required
def goal_setting(**kwargs):
    user = kwargs.get('user')
    if request.method == 'POST':
        set_exercise_goal(request, user, goals_collection)
        return redirect(url_for('goal_setting'))

    context = get_goal_setting_context(user, workout_days_collection, exercises_collection, goals_collection)
    return render_template('goal_setting.html', **context)

@app.route('/diet-plan', methods=['GET', 'POST'])
@login_required
def diet_plan(**kwargs):
    user = kwargs.get('user')
    selected_date_str = request.args.get('date', default=date.today().isoformat())

    if request.method == 'POST':
        add_diet_entry(request, user, diet_entries_collection)
        # Redirect to the same date the entry was added to
        return redirect(url_for('diet_plan', date=request.form.get('date')))

    selected_date = date.fromisoformat(selected_date_str)
    context = get_diet_plan_context(user, diet_entries_collection, selected_date)
    return render_template('diet_plan.html', timedelta=timedelta, **context)

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

        update_data = {'is_rest_day': is_rest_day, 'notes': notes}

        # Only update the title if it's not a Sunday.
        # For Sundays, the title field is disabled on the frontend and not submitted.
        # This prevents the title from being blanked out.
        workout_date = date.fromisoformat(workout_date_str)
        if workout_date.weekday() != 6: # Monday is 0, Sunday is 6
            # If marking as a rest day, we might want to clear the title,
            # unless a title was explicitly provided.
            if not is_rest_day or title:
                update_data['title'] = title

        # Find the workout day or create a new one if it doesn't exist
        workout_days_collection.find_one_and_update(
            {'user_id': user['_id'], 'date': workout_date_str},
            {
                '$set': update_data,
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
        rest_time = request.form.get('edit_rest_time', '') # Optional
        notes = request.form.get('edit_notes', '') # Optional

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
            'tasks.$[task].sets': new_set_list,
            'tasks.$[task].rest_time': rest_time,
            'tasks.$[task].notes': notes
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
        rest_time = request.form.get('rest_time', '') # Optional
        notes = request.form.get('notes', '') # Optional

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
            'sets': set_list, # Embed the list of sets
            'rest_time': rest_time,
            'notes': notes
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

@app.route('/copy-last-week', methods=['POST'])
@login_required
def copy_last_week(user):
    try:
        current_week_start_str = request.form.get('current_week_start_date')
        if not current_week_start_str:
            flash('Could not determine the current week.', 'danger')
            return redirect(url_for('dashboard'))

        current_week_start = date.fromisoformat(current_week_start_str)

        # 1. Calculate date ranges for previous and current weeks
        previous_week_start = current_week_start - timedelta(days=7)
        previous_week_end = previous_week_start + timedelta(days=6)
        current_week_end = current_week_start + timedelta(days=6)

        # 2. Fetch all workout days from the previous week
        last_week_workouts = list(workout_days_collection.find({
            'user_id': user['_id'],
            'date': {'$gte': previous_week_start.isoformat(), '$lte': previous_week_end.isoformat()}
        }))

        if not last_week_workouts:
            flash('No workouts found in the previous week to copy.', 'info')
            return redirect(request.referrer or url_for('dashboard'))

        # 3. Clear any existing workouts in the current week to prevent duplicates
        workout_days_collection.delete_many({
            'user_id': user['_id'],
            'date': {'$gte': current_week_start.isoformat(), '$lte': current_week_end.isoformat()}
        })

        # 4. Create new workout documents for the current week
        new_workouts = []
        for old_workout in last_week_workouts:
            new_workout = old_workout.copy()
            # Remove old ID to allow insertion as a new document
            del new_workout['_id']
            # Advance the date by 7 days
            new_workout['date'] = (date.fromisoformat(old_workout['date']) + timedelta(days=7)).isoformat()
            
            # Reset completion status by creating new IDs and resetting 'completed' flags
            for task in new_workout.get('tasks', []):
                task['_id'] = ObjectId()
                for set_item in task.get('sets', []):
                    set_item['_id'] = ObjectId()
                    set_item['completed'] = False
            
            new_workouts.append(new_workout)

        if new_workouts:
            workout_days_collection.insert_many(new_workouts)
            flash('Successfully copied last week\'s plan!', 'success')
        else:
            flash('Something went wrong during the copy process.', 'warning')

    except Exception as e:
        flash(f'An error occurred while copying the plan: {e}', 'danger')
    
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/copy-day', methods=['POST'])
@login_required
def copy_day(user):
    try:
        source_workout_id = request.form.get('source_workout_id')
        target_date_str = request.form.get('target_date')

        if not source_workout_id or not target_date_str:
            flash('Missing source workout or target date.', 'danger')
            return redirect(request.referrer or url_for('dashboard'))

        # 1. Fetch the source workout day
        source_workout = workout_days_collection.find_one({
            '_id': ObjectId(source_workout_id),
            'user_id': user['_id']
        })

        if not source_workout or not source_workout.get('tasks'):
            flash('The day you are trying to copy has no exercises.', 'info')
            return redirect(request.referrer or url_for('dashboard'))

        # 2. Prepare the new workout document
        new_workout_data = source_workout.copy()
        del new_workout_data['_id'] # Remove old ID
        new_workout_data['date'] = target_date_str

        # 3. Reset all task and set IDs and completion status
        for task in new_workout_data.get('tasks', []):
            task['_id'] = ObjectId()
            for set_item in task.get('sets', []):
                set_item['_id'] = ObjectId()
                set_item['completed'] = False

        # 4. Overwrite any existing workout on the target date (upsert)
        workout_days_collection.find_one_and_replace(
            {'user_id': user['_id'], 'date': target_date_str},
            new_workout_data,
            upsert=True
        )

        flash(f"Workout from {source_workout['date']} successfully copied to {target_date_str}!", 'success')

        # Redirect to the week of the target date
        target_date = date.fromisoformat(target_date_str)
        first_day_of_month = target_date.replace(day=1)
        start_of_first_week = first_day_of_month - timedelta(days=first_day_of_month.weekday())
        target_week_in_month = (target_date - start_of_first_week).days // 7 + 1
        return redirect(url_for('dashboard', year=target_date.year, month=target_date.month, week=target_week_in_month))

    except Exception as e:
        flash(f'An error occurred while copying the day: {e}', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

@app.route('/delete-diet-entry/<entry_id>', methods=['POST'])
@login_required
def delete_diet_entry_route(entry_id, **kwargs):
    user = kwargs.get('user')
    # The date is needed to redirect back to the correct page
    redirect_date = request.form.get('date', date.today().isoformat())
    delete_diet_entry(entry_id, user, diet_entries_collection)
    return redirect(url_for('diet_plan', date=redirect_date))
# Run the App
if __name__ == '__main__':
    app.run(debug=True)