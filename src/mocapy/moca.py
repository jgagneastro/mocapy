#Import packages

# Create environment
#python -m venv mocapy-env
#source mocapy-env/bin/activate

from sqlalchemy import create_engine
import pandas as pd
import numpy as np
from urllib.parse import quote_plus as urlquote #This is useful to avoid problems with special characters in passwords
import os
import uuid

__author__ = 'Jonathan Gagne'
__email__ = 'jonathan.gagne@astro.umontreal.ca'

__all__ = ["MocaEngine"]

#Hack pandas to make it upload temporary SQL tables, inspired from https://gist.github.com/alecxe/44682f79b18f0c82a99c
from pandas.io.sql import SQLTable, pandasSQL_builder, get_engine, _gt14
class TemporaryTable(SQLTable):
	#Override the _execute_create method such that the table that is created has the correct TEMPORARY prefix
	def _execute_create(self):
		# Inserting table into database, add to MetaData object
		if _gt14():
			self.table = self.table.to_metadata(self.pd_sql.meta)
		else:
			self.table = self.table.tometadata(self.pd_sql.meta)
		
		# allow creation of temporary tables
		self.table._prefixes.append('TEMPORARY')

		self.table.create(bind=self.pd_sql.connectable)

class MocaEngine:

	#Initialize the connection parameters
	def __init__(self):

		#Default connection parameters in the absence of environment variables
		default_host = '104.248.106.21'
		default_username = 'public'
		default_password = 'z@nUg_2h7_%?31y88'
		default_dbname = 'mocadb'

		#Read connection information for the database
		env_username = os.environ.get('MOCA_USERNAME')
		if env_username is not None:
			self.moca_username = env_username
		else:
			self.moca_username = default_username

		env_password = os.environ.get('MOCA_PASSWORD')
		if env_password is not None:
			self.moca_password = env_password
		else:
			self.moca_password = default_password

		env_dbname = os.environ.get('MOCA_DBNAME')
		if env_dbname is not None:
			self.moca_dbname = env_dbname
		else:
			self.moca_dbname = default_dbname

		env_host = os.environ.get('MOCA_HOST')
		if env_host is not None:
			self.moca_host = env_host
		else:
			self.moca_host = default_host

		#Prepare the database engine
		#print('mysql+pymysql://'+self.moca_username+':'+urlquote(self.moca_password)+'@'+self.moca_host+'/'+self.moca_dbname)
		#.replace('@','%40').replace('%21','$')
		self.engine = create_engine('mysql+pymysql://'+self.moca_username+':'+urlquote(self.moca_password)+'@'+self.moca_host+'/'+self.moca_dbname)

		#By default mocapy has no active connection
		self.connection = None

		#By default mocapy has no active raw connection
		self.raw_connection = None
		#self.tmptablename = 'tmp_table_'+str(uuid.uuid4()).replace('-','')

	def query(self,sql_query,tmp_table=None):
		
		#Connect to the database if needed, and run the SQL query
		df = None
		if self.connection is not None:
			print(' Using a SQL connection maintained outside of the mocapy package')
			active_connection=self.connection
		
		if self.connection is None:
			active_connection=self.engine.connect()

		#with self.engine.connect() as connection:
			
		#Upload a temporary table if needed
		if tmp_table is not None:
			
			#Determine a temporary table name for the database
			tmptablename = 'tmp_table_'+str(uuid.uuid4()).replace('-','')

			#Verify that the temporary table is a DataFrame
			assert isinstance(tmp_table,pd.DataFrame), "The temporary table tmp_table passed to MocaEngine.query() must be a pandas DataFrame"

			pandas_engine = pandasSQL_builder(active_connection)

			#Create a tenporary table
			table = TemporaryTable(tmptablename, pandas_engine, frame=tmp_table, if_exists="append")
			table.create()
				
			#Insert records in temporary table
			sql_engine = get_engine("auto")
			total_inserted = sql_engine.insert_records(table=table,con=active_connection,frame=tmp_table,name=tmptablename)
			
			sql_query = sql_query.replace('tmp_table',tmptablename)
			#Testing that the temporary table exists
			#d2 = pd.read_sql("SELECT * FROM tmp_table;",active_connection)
			#print(d2)


		#Execute the query
		df = pd.read_sql(sql_query, active_connection)
		
		#Close the connection unless it is maintained outside of this method
		if self.connection is None:
			active_connection.close()

		return(df)

	#This generally requires admin privileges
	def execute(self,sql_query,tmp_table=None):
		
		#Connect to the database if needed, and run the SQL query
		if self.connection is not None:
			print(' Using a SQL connection maintained outside of the mocapy package')
			active_connection=self.connection
		
		if self.connection is None:
			active_connection=self.engine.connect()

		#Upload a temporary table if needed
		if tmp_table is not None:
			
			#Determine a temporary table name for the database
			tmptablename = 'tmp_table_'+str(uuid.uuid4()).replace('-','')

			#Verify that the temporary table is a DataFrame
			assert isinstance(tmp_table,pd.DataFrame), "The temporary table tmp_table passed to MocaEngine.query() must be a pandas DataFrame"

			pandas_engine = pandasSQL_builder(active_connection)

			#Create a tenporary table
			table = TemporaryTable(tmptablename, pandas_engine, frame=tmp_table, if_exists="append")
			table.create()
				
			#Insert records in temporary table
			sql_engine = get_engine("auto")
			total_inserted = sql_engine.insert_records(table=table,con=active_connection,frame=tmp_table,name=tmptablename)

			sql_query = sql_query.replace('tmp_table',tmptablename)

		#Connect to the database and run the SQL execution statement
		#with self.engine.connect() as connection:
		
		#Split individual query into an array of queries
		queries = sql_query.split(';')
		for subq in queries:
			if subq.strip() == '':
				continue
			rs = active_connection.execute(subq.strip()+';')

		#Close the connection unless it is maintained outside of this method
		active_connection.commit()
		if self.connection is None:
			active_connection.close()
		
		return(rs)

	#This generally requires admin privileges
	def call(self,sql_procedure):
		
		#Connect to the database if needed, and run the SQL query
		#CALL requires a raw connection
		if self.raw_connection is not None:
			print(' Using a SQL raw_connection maintained outside of the mocapy package')
			active_connection=self.raw_connection
		
		if self.connection is None:
			active_connection=self.engine.raw_connection()
		
		cursor = active_connection.cursor()
		rs = cursor.callproc(sql_procedure)
		#This obscure step is required for changes to be reflected in the DB
		active_connection.commit()
		if self.raw_connection is None:
			active_connection.close()
		
		return(rs[0].fetchall())

#import pdb; pdb.set_trace()