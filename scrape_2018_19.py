import sys
import os
import lxml.etree
from optparse import OptionParser
import operator
import glob
import pandas as pd

parser = OptionParser()
parser.add_option("-i", "--input", dest="input", default="/home/alex/git/ug-scrape-2019/2018_19", help="Input pdf name", metavar="FILE")
parser.add_option("-o", "--output", dest="output", default="./", help="Output path. Default is './'", metavar="FOLDER")
parser.add_option("-d", "--debug", dest="debug", default=False, help="Debug", metavar="BOOLEAN")
(options, args) = parser.parse_args()


def trytext(el):
    textList = []
    text = el.text
    childText = None
    grandchildText = None
    children = el.getchildren()
    childLen = len(children)
    if childLen > 0:
        child = children[0]
        childText = child.text
        grandchildren = child.getchildren()
        grandchildLen = len(grandchildren)
        if grandchildLen > 0:
            grandchild = grandchildren[0]
            grandchildText = grandchild.text
    result = ""
    textList.append(text)
    textList.append(childText)
    textList.append(grandchildText)
    finalList = filter(None, textList)
    result = " ".join(finalList)
    output = result
    if output == "":
        return None
    else:
        return output


def pdftoxml(pdfdata, options):
    """converts pdf file to xml file"""
    # lots of hacky Windows fixes c.f. original
    basename = os.path.basename(pdfdata)
    inputname, _ = os.path.splitext(basename)
    absDir = os.path.dirname(pdfdata)+"/"
    cmd = 'pdftohtml -xml -nodrm -zoom 1.5 -enc UTF-8 -noframes "'
    if options:
        cmd += options
    cmd += pdfdata
    cmd += '" "'
    cmd += absDir
    cmd += inputname+'.xml"'
    cmd += " >/dev/null 2>&1"
    os.system(cmd)
    return absDir+inputname+'.xml'


def main():
    paths = glob.glob(options.input+"/*.pdf")
    dataset = []
    for path in paths:
        basename = os.path.basename(path)
        print("Reading "+basename+"...")
        xmlpath = pdftoxml(path, False)
        recov_parser = lxml.etree.XMLParser(ns_clean=True, recover=True)
        root = lxml.etree.parse(xmlpath, parser=recov_parser).getroot()
        pages = list(root)
        pageLen = len(pages)
        # Cascade these down...
        district = basename[38:-5]
        department = ""
        departments = [
            "Administration",
            "Finance",
            "Statutory Bodies",
            "Production and Marketing",
            "Health",
            "Education",
            "Roads and Engineering",
            "Water",
            "Natural Resources",
            "Community Based Services",
            "Planning",
            "Internal Audit"
        ]
        programme = ""
        output_class = ""
        output = ""
        output_classes = ["01  Higher LG Services", "02  Lower Local Services", "03  Capital Purchases"]
        isTable = False
        tableOnMarker = "B2: Expenditure Details by Programme, Output Class, Output and Item"
        tableOffMarker = "B1: Overview of Workplan Revenues and Expenditures by Source"
        for i in range(0, pageLen):
            page = pages[i]
            elLen = len(page)
            for j in range(0, elLen):
                el = page[j]
                if el.tag == "text":
                    left = int(el.attrib['left'])
                    right = int(el.attrib['left'])+int(el.attrib['width'])
                    top = int(el.attrib['top'])
                    font = el.attrib['font']
                    element_text = trytext(el)
                    if element_text in departments:
                        department = element_text
                    if element_text[:4].isdigit() and not element_text[:5].isdigit() and element_text != "2017-18 contracts":
                        programme = element_text
                    if element_text in output_classes:
                        output_class = element_text
                    if abs(left-57) < 10 and element_text[:6].isdigit() and not element_text[:7].isdigit() and len(element_text) > 6:
                        try:
                            child_tag = el.getchildren()[0].tag
                            if child_tag == "b":
                                output = element_text
                        except:
                            pass
                    if not isTable:
                        if element_text == tableOnMarker:
                            isTable = True
                    else:
                        if element_text == tableOffMarker:
                            isTable = False
                        if font == "4" and len(element_text) > 5 and element_text[:6].isdigit():
                            # Find row by going backwards and forwards...
                            row = []
                            obj = {}
                            obj['text'] = element_text
                            obj['top'] = top
                            obj['left'] = left
                            obj['right'] = right
                            obj['font'] = font
                            row.append(obj)
                            # Backwards
                            prev = el.getprevious()
                            if prev is not None:
                                try:
                                    prevTop = int(prev.attrib['top'])
                                except KeyError:
                                    prevTop = 0
                            else:
                                prevTop = 0
                            while prev is not None and "top" in prev.attrib:
                                obj = {}
                                obj['text'] = trytext(prev)
                                obj['top'] = int(prev.attrib['top'])
                                obj['left'] = int(prev.attrib['left'])
                                obj['right'] = int(prev.attrib['left'])+int(prev.attrib['width'])
                                obj['font'] = int(prev.attrib['font'])
                                if abs(top - prevTop) < 4:
                                    row.append(obj)
                                prev = prev.getprevious()
                                if prev is not None and "top" in prev.attrib:
                                    prevTop = int(prev.attrib['top'])
                                else:
                                    prevTop = 0
                            # Forwards
                            nxt = el.getnext()
                            if nxt is not None and "top" in nxt.attrib:
                                try:
                                    nxtTop = int(nxt.attrib['top'])
                                except KeyError:
                                    nxtTop = 0
                            else:
                                nxtTop = 0
                            while nxt is not None:
                                obj = {}
                                obj['text'] = trytext(nxt)
                                obj['top'] = int(nxt.attrib['top'])
                                obj['left'] = int(nxt.attrib['left'])
                                obj['right'] = int(nxt.attrib['left'])+int(nxt.attrib['width'])
                                obj['font'] = int(nxt.attrib['font'])
                                if abs(top - nxtTop) < 4:
                                    row.append(obj)
                                nxt = nxt.getnext()
                                if nxt is not None and "top" in nxt.attrib:
                                    nxtTop = int(nxt.attrib['top'])
                                else:
                                    nxtTop = 0
                            rowvals = operator.itemgetter('left')
                            row.sort(key=rowvals)
                            if len(row) == 7:
                                meta_data = [district, department, programme, output_class, output]
                                row_data = [item['text'] for item in row]
                                dataset.append(meta_data+row_data)
    header = ["District", "Department", "Programme", "Output class", "Output", "Item", "Approved Budget for FY 2017/18 Total", "Approved Budget Estimates for FY 2018/19 Wage", "Approved Budget Estimates for FY 2018/19 Non Wage", "Approved Budget Estimates for FY 2018/19 Gou Dev", "Approved Budget Estimates for FY 2018/19 Donor", "Approved Budget Estimates for FY 2018/19 Total"]
    df = pd.DataFrame(dataset, columns=header)
    df.to_csv(os.path.join(options.output, "2018-19.csv"), index=False)
    sys.stdout.write("\n")
    print("Done.")

main()
