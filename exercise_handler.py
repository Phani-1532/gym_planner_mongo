from flask import flash
from bson import ObjectId

def get_exercise_library_context(exercises_collection):
    """
    Fetches all exercises to be displayed in the library, sorted by name.
    
    Args:
        exercises_collection: The MongoDB collection for exercises.

    Returns:
        A dictionary containing the list of exercises.
    """
    # In the future, this could be expanded to differentiate between global and user-specific exercises
    all_exercises = list(exercises_collection.find().sort('name', 1))
    return {'all_exercises': all_exercises}

def add_custom_exercise(request, user, exercises_collection):
    """
    Handles the logic for adding a new custom exercise from a form submission.

    Args:
        request: The Flask request object containing form data.
        user: The current user object.
        exercises_collection: The MongoDB collection for exercises.
    """
    try:
        exercise_name = request.form.get('exercise_name')
        muscle_group = request.form.get('muscle_group')

        if not exercise_name or not muscle_group:
            flash('Both exercise name and muscle group are required.', 'danger')
            return

        # Check if an exercise with the same name already exists (case-insensitive)
        if exercises_collection.find_one({'name': {'$regex': f'^{exercise_name}$', '$options': 'i'}}):
            flash(f'An exercise named "{exercise_name}" already exists.', 'warning')
            return

        exercises_collection.insert_one({'name': exercise_name, 'muscle_group': muscle_group, 'created_by': user['_id']})
        flash(f'Exercise "{exercise_name}" added successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred while adding the exercise: {e}', 'danger')

def edit_exercise_in_library(request, exercise_id, exercises_collection):
    """
    Handles the logic for editing an existing exercise.
    """
    try:
        new_name = request.form.get('edit_exercise_name')
        new_muscle_group = request.form.get('edit_muscle_group')

        if not new_name or not new_muscle_group:
            flash('Both exercise name and muscle group are required.', 'danger')
            return

        # Check if another exercise with the same new name already exists
        existing_exercise = exercises_collection.find_one({
            'name': {'$regex': f'^{new_name}$', '$options': 'i'},
            '_id': {'$ne': ObjectId(exercise_id)}
        })
        if existing_exercise:
            flash(f'An exercise named "{new_name}" already exists.', 'warning')
            return

        exercises_collection.update_one(
            {'_id': ObjectId(exercise_id)},
            {'$set': {'name': new_name, 'muscle_group': new_muscle_group}}
        )
        flash('Exercise updated successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred while editing the exercise: {e}', 'danger')

def delete_exercise_from_library(exercise_id, exercises_collection, workout_days_collection, goals_collection):
    """
    Handles the logic for deleting an exercise, with safety checks.
    """
    try:
        obj_exercise_id = ObjectId(exercise_id)

        # Safety check: See if the exercise is used in any workout day tasks
        is_in_use = workout_days_collection.find_one({'tasks.exercise_id': obj_exercise_id})
        if is_in_use:
            flash('Cannot delete this exercise because it is currently used in one or more workout plans.', 'danger')
            return

        # Proceed with deletion from exercises and goals collections
        exercises_collection.delete_one({'_id': obj_exercise_id})
        goals_collection.delete_many({'exercise_id': obj_exercise_id})

        flash('Exercise deleted successfully.', 'success')
    except Exception as e:
        flash(f'An error occurred while deleting the exercise: {e}', 'danger')