import json
import os

PLANNER_FILE = "workout_planner.json"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def get_default_week():
    """Returns the default structure for a new week."""
    week_plan = {day: [] for day in DAYS if day != "Sunday"}
    week_plan["Sunday"] = "Rest Day"
    return week_plan

def load_planner():
    """Loads the planner from a JSON file. If not found, creates a default one."""
    if not os.path.exists(PLANNER_FILE):
        print("No existing planner found. Creating a new one.")
        return {"week_1": get_default_week()}
    
    try:
        with open(PLANNER_FILE, 'r') as f:
            # Handle empty file case
            content = f.read()
            if not content:
                print("Planner file is empty. Creating a default plan.")
                return {"week_1": get_default_week()}
            return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading planner file: {e}. Starting with a fresh plan.")
        return {"week_1": get_default_week()}

def save_planner(planner_data):
    """Saves the planner data to the JSON file."""
    try:
        with open(PLANNER_FILE, 'w') as f:
            json.dump(planner_data, f, indent=4)
        print("Planner saved successfully.")
    except IOError as e:
        print(f"Error saving planner: {e}")

def display_week(planner_data, week_key):
    """Displays the plan for a specific week."""
    if week_key not in planner_data:
        print(f"Error: {week_key} not found in the planner.")
        return

    print("\n" + "="*20)
    print(f"  Workout Plan for {week_key.replace('_', ' ').title()}  ")
    print("="*20)
    
    week_plan = planner_data[week_key]
    for day in DAYS:
        tasks = week_plan.get(day, "Not set")
        print(f"\n--- {day} ---")
        if isinstance(tasks, list):
            if tasks:
                for i, task in enumerate(tasks, 1):
                    print(f"  {i}. {task}")
            else:
                print("  No exercises scheduled.")
        else:
            print(f"  {tasks}") # For "Rest Day"
    print("\n" + "="*20)

def add_edit_workout(planner_data):
    """Adds or edits the workout for a specific day in a week."""
    week_key = input("Enter the week to edit (e.g., 'week_1'): ").lower().replace(' ', '_')
    if week_key not in planner_data:
        print(f"Error: {week_key} not found.")
        return

    day = input(f"Enter the day to edit ({', '.join(DAYS[:-1])}): ").capitalize()
    if day not in DAYS:
        print("Invalid day entered.")
        return

    if day == "Sunday":
        print("Sunday is a designated rest day and cannot be edited.")
        return

    print(f"Current exercises for {day}, {week_key}: {planner_data[week_key].get(day, [])}")
    new_exercises_str = input("Enter new exercises, separated by commas (or leave blank to clear): ")
    
    if new_exercises_str.strip():
        new_exercises = [ex.strip() for ex in new_exercises_str.split(',')]
        planner_data[week_key][day] = new_exercises
    else:
        planner_data[week_key][day] = []
        print(f"Cleared all exercises for {day}.")

    save_planner(planner_data)

def add_new_week(planner_data):
    """Adds a new, empty week to the planner."""
    week_keys = [int(k.split('_')[1]) for k in planner_data.keys() if k.startswith('week_')]
    next_week_num = max(week_keys) + 1 if week_keys else 1
    new_week_key = f"week_{next_week_num}"
    
    planner_data[new_week_key] = get_default_week()
    print(f"Successfully added '{new_week_key}'.")
    save_planner(planner_data)

def view_planner(planner_data):
    """Allows the user to select and view a week's plan."""
    if not planner_data:
        print("Planner is empty. Add a new week to get started.")
        return
        
    print("Available weeks:", ", ".join(planner_data.keys()))
    week_key = input("Enter which week you want to view (e.g., 'week_1'): ").lower().replace(' ', '_')
    display_week(planner_data, week_key)

def main():
    """Main function to run the planner application."""
    planner_data = load_planner()

    while True:
        print("\n--- Weekly Workout Planner ---")
        print("1. View a Weekly Plan")
        print("2. Add/Edit a Day's Workout")
        print("3. Add a New Week")
        print("4. Exit")
        
        choice = input("Choose an option (1-4): ")

        if choice == '1':
            view_planner(planner_data)
        elif choice == '2':
            add_edit_workout(planner_data)
        elif choice == '3':
            add_new_week(planner_data)
        elif choice == '4':
            print("Exiting planner. Have a great day!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")

if __name__ == "__main__":
    main()
