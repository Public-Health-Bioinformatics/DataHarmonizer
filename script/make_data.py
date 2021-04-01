#
# make_data.py: A script to generate a vocabulary JSON-LD data structure from
# a tabular representation of the vocabulary.
#
# FUTURE: Implement as JSON-LD "@graph" https://json-ld.org/spec/latest/json-ld/
# https://json-ld.org/playground/
#
# Author: Damion Dooley
# 

import csv
import json
import collections
import dpath.util

r_filename = 'data.tsv';
w_filename = 'data.js';
DATA = [];
FIELD_INDEX = {} # [field] -> field object in DATA
CHOICE_INDEX = {} # [choice] -> parent choice or field object in DATA
section = None;
reference_html = ''; # Content of a report that details section fields
search_root = '/';

# For a column in input spreadsheet named EXPORT_[EXPORT_FORMAT], add to
# dictionary structure (field) a field.exportField datastructure containing
# transforms to each EXPORT_FORMAT value, or column and value combination.
# e.g.
#	"Confusion": {
#		"exportField": {
#			"NML_LIMS": [
#				{
#					"field": "HC_SYMPTOMS",
#                   "value": "CONFUSION"
#               }
#            ],
#        },
#		 ... other child terms
#
# exportField: {[PREFIX]:[{"field":[value],"value":[value transform],...]}
# input spreadsheet EXPORT_[EXPORT_FORMAT] is coded as:
#    [column1]:[value];[column2]:[value]; // multiple column targets
#    or [value];[value]; // default column target
#
# @param Array<String> EXPORT_FORMAT list of export formats to search for
# @param Dict field Dictionary of vocabulary field details
# @param Dict row containing all field data
# @return Dict field modified

def export_fields (EXPORT_FORMAT, field, row, as_field = False):
	if len(EXPORT_FORMAT) > 0:
		formats = {};
		for export_field in EXPORT_FORMAT:
			prefix = export_field[7:]; # Get rid of "EXPORT_" part.
			if row[export_field] == None:
				print ('Error: ', export_field, 'not found in row with label [',row['name'], ']. Malformed text in row?');
				continue;

			# An export field may have one or more [field name]:[field value] transforms, separated by ";"
			for item in row[export_field].split(";"):
				item = item.strip();
				if len(item) > 0:
					conversion = {};
					# We have a transform of some kind
					if not prefix in formats:
						formats[prefix] = [];

					# A colon indicates a different target field is in play
					if ":" in item:
						binding = item.split(":",1);
						binding[0] = binding[0].strip();
						binding[1] = binding[1].strip();
						if binding[0] > '':
							conversion['field'] = binding[0];
						if binding[1] > '':
							conversion['value'] = binding[1];
						else:
							# A single ":" value enables clearing out of a value.
							conversion['value'] = '';

					# No colon
					elif as_field == True:
						conversion['field'] = item;
					else:
						conversion['value'] = item;	

					formats[prefix].append(conversion);

		if formats: # Only if some keys have been added.
			field['exportField'] = formats; # Like skos:exactMatch

'''
Creates section / field / field choice data structure directly off of tabular
data captured from a vocabulary spreadsheet.
'''
with open(r_filename) as tsvfile:
	reader = csv.DictReader(tsvfile, dialect='excel-tab');

	EXPORT_FORMAT = [];
	firstrow = True;
    # Row has keys 'identifier' 'parent class' 'name' 'dataType' 'requirement' ...	
	for row in reader:

		# Get list of exportable fields, each of which has "EXPORT_" prefixed into it.
		if (firstrow):
			firstrow = False;
			for key in row:
				if key[0:7] == 'EXPORT_':
					EXPORT_FORMAT.append(key);

		# Skip second row (a robot directive row)
		if len(row['identifier']) == 0 or row['identifier'] != 'ID':
			label = row['name'].strip();
			if label > '':
				if row['parent class'] == '': 
					# Define a section of fields
					section = {'name': label, 'children': []}
					DATA.append(section);
					reference_html += '''
						<tr class="section">
							<td colspan="5"><h3>{name}</h3></td>
						</tr>
						'''.format(**section);

				else:
					# Find parent class in DATA or in index of its fields
					parent_label = row['parent class'].strip();
					section = next((x for x in DATA if x['name'].strip() == parent_label), None);
					if section:
						# Convert data status into array of values.
						if len(row['statusEnumeration'])>0:
							statusEnumeration = list(map(lambda x: x.strip(), row['statusEnumeration'].split(';')));
						else:
							statusEnumeration = None;


						# context= "https://json-ld.org/contexts/person.jsonld"

						context = {
							'version':		'http://schema.org/version', # Property
							'identifier': 	'http://schema.org/identifier', # Property
							'name': 		'http://schema.org/name', 		# Property
							'description':	'http://schema.org/description', # Property
							'dataType':		'http://schema.org/DataType', 	# Data Type
							'minValue':		'http://schema.org/minValue',	# Property
							'maxValue':		'http://schema.org/maxValue',	# Property
							'statusEnumeration': 'https://schema.org/StatusEnumeration', # Intangible
							'isBasedOn':	'https://schema.org/isBasedOn',	# Property
							'itemList':		'https://schema.org/ItemList',	# Intangible
							'valueRequired':'https://schema.org/valueRequired', # Property

							#Custom fields
							'exportField':		'https://schema.org/ItemList',	# Intangible

							#'':			'https://schema.org/codeValue',

						}
						# A schema:propertyValueSpecification
						field = {
							'identifier': 		row['identifier'],	# was ontology_id
							'name':   			label, 				# was fieldName
							'dataType':			row['dataType'], 	# was datatype
							'isBasedOn': 		row['isBasedOn'],	# was source
							'statusEnumeration': statusEnumeration,	# was dataStatus
							'minValue': 		row['minValue'],	# was xs:minInclusive
							'maxValue': 		row['maxValue'],	# was xs:maxInclusive 
							'description': 		row['description'],
							'valueRequired': 	row['valueRequired'], # was requirement

							# These are not schema.org terms
							'capitalize': 		row['capitalize'],
							'guidance':			row['guidance'],
							'examples':			row['examples']
						}
						
						export_fields (EXPORT_FORMAT, field, row, True);

						reference_html += '''
						<tr>
							<td class="label">{name}</td>
							<td>{description}</td>
							<td>{guidance}</td>
							<td>{examples}</td>
							<td>{statusEnumeration}</td>
						</tr>\n
						'''.format(**field);

						if row['dataType'] == 'select' or row['dataType'] == 'multiple':
							# Use ordered dict to keeps additions in order:
							choice = collections.OrderedDict(); 
							# Top level case-sensitive field index, curators must be exact
							CHOICE_INDEX[label] = choice; 
							field['itemList'] = choice;

						section['children'].append(field)
						FIELD_INDEX[label.lower()] = field;

					# Item isn't a section or field, so it must be a select field choice
					else:
						parent_label_lc = parent_label.lower();
						# Find the choice's parent in FIELD_INDEX, if any
						# If parent in CHOICE_INDEX, then add it

						if parent_label_lc in FIELD_INDEX:
							# Always use most recently referenced field for a
							# vocabulary search root in CHOICE_INDEX
							if search_root != parent_label:
								search_root = parent_label;
								print ('vocabulary field:', parent_label);

							if not 'itemList' in FIELD_INDEX[parent_label_lc]:
								print ("error: field ",parent_label, "not marked as select or multiple but it has child term", label);
							else:
								# Basically top-level entries in field_map:
								choice = collections.OrderedDict();
								FIELD_INDEX[parent_label_lc]['itemList'][label] = choice;
	
								# Parent_label is top level field name:
								CHOICE_INDEX[parent_label][label] = choice;

								export_fields(EXPORT_FORMAT, choice, row);

						else:
							# If it isn't a field then it is a choice within a 
							# field's vocabulary.  Searches only against 
							# current field's vocabulary. In case a '/' exists
							# in parent label switches that to a wildcard.
							try:
								result = dpath.util.get(CHOICE_INDEX, '/' + search_root +'/**/' + parent_label.replace('/','?'), separator='/');
								choice = collections.OrderedDict(); # new child {}
								if not 'itemList' in result:
									result['itemList'] = {};
								result['itemList'][label] = choice; 
								export_fields(EXPORT_FORMAT, choice, row);
							except:
								print ("Error: parent class ", parent_label, "doesn't exist as section or field for term. Make sure parent term is trimmed of whitespace.", label);
								pass


reference_html += '</table>\n';

with open(w_filename, 'w') as output_handle:
	# DO NOT USE sort_keys=True because this overrides OrderedDict() sort order.
	output_handle.write("var DATA = " + json.dumps(DATA, sort_keys = False, indent = 2, separators = (',', ': ')));
	#output_handle.write("var EXPORT_FIELD_MAP = " + json.dumps(export_field_map, sort_keys = False, indent = 2, separators = (',', ': ')));

with open('reference_template.html', 'r') as template_handle:
	template = template_handle.read();

	with open('reference.html', 'w') as output_handle:
		output_handle.write(template.format( **{'html': reference_html} ));

