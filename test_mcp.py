from mcp_server import add_ugc, list_ugc, delete_ugc

def test_ugc_tools():
    print("Testing UGC MCP Server tools...\n")

    # Test add_ugc
    print("1. Adding UGC...")
    result1 = add_ugc(title="My First Video", content="https://example.com/video1.mp4", author="UserA")
    print(f"Result: {result1}")

    result2 = add_ugc(title="Awesome Review", content="This product is great!", author="UserB")
    print(f"Result: {result2}\n")

    # Test list_ugc
    print("2. Listing UGC...")
    ugc_list = list_ugc()
    print(f"Current UGC items ({len(ugc_list)} total):")
    for item in ugc_list:
        print(f"  - [{item['id']}] {item['title']} by {item['author']}")
    print()

    # Test delete_ugc
    print("3. Deleting UGC (ugc_1)...")
    delete_result = delete_ugc("ugc_1")
    print(f"Result: {delete_result}\n")

    # Test list_ugc again
    print("4. Listing UGC after deletion...")
    ugc_list_after = list_ugc()
    print(f"Current UGC items ({len(ugc_list_after)} total):")
    for item in ugc_list_after:
        print(f"  - [{item['id']}] {item['title']} by {item['author']}")

    print("\nTest completed successfully!")

if __name__ == "__main__":
    test_ugc_tools()
