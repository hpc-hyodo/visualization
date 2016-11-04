#!/usr/bin/python
# -*- coding: utf-8 -*-

import geoip2.database
import MySQLdb
import csv

# データベースの読み込み
reader = geoip2.database.Reader('/usr/local/share/GeoIP/GeoLite2-City.mmdb')

connect = MySQLdb.connect(host = "localhost", db = "macsdb", user = "root",passwd="07140708", charset="utf8")
cursor = connect.cursor()


#sql = "select distinct(inet_ntoa(ip_src)),cc_src  from packet_tcp_160801;"
#sql = "select distinct(inet_ntoa(ip_src)),cc_src  from packet_tcp_161017;"
sql = "select distinct(inet_ntoa(ip_src)),cc_src  from packet_tcp_161020_2;"

cursor.execute(sql)
result = cursor.fetchall()

f = open('geoip2.csv', 'ab')

csvWriter = csv.writer(f)

for row in result:
 listdata = []
 record = reader.city(row[0])
 #print row[0], row[1], record.country.name
 listdata.append(row[0])
 listdata.append(row[1])
 listdata.append(record.country.name)
 csvWriter.writerow(listdata)

f.close()
cursor.close()
connect.close()
