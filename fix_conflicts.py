import re

with open('d:/code/smart_search_project/search_engine/search_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Handle TAG MAPPING section conflict (keep HEAD - no semantic mapping rules)
old_tag_mapping = (
    '\t1. **Precision Guidelines**:\n'
    '=======\n'
    '\t1. **Semantic Mapping Rules**:\n'
    '\t   - "starving/hungry/nutrient deprivation" → ["Metabolism", "Nutrient Sensing", "Stress Response"]\n'
    '\t   - "light/blue light/optogenetics" → ["Optogenetics", "Light Sensing", "Signal Transduction"]\n'
    '\t   - "cancer/tumor/oncology" → ["Cancer", "Oncology", "Therapeutics"]\n'
    '\t   - "gene editing/CRISPR/genome engineering" → ["CRISPR", "Genome Editing", "Genetic Engineering"]\n'
    '\t   - "fluorescent/GFP/RFP/imaging" → ["Fluorescent Proteins", "Imaging", "Reporters"]\n'
    '\t   - "cell death/apoptosis/necrosis" → ["Apoptosis", "Cell Death", "Cell Biology"]\n'
    '\t   - "infection/virus/bacterial" → ["Infection", "Virology", "Microbiology"]\n'
    '\t   - "development/differentiation/growth" → ["Development", "Differentiation", "Cell Growth"]\n'
    '\n'
    '\t2. **Precision Guidelines**:\n'
    '>>>>>>> b26fe0879d6c3d08b887fc72ef509b810749cf8a'
)

# Check if this pattern exists
if old_tag_mapping in content:
    print("Found TAG MAPPING conflict")
    new_tag_mapping = '\t1. **Precision Guidelines**:'
    content = content.replace(old_tag_mapping, new_tag_mapping)
else:
    print("TAG MAPPING conflict NOT found - checking what's there")
    # Find the conflict area
    idx = content.find('<<<<<<< HEAD')
    if idx >= 0:
        print(f"First conflict found at position {idx}")
        print(repr(content[idx:idx+200]))

# 2. Handle Chinese Query Support numbering conflict
old_numbering = (
    '<<<<<<< HEAD\n'
    '\t2. **Chinese Query Support**:\n'
    '=======\n'
    '\t3. **Chinese Query Support**:\n'
    '>>>>>>> b26fe0879d6c3d08b887fc72ef509b810749cf8a'
)
if old_numbering in content:
    print("Found numbering conflict")
    content = content.replace(old_numbering, '\t2. **Chinese Query Support**:')
else:
    print("Numbering conflict NOT found")

# 3. Handle all blank-line conflicts (HEAD empty, Other has blank lines)
# These follow the pattern:
# <<<<<<< HEAD
# =======
# (blank lines)
# >>>>>>> b26fe0879d6c3d08b887fc72ef509b810749cf8a
count = 0
while True:
    idx = content.find('<<<<<<< HEAD\n=======\n')
    if idx < 0:
        break
    end_idx = content.find('>>>>>>> b26fe0879d6c3d08b887fc72ef509b810749cf8a', idx)
    if end_idx < 0:
        break

    # Extract what's between the markers
    between = content[idx + len('<<<<<<< HEAD\n=======\n'):end_idx]
    # Replace with just the content (the blank lines)
    replacement = between
    content = content[:idx] + replacement + content[end_idx + len('>>>>>>> b26fe0879d6c3d08b887fc72ef509b810749cf8a'):]
    count += 1

print(f"Resolved {count} blank-line conflicts")

with open('d:/code/smart_search_project/search_engine/search_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
