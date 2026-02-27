import re

def sonnet_generator(filepath):
    """
    Generates sonnets from a text file where each sonnet is marked by a Roman numeral
    followed by text enclosed in spaces.

    Args:
        filepath (str): The path to the text file.

    Yields:
        tuple: A tuple containing the Roman numeral identifier (e.g., "I") and the 
               text of the sonnet.  Yields nothing if the file is empty or 
               doesn't conform to the expected format.
    """

    try:
        with open(filepath, 'r', encoding='utf-8') as f:  # Handle potential encoding issues
            text = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Regular expression to find Roman numeral followed by text in spaces
    # This regex is more robust to handle variations in spacing.
    pattern = r"([IVXLCDM]+)\s+(.+?)\s+([IVXLCDM]+|$)"  # Match Roman numeral, text, and next Roman numeral or end of string
    matches = re.findall(pattern, text, re.DOTALL)  # re.DOTALL allows . to match newline characters

    if not matches:
        print("No sonnets found in the specified format.")
        return

    for match in matches:
        sonnet_id = match[0]
        sonnet_text = match[1].strip()  # Remove leading/trailing whitespace
        yield sonnet_id, sonnet_text


if __name__ == '__main__':
    # Example Usage:

    # Create a dummy text file for testing
    with open("sonnets.txt", "w", encoding="utf-8") as f:
        f.write("I This is the first sonnet.\nIt has multiple lines.\nAnd some more text.\n\n")
        f.write("II Another sonnet here.\nWith different content.\nThis one is shorter.\n\n")
        f.write("III A third sonnet, just for fun.\nMore lines to demonstrate.\nAnd even more.\n\n")
        f.write("IV The final sonnet in this example.\nThis shows how the generator works.\n")

    # Use the generator
    sonnet_gen = sonnet_generator("sonnets.txt")

    try:
        while True:
            sonnet_id, sonnet_text = next(sonnet_gen)
            print(f"Sonnet: {sonnet_id}")
            print("-" * 20)
            print(sonnet_text)
            print("\n")
    except StopIteration:
        print("No more sonnets.")
