def scan_project_structure(start_path):
    """Scan and print the entire project structure"""
    import os
    
    print(f"\nProject Structure from {start_path}:")
    print("=" * 50)
    
    for root, dirs, files in os.walk(start_path):
        level = root.replace(start_path, '').count(os.sep)
        indent = '  ' * level
        print(f"{indent}{os.path.basename(root)}/")
        sub_indent = '  ' * (level + 1)
        for f in files:
            if not f.startswith('.'):  # Skip hidden files
                print(f"{sub_indent}{f}")

# Save this as scan_structure.py and run it
if __name__ == "__main__":
    nova_path = "C:/AI/Nova"  # Adjust if your path is different
    scan_project_structure(nova_path)