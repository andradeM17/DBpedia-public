# DBpedia-Public

This is a collection of data and tools related to the validation of DBpedia triples.

## **Output**
This contains the bulk of the work from this project.

### **Dictionaries**
The folder contains dictionaries of :
 - entity classes (entity_types)
 - the expected domain and ranges of properties
 - superclasses for each other class

 these are available as .csv and .pickle formats.

### **Pages**
This folder contains the entity names for the Top 1000, Top 10000, and Random 1000 entities, from Wikipedia.

### **Validations**
This folder has triples with validity information included.

### **Values**
The same triples as **Validations** without validity information.

## **Results**
Each folder contains statistics for the properties and type pairs in each dataset.

## **Scripts**
Two scripts are included in the dataset.

### **Page checker**
This is used to create the tables in **dictionaries**, **validations**, and **values**.

### **Validity scorer**
Creates the datasets in **Results**.