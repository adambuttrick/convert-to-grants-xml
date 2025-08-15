#!/usr/bin/env python3
"""
Validate generated XML against Crossref Grant ID Schema
"""

import sys
from lxml import etree

def validate_xml(xml_file, xsd_file):
    """Validate XML file against XSD schema"""
    try:
        # Parse the XML document
        with open(xml_file, 'r') as f:
            xml_doc = etree.parse(f)
        
        # Parse the XSD schema
        with open(xsd_file, 'r') as f:
            xsd_doc = etree.parse(f)
        
        # Create XMLSchema object
        schema = etree.XMLSchema(xsd_doc)
        
        # Validate the XML
        is_valid = schema.validate(xml_doc)
        
        if is_valid:
            print(f"✓ XML file '{xml_file}' is valid against the schema")
            return True
        else:
            print(f"✗ XML file '{xml_file}' is NOT valid against the schema")
            print("\nValidation errors:")
            for error in schema.error_log:
                print(f"  Line {error.line}: {error.message}")
            return False
            
    except etree.XMLSyntaxError as e:
        print(f"XML Syntax Error: {e}")
        return False
    except Exception as e:
        print(f"Error during validation: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) == 3:
        xml_file = sys.argv[1]
        xsd_file = sys.argv[2]
    elif len(sys.argv) == 2:
        xml_file = sys.argv[1]
        xsd_file = "grant_id0.2.0.xsd.xml"
    else:
        xml_file = "../grants.xml"
        xsd_file = "grant_id0.2.0.xsd.xml"
    
    if validate_xml(xml_file, xsd_file):
        sys.exit(0)
    else:
        sys.exit(1)