import os
import os.path

# Set a dedicated folder for file I/O



def read_file(filename):
    try:
        filepath = filename
        with open(filepath, "r") as f:
            content = f.read()
        return content
    except Exception as e:
        return "Error: " + str(e)


def write_to_file(filename, text):
    try:
        filepath = filename
        directory = os.path.dirname(filepath)
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        with open(filepath, "a") as f:
            f.write(text)
        return "File written successfully."
    except Exception as e:
        return "Error: " + str(e)

def delete_file(filename):
    try:
        filepath =filename
        os.remove(filepath)
        return "File deleted successfully."
    except Exception as e:
        return "Error: " + str(e)

def list_files(directory):
    found_files = []

    if directory == "" or directory == "/":
        search_directory = os.getcwd()
    else:
        search_directory = directory

    for root, _, files in os.walk(search_directory):
        for file in files:
            if file.startswith('.'):
                continue
            relative_path = os.path.relpath(os.path.join(root, file), os.getcwd())
            found_files.append(relative_path)

    return found_files