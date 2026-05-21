import csv, ast
from collections import defaultdict

SCORE_IF_VALID = 1
SCORE_IF_POSSIBLY_VALID = 0
GROUP = "top"
QUANTITY = "10000"
if QUANTITY=="1000":
    categories = ["arts and recreation", "biography", "food and agriculture", "geography", "history", "language and literature", "measurements", "philosophy", "religion", "science", "social sciences", "technology"]
else:
    categories = ["anthropology, psychology and everyday life", "arts", "biology", "geography", "history", "language and literature", "mathematics", "people", "philosophy", "physics", "religion", "society and social sciences", "technology"]


def overall_validity():
    with open(f"results/{GROUP}-{QUANTITY}/validity of all categories.csv", "w", newline='', encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["Category", "Valid", "Valid because there was no expected domain or range", "Valid range but no expected domain", \
                         "Valid domain but no expected range", "Completely valid", "Possibly Valid", "Possibly Valid (No expected domain, no actual range to check against)", \
                        "Possibly Valid (No actual domain to check against, no expected range)", "Possibly Valid (No actual domain to check against, range matches)", \
                        "Possibly Valid (Domain matches, no actual range to check against)", "Possibly Valid (No actual domain to check against, no actual range to check against)", \
                        "Invalid", "Invalid (No expected domain, range does not match)", "Invalid (Domain does not match, no expected range)", "Invalid (Domain does not match, range matches)", \
                        "Invalid (Domain matches, range does not match)", "Invalid (No actual domain to check against, range does not match)", "Invalid (Domain does not match, no actual range to check against)", \
                        "Invalid (Domain does not match, range does not match)"])

        # Define mappings from validity string to counter key
        VALIDITY_KEYS = {
            # Valid
            "Valid (no expected domain, no expected range)": ("valid", "ss"),
            "Valid (No expected domain, range matches)": ("valid", "sp"),
            "Valid (Domain matches, no expected range)": ("valid", "ps"),
            # Completely valid (fallthrough)
            # Possibly Valid
            "Possibly Valid (No expected domain, no actual range to check against)": ("possibly_valid", "su"),
            "Possibly Valid (No actual domain to check against, no expected range)": ("possibly_valid", "us"),
            "Possibly Valid (No actual domain to check against, range matches)": ("possibly_valid", "up"),
            "Possibly Valid (Domain matches, no actual range to check against)": ("possibly_valid", "pu"),
            "Possibly Valid (No actual domain to check against, no actual range to check against)": ("possibly_valid", "uu"),
            # Invalid
            "Invalid (No expected domain, range does not match)": ("invalid", "sf"),
            "Invalid (Domain does not match, no expected range)": ("invalid", "fs"),
            "Invalid (Domain does not match, range matches)": ("invalid", "fp"),
            "Invalid (Domain matches, range does not match)": ("invalid", "pf"),
            "Invalid (No actual domain to check against, range does not match)": ("invalid", "uf"),
            "Invalid (Domain does not match, no actual range to check against)": ("invalid", "fu"),
            "Invalid (Domain does not match, range does not match)": ("invalid", "ff"),
        }

        for category in categories:
            counts = defaultdict(int)
            print(f"Processing category: {category}")

            with open(f"output/validations/{GROUP}-{QUANTITY}/{category}-validations.csv", newline='', encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    validity = row[3]
                    if validity in VALIDITY_KEYS:
                        group, key = VALIDITY_KEYS[validity]
                    elif validity.startswith("Valid"):
                        group, key = "valid", "pp"  # Completely valid fallthrough
                    else:
                        continue  # Unexpected value — skip or log
                    counts[group] += 1
                    counts[key] += 1

            writer.writerow([
                category,
                counts["valid"],  counts["ss"], counts["sp"], counts["ps"], counts["pp"],
                counts["possibly_valid"], counts["su"], counts["us"], counts["up"], counts["pu"], counts["uu"],
                counts["invalid"], counts["sf"], counts["fs"], counts["fp"], counts["pf"], counts["uf"], counts["fu"], counts["ff"],
            ])
        
  
def fine_grained_validity():
    with open(f"results/{GROUP}-{QUANTITY}/validity of all entities.csv", "w", newline='', encoding="utf-8") as g:
        writer = csv.writer(g)
        writer.writerow(["Entity", "Overall validity %", "Number of triples", "Subject validity %", "Number of instances as a subject",
                        "Object validity %", "Number of instances as a subject"])

        for category in categories:
            with open(f"output/pages/{GROUP}-{QUANTITY}/{category}.txt", encoding="utf-8") as entities_file:
                entities = [line.strip() for line in entities_file.readlines()]

            with open(f"output/validations/{GROUP}-{QUANTITY}/{category}-validations.csv", newline='', encoding="utf-8") as f:  
                reader = csv.reader(f)
                rows = list(reader)
            
                for entity in entities:
                    print(f"Processing entity: {entity}")
                    sub_valid_count = 0
                    obj_valid_count = 0
                    sub_count = 0
                    obj_count = 0
                    count = 0
                    for row in rows:
                        sub = row[0]
                        if sub.__contains__("__"):
                            sub = sub.split("__")[0]
                        obj = row[2]
                        if obj.__contains__("__"):
                            obj = obj.split("__")[0]
                        validity = row[3]
                        if sub == entity:
                            sub_count += 1
                            count += 1
                            if validity.startswith("Valid"):
                                sub_valid_count += SCORE_IF_VALID
                            elif validity.startswith("Possibly valid"):
                                sub_valid_count += SCORE_IF_POSSIBLY_VALID
                        elif obj == entity:
                            obj_count += 1
                            count += 1
                            if validity.startswith("Valid"):
                                obj_valid_count += SCORE_IF_VALID
                            elif validity.startswith("Possibly valid"):
                                obj_valid_count += SCORE_IF_POSSIBLY_VALID            
                    writer.writerow([entity,
                                    round((100*(sub_valid_count + obj_valid_count)) / count) if count > 0 else 0,
                                    count,
                                    round((100*sub_valid_count) / sub_count) if sub_count > 0 else 0,
                                    sub_count,
                                    round((100*obj_valid_count) / obj_count) if obj_count > 0 else 0,
                                    obj_count])

def invalid_entity_types():
    counts = defaultdict(lambda: defaultdict(int))
    for category in categories:
        with open(f"output/validations/{GROUP}-{QUANTITY}/{category}-validations.csv",
                  newline='', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[3].startswith("Invalid"):
                    invalidities = ast.literal_eval(row[4])

                    # first pair
                    if invalidities[0] and invalidities[1] and invalidities[0] not in invalidities[1]:
                        expected = invalidities[0]
                        actual = str(invalidities[1])
                        counts[(expected, actual)][category] += 1

                    # second pair
                    if invalidities[2] and invalidities[3] and invalidities[2] not in invalidities[3]:
                        expected = invalidities[2]
                        actual = str(invalidities[3])
                        counts[(expected, actual)][category] += 1

    with open(f"results/{GROUP}-{QUANTITY}/invalid-types-pairs.csv",
              "w", newline='', encoding="utf-8") as g:
        writer = csv.writer(g)

        # header row
        writer.writerow(["Expected", "Actual"] + categories)

        # write rows
        for (expected, actual) in sorted(counts.keys()):
            row = [expected, actual]
            for category in categories:
                row.append(counts[(expected, actual)][category])
            writer.writerow(row)

def invalid_properties():
    counts = defaultdict(lambda: defaultdict(int))
    for category in categories:
        with open(f"output/validations/{GROUP}-{QUANTITY}/{category}-validations.csv",
                  newline='', encoding="utf-8") as f:
            reader = csv.reader(f)

            for row in reader:
                if row[3].startswith("Invalid"):
                    prop = row[1]
                    counts[prop][category] += 1

    with open(f"results/{GROUP}-{QUANTITY}/invalid-properties.csv",
              "w", newline='', encoding="utf-8") as g:
        writer = csv.writer(g)

        # header row: Property + each category as a column
        writer.writerow(["Property"] + categories)

        # write each property row
        for prop in sorted(counts.keys()):
            row = [prop]
            for category in categories:
                row.append(counts[prop][category])
            writer.writerow(row)

def all_properties():
    data = {}  # property -> {category: count}
    # Count occurrences
    for category in categories:
        with open(f"output/validations/{GROUP}-{QUANTITY}/{category}-validations.csv",
                  newline='', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                prop = row[1]
                if prop not in data:
                    data[prop] = {c: 0 for c in categories}
                data[prop][category] += 1

    # Write pivot table
    with open(f"results/{GROUP}-{QUANTITY}/all-properties.csv",
              "w", newline='', encoding="utf-8") as g:
        writer = csv.writer(g)
        # Header row
        writer.writerow(["Property"] + categories)
        # Rows: property + counts per category
        for prop in sorted(data.keys()):
            writer.writerow([prop] + [data[prop][category] for category in categories])

def main():
    overall_validity()

    all_properties()

    invalid_entity_types()
    invalid_properties()

    fine_grained_validity()



if __name__ == "__main__":
    main()