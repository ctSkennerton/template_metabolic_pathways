#!/usr/bin/env python
import xml.etree.ElementTree as ET
import re
import argparse
import csv

ec_re = re.compile(r'([\d-]+\.[\d-]+\.[\d-]+\.[\d-]+)')
pfam_re = re.compile(r'PF\d+(\.\d+)?')
def process_box_name(name):
    ec_part = name[4:]  # remove box- from the start

    # I've encoded multiple EC numbers separated by a | character
    # but illustrator converts that to hex 7C
    if '_x7C_' in ec_part:
        ecs = ec_part.split('_x7C_')
    else:
        ecs = [ec_part]

    for i in range(len(ecs)):
        match = ec_re.search(ecs[i])
        if match:
            ecs[i] = match.group(1)
        else:
            match = pfam_re.search(ecs[i])
            if match:
                ecs[i] = match.group(0)
            else:
                raise ValueError("could not extract EC or Pfam from {}".format(ec_part))

    return ecs


def process_color_file(file_name):
    organism_classes = {}
    colors_to_classes = {}
    css_text = []
    color_class_counter = 1
    with open(file_name) as fp:
        csv_reader = csv.DictReader(fp)
        for row in csv_reader:
            try:
                color_class = colors_to_classes[row['color']]
            except:
                color_class = 'organismType{}'.format(color_class_counter)
                color_class_counter += 1
                colors_to_classes[row['color']] = color_class
                css = '.{}{{fill:{};stroke:#000000;stroke-width:0.4692;stroke-miterlimit:10;}}'.format(color_class, row['color'])
                css_text.append(css)

            organism_classes[row['organism']] = colors_to_classes[row['color']]

    return organism_classes, '\n'.join(css_text)


def process_ec_file(file_name):
    ec_to_organism = {}
    organisms = {}
    lineages = set()
    with open(file_name) as fp:
        csv_reader = csv.DictReader(fp)
        for row in csv_reader:
            organisms[row['organism']] = [0, 0, None]
            lineages.add(row['lineage'])
            try:
                ec_to_organism[row['ec']].append(row['organism'])
            except KeyError:
                ec_to_organism[row['ec']] = [row['organism']]

    lineages = sorted(list(lineages))
    if len(lineages) > 100:
        print("There are more than 100 genomes, truncating")
        lineages = lineages[:100]
    for i, l in enumerate(lineages):
        o = l.split(';')[-1]
        row = i // 10
        column = i % 10
        organisms[o][0] = row
        organisms[o][1] = column

    return ec_to_organism, organisms


def paint_box(box_element, organism):
    """Apply css class to organism box."""
    #  We have the enzyme box element
    #  the children of this group are 10 rows of 10 rect objects.
    #  due to the way that I made the 10x10 gird of boxes we need to hack the
    #  processing now. Basically the last child is visually at the top but the
    #  remaining rows exist in the right order. So first process the last child
    #  then process children 2..n-1.
    #  Second complication is that the rows of rects go from right to left so
    #  we need to reverse their order for more natural left to right
    organism_row = organism[0]
    organism_col = organism[1]
    organism_class = organism[2]
    if organism_row == 0:
        box_row = box_element[-1]
    else:
        box_row = box_element[organism_row - 1]

    box_column = len(box_row) - organism_col - 1
    box_row[box_column].set('class', organism_class)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='template svg file')
    parser.add_argument('-o', '--output', help='output svg file')
    parser.add_argument('-e', '--ec', help='csv file containing three columns: ' \
                        'first is the organism name; second is the EC number; third is the taxonomy string')
    parser.add_argument('-c', '--color', help='csv file containing two columns: ' \
                        'first is the organism name; second is the color')
    args = parser.parse_args()

    organism_classes, css_text = process_color_file(args.color)

    ec_to_organism, organism_positions = process_ec_file(args.ec)
    for k,v in organism_classes.items():
        organism_positions[k][2] = v

    tree = ET.parse(args.input)
    root = tree.getroot()

    root[0].text += css_text

    for o, (row, column, color) in organism_positions.items():
        print('{} {} {}'.format(row + 1, column + 1, o))

    for group in root.iter():
        name = group.get('id')
        if name and 'legend-box' == name:
            for values in organism_positions.values():
                paint_box(group, values)
        if name and 'box-' in name:
            ec_numbers = process_box_name(name)
            organisms_with_ec = []
            for ec in ec_numbers:
                try:
                    organisms_with_ec.extend(ec_to_organism[ec])
                except KeyError:
                    pass
            organisms_with_ec = set(organisms_with_ec)
            for o in organisms_with_ec:
                paint_box(group, organism_positions[o])

    tree.write(args.output)
