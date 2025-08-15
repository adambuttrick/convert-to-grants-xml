import re
import sys
import csv
import json
import logging
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import yaml


class EnhancedGrantConverter:
    def __init__(self, config_path, log_path=None):
        self.config = self._load_config(config_path)
        self._setup_logging(log_path)
        self.records_processed = 0
        self.records_failed = 0
        self.related_works = defaultdict(list)
        
    def _load_config(self, config_path):
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            required_sections = ['header_static_values', 'namespace_values', 'field_mappings']
            for section in required_sections:
                if section not in config:
                    raise ValueError(f"Missing required section: {section}")
            
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")
    
    def _setup_logging(self, log_path):
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        
        if log_path:
            logging.basicConfig(
                filename=log_path,
                level=logging.INFO,
                format=log_format
            )
        else:
            logging.basicConfig(
                level=logging.INFO,
                format=log_format,
                stream=sys.stdout
            )
    
    def read_input_data(self, input_path):
        input_file = Path(input_path)
        
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        if input_file.suffix.lower() == '.csv':
            return self._read_csv(input_path)
        elif input_file.suffix.lower() == '.json':
            return self._read_json(input_path)
        else:
            raise ValueError(f"Unsupported file format: {input_file.suffix}")
    
    def _read_csv(self, file_path):
        records = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)
            logging.info(f"Read {len(records)} records from CSV file: {file_path}")
            return records
        except Exception as e:
            raise ValueError(f"Error reading CSV file: {e}")
    
    def _read_json(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            json_root = self.config.get('options', {}).get('json_root_path')
            if json_root and isinstance(data, dict):
                for key in json_root.split('.'):
                    data = data.get(key, [])
            
            if not isinstance(data, list):
                raise ValueError("JSON file must contain a list of grant records")
            
            logging.info(f"Read {len(data)} records from JSON file: {file_path}")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {e}")
    
    def load_related_works(self, related_works_files):
        for file_path in related_works_files:
            try:
                records = self.read_input_data(file_path)

                join_key = self.config.get('related_works_config', {}).get('join_key', 'award_id')
                
                for record in records:
                    award_id = record.get(join_key)
                    if award_id:
                        self.related_works[award_id].append(record)
                
                logging.info(f"Loaded related works from {file_path}")
                
            except Exception as e:
                logging.warning(f"Failed to load related works from {file_path}: {e}")
    
    def convert(self, input_path, output_path, related_works_files=None):
        logging.info(f"Starting conversion process")
        logging.info(f"Input: {input_path}")
        logging.info(f"Output: {output_path}")
        
        if related_works_files:
            self.load_related_works(related_works_files)
            logging.info(f"Loaded related works for {len(self.related_works)} grants")
        
        records = self.read_input_data(input_path)
        
        root = self._create_xml_root()
        head = self._create_xml_head(root)
        body = ET.SubElement(root, 'body')
        
        for record in records:
            try:
                grant_element = self._process_grant_record(record, body)
                self.records_processed += 1
            except Exception as e:
                logging.warning(f"Failed to process record: {e}")
                self.records_failed += 1
                continue
        
        self._write_xml(root, output_path)
        
        logging.info(f"Conversion completed")
        logging.info(f"Records processed: {self.records_processed}")
        logging.info(f"Records failed: {self.records_failed}")
    
    def _create_xml_root(self):
        namespaces = self.config['namespace_values']
        
        ET.register_namespace('', 'http://www.crossref.org/grant_id/0.2.0')
        ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        ET.register_namespace('rel', 'http://www.crossref.org/relations.xsd')
        
        root = ET.Element('doi_batch')
        root.set('version', '0.2.0')
        root.set('xmlns', namespaces.get('xmlns', 'http://www.crossref.org/grant_id/0.2.0'))
        root.set('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', 
                 namespaces.get('xsi:schemaLocation', 
                 'http://www.crossref.org/grant_id/0.2.0 http://www.crossref.org/schemas/grant_id0.2.0.xsd'))
        
        return root
    
    def _create_xml_head(self, root):
        head = ET.SubElement(root, 'head')
        header_config = self.config['header_static_values']
        
        batch_id = ET.SubElement(head, 'doi_batch_id')
        batch_id.text = header_config.get('doi_batch_id', f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        timestamp = ET.SubElement(head, 'timestamp')
        timestamp.text = datetime.now().strftime('%Y%m%d%H%M%S')
        
        depositor = ET.SubElement(head, 'depositor')
        depositor_name = ET.SubElement(depositor, 'depositor_name')
        depositor_name.text = header_config.get('depositor_name', '')
        email = ET.SubElement(depositor, 'email_address')
        email.text = header_config.get('depositor_email', '')
        
        registrant = ET.SubElement(head, 'registrant')
        registrant.text = header_config.get('registrant', header_config.get('depositor_name', 'Unknown Registrant'))
        
        return head
    
    def _process_grant_record(self, record, body):
        grant = ET.SubElement(body, 'grant')
        mappings = self.config['field_mappings']
        
        project = ET.SubElement(grant, 'project')
        
        self._process_project_fields(record, project, mappings)
        
        if 'award-number' in mappings:
            award_number = ET.SubElement(grant, 'award-number')
            award_number.text = self._get_field_value(record, mappings['award-number'])
        
        if 'award-start-date' in mappings:
            date_config = mappings['award-start-date']
            date_value = self._get_field_value(record, date_config)
            if date_value:
                award_start = ET.SubElement(grant, 'award-start-date')
                award_start.text = date_value
        
        award_id = self._get_award_id(record)
        if award_id and award_id in self.related_works:
            self._add_related_works(grant, self.related_works[award_id])
        
        embedded_config = self.config.get('related_works_config', {}).get('embedded_field')
        if embedded_config:
            embedded_works = self._get_nested_value(record, embedded_config)
            if embedded_works and isinstance(embedded_works, list):
                self._add_embedded_related_works(grant, embedded_works)
        
        doi_data = ET.SubElement(grant, 'doi_data')
        
        if 'doi' in mappings:
            doi = ET.SubElement(doi_data, 'doi')
            doi.text = self._get_field_value(record, mappings['doi'])
        
        if 'resource' in mappings:
            resource = ET.SubElement(doi_data, 'resource')
            resource.text = self._get_field_value(record, mappings['resource'])
        
        return grant
    
    def _add_embedded_related_works(self, grant, works):
        rw_config = self.config.get('related_works_config', {})
        doi_field = rw_config.get('doi_field', 'url_open_access')
        filter_pattern = rw_config.get('filter_pattern', 'doi\\.org')
        relationship_type = rw_config.get('relationship_type', 'finances')
        
        doi_works = []
        for work in works:
            doi_url = work.get(doi_field, '')
            if doi_url and filter_pattern:
                import re
                if re.search(filter_pattern, doi_url):
                    doi_works.append(work)
        
        if not doi_works:
            return
        
        program = ET.SubElement(grant, '{http://www.crossref.org/relations.xsd}program')
        program.set('name', 'relations')
        
        for work in doi_works:
            try:
                related_item = ET.SubElement(program, '{http://www.crossref.org/relations.xsd}related_item')
                
                relation = ET.SubElement(related_item, '{http://www.crossref.org/relations.xsd}inter_work_relation')
                relation.set('relationship-type', relationship_type)
                relation.set('identifier-type', 'doi')
                
                doi_url = work[doi_field]
                import re
                doi_match = re.search(r'doi\.org/(.+)', doi_url)
                if doi_match:
                    doi_value = doi_match.group(1)
                    relation.text = doi_value
                
            except Exception as e:
                logging.debug(f"Failed to add embedded related work: {e}")
                continue
    
    def _process_project_fields(self, record, project, mappings):
        if 'project-title' in mappings:
            title_config = mappings['project-title']
            title = ET.SubElement(project, 'project-title')
            title.text = self._get_field_value(record, title_config)
        
        if 'investigators' in mappings:
            self._process_investigators(record, project, mappings['investigators'])
        
        if 'description' in mappings:
            desc_config = mappings['description']
            description = ET.SubElement(project, 'description')
            description.text = self._get_field_value(record, desc_config)
        
        if 'award_amount' in mappings:
            amount_config = mappings['award_amount']
            amount_elem = ET.SubElement(project, 'award_amount')
            amount_elem.text = self._get_field_value(record, amount_config)
            if 'currency' in amount_config:
                amount_elem.set('currency', amount_config['currency'])
        
        funding = ET.SubElement(project, 'funding')
        funding.set('funding-type', mappings.get('funding_type', {}).get('static_value', 'grant'))
        
        if 'funder_ror' in mappings:
            ror = ET.SubElement(funding, 'ROR')
            ror.text = self._get_field_value(record, mappings['funder_ror'])
        else:
            if 'funder_name' in mappings:
                funder_name = ET.SubElement(funding, 'funder-name')
                funder_name.text = self._get_field_value(record, mappings['funder_name'])
            
            if 'funder_id' in mappings:
                funder_id = ET.SubElement(funding, 'funder-id')
                funder_id.text = self._get_field_value(record, mappings['funder_id'])
        
        if 'funding_scheme' in mappings:
            funding_scheme = ET.SubElement(funding, 'funding-scheme')
            funding_scheme.text = self._get_field_value(record, mappings['funding_scheme'])
    
    def _add_related_works(self, grant, works):
        program = ET.SubElement(grant, '{http://www.crossref.org/relations.xsd}program')
        program.set('name', 'relations')
        
        rw_config = self.config.get('related_works_config', {})
        
        for work in works:
            try:
                related_item = ET.SubElement(program, '{http://www.crossref.org/relations.xsd}related_item')
                
                relation = ET.SubElement(related_item, '{http://www.crossref.org/relations.xsd}inter_work_relation')
                relation.set('relationship-type', rw_config.get('relationship_type', 'isFinancedBy'))
                
                if work.get('doi'):
                    relation.set('identifier-type', 'doi')
                    doi_value = work['doi']
                    if doi_value.startswith('https://doi.org/'):
                        doi_value = doi_value.replace('https://doi.org/', '')
                    elif doi_value.startswith('http://doi.org/'):
                        doi_value = doi_value.replace('http://doi.org/', '')
                    relation.text = doi_value
                elif work.get('openalex_work_id'):
                    relation.set('identifier-type', 'uri')
                    relation.text = work['openalex_work_id']
                else:
                    continue
                    
            except Exception as e:
                logging.debug(f"Failed to add related work: {e}")
                continue
    
    def _get_award_id(self, record):
        join_config = self.config.get('related_works_config', {}).get('grant_join_field')
        
        if join_config:
            return record.get(join_config)
        
        if 'award-number' in self.config['field_mappings']:
            award_config = self.config['field_mappings']['award-number']
            return self._get_field_value(record, award_config)
        
        return None
    
    def _process_investigators(self, record, project, inv_config):
        investigators = ET.SubElement(project, 'investigators')
        
        if 'source_field' in inv_config and isinstance(inv_config['source_field'], str) and inv_config['source_field'].startswith('_complex:'):
            complex_key = inv_config['source_field'].replace('_complex:', '')
            self._process_complex_investigators(record, investigators, complex_key)
            return
        
        if 'person_name' in inv_config:
            person = ET.SubElement(investigators, 'person')
            person.set('role', 'lead_investigator')
            
            name_config = inv_config['person_name']
            
            if name_config.get('transform') == 'split_name':
                full_name = record.get(name_config.get('source_field', ''), '')
                separator = name_config.get('separator', ',')
                
                if full_name and separator in full_name:
                    parts = full_name.split(separator, 1)
                    if len(parts) == 2:
                        given_name = ET.SubElement(person, 'givenName')
                        given_name.text = parts[1].strip()
                        family_name = ET.SubElement(person, 'familyName')
                        family_name.text = parts[0].strip()
                    else:
                        family_name = ET.SubElement(person, 'familyName')
                        family_name.text = full_name.strip()
                else:
                    family_name = ET.SubElement(person, 'familyName')
                    family_name.text = full_name.strip() if full_name else 'Unknown'
            
            if 'affiliation' in inv_config:
                affiliation = ET.SubElement(person, 'affiliation')
                institution = ET.SubElement(affiliation, 'institution')
                
                inst_field = inv_config['affiliation'].get('source_field', 'Institution-Établissement')
                institution.text = record.get(inst_field, 'Unknown Institution')
                
                if 'country_field' in inv_config['affiliation']:
                    country_field = inv_config['affiliation']['country_field']
                    country = record.get(country_field, '')
                    if country:
                        country_code = self._get_country_code(country)
                        if country_code:
                            institution.set('country', country_code)
    
    def _get_field_value(self, record, field_config):
        if 'static_value' in field_config:
            return field_config['static_value']
        
        if 'transform' in field_config:
            return self._apply_transform(record, field_config)
        
        if 'source_field' in field_config:
            source_field = field_config['source_field']
            
            if isinstance(source_field, str) and source_field.startswith('_literal:'):
                return source_field.replace('_literal:', '')
            
            if isinstance(source_field, str) and source_field.startswith('_complex:'):
                return ''
            
            value = self._get_nested_value(record, source_field)
            
            if not value and 'default' in field_config:
                value = field_config['default']
            return str(value) if value is not None else ''
        
        if 'concatenate' in field_config:
            fields = field_config['concatenate']
            separator = field_config.get('separator', ' ')
            values = [self._get_nested_value(record, field) for field in fields]
            return separator.join(filter(None, values))
        
        return ''
    
    def _apply_transform(self, record, config):
        transform = config['transform']
        
        if transform == 'construct_doi':
            prefix = config.get('prefix', '10.5555/')
            source_value = self._get_nested_value(record, config.get('source_field', ''))
            return f"{prefix}{source_value}" if source_value else ''
        
        elif transform == 'construct_url':
            prefix = config.get('prefix', 'https://example.org/')
            source_value = self._get_nested_value(record, config.get('source_field', ''))
            return f"{prefix}{source_value}" if source_value else ''
        
        elif transform == 'format_date':
            source_value = self._get_nested_value(record, config.get('source_field', ''))
            if source_value:
                input_format = config.get('input_format')
                output_format = config.get('output_format', '%Y-%m-%d')
                
                if input_format:
                    try:
                        dt = datetime.strptime(str(source_value), input_format)
                        return dt.strftime(output_format)
                    except ValueError:
                        pass
                
                try:
                    year = int(source_value)
                    return f"{year}-01-01"
                except ValueError:
                    return str(source_value)
            return ''
        
        return ''

    # TODO: Partial implementation
    def _get_country_code(self, country_name):
        country_map = {
            'CANADA': 'CA',
            'Canada': 'CA',
            'UNITED STATES': 'US',
            'United States': 'US',
            'USA': 'US',
            'FRANCE': 'FR',
            'France': 'FR',
            'GERMANY': 'DE',
            'Germany': 'DE',
            'UNITED KINGDOM': 'GB',
            'United Kingdom': 'GB',
            'UK': 'GB',
            'NETHERLANDS': 'NL',
            'Netherlands': 'NL',
            'Nederland': 'NL',
        }
        return country_map.get(country_name, None)
    
    def _get_nested_value(self, obj, path):
        if not path:
            return None
        
        keys = path.split('.')
        value = obj
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    def _process_complex_investigators(self, record, investigators, complex_key):
        complex_config = self.config.get('complex_fields', {}).get(complex_key)
        if not complex_config:
            return
        
        source_field = complex_config.get('source')
        members = self._get_nested_value(record, source_field)
        
        if not isinstance(members, list):
            return
        
        priority_roles = complex_config.get('priority_roles', [])
        
        lead_investigator = None
        for role in priority_roles:
            for member in members:
                if member.get('role') == role:
                    lead_investigator = member
                    break
            if lead_investigator:
                break
        
        if not lead_investigator:
            if members:
                lead_investigator = members[0]
            else:
                return
        
        person = ET.SubElement(investigators, 'person')
        person.set('role', 'lead_investigator')
        
        fields_config = complex_config.get('fields', {})
        
        if 'first_name' in fields_config:
            first_name_field = fields_config['first_name']
            first_name = lead_investigator.get(first_name_field, '')
            if first_name:
                given_name = ET.SubElement(person, 'givenName')
                given_name.text = first_name
        
        if 'last_name' in fields_config:
            last_name_field = fields_config['last_name']
            last_name = lead_investigator.get(last_name_field, '')
            if last_name:
                family_name = ET.SubElement(person, 'familyName')
                family_name.text = last_name
        
        if 'organisation' in fields_config:
            org_field = fields_config['organisation']
            org = lead_investigator.get(org_field, '')
            if org:
                affiliation = ET.SubElement(person, 'affiliation')
                institution = ET.SubElement(affiliation, 'institution')
                org_parts = org.split('||')
                institution.text = org_parts[0].strip()
                
                country = fields_config.get('country', '')
                if country.startswith('_literal:'):
                    country_code = country.replace('_literal:', '')
                    institution.set('country', country_code)
        
        if 'orcid' in fields_config:
            orcid_field = fields_config['orcid']
            orcid = lead_investigator.get(orcid_field, '')
            if orcid and orcid != 'https://orcid.org/-':
                import re
                orcid_pattern = r'^https://orcid\.org/[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[X0-9]{1}$'
                if re.match(orcid_pattern, orcid):
                    orcid_elem = ET.SubElement(person, 'ORCID')
                    orcid_elem.text = orcid
                elif 'orcid.org/' in orcid:
                    orcid_id = orcid.split('orcid.org/')[-1]
                    orcid_digits = re.sub(r'[^0-9X]', '', orcid_id.upper())
                    if len(orcid_digits) == 16:
                        formatted_orcid = f"https://orcid.org/{orcid_digits[0:4]}-{orcid_digits[4:8]}-{orcid_digits[8:12]}-{orcid_digits[12:16]}"
                        if re.match(orcid_pattern, formatted_orcid):
                            orcid_elem = ET.SubElement(person, 'ORCID')
                            orcid_elem.text = formatted_orcid
    
    def _write_xml(self, root, output_path):
        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')
        
        with open(output_path, 'wb') as f:
            tree.write(f, encoding='utf-8', xml_declaration=True)
        
        logging.info(f"XML output written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert grant data from CSV/JSON to Crossref Grant ID XML format with related works support'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='Path to the source data file (CSV or JSON)'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Path for the generated output XML file'
    )
    parser.add_argument(
        '--config',
        required=True,
        help='Path to the YAML configuration file'
    )
    parser.add_argument(
        '--related-works',
        nargs='+',
        help='Path(s) to related works data files (CSV or JSON)'
    )
    parser.add_argument(
        '--log',
        required=False,
        help='Path to a log file (optional)'
    )
    
    args = parser.parse_args()
    
    try:
        converter = EnhancedGrantConverter(args.config, args.log)
        converter.convert(args.input, args.output, args.related_works)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()