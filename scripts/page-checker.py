# Import necessary libraries
from SPARQLWrapper import SPARQLWrapper, JSON
from SPARQLWrapper.SPARQLExceptions import EndPointInternalError
import csv
import re
from datetime import datetime
import ast
import time

# Initialize the SPARQL endpoint to DBpedia
sparql = SPARQLWrapper("http://dbpedia.org/sparql")
LIMIT = 50  # Limit the number of property values per entity to avoid huge queries
TYPE = "top"
QUANTITY = "10000"
if QUANTITY=="1000":
    CATEGORIES = ["arts and recreation", "biography", "food and agriculture", "geography", "history", "language and literature", "measurements", "philosophy", "religion", "science", "social sciences", "technology"]
else:
    CATEGORIES = ["anthropology, psychology and everyday life", "arts", "biology", "geography", "history", "language and literature", "mathematics", "people", "philosophy", "physics", "religion", "society and social sciences", "technology"]
CACHING = True

if CACHING:
    with open("output/dictionaries/properties.txt", "r", encoding="utf-8") as p:
        prop_domain_and_range = ast.literal_eval(p.read())
    with open("output/dictionaries/entity_types.txt", "r", encoding="utf-8") as e:
        entity_types = ast.literal_eval(e.read())
    with open("output/dictionaries/superclasses.txt", "r", encoding="utf-8") as s:
        superclasses_for_types = ast.literal_eval(s.read())

edges = {}
with open("output/dictionaries/superclasses.csv", newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    for subclass, superclass in reader:
        edges.setdefault(subclass, []).append(superclass)

OUTCOMES = {
            # Valid
            ('skip', 'skip'):    'Valid (No expected domain, no expected range)',
            ('skip', 'pass'):    'Valid (No expected domain, range matches)',
            ('pass', 'skip'):    'Valid (Domain matches, no expected range)',
            ('pass', 'pass'):    'Valid (Domain matches, range matches)',
            # Possibly Valid
            ('skip', 'unknown'):    'Possibly Valid (No expected domain, no actual range to check against)',
            ('unknown', 'skip'):    'Possibly Valid (No actual domain to check against, no expected range)',
            ('unknown', 'pass'):    'Possibly Valid (No actual domain to check against, range matches)',
            ('pass', 'unknown'):    'Possibly Valid (Domain matches, no actual range to check against)',
            ('unknown', 'unknown'): 'Possibly Valid (No actual domain to check against, no actual range to check against)',
            # Invalid
            ('skip', 'fail'):    'Invalid (No expected domain, range does not match)',
            ('fail', 'skip'):    'Invalid (Domain does not match, no expected range)',
            ('fail', 'pass'):    'Invalid (Domain does not match, range matches)',
            ('pass', 'fail'):    'Invalid (Domain matches, range does not match)',
            ('fail', 'fail'):    'Invalid (Domain does not match, range does not match)',
            ('unknown', 'fail'): 'Invalid (No actual domain to check against, range does not match)',
            ('fail', 'unknown'): 'Invalid (Domain does not match, no actual range to check against)',
        }

# -------------------------
# --- Validation functions
# -------------------------

def always_valid(text):
    """Validation function that always returns True. Used for XSD string types."""
    return True

def is_yyyy_mm_dd(text: str) -> bool:
    """
    Checks if a string is a valid date in YYYY-MM-DD format.
    Handles negative years by stripping the minus sign and padding the year to 4 digits.
    """
    try:
        if text.startswith('-'):
            temp_text = text[1:]
            parts = temp_text.split("-")
            if len(parts[0]) < 4:
                parts[0] = parts[0].zfill(4)  # pad negative year to 4 digits
            padded_text = "-".join(parts)
            datetime.strptime(padded_text, "%Y-%m-%d")
        else:
            datetime.strptime(text, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_double(text: str) -> bool:
    """Checks if text can be converted to a float."""
    try:
        float(text)
        return True
    except ValueError:
        return False

def is_year(text: str) -> bool:
    """Checks if text is an integer, possibly negative (for years)."""
    return re.fullmatch(r"-?\d+", text) is not None

def is_non_negative_integer(text: str) -> bool:
    """Checks if text is a non-negative integer."""
    if not text:
        return False
    text = text.strip()
    return text.isdigit()

def is_positive_integer(text: str) -> bool:
    """Checks if text is a positive integer (>0)."""
    return text.isdigit() and int(text) > 0

def is_integer(text: str) -> bool:
    """Checks if text is an integer (non-negative, as written)."""
    return text.isdigit()

# XSD validators for literal types
XSD_VALIDATORS = {
    "http://www.w3.org/2001/XMLSchema#string": always_valid,
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString": always_valid,
    "http://www.w3.org/2001/XMLSchema#date": is_yyyy_mm_dd,
    "http://www.w3.org/2001/XMLSchema#double": is_double,
    "http://www.w3.org/2001/XMLSchema#float": is_double,
    "http://www.w3.org/2001/XMLSchema#gYear": is_year,
    "http://www.w3.org/2001/XMLSchema#nonNegativeInteger": is_non_negative_integer,
    "http://www.w3.org/2001/XMLSchema#positiveInteger": is_positive_integer,
    "http://www.w3.org/2001/XMLSchema#integer": is_integer,
}


# -------------------------
# --- SPARQL query execution
# -------------------------

def run_query(query):
    """
    Executes a SPARQL query against DBpedia.
    Returns results in JSON format.
    Handles endpoint errors by returning an empty bindings list.
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        return sparql.query().convert()
    except EndPointInternalError as e:
        # DBpedia endpoint errors handled gracefully
        return "RETRY"
    except Exception as e:
        # Catch-all for unexpected errors
        return "RETRY"

# -------------------------
# --- Functions to fetch counts
# -------------------------

def get_counts(entity):
    """
    Counts the number of distinct ontology properties where the entity appears as subject or object.
    Excludes certain trivial properties (like abstract or image-related ones) to reduce noise.
    Returns SPARQL results.
    """
    query = f"""SELECT
        (COUNT(DISTINCT ?prop_as_subject) AS ?subjectPropertyCount)
        (COUNT(DISTINCT ?prop_as_object) AS ?objectPropertyCount)
        WHERE {{
            {{<http://dbpedia.org/resource/{entity}> ?prop_as_subject ?value .
                FILTER(STRSTARTS(STR(?prop_as_subject), "http://dbpedia.org/ontology/"))
                FILTER(!CONTAINS(STR(?prop_as_subject), "wikiPage"))
                FILTER(?prop_as_subject NOT IN ( dbo:abstract, dbo:bicycleInformation, dbo:boilerPressure, dbo:carNumber, dbo:careerStation, dbo:collection, dbo:damage, dbo:depictionDescription, dbo:description, dbo:event, dbo:imageSize, dbo:impactFactorAsOf, dbo:isHandicappedAccessible, dbo:leaderFunction, dbo:lengthReference, dbo:liberationDate, dbo:logo, dbo:mapCaption, dbo:militaryService, dbo:minister, dbo:name, dbo:note, dbo:notes, dbo:numberOfVisitorsAsOf, dbo:orderInOffice, dbo:other, dbo:parkingInformation, dbo:personFunction, dbo:picture, dbo:politicalLeader, dbo:projectKeyword, dbo:pronunciation, dbo:quote, dbo:reference, dbo:restingPlacePosition, dbo:restriction, dbo:sales, dbo:selection, dbo:signature, dbo:soundRecording, dbo:speaker, dbo:statisticLabel, dbo:strength, dbo:termPeriod, dbo:thumbnail, dbo:title, dbo:tournamentRecord, dbo:visitorStatisticsAsOf, dbo:winsAtAsia, dbo:winsAtAus, dbo:winsAtChallenges, dbo:winsAtChampionships, dbo:winsAtJapan, dbo:winsAtLET, dbo:winsAtNWIDE, dbo:winsAtOtherTournaments, dbo:winsAtPGA, dbo:winsAtSenEuro, dbo:winsInEurope ))
            }}
            UNION
            {{?value ?prop_as_object <http://dbpedia.org/resource/{entity}> .
                FILTER(STRSTARTS(STR(?prop_as_object), "http://dbpedia.org/ontology/"))
                FILTER(!CONTAINS(STR(?prop_as_object), "wikiPage"))
                FILTER(?prop_as_object NOT IN ( dbo:abstract, dbo:bicycleInformation, dbo:boilerPressure, dbo:carNumber, dbo:careerStation, dbo:collection, dbo:damage, dbo:depictionDescription, dbo:description, dbo:event, dbo:imageSize, dbo:impactFactorAsOf, dbo:isHandicappedAccessible, dbo:leaderFunction, dbo:lengthReference, dbo:liberationDate, dbo:logo, dbo:mapCaption, dbo:militaryService, dbo:minister, dbo:name, dbo:note, dbo:notes, dbo:numberOfVisitorsAsOf, dbo:orderInOffice, dbo:other, dbo:parkingInformation, dbo:personFunction, dbo:picture, dbo:politicalLeader, dbo:projectKeyword, dbo:pronunciation, dbo:quote, dbo:reference, dbo:restingPlacePosition, dbo:restriction, dbo:sales, dbo:selection, dbo:signature, dbo:soundRecording, dbo:speaker, dbo:statisticLabel, dbo:strength, dbo:termPeriod, dbo:thumbnail, dbo:title, dbo:tournamentRecord, dbo:visitorStatisticsAsOf, dbo:winsAtAsia, dbo:winsAtAus, dbo:winsAtChallenges, dbo:winsAtChampionships, dbo:winsAtJapan, dbo:winsAtLET, dbo:winsAtNWIDE, dbo:winsAtOtherTournaments, dbo:winsAtPGA, dbo:winsAtSenEuro, dbo:winsInEurope ))
            }}
        }}
    """
    result = run_query(query)
    return result

# -------------------------
# --- Functions to fetch properties/values
# -------------------------

def get_prop_and_obj(entity):
    """Fetches all ontology properties and values where entity is the subject."""
    query = f"""
        SELECT ?property ?value
        WHERE {{
            <http://dbpedia.org/resource/{entity}> ?property ?value .
            FILTER(STRSTARTS(STR(?property), "http://dbpedia.org/ontology/"))
            FILTER(!CONTAINS(STR(?property), "wikiPage"))
            FILTER(?property NOT IN ( dbo:abstract, dbo:bicycleInformation, dbo:boilerPressure, dbo:carNumber, dbo:careerStation, dbo:collection, dbo:damage, dbo:depictionDescription, dbo:description, dbo:event, dbo:imageSize, dbo:impactFactorAsOf, dbo:isHandicappedAccessible, dbo:leaderFunction, dbo:lengthReference, dbo:liberationDate, dbo:logo, dbo:mapCaption, dbo:militaryService, dbo:minister, dbo:name, dbo:note, dbo:notes, dbo:numberOfVisitorsAsOf, dbo:orderInOffice, dbo:other, dbo:parkingInformation, dbo:personFunction, dbo:picture, dbo:politicalLeader, dbo:projectKeyword, dbo:pronunciation, dbo:quote, dbo:reference, dbo:restingPlacePosition, dbo:restriction, dbo:sales, dbo:selection, dbo:signature, dbo:soundRecording, dbo:speaker, dbo:statisticLabel, dbo:strength, dbo:termPeriod, dbo:thumbnail, dbo:title, dbo:tournamentRecord, dbo:visitorStatisticsAsOf, dbo:winsAtAsia, dbo:winsAtAus, dbo:winsAtChallenges, dbo:winsAtChampionships, dbo:winsAtJapan, dbo:winsAtLET, dbo:winsAtNWIDE, dbo:winsAtOtherTournaments, dbo:winsAtPGA, dbo:winsAtSenEuro, dbo:winsInEurope ))
        }}
    """
    result = run_query(query)
    return result

def get_prop_and_subj(entity):
    """Fetches all ontology properties and values where entity is the object."""
    query = f"""
        SELECT ?property ?value
        WHERE {{
            ?value ?property <http://dbpedia.org/resource/{entity}> .
            FILTER(STRSTARTS(STR(?property), "http://dbpedia.org/ontology/"))
            FILTER(!CONTAINS(STR(?property), "wikiPage"))
            FILTER(?property NOT IN ( dbo:abstract, dbo:bicycleInformation, dbo:boilerPressure, dbo:carNumber, dbo:careerStation, dbo:collection, dbo:damage, dbo:depictionDescription, dbo:description, dbo:event, dbo:imageSize, dbo:impactFactorAsOf, dbo:isHandicappedAccessible, dbo:leaderFunction, dbo:lengthReference, dbo:liberationDate, dbo:logo, dbo:mapCaption, dbo:militaryService, dbo:minister, dbo:name, dbo:note, dbo:notes, dbo:numberOfVisitorsAsOf, dbo:orderInOffice, dbo:other, dbo:parkingInformation, dbo:personFunction, dbo:picture, dbo:politicalLeader, dbo:projectKeyword, dbo:pronunciation, dbo:quote, dbo:reference, dbo:restingPlacePosition, dbo:restriction, dbo:sales, dbo:selection, dbo:signature, dbo:soundRecording, dbo:speaker, dbo:statisticLabel, dbo:strength, dbo:termPeriod, dbo:thumbnail, dbo:title, dbo:tournamentRecord, dbo:visitorStatisticsAsOf, dbo:winsAtAsia, dbo:winsAtAus, dbo:winsAtChallenges, dbo:winsAtChampionships, dbo:winsAtJapan, dbo:winsAtLET, dbo:winsAtNWIDE, dbo:winsAtOtherTournaments, dbo:winsAtPGA, dbo:winsAtSenEuro, dbo:winsInEurope ))
        }}
    """
    result = run_query(query)
    return result

# -------------------------
# --- CSV writing
# -------------------------

def get_values(category, titles):
    values_to_redo = []
    """
    For a given category and list of entity titles:
    - Fetch values where each entity appears as subject and object.
    - Write results to a CSV file with columns: Subject, Property, Object.
    - Limits the number of values per property to avoid huge files.
    """
    with open(f"output/values/{category}-values.csv", "w", newline="", encoding="utf-8") as f:
        new_titles = []
        writer = csv.DictWriter(f, fieldnames=["Subject", "Property", "Object"])
        for i, title in enumerate(titles):
            print(f"{i+1}. {title} ({round((100*i)/len(titles))}%)")
            po = get_prop_and_obj(title)
            ps = get_prop_and_subj(title)
            if po == ps:
                redirects = run_query(f"""
                                SELECT ?value
                                WHERE {{
                                    <http://dbpedia.org/resource/{title}> <http://dbpedia.org/ontology/wikiPageRedirects> ?value .
                                    }}
                                """)
                if redirects == "RETRY":
                    print("Query failed, skipping", title, "for", direction)
                    values_to_redo.append((title, direction))
                    continue
                if redirects != {'head': {'link': [], 'vars': ['value']}, 'results': {'distinct': False, 'ordered': True, 'bindings': []}}:
                    title = redirects['results']['bindings'][0]['value']['value']
                    print("Redirected to", title)
                    po = get_prop_and_obj(title)
                    ps = get_prop_and_subj(title)
            new_titles.append(title.removeprefix("http://dbpedia.org/resource/"))
            results = [
                ("subject", po),  # Entity as subject
                ("object", ps)   # Entity as object
            ]
            prop_count= {}
            for direction, result in results:
                print("Checking", direction)
                if result == "RETRY":
                    print("Query failed, skipping", title, "for", direction)
                    values_to_redo.append((title, direction))
                    continue
                for binding in result["results"]["bindings"]:
                    prop = binding["property"]["value"]  # Get local name
                    if LIMIT == -1 or prop_count.get(prop, 0) < LIMIT:
                        value_name = binding["value"]["value"]
                        if direction == "subject":
                            writer.writerow({
                                "Subject": "http://dbpedia.org/resource/" + title,
                                "Property": prop,
                                "Object": value_name
                            })
                        else:  # entity is object
                            writer.writerow({
                                "Subject": value_name,
                                "Property": prop,
                                "Object": "http://dbpedia.org/resource/" + title
                            })
                        prop_count[prop] = prop_count.get(prop, 0) + 1
            f.flush()

    print(values_to_redo)
    return new_titles, values_to_redo

# -------------------------
# --- Validation of values
# -------------------------

def validate(category):
    """
    Validates the values in the CSV file for a given category.
    - Checks types of subjects and objects.
    - Uses XSD validators for literal values.
    - Writes results to a validation CSV with validity status.
    - Processes entities in batches of 100.
    """
    BATCH_SIZE = 100

    with open(f"output/values/{category}-values.csv", newline="", encoding="utf-8") as values, \
    open(f"output/validations/{category}-validations.csv", "w", newline="", encoding="utf-8") as validations:
        reader = csv.reader(values)
        writer = csv.DictWriter(validations, fieldnames=["Subject", "Property", "Object", "Validity", "Lists"])

        rows = list(reader)
        total = len(rows)

        for batch_start in range(0, total, BATCH_SIZE):
            batch = rows[batch_start:batch_start + BATCH_SIZE]

            # Pre-fetch all unique props, subjects, and objects in this batch
            if CACHING:
                unique_props = {row[1] for row in batch}
                unique_entities = {
                    row[i] for row in batch for i in (0, 2)
                    if row[i].startswith("http://dbpedia.org/resource/")
                }

                for prop in unique_props:
                    if prop not in prop_domain_and_range:
                        print(prop, "not in cache")
                        prop_domain_and_range[prop] = get_domain_and_range(prop)

                uncached_entities = [e for e in unique_entities if e not in entity_types]
                if uncached_entities:
                    batch_results = get_types_batch(uncached_entities)
                    if "RETRY" in batch_results:
                        # Fall back to individual queries if batch failed
                        print("Batch query failed, falling back to individual queries for entities.")
                        for entity in uncached_entities:
                            entity_types[entity] = get_types(entity)
                    else:
                        print(f"Batch query successful for {len(uncached_entities)} entities.")
                        entity_types.update(batch_results)

            for i, (subj, prop, obj) in enumerate(batch, start=batch_start):
                subj_short = subj.removeprefix("http://dbpedia.org/resource/")
                prop_short = prop.removeprefix("http://dbpedia.org/ontology/")
                obj_short  = obj.removeprefix("http://dbpedia.org/resource/")

                print(subj_short, prop_short, obj_short, f"({round((100*i)/total)}%)")

                if CACHING:
                    expected_domain, expected_range = prop_domain_and_range[prop]

                    actual_domain = entity_types[subj] if subj.startswith("http://dbpedia.org/resource/") else set()
                    actual_range  = entity_types[obj]  if obj.startswith("http://dbpedia.org/resource/")  else set()
                else:
                    expected_domain, expected_range = get_domain_and_range(prop)
                    actual_domain = get_types(subj)
                    actual_range = get_types(obj)

                # Validate literals
                if expected_range.__contains__("http://www.w3.org/2001/XMLSchema") or expected_range.__contains__("http://www.w3.org/1999/02/22-rdf-syntax-ns"):
                    validator = XSD_VALIDATORS.get(expected_range)
                    if validator and validator(obj):
                        validity = "Valid"
                    elif validator:
                        validity = "Invalid"
                    else:
                        validity = f"Unknown {expected_range}"
                else:
                    # Validate resources using their types
                    # Normalize empty values
                    domain_expected_blank = expected_domain == ''
                    range_expected_blank = expected_range == ''
                    domain_actual_blank = actual_domain == set()
                    range_actual_blank = actual_range == set()

                    # Evaluate domain check
                    if domain_expected_blank:
                        domain_result = 'skip'
                    elif domain_actual_blank:
                        domain_result = 'unknown'
                    elif expected_domain in actual_domain:
                        domain_result = 'pass'
                    else:
                        domain_result = 'fail'

                    # Evaluate range check
                    if range_expected_blank:
                        range_result = 'skip'
                    elif range_actual_blank:
                        range_result = 'unknown'
                    elif expected_range in actual_range:
                        range_result = 'pass'
                    else:
                        range_result = 'fail'

                    validity = OUTCOMES[(domain_result, range_result)]

                print("\t", validity)
                writer.writerow({
                    "Subject": subj_short,
                    "Property": prop_short,
                    "Object": obj_short,
                    "Validity": validity,
                    "Lists": [expected_domain, actual_domain, expected_range, actual_range]
                })

            # Flush and save caches after every batch
            if CACHING:
                validations.flush()
                with open('output/dictionaries/entity_types.txt', 'w', encoding="utf-8") as e, \
                     open('output/dictionaries/properties.txt', 'w', encoding="utf-8") as p, \
                     open('output/dictionaries/superclasses.txt', 'w', encoding="utf-8") as s:
                    e.write(str(entity_types))
                    p.write(str(prop_domain_and_range))
                    s.write(str(superclasses_for_types))

        print("\nValidation completed.")

# -------------------------
# --- Helper functions for SPARQL
# -------------------------

def get_domain_and_range(property):
    with open("output/dictionaries/properties.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for prop, domain, range in reader:
            if prop == property:
                return domain, range
        return [], []

def get_superclasses(type_uri):
    result = []
    visited = set()
    stack = [type_uri]

    while stack:
        current = stack.pop()
        for sup in edges.get(current, []):
            if sup not in visited:
                visited.add(sup)
                result.append(sup)
                stack.append(sup)

    return result

def get_types(entity):
    """
    Returns the ontology types of an entity, including all superclasses.
    Only returns types in the dbo: namespace.
    """
    types = []
    query = f"""
        SELECT DISTINCT ?type
        WHERE {{
            <{entity}> rdf:type ?type .
            FILTER(STRSTARTS(STR(?type), "http://dbpedia.org/ontology/"))
        }}
    """
    result = run_query(query)
    if result == "RETRY":
        time.sleep(2)
        return {"RETRY"}
    if result["results"]["bindings"]:
        for binding in result["results"]["bindings"]:
            if "type" in binding:
                base_type = binding["type"]["value"]
                if base_type not in superclasses_for_types:
                    print(base_type, "not in cache")
                    superclasses_for_types[base_type] = get_superclasses(base_type)
                types.extend([base_type] + superclasses_for_types[base_type])
    return set(types)  # Return unique types

def get_types_batch(entities):
    """
    Returns the ontology types of a batch of entities, including all superclasses.
    Only returns types in the dbo: namespace.
    Returns a dict mapping entity URI -> set of types.
    """
    if not entities:
        return {}

    values_clause = " ".join(f"<{e}>" for e in entities)
    query = f"""
        SELECT DISTINCT ?entity ?type
        WHERE {{
            VALUES ?entity {{ {values_clause} }}
            ?entity rdf:type ?type .
            FILTER(STRSTARTS(STR(?type), "http://dbpedia.org/ontology/"))
        }}
    """
    result = run_query(query)
    if result == "RETRY":
        time.sleep(2)
        return {"RETRY": {"RETRY"}}

    entity_type_map = {e: [] for e in entities}

    if result["results"]["bindings"]:
        for binding in result["results"]["bindings"]:
            if "entity" in binding and "type" in binding:
                entity = binding["entity"]["value"]
                base_type = binding["type"]["value"]

                if base_type not in superclasses_for_types:
                    print(base_type, "not in cache")
                    superclasses_for_types[base_type] = get_superclasses(base_type)

                entity_type_map[entity].extend([base_type] + superclasses_for_types[base_type])

    return {entity: set(types) for entity, types in entity_type_map.items()}

def get_du_values(category):
    with open(f"output/values/{category}-values.csv", newline="", encoding="utf-8") as values, open(f"output/pages/{category}.txt", newline="", encoding="utf-8") as pages:
        reader = csv.reader(values)
        pages = set(line.strip() for line in pages if line.strip())
        new_rows = []
        values_to_redo = []

        for i, (subj, prop, obj) in enumerate(reader):
            if obj.__contains__("__"):
                du_value = obj.removeprefix("http://dbpedia.org/resource/").split("__")[0]
                if du_value in pages:
                    print(subj, prop, obj)
                    subentity_po = get_prop_and_obj(du_value)
                    print("Checking outgoing properties of", obj.split("__")[0])
                    subentity_ps = get_prop_and_subj(du_value)
                    print("Checking incoming properties of", obj.split("__")[0])

                    results = [
                        ("subject", subentity_po),  # Entity as subject
                        ("object", subentity_ps)   # Entity as object
                    ]
                    prop_count= {}

                    for direction, result in results:
                        if result == "RETRY":
                            print("Query failed, skipping", du_value, "for", direction)
                            values_to_redo.append((du_value, direction))
                            continue
                        for binding in result["results"]["bindings"]:
                            prop = binding["property"]["value"]  # Get local name
                            if LIMIT == -1 or prop_count.get(prop, 0) < LIMIT:
                                value_name = binding["value"]["value"]
                                if direction == "subject":
                                    if obj != value_name:
                                        new_rows.append({
                                            "Subject": obj,
                                            "Property": prop,
                                            "Object": value_name
                                        })
                                else:  # entity is object
                                    if obj != value_name:
                                        new_rows.append({
                                            "Subject": value_name,
                                            "Property": prop,
                                            "Object": obj
                                        })
                                prop_count[prop] = prop_count.get(prop, 0) + 1
    with open(f"output/values/{category}-values.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Subject", "Property", "Object"])
        writer.writerows(new_rows)
    
    return values_to_redo

def get_pages_from_specific_list():
    # Ask the user for a DBpedia category (resource name)
    category = input("Category? ")

    # Base SPARQL query:
    # Select distinct pages that are wiki-linked from the given category resource
    query = f"""SELECT DISTINCT ?page
        WHERE {{
        <http://dbpedia.org/resource/{category}>
            <http://dbpedia.org/ontology/wikiPageWikiLink> ?page .
    """

    # --- Filtering by properties ---
    # Ask the user for filtering properties (comma-separated)
    filtering_props = input("Filtering property? ").split(",")
    prop_patterns = []

    # If the input is not empty
    if filtering_props != ['']:
        for p in filtering_props:
            p = p.strip()  # Remove extra spaces
            # Create a SPARQL pattern where ?value has a given property pointing to ?page
            prop_patterns.append(
                f"?value <http://dbpedia.org/ontology/{p}> ?page ."
            )
    
        # Combine all property patterns using UNION
        # This means a page is kept if it matches at least one property
        if prop_patterns:
            query += " { " + " } UNION { ".join(prop_patterns) + " } "

    # --- Filtering by types ---
    # Ask the user for filtering types (comma-separated)
    filtering_types = input("Filtering type? ").split(",")
    type_patterns = []

    # If the input is not empty
    if filtering_types != ['']:
        for t in filtering_types:
            t = t.strip()  # Remove extra spaces
            # Create a SPARQL pattern enforcing a specific rdf:type
            type_patterns.append(f"?page rdf:type dbo:{t} .")

        # Combine all type patterns using UNION
        # This means a page is kept if it matches at least one type
        if type_patterns:
            query += " { " + " } UNION { ".join(type_patterns) + " } "

    # Close the WHERE block of the SPARQL query
    query += " }"

    # Execute the SPARQL query
    result = run_query(query)

    # Write the resulting page names to a text file
    # The filename is based on the chosen category
    with open(f"output/pages/{category}.txt", "w", encoding="utf-8") as f:
        for binding in result['results']['bindings']:
            # Extract only the page name from the full DBpedia URI
            page = binding['page']['value'].split("/")[-1]
            f.write(page + "\n")

# -------------------------
# --- Main workflow
# -------------------------

def main():
    choice = input("Get counts (C), get values (V), get more values (M), get names from a specific current_category (S) or validate existing values (E)? ")

    if choice == "E":
        # Validate previously fetched CSV values
        for category in CATEGORIES:
            current_category = f"{TYPE}-{QUANTITY}/{category}"
            validate(current_category)
    elif choice == "S":
        get_pages_from_specific_list()
    elif choice == "V":
        all_values_to_redo = []
        for category in CATEGORIES:
            current_category = f"{TYPE}-{QUANTITY}/{category}"
            if current_category:
                print(current_category)
                # Read entity titles from file
                with open(f"output/pages/{current_category}.txt", "r", encoding="utf-8") as f:
                    titles = [line.strip() for line in f if line.strip()]
                    # Fetch values for the entities and write to CSV
                    new_titles, values_to_redo = get_values(current_category, titles)
                    all_values_to_redo.extend(values_to_redo)

                with open(f"output/pages/{current_category}.txt", "w", encoding="utf-8") as f:
                    for title in new_titles:
                        f.write(title + "\n")
        print("Values to redo:", all_values_to_redo)
    elif choice == "M":
        all_values_to_redo = []
        for category in CATEGORIES:
            current_category = f"{TYPE}-{QUANTITY}/{category}"
            if current_category:
                print(current_category)
                # Read entity titles from file
                values_to_redo = get_du_values(current_category)
                print("Values to redo:", values_to_redo)
                all_values_to_redo.extend(values_to_redo)
        print("All values to redo:", all_values_to_redo)
    else:
        print(current_category)
        # Read entity titles from file
        with open(f"output/pages/{current_category}.txt", "r", encoding="utf-8") as f:
            titles = [line.strip() for line in f if line.strip()]

            # Fetch counts of subject/object properties and write to CSV
            with open("counts.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["title", "Subject Count", "Object Count"])
                writer.writeheader()
                for title in enumerate(titles):
                    result = get_counts(title)
                    bindings = result["results"]["bindings"][0]
                    subject_count = int(bindings["subjectPropertyCount"]["value"])
                    object_count = int(bindings["objectPropertyCount"]["value"])

                    print(title, ":", subject_count, "and", object_count)
                    writer.writerow({
                        "title": title,
                        "Subject Count": subject_count,
                        "Object Count": object_count
                    })
                    f.flush()

if __name__ == "__main__":
    main()