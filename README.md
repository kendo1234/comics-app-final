# Comic Collection Manager

A Python web application for managing your comic book collection with Excel integration.

## Features

- **Add, Edit, Delete Comics**: Full CRUD operations for your comic collection
- **Bulk Add Comics**: Add multiple comics at once through an intuitive interface
- **CSV Integration**: Import from and export to CSV files
- **Search Functionality**: Search comics by title, writer, or artist
- **Web Interface**: Clean, responsive web UI built with Flask
- **Local Storage**: Data persistence using JSON and CSV files
- **RESTful API**: JSON API endpoints for potential integrations

## Project Structure

```
ComicsApp/
├── app.py                 # Flask web application
├── comic_service.py       # Core service layer with business logic
├── test_comic_service.py  # Unit tests for the service layer
├── Comics.csv            # Original CSV file with existing comics
├── comics_data.json      # JSON storage for new/modified comics
├── templates/            # HTML templates
│   ├── base.html         # Base template with common layout
│   ├── index.html        # Main page showing all comics
│   ├── add_comic.html    # Add new comic form
│   └── edit_comic.html   # Edit existing comic form
└── README.md            # This file
```

## Installation

1. **Clone or download the project files**

2. **Install required Python packages:**

   ```bash
   pip3 install pandas openpyxl flask pytest
   ```

3. **Verify your Comics.csv file is in the project directory**

## Usage

### Running the Web Application

1. **Start the Flask server:**

   ```bash
   python3 app.py
   ```

2. **Open your web browser and navigate to:**

   ```
   http://localhost:5001
   ```

3. **Use the web interface to:**
   - View all comics in your collection
   - Search for specific comics
   - Add new comics to your collection
   - Add multiple comics at once using the bulk add feature
   - Edit existing comic information
   - Delete comics from your collection
   - Export your collection to CSV

### Web Interface Features

- **Home Page**: Displays all comics in a searchable table
- **Search**: Real-time search by title, writer, or artist
- **Add Comic**: Form to add new comics with validation
- **Add Multiple Comics**: Bulk add interface with dynamic form fields
- **Edit Comic**: Modify existing comic information
- **Delete Comic**: Remove comics with confirmation
- **Export**: Download your collection as a CSV file

### Bulk Add Feature

The bulk add functionality allows you to add multiple comics efficiently:

1. **Dynamic Form Fields**: Start with one comic entry and add more as needed
2. **Keyboard Shortcuts**: Use Ctrl/Cmd + Enter to quickly add another comic form
3. **Smart Validation**: Only complete entries (all fields filled) are processed
4. **Responsive Design**: Works well on both desktop and mobile devices
5. **Auto-focus**: Automatically focuses on the first field of new entries

**Usage Tips:**

- Fill in complete information for each comic before adding more fields
- Use the "Add Another Comic" button or keyboard shortcut to add more entries
- Incomplete entries (missing any field) will be skipped during submission
- You can remove the last comic entry if you added too many fields

### API Endpoints

The application also provides REST API endpoints:

- `GET /api/comics` - Get all comics as JSON
- `GET /api/comics/<id>` - Get a specific comic by ID

## Data Storage

The application uses a hybrid storage approach:

1. **CSV File (Comics.csv)**: Your original comic data is preserved
2. **JSON File (comics_data.json)**: New additions and modifications are stored here
3. **Export Function**: Combines both sources into a single CSV file

## Testing

### Running Unit Tests

Execute the test suite to verify functionality:

```bash
python3 -m pytest test_comic_service.py -v
```

### Test Coverage

The test suite covers:

- Comic creation and data validation
- Service initialization with various data sources
- CRUD operations (Create, Read, Update, Delete)
- Search functionality
- Data persistence (JSON and CSV)
- Error handling for edge cases

### Sample Test Output

```
test_comic_service.py::TestComicService::test_comic_creation PASSED
test_comic_service.py::TestComicService::test_service_initialization_empty PASSED
test_comic_service.py::TestComicService::test_add_comic PASSED
test_comic_service.py::TestComicService::test_get_all_comics PASSED
test_comic_service.py::TestComicService::test_search_comics PASSED
...
```

## Development

### Service Layer (comic_service.py)

The `ComicService` class provides:

- Data loading from CSV and JSON sources
- CRUD operations for comic management
- Search functionality
- Data persistence and export capabilities

### Web Layer (app.py)

The Flask application provides:

- Web routes for all user interactions
- Form handling and validation
- Template rendering
- API endpoints for programmatic access

### Key Classes

**Comic**: Data class representing a comic book

```python
@dataclass
class Comic:
    title: str
    volume: str
    writer: str
    artist: str
    id: Optional[int] = None
```

**ComicService**: Main service class for comic management

- `add_comic()`: Add a new comic
- `get_all_comics()`: Retrieve all comics
- `update_comic()`: Modify existing comic
- `delete_comic()`: Remove a comic
- `search_comics()`: Search by title/writer/artist
- `export_to_csv()`: Export collection to CSV

## Troubleshooting

### Common Issues

1. **Module not found errors**: Ensure all required packages are installed

   ```bash
   pip3 install pandas openpyxl flask pytest
   ```

2. **Port already in use**: If port 5000 is busy, modify the port in app.py:

   ```python
   app.run(debug=True, host='0.0.0.0', port=5001)
   ```

3. **CSV file permissions**: Ensure the Comics.csv file is not open in a spreadsheet application when running the app

4. **Data not persisting**: Check that the application has write permissions in the project directory

### File Permissions

Ensure the application can read/write these files:

- `Comics.xlsx` (read access)
- `comics_data.json` (read/write access)

## Future Enhancements

Potential improvements for the application:

- User authentication and multiple collections
- Image upload for comic covers
- Advanced filtering and sorting options
- Backup and restore functionality
- Integration with comic databases (e.g., Comic Vine API)
- Mobile-responsive design improvements

## License

This project is provided as-is for educational and personal use.
