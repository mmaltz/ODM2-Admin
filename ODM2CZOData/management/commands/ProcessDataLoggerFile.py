from __future__ import unicode_literals
__author__ = 'leonmi'

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "templatesAndSettings.settings")
from django.db.models import Q
from ODM2CZOData.models import *

import argparse
from django.core.exceptions import ObjectDoesNotExist


from templatesAndSettings.settings import MEDIA_ROOT
from django.db import transaction
from django.db import IntegrityError
#from django.contrib.gis.db import models
import time

import csv
import io

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
import itertools
from django.utils.translation import ugettext as _
#using atomic transaction should improve the speed of loading the data.


#process_datalogger_file(self.dataloggerfileid.dataloggerfilelink,self.dataloggerfileid, self.databeginson, self.columnheaderson)


parser = argparse.ArgumentParser(description='process datalogger file.')
#entered_start_date,entered_end_date,emailAddress,profileResult,selectedMResultSeries

#args = parser.parse_args()
#process_datalogger_file(args.dataloggerfilelink,args.dataloggerfileid,args.databeginson,args.columnheaderson , True)

class Command(BaseCommand):


    def add_arguments(self, parser):
        parser.add_argument('dataloggerfilelink', nargs=1)
        parser.add_argument('dataloggerfileid', nargs=1)
        parser.add_argument('databeginson', nargs=1, type=int)
        parser.add_argument('columnheaderson', nargs=1, type=int)
        parser.add_argument('cmdline', nargs=1, type=bool)
    @transaction.atomic
    def handle(self,*args,**options):#(f,fileid, databeginson,columnheaderson, cmd):
        cmdline = args[4]
        if cmdline:
            file = MEDIA_ROOT + args[0]#f[0]
            fileid = args[1] #fileid[0]
            fileid = Dataloggerfiles.objects.filter(dataloggerfilename=fileid).get()
        else:
            file = MEDIA_ROOT +  args[0].name
            fileid = args[1]

        databeginson = args[2] #int(databeginson[0])
        columnheaderson= args[3] #int(columnheaderson[0])
        try:
            with io.open(file, 'rt', encoding='ascii') as f:
                #reader = csv.reader(f)
                columnsinCSV=None
                reader, reader2 = itertools.tee(csv.reader(f))
                for i in range(0,databeginson):
                    columnsinCSV = len(next(reader2))
                rowColumnMap = list()
                dateTimeColumnNum = -1
                DataloggerfilecolumnSet = Dataloggerfilecolumns.objects.filter(dataloggerfileid=fileid.dataloggerfileid)
                i=0
                numCols=DataloggerfilecolumnSet.count()
                if numCols == 0:
                    raise CommandError(_('This file has no dataloggerfilecolumns associated with it. '), code='noDataloggerfilecolumns')
                if not numCols == columnsinCSV:
                     raise CommandError(_('The number of columns in the '+ str(columnsinCSV) +' csv file do not match the number of'+
                                           ' dataloggerfilecolumns '+ str(numCols) + ' associated with the dataloggerfile in the database. '), code='ColumnMisMatch')
                for row in reader:
                    #map the column objects to the column in the file assumes first row in file contains columnlabel.
                    if i==columnheaderson:

                        for dloggerfileColumns in DataloggerfilecolumnSet:
                            foundColumn=False
                            for j in range(numCols):
                                #raise ValidationError(" in file " + row[j] + " in obj column label "+dloggerfileColumns.columnlabel)
                                if row[j] == dloggerfileColumns.columnlabel:
                                    foundColumn=True
                                    dloggerfileColumns.columnnum = j
                                    rowColumnMap += [dloggerfileColumns]
                            if not foundColumn:
                                 raise CommandError(_('Cannot find a column in the CSV matching the dataloggerfilecolumn '+
                                                         str(dloggerfileColumns.columnlabel) ), code='ColumnMisMatch')
                            #if you didn't find a matching name for this column amoung the dloggerfileColumns raise error

                    elif i >= databeginson:

                        #assume date is first column for the moment
                        try:
                            dateT = time.strptime(row[0],"%m/%d/%Y %H:%M")#'1/1/2013 0:10
                            datestr = time.strftime("%Y-%m-%d %H:%M",dateT)
                        except ValueError:
                            try:
                                dateT = time.strptime(row[0],"%m/%d/%Y %H:%M:%S")#'1/1/2013 0:10
                                datestr = time.strftime("%Y-%m-%d %H:%M:%S",dateT)
                            except ValueError:
                                try:
                                    dateT = time.strptime(row[0],"%Y-%m-%d %H:%M:%S")#'1/1/2013 0:10
                                    datestr = time.strftime("%Y-%m-%d %H:%M:%S",dateT)
                                except ValueError:
                                    dateT = time.strptime(row[0],"%Y-%m-%d %H:%M:%S.%f")#'1/1/2013 0:10
                                    datestr = time.strftime("%Y-%m-%d %H:%M:%S",dateT)
                        #for each column in the data table
                        #raise ValidationError("".join(str(rowColumnMap)))
                        for colnum in rowColumnMap:
                            #x[0] for x in my_tuples
                            #colnum[0] = column number, colnum[1] = dataloggerfilecolumn object
                            if not colnum.columnnum ==0:
                                #raise ValidationError("result: " + str(colnum.resultid) + " datavalue "+
                                                      #str(row[colnum.columnnum])+ " dateTime " + datestr)
                                #thisresultid = colnum.resultid #result.values('resultid')

                                measurementresult = Measurementresults.objects.filter(resultid= colnum.resultid)
                                if  measurementresult.count() == 0:
                                    raise ValidationError(_('No Measurement results for column ' + colnum.columnlabel + ' Add measurement results for'+
                                                      'each column. Both results and measurement results are needed.' ))
                                #only one measurement result is allowed per result
                                value = row[colnum.columnnum]
                                for mresults in measurementresult:
                                    try:
                                        if(value==''):
                                            raise IntegrityError
                                        try:
                                            mrv = Measurementresultvalues.objects.filter(valuedatetime=datestr).filter(resultid=mresults).get()
                                        except ObjectDoesNotExist:
                                            Measurementresultvalues(resultid=mresults
                                                        ,datavalue=row[colnum.columnnum],
                                                        valuedatetime=datestr,valuedatetimeutcoffset=4).save()
                                    except IntegrityError:
                                        pass
                                        #Measurementresultvalues.delete()
                                    #row[0] is this column object
                    i+=1
            Measurementresults.objects.raw("SELECT odm2.\"MeasurementResultValsToResultsCountvalue\"()")

        except IndexError:
            raise ValidationError('encountered a problem with row '+row)

