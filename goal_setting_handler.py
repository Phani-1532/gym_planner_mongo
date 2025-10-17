from collections import defaultdict
from bson import ObjectId
from flask import flash

def get_goal_setting_context(user, workout_days_collection, exercises_collection, goals_collection):
    """
    Calculates current PRs, fetches user goals, and prepares the context for the goal setting page.

    Args:
        user: The current user object.
        workout_days_collection: The MongoDB collection for workout days.
        exercises_collection: The MongoDB collection for exercises.
        goals_collection: The MongoDB collection for user goals.

    Returns:
        A dictionary of context variables for rendering the template.
    """
    # 1. Calculate current Personal Records (PRs) from workout history
    current_prs = defaultdict(lambda: {'weight': 0, 'date': None})
    workouts = workout_days_collection.find({'user_id': user['_id'], 'tasks.0': {'$exists': True}})

    for workout in workouts:
        for task in workout.get('tasks', []):
            exercise_id = str(task.get('exercise_id'))
            if not exercise_id:
                continue
            
            for s in task.get('sets', []):
                try:
                    weight = float(s.get('weight_kg', 0))
                    if weight > current_prs[exercise_id]['weight']:
                        current_prs[exercise_id]['weight'] = weight
                        current_prs[exercise_id]['date'] = workout['date']
                except (ValueError, TypeError):
                    continue

    # 2. Fetch user-defined goals
    user_goals_cursor = goals_collection.find({'user_id': user['_id']})
    user_goals = {str(goal['exercise_id']): goal for goal in user_goals_cursor}

    # 3. Fetch all exercises to build the main list
    all_exercises = list(exercises_collection.find().sort('name', 1))

    # 4. Combine all data for the template
    goal_tracking_list = []
    for exercise in all_exercises:
        exercise_id_str = str(exercise['_id'])
        pr_info = current_prs.get(exercise_id_str)
        goal_info = user_goals.get(exercise_id_str)
        
        goal_tracking_list.append({
            'exercise': exercise,
            'pr_weight': pr_info['weight'] if pr_info else 0,
            'pr_date': pr_info['date'] if pr_info else None,
            'goal_weight': goal_info['goal_weight_kg'] if goal_info else None
        })

    return {
        'goal_tracking_list': goal_tracking_list,
        'all_exercises': all_exercises
    }

def set_exercise_goal(request, user, goals_collection):
    """
    Handles the logic for setting or updating a user's goal for an exercise.
    """
    try:
        exercise_id = request.form.get('exercise_id')
        goal_weight = request.form.get('goal_weight')

        if not exercise_id or not goal_weight:
            flash('Exercise and goal weight are required.', 'danger')
            return

        goals_collection.update_one(
            {'user_id': user['_id'], 'exercise_id': ObjectId(exercise_id)},
            {'$set': {'goal_weight_kg': float(goal_weight)}},
            upsert=True
        )
        flash('Goal updated successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')