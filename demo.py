#!/usr/bin/env python3
"""
Demo script to showcase the Comic Collection Manager functionality
"""

from comic_service import ComicService

def main():
    print("=== Comic Collection Manager Demo ===\n")
    
    # Initialize service
    service = ComicService()
    
    print(f"📚 Loaded {len(service.comics)} comics from existing collection")
    
    # Show first few comics
    print("\n🔍 First 5 comics in collection:")
    for i, comic in enumerate(service.comics[:5]):
        print(f"  {i+1}. {comic.title} Vol.{comic.volume} by {comic.writer}")
    
    # Add a new comic
    print("\n➕ Adding a new comic...")
    new_comic = service.add_comic(
        title="Demo Comic",
        volume="1",
        writer="Demo Writer",
        artist="Demo Artist"
    )
    print(f"   Added: {new_comic.title} (ID: {new_comic.id})")
    
    # Test bulk add functionality
    print("\n📚 Testing bulk add functionality...")
    bulk_comics = [
        {'title': 'Bulk Comic 1', 'volume': '1', 'writer': 'Bulk Writer 1', 'artist': 'Bulk Artist 1'},
        {'title': 'Bulk Comic 2', 'volume': '2', 'writer': 'Bulk Writer 2', 'artist': 'Bulk Artist 2'},
        {'title': 'Bulk Comic 3', 'volume': '1', 'writer': 'Bulk Writer 3', 'artist': 'Bulk Artist 3'}
    ]
    
    added_bulk = service.add_multiple_comics(bulk_comics)
    print(f"   Added {len(added_bulk)} comics in bulk operation")
    for comic in added_bulk:
        print(f"     - {comic.title} (ID: {comic.id})")
    
    # Search functionality
    print("\n🔎 Searching for comics with 'Century' in title...")
    search_results = service.search_comics("Century")
    for comic in search_results[:3]:  # Show first 3 results
        print(f"   Found: {comic.title} by {comic.writer}")
    
    # Update the demo comic
    print(f"\n✏️  Updating demo comic (ID: {new_comic.id})...")
    updated = service.update_comic(
        new_comic.id,
        title="Updated Demo Comic",
        writer="Updated Writer"
    )
    if updated:
        print(f"   Updated: {updated.title} by {updated.writer}")
    
    # Show total count
    print(f"\n📊 Total comics in collection: {len(service.comics)}")
    
    # Clean up - remove the demo comics
    print(f"\n🗑️  Cleaning up demo comics...")
    cleanup_count = 0
    if service.delete_comic(new_comic.id):
        cleanup_count += 1
    
    for comic in added_bulk:
        if service.delete_comic(comic.id):
            cleanup_count += 1
    
    print(f"   Removed {cleanup_count} demo comics successfully")
    
    print(f"\n✅ Demo completed! Final count: {len(service.comics)} comics")
    print("\n🌐 To use the web interface, run: python3 app.py")
    print("   Then open http://localhost:5001 in your browser")

if __name__ == "__main__":
    main()