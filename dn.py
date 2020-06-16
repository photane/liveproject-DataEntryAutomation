from pathlib import Path
import configparser
from abc import ABC, abstractmethod
import pdfplumber
import re
from collections import OrderedDict
import sys

#utility functions

def getfiles(directory, suffix='.*'):
  """Returns list of Path objects contained within directory and its subdirectories

  Parameters:
    directory (str or Path OBJECT): Topmost directory to search
    suffix (str): filter by desired suffix (begin with '.'). If not specified, return all files.
  Returns:
    list of Path objects
  """
  path=Path(directory)
  fileslist = list(path.rglob(f'*{suffix}'))
  return fileslist

def getPDFfiles(directory):
  return getfiles(directory, '.pdf')
  
def getinifiles(directory):
  return getfiles(directory, '.ini')

def str_to_class(str):
    return getattr(sys.modules[__name__], str)
    
#ini functions and constants

INIKEY = 'fields'
EDITMARKER = '|e'
#SELECTMARKER = '|s' -- not used since only two formfield types
CONCAT = -2

EDITTYPE = 'e'
SELECTTYPE = 's'

FORMSCATALOG = {}

#iniparser factory
def iniparserfactory():
  iniparser = configparser.ConfigParser(allow_no_value=True)
  iniparser.optionxform = str  #maintain key case, remove for lower case 
  return iniparser  

def readfieldsfromini(file):
  fields = {}
  fields['textfields'] = {}
  fields['formfields'] = {}
  #iniparser =iniparserfactory()
  iniparser = readinifile(file)
  for field in iniparser['fields']:
    value=iniparser['fields'][field]
    storefield(fields, field, value)
  return fields
  
def readinifile(file):
  iniparser = iniparserfactory()
  iniparser.read(file)
  return iniparser 

def storefield(fields, field, value):
  if value is None:
    formfield = parseffield(field)
    if field.endswith(EDITMARKER):
      fields['formfields'][formfield] = EDITTYPE
    else:
      fields['formfields'][formfield] = SELECTTYPE
  else:
      fields['textfields'][field] = value
  return
  
def parseffield(field):
  return field[0:CONCAT]
  
#PDF Forms Classes and Utilities

class PDFParser:
  parser = pdfplumber
  text = None
  formdata = None
  
  @classmethod
  def parse(cls, pdffile):
    with cls.parser.open(pdffile) as pdf:
      cls.text = pdf.pages[0].extract_text()
      cls.formdata = {}
      fields = pdf.doc.catalog["AcroForm"].resolve()["Fields"]
      for objref in fields:
        field=objref.resolve()
        field_name = field.get("T").decode()
        field_value = field.get("V")
        if field_value is not None:
          field_value = field_value.decode()
        cls.formdata[field_name] = field_value   

class AbstractPDFForm(ABC):
    name = None
    textfields = None
    formfields = None
    
    @staticmethod
    @abstractmethod
    def isForm(parser):
      pass
      
    @classmethod   
    def initialize(cls,inifieldscatalog):
      cls.textfields = inifieldscatalog['textfields']
      cls.formfields = inifieldscatalog['formfields']
      #cls.pdfparser = pdfparser
      
    @classmethod
    def extractDataFromParser(cls, parser):
      formdata = cls._readPDFFormFields(parser.formdata)
      textdata = cls._readPDFTextFields(parser.text)
      return {**textdata, **formdata}
      
    # @classmethod
    # def _parsePDF(cls, pdffile):
      # pdf= cls.pdfparser.open(pdffile)
      # return {pdf.formdata, pdf.textdata}
    
    @classmethod
    def _readPDFFormFields(cls, pdfformdata):
      formdata = {}
      for field in cls.formfields:
        formdata[field] = pdfformdata.get(field)
      return formdata
      
    @staticmethod     
    @abstractmethod
    def _readPDFTextFields(pdftext):
      pass
    
    @classmethod
    def _generateDataDict(cls, pdfformdata, pdftext):
      formdata=cls._readPDFFormFields(pdfformdata)
      textdata=cls_readPDFTextFields(pdftext)
      return {**textdata, **formdata}   #concatenates dictionaries
        
class PDFForm_211559_050(AbstractPDFForm):
  name = '211559-050'
  
  @staticmethod
  def isForm(parser):
    #text = pdf.pages[0].extract_text()
    return parser.text.find('TALLER') > -1
    
  @staticmethod     
  def _readPDFTextFields(pdftext):
      return {}

    
class PDFForm_1900070(AbstractPDFForm):
  name='1900070'
 
  @staticmethod
  def isForm(parser):
    #text = pdf.pages[0].extract_text()
    return parser.text.find('TALLER') == -1
    
  @staticmethod
  def _readPDFTextFields(pdftext):
    textdata = {}
    textregex = r"ALBARAN.*[\r\n]*([\d]+-[\d]+-[\d]+) (\w*)" #([\w]+)"
    textcapturesmap = {'DeliveryNote' : 2, 'DeliveryDate' : 1}
    fielddata= re.search(textregex, pdftext)
    for field in textcapturesmap:
      textdata[field] = fielddata.group(textcapturesmap[field])
    return textdata
    
#forms_catalog = {'211559-050' : PDFForm_211559_050, '1900070': PDFForm_1900070}

def identifyform(formscatalog, parser):

  for form in formscatalog.values():
    if form.isForm(parser):
      return form 
  return None  #raise exception here instead
  
def createscript(formsdata):
  for iter in formsdata:
    iterstr = str(iter)
    formtype = formsdata[iter]["formtype"]
    filename = formtype + "_" + iterstr + ".txt"
    formdata = formsdata[iter]['data']
    pdfform = FORMSCATALOG[formtype]
 
    fieldobjects = genscriptdataobjects(pdfform, formdata) 
    writescript(filename, fieldobjects)
   
def genscriptdataobjects(pdfform, formdata):

  rows = []
  rows.append('\nlet formdata = [\n')
  
  textfields = pdfform.textfields
  formfields = pdfform.formfields
  

  for textfield in textfields:
    row = '{field: "' + textfield + '", fieldtype: "e", value: "' + formdata[textfield] + '"},\n'
    rows.append(row)
    
  for formfield in formfields:
    row = row = '{field: "' + formfield + '", fieldtype: "' + formfields[formfield] + '", value: "' + formdata[formfield] + '"},\n'
    rows.append(row)
  rows.append(']\n')
  return rows


def writescript(filename, fieldobjects):
  s1 ='''const S = 's'

function processfield(data) {
  formfield = document.getElementById(data.field)
  if (data.field == S) {
    processselectfield(formfield, data.value)
  } else {                    //otherwise text data
    formfield.value = data.value
  }
}

function processselectfield(field, value) {
  for (var i = 0; i < field.options.length; i++) {
    if (field.options[i].text == value) {
      field.options[i].selected = true;
      return; 
    }
  }
}'''

  s3 = '''for (data of formdata) {
  processfield(data)
}'''
  try:
    f = open(filename, "w")
    f.write(s1)
    f.writelines(fieldobjects)
    f.write(s3)
    f.close()
  except BaseException as msg:
    print('Write Error occurred: ' + str(msg))
      
def execute():
  try:

    appconfig=readinifile("app.ini")
    ini_dir = appconfig['dirs']['inidir']
    data_dir = appconfig['dirs']['datadir']

    forms = appconfig['forms']
    
    #formscatalog = {}
    for formname in forms:
      classname = forms[formname]
      FORMSCATALOG[formname] = str_to_class(classname)

    parser = PDFParser

    #initialize form classes from ini file

    for formname in FORMSCATALOG:
      formini = ini_dir+formname+'.ini'
      formfieldscatalog = readfieldsfromini(formini)
      formclass = FORMSCATALOG[formname]
      formclass.initialize(formfieldscatalog)
      
    #retrieve PDFs

    iter = 1
    datadict = OrderedDict()

    pdffiles = getPDFfiles(data_dir)
    for pdffile in pdffiles:
      parser.parse(pdffile)
      form = identifyform(FORMSCATALOG, parser)
      formdata = form.extractDataFromParser(parser)
      datastore = {'file': pdffile.resolve(), 'formtype': form.name, 'data' : formdata}
      datadict[iter] = datastore
      iter = iter + 1
      
    return datadict
    
  except BaseException as msg:
    print('Execute Error occurred: ' + str(msg))

  
if __name__ == '__main__':
  data = execute()
  createscript(data)
  
  
