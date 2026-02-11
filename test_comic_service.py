import pytest
import os
import json
import pandas as pd
from comic_service import ComicService, Comic

class TestComicService:
    
    @pytest.fixture
    def temp_files(self, tmp_path):
        """Create temporary files for testing"""
        csv_file = tmp_path / "test_comics.csv"
        json_file = tmp_path / "test_comics.json"
        return str(csv_file), str(json_file)
    
    @pytest.fixture
    def service(self, temp_files):
        """Create a ComicService instance for testing"""
        csv_file, json_file = temp_files
        return ComicService(csv_file, json_file)
    
    @pytest.fixture
    def sample_csv_data(self, temp_files):
        """Create sample CSV data for testing"""
        csv_file, json_file = temp_files
        data = {
            'Title': ['Batman', 'Superman', 'Wonder Woman'],
            'Volume': ['1', '2', '1'],
            'Writer': ['Bob Kane', 'Jerry Siegel', 'William Moulton Marston'],
            'Artist': ['Bob Kane', 'Joe Shuster', 'Harry G. Peter']
        }
        df = pd.DataFrame(data)
        df.to_csv(csv_file, index=False)
        return csv_file, json_file
    
    def test_comic_creation(self):
        """Test Comic dataclass creation"""
        comic = Comic("Batman", "1", "Bob Kane", "Bob Kane", 1)
        assert comic.title == "Batman"
        assert comic.volume == "1"
        assert comic.writer == "Bob Kane"
        assert comic.artist == "Bob Kane"
        assert comic.id == 1
    
    def test_service_initialization_empty(self, service):
        """Test service initialization with no existing data"""
        assert len(service.comics) == 0
        assert service.next_id == 1
    
    def test_service_initialization_with_csv(self, sample_csv_data):
        """Test service initialization with existing CSV data"""
        csv_file, json_file = sample_csv_data
        service = ComicService(csv_file, json_file)
        
        assert len(service.comics) == 3
        assert service.next_id == 4
        assert service.comics[0].title == "Batman"
        assert service.comics[1].title == "Superman"
        assert service.comics[2].title == "Wonder Woman"
    
    def test_add_comic(self, service):
        """Test adding a new comic"""
        comic = service.add_comic("Spider-Man", "1", "Stan Lee", "Steve Ditko")
        
        assert comic.title == "Spider-Man"
        assert comic.volume == "1"
        assert comic.writer == "Stan Lee"
        assert comic.artist == "Steve Ditko"
        assert comic.id == 1
        assert len(service.comics) == 1
        assert service.next_id == 2
    
    def test_get_all_comics(self, service):
        """Test getting all comics"""
        service.add_comic("Comic 1", "1", "Writer 1", "Artist 1")
        service.add_comic("Comic 2", "2", "Writer 2", "Artist 2")
        
        comics = service.get_all_comics()
        assert len(comics) == 2
        assert comics[0].title == "Comic 1"
        assert comics[1].title == "Comic 2"
    
    def test_get_comic_by_id(self, service):
        """Test getting a comic by ID"""
        comic1 = service.add_comic("Comic 1", "1", "Writer 1", "Artist 1")
        comic2 = service.add_comic("Comic 2", "2", "Writer 2", "Artist 2")
        
        found_comic = service.get_comic_by_id(comic1.id)
        assert found_comic is not None
        assert found_comic.title == "Comic 1"
        
        found_comic = service.get_comic_by_id(comic2.id)
        assert found_comic is not None
        assert found_comic.title == "Comic 2"
        
        not_found = service.get_comic_by_id(999)
        assert not_found is None
    
    def test_update_comic(self, service):
        """Test updating a comic"""
        comic = service.add_comic("Original Title", "1", "Original Writer", "Original Artist")
        
        updated = service.update_comic(comic.id, title="Updated Title", writer="Updated Writer")
        
        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.volume == "1"  # unchanged
        assert updated.writer == "Updated Writer"
        assert updated.artist == "Original Artist"  # unchanged
    
    def test_update_nonexistent_comic(self, service):
        """Test updating a comic that doesn't exist"""
        result = service.update_comic(999, title="New Title")
        assert result is None
    
    def test_delete_comic(self, service):
        """Test deleting a comic"""
        comic1 = service.add_comic("Comic 1", "1", "Writer 1", "Artist 1")
        comic2 = service.add_comic("Comic 2", "2", "Writer 2", "Artist 2")
        
        assert len(service.comics) == 2
        
        result = service.delete_comic(comic1.id)
        assert result is True
        assert len(service.comics) == 1
        assert service.get_comic_by_id(comic1.id) is None
        assert service.get_comic_by_id(comic2.id) is not None
    
    def test_delete_nonexistent_comic(self, service):
        """Test deleting a comic that doesn't exist"""
        result = service.delete_comic(999)
        assert result is False
    
    def test_search_comics(self, service):
        """Test searching comics"""
        service.add_comic("Batman Begins", "1", "Bob Kane", "Bob Kane")
        service.add_comic("Superman Returns", "1", "Jerry Siegel", "Joe Shuster")
        service.add_comic("Wonder Woman", "1", "William Marston", "Harry Peter")
        service.add_comic("Batman Forever", "2", "Bob Kane", "Different Artist")
        
        # Search by title
        results = service.search_comics("batman")
        assert len(results) == 2
        assert all("batman" in comic.title.lower() for comic in results)
        
        # Search by writer
        results = service.search_comics("bob kane")
        assert len(results) == 2
        assert all("bob kane" in comic.writer.lower() for comic in results)
        
        # Search by artist
        results = service.search_comics("joe shuster")
        assert len(results) == 1
        assert results[0].title == "Superman Returns"
        
        # Search with no results
        results = service.search_comics("nonexistent")
        assert len(results) == 0
    
    def test_save_and_load_json(self, service, temp_files):
        """Test saving to and loading from JSON"""
        excel_file, json_file = temp_files
        
        # Add some comics
        service.add_comic("Comic 1", "1", "Writer 1", "Artist 1")
        service.add_comic("Comic 2", "2", "Writer 2", "Artist 2")
        
        # Verify JSON file was created
        assert os.path.exists(json_file)
        
        # Create new service instance and verify data loads
        new_service = ComicService(excel_file, json_file)
        assert len(new_service.comics) == 2
        assert new_service.comics[0].title == "Comic 1"
        assert new_service.comics[1].title == "Comic 2"
    
    def test_export_to_csv(self, service, temp_files):
        """Test exporting to CSV"""
        csv_file, json_file = temp_files
        
        service.add_comic("Comic 1", "1", "Writer 1", "Artist 1")
        service.add_comic("Comic 2", "2", "Writer 2", "Artist 2")
        
        # Export to CSV
        exported_file = service.export_to_csv()
        assert exported_file == csv_file
        assert os.path.exists(csv_file)
        
        # Verify CSV content
        df = pd.read_csv(csv_file)
        assert len(df) == 2
        assert df.iloc[0]['Title'] == "Comic 1"
        assert df.iloc[1]['Title'] == "Comic 2"
    
    def test_mixed_data_sources(self, sample_csv_data):
        """Test loading from both CSV and JSON sources"""
        csv_file, json_file = sample_csv_data
        
        # Create JSON data with additional comics
        json_data = [
            {"id": 4, "title": "X-Men", "volume": "1", "writer": "Stan Lee", "artist": "Jack Kirby"},
            {"id": 5, "title": "Fantastic Four", "volume": "1", "writer": "Stan Lee", "artist": "Jack Kirby"}
        ]
        with open(json_file, 'w') as f:
            json.dump(json_data, f)
        
        # Load service with both data sources
        service = ComicService(csv_file, json_file)
        
        # Should have 3 from CSV + 2 from JSON = 5 total
        assert len(service.comics) == 5
        assert service.next_id == 6
        
        # Verify all comics are loaded
        titles = [comic.title for comic in service.comics]
        assert "Batman" in titles
        assert "Superman" in titles
        assert "Wonder Woman" in titles
        assert "X-Men" in titles
        assert "Fantastic Four" in titles

    def test_add_multiple_comics(self, service):
        """Test adding multiple comics at once"""
        comics_data = [
            {'title': 'Comic 1', 'volume': '1', 'writer': 'Writer 1', 'artist': 'Artist 1'},
            {'title': 'Comic 2', 'volume': '2', 'writer': 'Writer 2', 'artist': 'Artist 2'},
            {'title': 'Comic 3', 'volume': '1', 'writer': 'Writer 3', 'artist': 'Artist 3'}
        ]
        
        added_comics = service.add_multiple_comics(comics_data)
        
        assert len(added_comics) == 3
        assert len(service.comics) == 3
        assert service.next_id == 4
        
        # Verify all comics were added correctly
        assert added_comics[0].title == 'Comic 1'
        assert added_comics[1].title == 'Comic 2'
        assert added_comics[2].title == 'Comic 3'
        
        # Verify IDs are sequential
        assert added_comics[0].id == 1
        assert added_comics[1].id == 2
        assert added_comics[2].id == 3
    
    def test_add_multiple_comics_with_empty_entries(self, service):
        """Test adding multiple comics with some empty entries"""
        comics_data = [
            {'title': 'Valid Comic', 'volume': '1', 'writer': 'Writer', 'artist': 'Artist'},
            {'title': '', 'volume': '2', 'writer': 'Writer 2', 'artist': 'Artist 2'},  # Empty title
            {'title': 'Another Valid', 'volume': '3', 'writer': 'Writer 3', 'artist': 'Artist 3'},
            {'title': 'Incomplete', 'volume': '', 'writer': 'Writer 4', 'artist': ''}  # Missing fields
        ]
        
        added_comics = service.add_multiple_comics(comics_data)
        
        # Only valid comics should be added
        assert len(added_comics) == 2
        assert len(service.comics) == 2
        assert added_comics[0].title == 'Valid Comic'
        assert added_comics[1].title == 'Another Valid'
    
    def test_add_multiple_comics_empty_list(self, service):
        """Test adding multiple comics with empty list"""
        added_comics = service.add_multiple_comics([])
        
        assert len(added_comics) == 0
        assert len(service.comics) == 0
        assert service.next_id == 1

    def test_duplicate_detection_add_comic(self, service):
        """Test duplicate detection when adding a single comic"""
        # Add first comic
        service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        
        # Try to add duplicate (same title and volume)
        with pytest.raises(ValueError, match="A comic with title 'Batman' and volume '1' already exists!"):
            service.add_comic("Batman", "1", "Different Writer", "Different Artist")
        
        # Should still have only one comic
        assert len(service.comics) == 1
    
    def test_duplicate_detection_case_insensitive(self, service):
        """Test that duplicate detection is case insensitive"""
        service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        
        # Try to add with different case
        with pytest.raises(ValueError, match="A comic with title 'BATMAN' and volume '1' already exists!"):
            service.add_comic("BATMAN", "1", "Different Writer", "Different Artist")
        
        with pytest.raises(ValueError, match="A comic with title 'batman' and volume '1' already exists!"):
            service.add_comic("batman", "1", "Different Writer", "Different Artist")
    
    def test_duplicate_detection_different_volume_allowed(self, service):
        """Test that same title with different volume is allowed"""
        service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        service.add_comic("Batman", "2", "Different Writer", "Different Artist")
        
        assert len(service.comics) == 2
        assert service.comics[0].volume == "1"
        assert service.comics[1].volume == "2"
    
    def test_duplicate_detection_different_title_allowed(self, service):
        """Test that different title with same volume is allowed"""
        service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        service.add_comic("Superman", "1", "Jerry Siegel", "Joe Shuster")
        
        assert len(service.comics) == 2
        assert service.comics[0].title == "Batman"
        assert service.comics[1].title == "Superman"
    
    def test_duplicate_detection_add_multiple_comics(self, service):
        """Test duplicate detection when adding multiple comics"""
        # Add first comic
        service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        
        comics_data = [
            {'title': 'Superman', 'volume': '1', 'writer': 'Jerry Siegel', 'artist': 'Joe Shuster'},
            {'title': 'Batman', 'volume': '1', 'writer': 'Different Writer', 'artist': 'Different Artist'},  # Duplicate
            {'title': 'Wonder Woman', 'volume': '1', 'writer': 'William Marston', 'artist': 'Harry Peter'}
        ]
        
        with pytest.raises(ValueError, match="Duplicate comics found: Batman \\(Volume 1\\)"):
            service.add_multiple_comics(comics_data)
        
        # Should have only the original Batman (no new comics added due to duplicate)
        assert len(service.comics) == 1  # Only original Batman
    
    def test_duplicate_detection_update_comic(self, service):
        """Test duplicate detection when updating a comic"""
        comic1 = service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        comic2 = service.add_comic("Superman", "1", "Jerry Siegel", "Joe Shuster")
        
        # Try to update Superman to have same title/volume as Batman
        with pytest.raises(ValueError, match="A comic with title 'Batman' and volume '1' already exists!"):
            service.update_comic(comic2.id, title="Batman", volume="1")
        
        # Comic should remain unchanged
        updated_comic = service.get_comic_by_id(comic2.id)
        assert updated_comic.title == "Superman"
        assert updated_comic.volume == "1"
    
    def test_duplicate_detection_update_same_comic(self, service):
        """Test that updating a comic to its own values is allowed"""
        comic = service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        
        # Should be able to update other fields without changing title/volume
        updated = service.update_comic(comic.id, writer="Updated Writer", artist="Updated Artist")
        
        assert updated is not None
        assert updated.title == "Batman"
        assert updated.volume == "1"
        assert updated.writer == "Updated Writer"
        assert updated.artist == "Updated Artist"
    
    def test_auto_export_csv_on_add(self, service, temp_files):
        """Test that CSV is automatically exported when adding a comic"""
        csv_file, json_file = temp_files
        
        # Add a comic
        service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        
        # CSV should be automatically created/updated
        assert os.path.exists(csv_file)
        
        # Verify CSV content
        df = pd.read_csv(csv_file)
        assert len(df) == 1
        assert df.iloc[0]['Title'] == "Batman"
    
    def test_auto_export_csv_on_update(self, service, temp_files):
        """Test that CSV is automatically exported when updating a comic"""
        csv_file, json_file = temp_files
        
        comic = service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        service.update_comic(comic.id, title="Updated Batman")
        
        # Verify CSV was updated
        df = pd.read_csv(csv_file)
        assert len(df) == 1
        assert df.iloc[0]['Title'] == "Updated Batman"
    
    def test_auto_export_csv_on_delete(self, service, temp_files):
        """Test that CSV is automatically exported when deleting a comic"""
        csv_file, json_file = temp_files
        
        comic1 = service.add_comic("Batman", "1", "Bob Kane", "Bob Kane")
        comic2 = service.add_comic("Superman", "1", "Jerry Siegel", "Joe Shuster")
        
        # Delete one comic
        service.delete_comic(comic1.id)
        
        # Verify CSV was updated
        df = pd.read_csv(csv_file)
        assert len(df) == 1
        assert df.iloc[0]['Title'] == "Superman"

if __name__ == "__main__":
    pytest.main([__file__])