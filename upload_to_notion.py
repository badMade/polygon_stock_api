# Notion Upload Script
# Database: https://www.notion.so/638a8018f09d4e159d6d84536f411441
# Data Source: collection://7c5225aa-429b-4580-946e-ba5b1db2ca6d

import json

# Process each batch file
for batch_num in range(1, 2):
    filename = f'/mnt/user-data/outputs/notion_batch_{batch_num:04d}.json'
    
    with open(filename, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
        
    print(f"Uploading batch {batch_num}: {len(batch_data['pages'])} pages")
    
    # Use Notion API to create pages
    # notion.create_pages(
    #     parent={"data_source_id": "7c5225aa-429b-4580-946e-ba5b1db2ca6d"},
    #     pages=batch_data['pages']
    # )
