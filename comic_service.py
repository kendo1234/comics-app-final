import pandas as pd
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import json
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None

    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        pass

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
        self.storage_backend = os.getenv("COMICS_STORAGE_BACKEND", "file").strip().lower()
        self.dynamodb_table_name = os.getenv("DYNAMODB_TABLE_NAME", "comics")
        self.dynamodb_region = os.getenv("AWS_REGION", "us-east-1")
        self.dynamodb_table = None
        self.comics = []
        self.next_id = 1
        self._configure_storage_backend()
        self.load_data()

    def _configure_storage_backend(self):
        """Configure storage backend based on environment."""
        if self.storage_backend != "dynamodb":
            self.storage_backend = "file"
            return

        if boto3 is None:
            print("boto3 not installed, falling back to file storage")
            self.storage_backend = "file"
            return

        try:
            resource = boto3.resource("dynamodb", region_name=self.dynamodb_region)
            self.dynamodb_table = resource.Table(self.dynamodb_table_name)
            # Lightweight call to verify the table is reachable/configured.
            self.dynamodb_table.load()
        except (BotoCoreError, ClientError) as e:
            print(f"Error configuring DynamoDB, falling back to file storage: {e}")
            self.storage_backend = "file"
            self.dynamodb_table = None
    
    def load_data(self):
        """Load comics from CSV file and JSON storage"""
        if self.storage_backend == "dynamodb":
            self._load_data_from_dynamodb()
            return

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

    def _load_data_from_dynamodb(self):
        """Load comics from DynamoDB table."""
        self.comics = []
        self.next_id = 1

        if not self.dynamodb_table:
            return

        try:
            response = self.dynamodb_table.scan()
            items = response.get("Items", [])
            while "LastEvaluatedKey" in response:
                response = self.dynamodb_table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items.extend(response.get("Items", []))

            for item in items:
                comic = Comic(
                    id=int(item["id"]),
                    title=str(item["title"]),
                    volume=str(item["volume"]),
                    writer=str(item["writer"]),
                    artist=str(item["artist"]),
                )
                self.comics.append(comic)

            self.comics.sort(key=lambda c: c.id or 0)
            if self.comics:
                self.next_id = max(c.id or 0 for c in self.comics) + 1
        except (BotoCoreError, ClientError) as e:
            print(f"Error loading DynamoDB data: {e}")
    
    def save_to_json(self):
        """Save all comics to JSON file"""
        if self.storage_backend == "dynamodb":
            return
        try:
            with open(self.json_file, 'w') as f:
                json.dump([asdict(comic) for comic in self.comics], f, indent=2)
        except Exception as e:
            print(f"Error saving to JSON: {e}")
    
    def save_to_csv(self):
        """Save all comics to CSV file"""
        if self.storage_backend == "dynamodb":
            return
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

    def _save_comic_to_dynamodb(self, comic: Comic):
        if self.storage_backend != "dynamodb" or not self.dynamodb_table:
            return

        try:
            self.dynamodb_table.put_item(
                Item={
                    "id": comic.id,
                    "title": comic.title,
                    "volume": comic.volume,
                    "writer": comic.writer,
                    "artist": comic.artist,
                }
            )
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Failed to save comic to DynamoDB: {e}") from e

    def _delete_comic_from_dynamodb(self, comic_id: int):
        if self.storage_backend != "dynamodb" or not self.dynamodb_table:
            return

        try:
            self.dynamodb_table.delete_item(Key={"id": comic_id})
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Failed to delete comic from DynamoDB: {e}") from e
    
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
        if self.storage_backend == "dynamodb":
            self._save_comic_to_dynamodb(comic)
        else:
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
            if self.storage_backend == "dynamodb":
                for comic in added_comics:
                    self._save_comic_to_dynamodb(comic)
            else:
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
            if self.storage_backend == "dynamodb":
                self._save_comic_to_dynamodb(comic)
            else:
                self.save_to_json()
                self.save_to_csv()  # Auto-export to CSV
            return comic
        return None
    
    def delete_comic(self, comic_id: int) -> bool:
        """Delete a comic"""
        for i, comic in enumerate(self.comics):
            if comic.id == comic_id:
                del self.comics[i]
                if self.storage_backend == "dynamodb":
                    self._delete_comic_from_dynamodb(comic_id)
                else:
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
        if self.storage_backend == "dynamodb":
            raise RuntimeError("CSV export is unavailable when using DynamoDB backend")
        if filename is None:
            filename = self.csv_file
        self.save_to_csv()
        return filename
