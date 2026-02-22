from tinydb import TinyDB, Query
#from tinydb.table import Document
from typing import List, Dict, Optional, Union, Any

class CorpusManager:
    """
    A generic class to manage interactions with a TinyDB database for corpus elements.
    """

    def __init__(self, db_path: str = 'corpus.json'):
        """
        Initialize the Corpus manager with the path to the database file.

        Args:
            db_path (str): Path to the TinyDB JSON file
        """
        self.db = TinyDB(db_path)
        self.items = self.db.table('items')
        self.collections = self.db.table('collections')
        self.Item = Query()

    def close(self):
        """Close the database connection."""
        self.db.close()

    def add_item(self, item_type: str, name: str, content: str,
                metadata: Dict[str, Any] = None) -> int:
        """
        Add a new item to the corpus.

        Args:
            item_type (str): Type/category of the item
            name (str): Name/title of the item
            content (str): Main content of the item
            metadata (Dict[str, Any]): Additional metadata about the item

        Returns:
            int: The doc_id of the inserted item
        """
        if metadata is None:
            metadata = {}

        item_data = {
            'type': item_type,
            'name': name,
            'content': content,
            'metadata': metadata
        }

        return self.items.insert(item_data)

    def get_item(self, item_id: int) -> Optional[Dict]:
        """
        Retrieve an item by its ID.

        Args:
            item_id (int): The ID of the item to retrieve

        Returns:
            Optional[Dict]: The item data if found, None otherwise
        """
        result = self.items.get(doc_id=item_id)
        return result if result else None

    def get_items_by_type(self, item_type: str) -> List[Dict]:
        """
        Retrieve all items of a specific type.

        Args:
            item_type (str): Type of items to retrieve

        Returns:
            List[Dict]: List of matching items
        """
        return self.items.search(self.Item.type == item_type)

    def get_items_by_metadata(self, key: str, value: Any) -> List[Dict]:
        """
        Retrieve all items that have specific metadata.

        Args:
            key (str): Metadata key to search for
            value (Any): Metadata value to match

        Returns:
            List[Dict]: List of matching items
        """
        return self.items.search(self.Item.metadata[key] == value)

    def update_item(self, item_id: int, name: str = None, content: str = None,
                   metadata: Dict[str, Any] = None) -> bool:
        """
        Update an existing item.

        Args:
            item_id (int): The ID of the item to update
            name (str): New name (optional)
            content (str): New content (optional)
            metadata (Dict[str, Any]): New metadata (optional)

        Returns:
            bool: True if update was successful, False otherwise
        """
        updates = {}
        if name is not None:
            updates['name'] = name
        if content is not None:
            updates['content'] = content
        if metadata is not None:
            updates['metadata'] = metadata

        if updates:
            self.items.update(updates, doc_ids=[item_id])
            return True
        return False

    def delete_item(self, item_id: int) -> bool:
        """
        Delete an item from the corpus.

        Args:
            item_id (int): The ID of the item to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        return self.items.remove(doc_ids=[item_id]) == [item_id]

    def add_collection(self, name: str, description: str = "",
                      item_ids: List[int] = None) -> int:
        """
        Add a new collection to the corpus.

        Args:
            name (str): Name of the collection
            description (str): Description of the collection
            item_ids (List[int]): List of item IDs in the collection

        Returns:
            int: The doc_id of the inserted collection
        """
        if item_ids is None:
            item_ids = []

        collection_data = {
            'name': name,
            'description': description,
            'items': item_ids
        }

        return self.collections.insert(collection_data)

    def get_collection(self, collection_id: int) -> Optional[Dict]:
        """
        Retrieve a collection by its ID.

        Args:
            collection_id (int): The ID of the collection to retrieve

        Returns:
            Optional[Dict]: The collection data if found, None otherwise
        """
        result = self.collections.get(doc_id=collection_id)
        return result if result else None

    def get_collections_by_item(self, item_id: int) -> List[Dict]:
        """
        Retrieve all collections that contain a specific item.

        Args:
            item_id (int): The ID of the item to search for

        Returns:
            List[Dict]: List of matching collections
        """
        return self.collections.search(self.Item.items.any([item_id]))

    def update_collection(self, collection_id: int, name: str = None,
                         description: str = None,
                         item_ids: List[int] = None) -> bool:
        """
        Update an existing collection.

        Args:
            collection_id (int): The ID of the collection to update
            name (str): New name (optional)
            description (str): New description (optional)
            item_ids (List[int]): New list of item IDs (optional)

        Returns:
            bool: True if update was successful, False otherwise
        """
        updates = {}
        if name is not None:
            updates['name'] = name
        if description is not None:
            updates['description'] = description
        if item_ids is not None:
            updates['items'] = item_ids

        if updates:
            self.collections.update(updates, doc_ids=[collection_id])
            return True
        return False

    def delete_collection(self, collection_id: int) -> bool:
        """
        Delete a collection from the corpus.

        Args:
            collection_id (int): The ID of the collection to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        return self.collections.remove(doc_ids=[collection_id]) == [collection_id]

    def search_items(self, query: str, fields: List[str] = None) -> List[Dict]:
        """
        Search for items by content in specified fields.

        Args:
            query (str): Search term
            fields (List[str]): Fields to search in (default: ['name', 'content'])

        Returns:
            List[Dict]: List of matching items
        """
        if fields is None:
            fields = ['name', 'content']

        search_query = None
        for field in fields:
            if field == 'metadata':
                # Special handling for metadata which is a dict
                continue
            field_query = self.Item[field].search(query, flags='i')
            search_query = field_query if search_query is None else (search_query | field_query)

        return self.items.search(search_query) if search_query else []

    def get_all_items(self) -> List[Dict]:
        """
        Retrieve all items from the corpus.

        Returns:
            List[Dict]: List of all items
        """
        return self.items.all()

    def get_all_collections(self) -> List[Dict]:
        """
        Retrieve all collections from the corpus.

        Returns:
            List[Dict]: List of all collections
        """
        return self.collections.all()
