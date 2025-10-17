from datetime import date, timedelta

def get_monthly_plan_context(request, user, workout_days_collection):
    """
    Calculates the calendar grid and fetches workout data for the monthly view.

    Args:
        request: The Flask request object to get query parameters.
        user: The current user object.
        workout_days_collection: The MongoDB collection for workout days.

    Returns:
        A dictionary of context variables for rendering the template.
    """
    today = date.today()
    selected_year = request.args.get('year', default=today.year, type=int)
    selected_month = request.args.get('month', default=today.month, type=int)

    # Determine the first day of the selected month and its weekday (0=Monday, 6=Sunday)
    first_day_of_month = date(selected_year, selected_month, 1)
    
    # Calculate the start of the calendar view (which could be in the previous month)
    start_of_calendar = first_day_of_month - timedelta(days=first_day_of_month.weekday())

    # Calculate the end of the calendar view (which could be in the next month)
    end_of_calendar = start_of_calendar + timedelta(days=41)

    # Fetch all workout days for the user that fall within the calendar's date range
    workouts_query = {
        'user_id': user['_id'],
        'date': {'$gte': start_of_calendar.isoformat(), '$lte': end_of_calendar.isoformat()}
    }
    user_workouts = workout_days_collection.find(workouts_query)
    workouts_by_date = {workout['date']: workout for workout in user_workouts}

    # Create the calendar grid data structure for the template
    calendar_weeks = []
    current_day = start_of_calendar
    for _ in range(6): # A month fits in a maximum of 6 weeks
        week = []
        for _ in range(7): # 7 days a week
            week.append(current_day)
            current_day += timedelta(days=1)
        calendar_weeks.append(week)

    return {
        'calendar_weeks': calendar_weeks,
        'workouts_by_date': workouts_by_date,
        'selected_date': first_day_of_month,
        'today': today
    }