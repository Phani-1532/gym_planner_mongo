from datetime import date
from bson import ObjectId
from flask import flash

def get_diet_plan_context(user, diet_entries_collection, selected_date):
    """
    Fetches diet entries for a given date and calculates macro totals.

    Args:
        user: The current user object.
        diet_entries_collection: The MongoDB collection for diet entries.
        selected_date: The date for which to fetch entries.

    Returns:
        A dictionary of context variables for the template.
    """
    entries = list(diet_entries_collection.find({
        'user_id': user['_id'],
        'date': selected_date.isoformat()
    }))

    totals = {
        'calories': sum(e.get('calories', 0) for e in entries),
        'protein': sum(e.get('protein_g', 0) for e in entries),
        'carbs': sum(e.get('carbs_g', 0) for e in entries),
        'fat': sum(e.get('fat_g', 0) for e in entries)
    }

    return {
        'selected_date': selected_date,
        'entries': entries,
        'totals': totals
    }

def add_diet_entry(request, user, diet_entries_collection):
    """
    Handles adding a new food entry to the diet plan.
    """
    try:
        entry = {
            'user_id': user['_id'],
            'date': request.form.get('date'),
            'food_name': request.form.get('food_name'),
            'calories': int(request.form.get('calories', 0)),
            'protein_g': int(request.form.get('protein_g', 0)),
            'carbs_g': int(request.form.get('carbs_g', 0)),
            'fat_g': int(request.form.get('fat_g', 0))
        }
        if not entry['food_name'] or not entry['date']:
            flash('Food name and date are required.', 'danger')
            return
        
        diet_entries_collection.insert_one(entry)
        flash('Food entry added successfully!', 'success')
    except (ValueError, TypeError) as e:
        flash('Invalid input. Please enter numbers for calories and macros.', 'danger')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')

def delete_diet_entry(entry_id, user, diet_entries_collection):
    """
    Handles deleting a food entry.
    """
    result = diet_entries_collection.delete_one({'_id': ObjectId(entry_id), 'user_id': user['_id']})
    if result.deleted_count > 0:
        flash('Entry deleted successfully.', 'success')
    else:
        flash('Could not delete entry. It may have already been removed.', 'warning')