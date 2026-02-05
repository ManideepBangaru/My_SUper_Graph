# Read a yaml file and return the content by providing the file path from different directories
from pathlib import Path
import yaml

def read_yaml(file_path):
    file_path = Path(__file__).parent.parent / file_path
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)