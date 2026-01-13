
import sys
import os

# Add current dir to path to import utils
sys.path.append(os.getcwd())

from utils.pdf_extractor import extract_text_from_pdf

pdf_path = r"d:\Elysium\Study\大物实验\大物实验报告\光电探测\实验指导书.pdf"

if not os.path.exists(pdf_path):
    print(f"File not found: {pdf_path}")
    sys.exit(1)

print(f"Testing extraction from: {pdf_path}")
text = extract_text_from_pdf(pdf_path)

if text:
    print("Success! Extracted length:", len(text))
    print("Preview:")
    print(text[:500])
else:
    print("Failed to extract text.")
