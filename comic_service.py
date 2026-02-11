import pandas as pd
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import json

@dataclass
class Comic:
    title: str
    volume: str
    writer: str
    artist: str
    id: Optional[int] = None

class ComicService:
    def __init__(self, csv_file: str = "Comics.csv", json_file: str = "comics_data.json"):
        self.csv_file = csv_file
        self.json_file = json_file
        self.comics = []
        self.next_id = 1
        self.load_data()
    
    def load_data(self):
        """Load comics from CSV file and JSON storage"""
        # Load from CSV if exists
        if os.path.exists(self.csv_file):
            try:
                df = pd.read_csv(self.csv_file)
                for index, row in df.iterrows():
                    comic = Comic(
                        id=index + 1,
                        title=str(row['Title']),
                        volume=str(row['Volume']),
                        writer=str(row['Writer']),
                        artist=str(row['Artist'])
                    )
                    self.comics.append(comic)
                self.next_id = len(self.comics) + 1
            except Exception as e:
                print(f"Error loading CSV file: {e}")
        
        # Load from JSON if exists (for new additions)
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r') as f:
                    data = json.load(f)
                    for comic_data in data:
                        comic = Comic(**comic_data)
                        if comic.id >= self.next_id:
                            self.next_id = comic.id + 1
                        # Only add if not already loaded from CSV
                        if not any(c.id == comic.id for c in self.comics):
                            self.comics.append(comic)
            except Exception as e:
                print(f"Error loading JSON file: {e}")
    
    def save_to_json(self):
        """Save all comics to JSON file"""
        try:
            with open(self.json_file, 'w') as f:
                json.dump([asdict(comic) for comic in self.comics], f, indent=2)
        except Exception as e:
            print(f"Error saving to JSON: {e}")
    
    def save_to_csv(self):
        """Save all comics to CSV file"""
        try:
            df = pd.DataFrame([{
                'Title': comic.title,
                'Volume': comic.volume,
                'Writer': comic.writer,
                'Artist': comic.artist
            } for comic in self.comics])
            df.to_csv(self.csv_file, index=False)
        except Exception as e:
            print(f"Error saving to CSV: {e}")
    
    def check_duplicate(self, title: str, volume: str, exclude_id: int = None) -> bool:
        """Check if a comic with the same title and volume already exists"""
        for comic in self.comics:
            if (exclude_id is None or comic.id != exclude_id) and \
               comic.title.lower() == title.lower() and \
               comic.volume.lower() == volume.lower():
                return True
        return False
    
    def add_comic(self, title: str, volume: str, writer: str, artist: str) -> Comic:
        """Add a new comic"""
        # Check for duplicates
        if self.check_duplicate(title, volume):
            raise ValueError(f"A comic with title '{title}' and volume '{volume}' already exists!")
        
        comic = Comic(
            id=self.next_id,
            title=title,
            volume=volume,
            writer=writer,
            artist=artist
        )
        self.comics.append(comic)
        self.next_id += 1
        self.save_to_json()
        self.save_to_csv()  # Auto-export to CSV
        return comic
    
    def add_multiple_comics(self, comics_data: List[Dict[str, str]]) -> List[Comic]:
        """Add multiple comics at once"""
        added_comics = []
        duplicates = []
        valid_comics = []
        
        # First, validate all comics and check for duplicates
        for comic_data in comics_data:
            if all(key in comic_data and comic_data[key].strip() for key in ['title', 'volume', 'writer', 'artist']):
                title = comic_data['title'].strip()
                volume = comic_data['volume'].strip()
                
                # Check for duplicates
                if self.check_duplicate(title, volume):
                    duplicates.append(f"{title} (Volume {volume})")
                else:
                    valid_comics.append({
                        'title': title,
                        'volume': volume,
                        'writer': comic_data['writer'].strip(),
                        'artist': comic_data['artist'].strip()
                    })
        
        # If there are duplicates, raise error before adding any comics
        if duplicates:
            raise ValueError(f"Duplicate comics found: {', '.join(duplicates)}")
        
        # Add all valid comics
        for comic_data in valid_comics:
            comic = Comic(
                id=self.next_id,
                title=comic_data['title'],
                volume=comic_data['volume'],
                writer=comic_data['writer'],
                artist=comic_data['artist']
            )
            self.comics.append(comic)
            added_comics.append(comic)
            self.next_id += 1
        
        if added_comics:
            self.save_to_json()
            self.save_to_csv()  # Auto-export to CSV
        
        return added_comics
    
    def get_all_comics(self) -> List[Comic]:
        """Get all comics"""
        return self.comics.copy()
    
    def get_comic_by_id(self, comic_id: int) -> Optional[Comic]:
        """Get a comic by ID"""
        for comic in self.comics:
            if comic.id == comic_id:
                return comic
        return None
    
    def update_comic(self, comic_id: int, title: str = None, volume: str = None, 
                    writer: str = None, artist: str = None) -> Optional[Comic]:
        """Update a comic"""
        comic = self.get_comic_by_id(comic_id)
        if comic:
            # Check for duplicates if title or volume is being changed
            new_title = title if title is not None else comic.title
            new_volume = volume if volume is not None else comic.volume
            
            if (title is not None or volume is not None) and \
               self.check_duplicate(new_title, new_volume, exclude_id=comic_id):
                raise ValueError(f"A comic with title '{new_title}' and volume '{new_volume}' already exists!")
            
            if title is not None:
                comic.title = title
            if volume is not None:
                comic.volume = volume
            if writer is not None:
                comic.writer = writer
            if artist is not None:
                comic.artist = artist
            self.save_to_json()
            self.save_to_csv()  # Auto-export to CSV
            return comic
        return None
    
    def delete_comic(self, comic_id: int) -> bool:
        """Delete a comic"""
        for i, comic in enumerate(self.comics):
            if comic.id == comic_id:
                del self.comics[i]
                self.save_to_json()
                self.save_to_csv()  # Auto-export to CSV
                return True
        return False
    
    def search_comics(self, query: str) -> List[Comic]:
        """Search comics by title, writer, or artist"""
        query = query.lower()
        results = []
        for comic in self.comics:
            if (query in comic.title.lower() or 
                query in comic.writer.lower() or 
                query in comic.artist.lower()):
                results.append(comic)
        return results
    
    def export_to_csv(self, filename: str = None):
        """Export all comics to CSV file"""
        if filename is None:
            filename = self.csv_file
        self.save_to_csv()
        return filename