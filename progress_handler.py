from datetime import datetime, timedelta
from collections import defaultdict

def get_progress_data(user, workout_days_collection):
    """
    Fetches and processes workout data to generate statistics for charts.

    Args:
        user: The current user object.
        workout_days_collection: The MongoDB collection for workout days.

    Returns:
        A dictionary containing processed data for volume and exercise progression.
    """
    # Fetch all workout days for the user that have at least one exercise task
    workouts = list(workout_days_collection.find({
        'user_id': user['_id'],
        'tasks.0': {'$exists': True}
    }).sort('date', 1))

    if not workouts:
        return {
            'volume_data': {'labels': [], 'data': []},
            'exercise_progression': {}
        }

    # --- 1. Calculate Total Volume Over Time (Grouped by Week) ---
    weekly_volume = defaultdict(float)
    for workout in workouts:
        try:
            workout_date = datetime.fromisoformat(workout['date'])
            # Group by the start of the week (Monday)
            start_of_week = workout_date - timedelta(days=workout_date.weekday())
            week_label = start_of_week.strftime('%Y-%m-%d')

            day_volume = 0
            for task in workout.get('tasks', []):
                for s in task.get('sets', []):
                    try:
                        weight = float(s.get('weight_kg', 0))
                        reps = int(s.get('actual_reps', 0))
                        if weight > 0 and reps > 0:
                            day_volume += weight * reps
                    except (ValueError, TypeError):
                        continue # Skip if weight/reps are not valid numbers
            weekly_volume[week_label] += day_volume
        except (ValueError, TypeError):
            continue

    sorted_weeks = sorted(weekly_volume.keys())
    volume_data = {
        'labels': [datetime.strptime(w, '%Y-%m-%d').strftime('%b %d, %Y') for w in sorted_weeks],
        'data': [weekly_volume[w] for w in sorted_weeks]
    }

    # --- 2. Calculate Max Weight Lifted for Each Exercise Over Time ---
    exercise_progression = defaultdict(lambda: defaultdict(float))
    for workout in workouts:
        for task in workout.get('tasks', []):
            exercise_name = task.get('exercise_name')
            if not exercise_name:
                continue
            
            max_weight_for_day = 0
            for s in task.get('sets', []):
                try:
                    max_weight_for_day = max(max_weight_for_day, float(s.get('weight_kg', 0)))
                except (ValueError, TypeError):
                    continue
            
            # Store the max weight for that day, avoiding duplicates if an exercise is done twice
            if max_weight_for_day > exercise_progression[exercise_name][workout['date']]:
                exercise_progression[exercise_name][workout['date']] = max_weight_for_day

    return {
        'volume_data': volume_data,
        'exercise_progression': dict(exercise_progression)
    }