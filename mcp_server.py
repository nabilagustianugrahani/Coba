from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any

# Initialize FastMCP server
mcp = FastMCP("UGC_Server")

# In-memory storage for UGC
ugc_database: Dict[str, Dict[str, Any]] = {}
ugc_counter = 1

@mcp.tool()
def add_ugc(title: str, content: str, author: str) -> str:
    """
    Add a new piece of User Generated Content.

    Args:
        title: The title of the content.
        content: The actual content.
        author: The author of the content.

    Returns:
        A success message with the UGC ID.
    """
    global ugc_counter
    ugc_id = f"ugc_{ugc_counter}"
    ugc_counter += 1

    ugc_database[ugc_id] = {
        "title": title,
        "content": content,
        "author": author,
        "id": ugc_id
    }
    return f"Successfully added UGC with ID: {ugc_id}"

@mcp.tool()
def list_ugc() -> List[Dict[str, Any]]:
    """
    List all available User Generated Content.

    Returns:
        A list of all UGC items.
    """
    return list(ugc_database.values())

@mcp.tool()
def delete_ugc(ugc_id: str) -> str:
    """
    Delete a specific piece of User Generated Content by its ID.

    Args:
        ugc_id: The ID of the UGC to delete (e.g., 'ugc_1').

    Returns:
        A message indicating success or failure.
    """
    if ugc_id in ugc_database:
        del ugc_database[ugc_id]
        return f"Successfully deleted UGC with ID: {ugc_id}"
    return f"Error: UGC with ID {ugc_id} not found."

if __name__ == "__main__":
    mcp.run()
