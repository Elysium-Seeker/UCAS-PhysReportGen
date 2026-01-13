
from werkzeug.utils import secure_filename

name = "实验指导书.pdf"
secured = secure_filename(name)
print(f"Original: {name}")
print(f"Secured: '{secured}'")
