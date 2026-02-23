from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from comic_service import ComicService, Comic
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Initialize the comic service
comic_service = ComicService()

@app.route('/')
def index():
    """Main page showing all comics"""
    sort_by = request.args.get('sort', 'title')  # Default sort by title
    sort_order = request.args.get('order', 'asc')  # Default ascending order
    page = int(request.args.get('page', 1))  # Default to page 1
    per_page = 50  # Comics per page
    
    comics = comic_service.get_all_comics()
    
    # Sort comics based on the selected field
    if sort_by == 'title':
        comics.sort(key=lambda x: x.title.lower(), reverse=(sort_order == 'desc'))
    elif sort_by == 'writer':
        comics.sort(key=lambda x: x.writer.lower(), reverse=(sort_order == 'desc'))
    elif sort_by == 'artist':
        comics.sort(key=lambda x: x.artist.lower(), reverse=(sort_order == 'desc'))
    elif sort_by == 'volume':
        comics.sort(key=lambda x: int(x.volume) if x.volume.isdigit() else 0, reverse=(sort_order == 'desc'))
    
    # Calculate pagination
    total_comics = len(comics)
    total_pages = (total_comics + per_page - 1) // per_page  # Ceiling division
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_comics = comics[start_idx:end_idx]
    
    # Calculate pagination info
    has_prev = page > 1
    has_next = page < total_pages
    prev_page = page - 1 if has_prev else None
    next_page = page + 1 if has_next else None
    
    return render_template('index.html', 
                         comics=paginated_comics,
                         sort_by=sort_by, 
                         sort_order=sort_order,
                         page=page,
                         total_pages=total_pages,
                         total_comics=total_comics,
                         has_prev=has_prev,
                         has_next=has_next,
                         prev_page=prev_page,
                         next_page=next_page,
                         per_page=per_page)

@app.route('/add', methods=['GET', 'POST'])
def add_comic():
    """Add a new comic"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        volume = request.form.get('volume', '').strip()
        writer = request.form.get('writer', '').strip()
        artist = request.form.get('artist', '').strip()
        
        if not all([title, volume, writer, artist]):
            flash('All fields are required!', 'error')
            return render_template('add_comic.html')
        
        try:
            comic = comic_service.add_comic(title, volume, writer, artist)
            flash(f'Comic "{title}" added successfully!', 'success')
            return redirect(url_for('index'))
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('add_comic.html')
    
    return render_template('add_comic.html')

@app.route('/add-multiple', methods=['GET', 'POST'])
def add_multiple_comics():
    """Add multiple comics at once"""
    if request.method == 'POST':
        # Get the number of comics to process
        comic_count = 0
        comics_data = []
        
        # Process form data - look for comic entries
        i = 0
        while True:
            title = request.form.get(f'title_{i}', '').strip()
            volume = request.form.get(f'volume_{i}', '').strip()
            writer = request.form.get(f'writer_{i}', '').strip()
            artist = request.form.get(f'artist_{i}', '').strip()
            
            # If no title for this index, we've reached the end
            if not title:
                break
                
            # Only add if all fields are filled
            if all([title, volume, writer, artist]):
                comics_data.append({
                    'title': title,
                    'volume': volume,
                    'writer': writer,
                    'artist': artist
                })
            i += 1
        
        if not comics_data:
            flash('Please fill in at least one complete comic entry!', 'error')
            return render_template('add_multiple_comics.html')
        
        try:
            # Add all comics
            added_comics = comic_service.add_multiple_comics(comics_data)
            
            if added_comics:
                flash(f'Successfully added {len(added_comics)} comics!', 'success')
                return redirect(url_for('index'))
            else:
                flash('No comics were added. Please check your entries.', 'error')
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('add_multiple_comics.html')
    
    return render_template('add_multiple_comics.html')

@app.route('/edit/<int:comic_id>', methods=['GET', 'POST'])
def edit_comic(comic_id):
    """Edit an existing comic"""
    comic = comic_service.get_comic_by_id(comic_id)
    if not comic:
        flash('Comic not found!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        volume = request.form.get('volume', '').strip()
        writer = request.form.get('writer', '').strip()
        artist = request.form.get('artist', '').strip()
        
        if not all([title, volume, writer, artist]):
            flash('All fields are required!', 'error')
            return render_template('edit_comic.html', comic=comic)
        
        try:
            updated_comic = comic_service.update_comic(comic_id, title, volume, writer, artist)
            if updated_comic:
                flash(f'Comic "{title}" updated successfully!', 'success')
            else:
                flash('Error updating comic!', 'error')
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('edit_comic.html', comic=comic)
        
        return redirect(url_for('index'))
    
    return render_template('edit_comic.html', comic=comic)

@app.route('/delete/<int:comic_id>')
def delete_comic(comic_id):
    """Delete a comic"""
    comic = comic_service.get_comic_by_id(comic_id)
    if comic:
        if comic_service.delete_comic(comic_id):
            flash(f'Comic "{comic.title}" deleted successfully!', 'success')
        else:
            flash('Error deleting comic!', 'error')
    else:
        flash('Comic not found!', 'error')
    
    return redirect(url_for('index'))

@app.route('/search')
def search():
    """Search comics"""
    query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'title')  # Default sort by title
    sort_order = request.args.get('order', 'asc')  # Default ascending order
    page = int(request.args.get('page', 1))  # Default to page 1
    per_page = 50  # Comics per page
    
    if query:
        comics = comic_service.search_comics(query)
        
        # Sort search results based on the selected field
        if sort_by == 'title':
            comics.sort(key=lambda x: x.title.lower(), reverse=(sort_order == 'desc'))
        elif sort_by == 'writer':
            comics.sort(key=lambda x: x.writer.lower(), reverse=(sort_order == 'desc'))
        elif sort_by == 'artist':
            comics.sort(key=lambda x: x.artist.lower(), reverse=(sort_order == 'desc'))
        elif sort_by == 'volume':
            comics.sort(key=lambda x: int(x.volume) if x.volume.isdigit() else 0, reverse=(sort_order == 'desc'))
        
        # Calculate pagination
        total_comics = len(comics)
        total_pages = (total_comics + per_page - 1) // per_page  # Ceiling division
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_comics = comics[start_idx:end_idx]
        
        # Calculate pagination info
        has_prev = page > 1
        has_next = page < total_pages
        prev_page = page - 1 if has_prev else None
        next_page = page + 1 if has_next else None
        
        return render_template('index.html', 
                             comics=paginated_comics,
                             search_query=query, 
                             sort_by=sort_by, 
                             sort_order=sort_order,
                             page=page,
                             total_pages=total_pages,
                             total_comics=total_comics,
                             has_prev=has_prev,
                             has_next=has_next,
                             prev_page=prev_page,
                             next_page=next_page,
                             per_page=per_page)
    else:
        return redirect(url_for('index'))

# API endpoints for potential future use
@app.route('/api/comics')
def api_get_comics():
    """API endpoint to get all comics"""
    comics = comic_service.get_all_comics()
    return jsonify([{
        'id': comic.id,
        'title': comic.title,
        'volume': comic.volume,
        'writer': comic.writer,
        'artist': comic.artist
    } for comic in comics])

@app.route('/api/comics/<int:comic_id>')
def api_get_comic(comic_id):
    """API endpoint to get a specific comic"""
    comic = comic_service.get_comic_by_id(comic_id)
    if comic:
        return jsonify({
            'id': comic.id,
            'title': comic.title,
            'volume': comic.volume,
            'writer': comic.writer,
            'artist': comic.artist
        })
    return jsonify({'error': 'Comic not found'}), 404

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(debug=True, host='0.0.0.0', port=5001)