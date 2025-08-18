# Convert Grants Data to XML

Tool for converting funder grant data from CSV or JSON formats to Crossref Grant ID XML format, with support for combining multiple data sources, including of related works and additional investigators, as well as validation against the grants schema.


## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Data Transformations](#data-transformations)
- [Validation](#validation)
- [File Formats](#file-formats)
- [Troubleshooting](#troubleshooting)

## Installation
```bash
pip install -r requirements.txt
```

- `pyyaml>=6.0` - YAML configuration parsing
- `lxml>=4.9.0` - XML validation with XSD schemas

## Quick Start

### Basic CSV Conversion

1. Prepare a CSV file with grant data
2. Use the provided sample configuration or create your own
3. Run the conversion:

```bash
python convert.py --input grants.csv --output grants.xml --config config.yaml
```

### Basic JSON Conversion

```bash
python convert.py --input grants.json --output grants.xml --config config.yaml
```

### With Related Works

```bash
python convert.py --input grants.csv --output grants.xml --config config.yaml \
    --related-works related_publications.csv
```

### With Co-Applicants

```bash
python convert.py --input grants.csv --output grants.xml --config config.yaml \
    --coapplicants coapplicants.csv
```

## Configuration

The converter uses YAML configuration files to define how input data maps to XML elements. A configuration file consists of several sections:

### Basic Structure

```yaml
# Static header values
header_static_values:
  doi_batch_id: "batch_20250815"
  depositor_name: "Organization Name"
  depositor_email: "depositor@example.org"
  registrant: "Organization Name"

# XML namespaces
namespace_values:
  xmlns: "http://www.crossref.org/grant_id/0.2.0"
  "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"
  "xmlns:rel": "http://www.crossref.org/relations.xsd"
  "xsi:schemaLocation": "http://www.crossref.org/grant_id/0.2.0 http://www.crossref.org/schemas/grant_id0.2.0.xsd"

# Field mappings
field_mappings:
  # ... field definitions ...
```

### Field Mapping Types

#### 1. Direct Mapping
Maps a source field directly to an XML element:
```yaml
project-title:
  source_field: "title"
```

#### 2. Static Values
Uses a fixed value for all records:
```yaml
funding_type:
  static_value: "grant"
```

#### 3. Transformations
Applies transformations to source data:
```yaml
doi:
  transform: construct_doi
  prefix: "10.13039/grant-"
  source_field: "grant_id"
```

#### 4. Complex Fields
Extracts data from nested structures:
```yaml
investigators:
  source_field: "_complex:lead_investigator"
```

## Data Transformations

The converter supports several built-in transformations:

### split_name
Splits a full name into given and family names:
```yaml
person_name:
  transform: split_name
  source_field: "investigator_name"
  separator: ","  # "Last, First" format
```

### construct_doi
Builds a DOI from a prefix and source field:
```yaml
doi:
  transform: construct_doi
  prefix: "10.13039/grant-"
  source_field: "award_id"
```

### construct_url
Creates a URL from components:
```yaml
resource:
  transform: construct_url
  prefix: "https://example.org/grants/"
  source_field: "grant_id"
```

### format_date
Converts date formats:
```yaml
award-start-date:
  transform: format_date
  source_field: "start_date"
  input_format: "%Y-%m-%dT%H:%M:%S"  # ISO datetime
  output_format: "%Y-%m-%d"          # YYYY-MM-DD
```

## Validation

The package includes a validation script to check generated XML against the Crossref Grant ID schema.

### Setup Validation

The validation directory contains:
- `validate_xml.py` - Validation script
- `grant_id0.2.0.xsd.xml` - Main schema file
- Supporting schema files used in `grant_id0.2.0.xsd.xml`

### Running Validation

```bash
cd validation
python validate_xml.py <xml_file> grant_id0.2.0.xsd.xml
```

Output:
- Success: "XML file is valid against the schema"
- Failure: Lists specific validation errors with line numbers


## File Formats

### Input CSV Format

CSV files should have headers matching the field names in your configuration:

```csv
ApplicationID,ApplicationTitle,Name-Nom,Institution,AwardAmount,FiscalYear
12345,Research Project,Smith John,University,50000,2024
```

### Input JSON Format

JSON files can be either:

1. **Simple array of records**:
```json
[
  {
    "grant_id": "12345",
    "title": "Research Project",
    "investigator": "John Smith"
  }
]
```

2. **Nested structure** (like NWO data):
```json
{
  "metadata": { ... },
  "projects": [
    {
      "project_id": "12345",
      "title": "Research Project",
      "project_members": [
        {
          "role": "Project leader",
          "first_name": "John",
          "last_name": "Smith"
        }
      ]
    }
  ]
}
```

For nested JSON, specify the path to the data array in configuration:
```yaml
options:
  json_root_path: "projects"
```

### Output XML Format

The converter generates Crossref Grant ID XML format v0.2.0:

```xml
<?xml version='1.0' encoding='utf-8'?>
<doi_batch xmlns="http://www.crossref.org/grant_id/0.2.0" version="0.2.0">
  <head>
    <doi_batch_id>batch_20250815</doi_batch_id>
    <timestamp>20250815120000</timestamp>
    <depositor>
      <depositor_name>Organization Name</depositor_name>
      <email_address>depositor@example.org</email_address>
    </depositor>
    <registrant>Organization Name</registrant>
  </head>
  <body>
    <grant>
      <project>
        <project-title>Research Project Title</project-title>
        <investigators>
          <person role="lead_investigator">
            <givenName>John</givenName>
            <familyName>Smith</familyName>
            <affiliation>
              <institution country="US">University Name</institution>
            </affiliation>
          </person>
          <person role="investigator">
            <givenName>Jane</givenName>
            <familyName>Doe</familyName>
            <affiliation>
              <institution country="US">Another University</institution>
            </affiliation>
          </person>
        </investigators>
        <description>Project description...</description>
        <award_amount currency="USD">50000</award_amount>
        <funding funding-type="grant">
          <ROR>https://ror.org/example</ROR>
          <funding-scheme>Grant Program</funding-scheme>
        </funding>
      </project>
      <award-number>12345</award-number>
      <award-start-date>2024-01-01</award-start-date>
      <doi_data>
        <doi>10.13039/grant-12345</doi>
        <resource>https://example.org/grants/12345</resource>
      </doi_data>
    </grant>
  </body>
</doi_batch>
```

## Advanced

### Related Works Integration

The converter can integrate related publications, datasets, or other outputs:

1. **From External Files**:
```yaml
related_works_config:
  join_key: "award_id"           # Field in related works file
  grant_join_field: "grant_id"   # Field in grant file
  relationship_type: "isFinancedBy"
```

2. **From Embedded Arrays** (e.g., NWO products):
```yaml
related_works_config:
  embedded_field: "products"
  relationship_type: "finances"
  doi_field: "url_open_access"
  filter_pattern: "doi\\.org"
```

### Co-Applicants Integration

The converter can load additional grant participants (co-applicants/co-investigators) from separate files:

```yaml
coapplicants_config:
  join_key: "ApplicationID"              # Field in co-applicants file to match
  grant_join_field: "ApplicationID"      # Corresponding field in grant file
  name_field: "CoApplicantName"          # Field containing co-applicant name
  name_transform: "split_name"           # Transform to apply (optional)
  name_separator: ","                    # Separator for name splitting
  institution_field: "CoAppInstitution"  # Field containing institution
  country_field: "CountryEN"             # Field containing country
```

Co-applicants are added as additional `<person>` elements with `role="investigator"` in the XML output.

### Complex Field Extraction

For nested data structures (like investigator arrays):

```yaml
complex_fields:
  lead_investigator:
    source: "project_members"
    priority_roles:
      - "Project leader"
      - "Main Applicant"
      - "Co-applicant"
    fields:
      first_name: "first_name"
      last_name: "last_name"
      orcid: "orcid"
      organisation: "organisation"
```

### Funder Identification

The converter supports two methods:

1. **ROR ID**:
```yaml
funder_ror:
  static_value: "https://ror.org/04jsz6e67"
```

2. **Funder Name + DOI**:
```yaml
funder_name:
  static_value: "Organization Name"
funder_id:
  static_value: "https://doi.org/10.13039/501100000038"
```

### Logging

Enable logging for debugging:

```bash
python convert.py --input data.csv --output output.xml --config config.yaml --log debug.log
```

The log file will contain:
- Number of records processed
- Transformation details
- Warning messages for skipped records
- Error details for failed records

## Command Line Reference

### convert.py

```bash
python convert.py [options]
```

**Required Arguments:**
- `--input PATH` - Path to input data file (CSV or JSON)
- `--output PATH` - Path for output XML file
- `--config PATH` - Path to YAML configuration file

**Optional Arguments:**
- `--related-works PATH [PATH ...]` - Path(s) to related works files
- `--coapplicants PATH [PATH ...]` - Path(s) to co-applicants data files
- `--log PATH` - Path to log file (optional, defaults to console output)

### validate_xml.py

```bash
python validate_xml.py <xml_file> <schema_file>
```

**Arguments:**
- `xml_file` - Path to XML file to validate
- `schema_file` - Path to XSD schema file
