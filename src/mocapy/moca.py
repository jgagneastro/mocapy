#Import packages

# Create environment
#python -m venv mocapy-env
#source mocapy-env/bin/activate

from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from urllib.parse import quote_plus as urlquote #This is useful to avoid problems with special characters in passwords
import os
import uuid

__author__ = 'Jonathan Gagne'
__email__ = 'jonathan.gagne@astro.umontreal.ca'

__all__ = ["MocaEngine"]

#This is not required anymore
#Hack pandas to make it upload temporary SQL tables, inspired from https://gist.github.com/alecxe/44682f79b18f0c82a99c
from pandas.io.sql import SQLTable, pandasSQL_builder, get_engine

class TemporaryTable(SQLTable):
	#Override the _execute_create method such that the table that is created has the correct TEMPORARY prefix
	def _execute_create(self):
		# Inserting table into database, add to MetaData object
		self.table = self.table.to_metadata(self.pd_sql.meta)
		
		# allow creation of temporary tables
		self.table._prefixes.append('TEMPORARY')

		self.table.create(bind=self.pd_sql.con)

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
			#tmptablename = 'tmp_table'

			#Verify that the temporary table is a DataFrame
			assert isinstance(tmp_table,pd.DataFrame), "The temporary table tmp_table passed to MocaEngine.query() must be a pandas DataFrame"

			pandas_engine = pandasSQL_builder(active_connection)

			#Delete temporary table
			#self.execute("DROP TEMPORARY TABLE IF EXISTS "+tmptablename)

			#Create a temporary table
			table = TemporaryTable(tmptablename, pandas_engine, frame=tmp_table, if_exists="append", index=False)
			table.create()
				
			#Insert records in temporary table
			sql_engine = get_engine("auto")
			total_inserted = sql_engine.insert_records(table=table,con=active_connection,frame=tmp_table,name=tmptablename)
			
			sql_query = sql_query.replace('tmp_table',tmptablename)
			#Testing that the temporary table exists
			#d2 = pd.read_sql("SELECT * FROM tmp_table;",active_connection)
			#print(d2)

		#Replace problematic cases of % characters
		sql_query = sql_query.replace("%","%%")

		#Execute the query
		df = pd.read_sql(text(sql_query), active_connection, coerce_float=False)
		
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
			#tmptablename = 'tmp_table'

			#Verify that the temporary table is a DataFrame
			assert isinstance(tmp_table,pd.DataFrame), "The temporary table tmp_table passed to MocaEngine.query() must be a pandas DataFrame"

			pandas_engine = pandasSQL_builder(active_connection)

			#Delete temporary table
			#self.execute("DROP TEMPORARY TABLE IF EXISTS "+tmptablename)

			#Create a temporary table
			table = TemporaryTable(tmptablename, pandas_engine, frame=tmp_table, if_exists="append", index=False)
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
			#Replace problematic cases of % characters
			subq = subq.replace("%","%%")
			rs = active_connection.execute(text(subq.strip()+';'))

		#Commit changes to the db
		active_connection.commit()

		#Close the connection unless it is maintained outside of this method
		#active_connection.commit()#This appears to generate an error ?
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
		
		return("Done")
	
class MocaViz:

	def __init__(self):
		pass

	def get_cmd(self, m1m2, M, em1m2, eM, m1_type = 'j_any', m2_type = 'k_any', M_type = 'j_any', spt = False, young_seq = False, ref_err = False, xmin = None, xmax = None, ymin = None, ymax = None, path = None, con = None) :

		'''Variables :
		m1m2, em1m2 : band 1 minus band 2 (x-axis) and uncertainties
		M, eM : absolute magnitude of y-axis band and uncertainties
		m1_type, m2_type, M_type : names of band (j_any, h_any, k_any or any specific band in the moca_photometry_systems table) where M is the band on the y-axis
		spt : True or False, to plot the spectral types of the field BD ref sequence (default = False)
		young_field : True or False, to plot the intermediate and low gravity substellar objs over the field BD ref sequence (default = False)
		ref_err : True or False, to plot the errorbars of the field BD ref sequence (default = False)
		xmin, xmax ; x-axis range (default = None)
		ymin, ymax : y-axis range (default = None)
		path : path of figure saving (default = None)
		con : connection to the database (default = None, public connection)'''

		#Build connection with database :
		moca = MocaEngine()
		if con is not None :
			moca.connection = con

		list_bands = moca.query('SELECT moca_psid, name FROM moca_photometry_systems') #accessible bands

		def find_bands(m_type) :

			if m_type not in list_bands['moca_psid'].values :
				if m_type == 'j_any' : bmag_type = 'moca_psid LIKE "%_jmag"'; m_type_final = 'J'
				if m_type == 'h_any' : bmag_type = 'moca_psid LIKE "%_hmag"'; m_type_final = 'H'
				if m_type == 'k_any' : bmag_type = '(moca_psid LIKE "%_kmag" OR moca_psid LIKE "%_ksmag")'; m_type_final = 'K'

			else :
				bmag_type = 'moca_psid LIKE "'+str(m_type)+'"'
				i_m_type = np.where(list_bands['moca_psid'] == m_type)[0]
				m_type_final = list_bands.at[i_m_type[0], 'name']

			return bmag_type, m_type_final
		
		#find the requested magnitude bands :
		b1mag_type, m1_type = find_bands(m1_type)
		b2mag_type, m2_type = find_bands(m2_type)
		Bmag_type, M_type = find_bands(M_type)
	
		#Get the reference plot of all field brown dwarfs from the database :
		df = None
		df = moca.query("SELECT mo.designation, spt.spectral_type, spt.spectral_type_number AS sptn, cdist.dmod, cdist.dmod_unc AS edmod, b1mags.magnitude AS b1mag, b1mags.magnitude_unc AS\
		eb1mag, b2mags.magnitude AS b2mag, b2mags.magnitude_unc AS eb2mag, Bmags.magnitude AS Bmag, Bmags.magnitude_unc AS eBmag, b1mags.nn AS nn1, b2mags. nn AS nn2, Bmags.nn AS nn3\
			FROM\
				cdata_spectral_types spt\
				JOIN moca_objects mo USING (moca_oid)\
				LEFT JOIN cdata_distances cdist USING (moca_oid)\
				JOIN (SELECT * FROM \
					(SELECT moca_oid, magnitude, magnitude_unc, ROW_NUMBER() OVER(PARTITION BY moca_oid ORDER BY magnitude_unc ASC) AS nn FROM cdata_photometry WHERE "+str(b1mag_type)+" AND \
						adopted = 1) subq1 WHERE subq1.nn = 1) AS b1mags ON (b1mags.moca_oid = spt.moca_oid)\
				JOIN (SELECT * FROM \
					(SELECT moca_oid, magnitude, magnitude_unc, ROW_NUMBER() OVER(PARTITION BY moca_oid ORDER BY magnitude_unc ASC) AS nn FROM cdata_photometry WHERE "+str(b2mag_type)+" AND \
						adopted = 1) subq2 WHERE subq2.nn = 1) AS b2mags ON (b2mags.moca_oid = spt.moca_oid)\
				JOIN (SELECT * FROM \
					(SELECT moca_oid, magnitude, magnitude_unc, ROW_NUMBER() OVER(PARTITION BY moca_oid ORDER BY magnitude_unc ASC) AS nn FROM cdata_photometry WHERE "+str(Bmag_type)+" AND \
						adopted = 1) subq3 WHERE subq3.nn = 1) AS Bmags ON (Bmags.moca_oid = spt.moca_oid)\
			WHERE\
				spt.spectral_type_unc <= 0.6\
				AND spt.spectral_type_number >= 6\
				AND spt.complete_spectral_type NOT LIKE '%:%'\
				AND(spt.gravity_class IS NULL\
					OR spt.gravity_class = 'α')\
				AND spt.photometric_estimate = 0\
				AND(spt.luminosity_class IS NULL\
					OR spt.luminosity_class = 'V')\
				AND spt.adopted = 1\
				AND spt.complete_spectral_type NOT LIKE '%pec%'\
				AND spt.complete_spectral_type NOT LIKE '%+%'\
				AND spt.complete_spectral_type NOT LIKE '%sd%'\
				AND spt.spectral_type NOT LIKE '%pec%'\
				AND spt.spectral_type NOT LIKE '%blue%'\
				AND spt.spectral_type NOT LIKE '%red%'\
				AND spt.spectral_type NOT LIKE '%p%'\
				AND cdist.photometric_estimate = 0\
				AND cdist.adopted = 1\
				AND mo.designation NOT LIKE '%AB'\
				AND mo.designation NOT LIKE '%CD'\
				AND b1mags.magnitude_unc <= 0.1\
				AND b2mags.magnitude_unc <= 0.1\
				AND Bmags.magnitude_unc <= 0.1\
				AND cdist.dmod_unc <= 0.1\
			ORDER BY\
				spt.spectral_type_number")

		#Find the absolute magnitude for y-axis and the uncertainties of x and y :
		df2 = pd.DataFrame({"Bmag_abs" : df['Bmag'] - df['dmod'], "Bmag_abs_unc" : np.sqrt(df['eBmag']**2 + df['edmod']**2), "b1b2_unc" : np.sqrt( df['eb1mag']**2 + df['eb2mag']**2)})
		dfnew = pd.concat([df,df2], axis=1)

		#Separate the spectral types :
		df_spt_list = [dfnew[dfnew.sptn < 10.0], dfnew[(dfnew.sptn < 20) & (dfnew.sptn > 10)], dfnew[(dfnew.sptn < 30) & (dfnew.sptn > 20)], dfnew[(dfnew.sptn > 30) & (dfnew.sptn < 40)]]

		#Find the young substellar objects :
		if young_seq :

			df_young = moca.query("SELECT mo.designation, spt.spectral_type, spt.spectral_type_number AS sptn, spt.gravity_class AS grav_class, spt.grav_type AS grav_type, cdist.dmod, cdist.dmod_unc AS edmod, b1mags.magnitude AS b1mag, b1mags.magnitude_unc AS\
		eb1mag, b2mags.magnitude AS b2mag, b2mags.magnitude_unc AS eb2mag, Bmags.magnitude AS Bmag, Bmags.magnitude_unc AS eBmag, b1mags.nn AS nn1, b2mags. nn AS nn2, Bmags.nn AS nn3 \
				FROM \
					(SELECT *, 'Intermediate gravity' AS grav_type FROM cdata_spectral_types cspt WHERE cspt.photometric_estimate = 0 AND cspt.spectral_type_number >= 6 AND (cspt.gravity_class REGEXP 'INT|β') UNION ALL \
					SELECT *, 'Low gravity' AS grav_type FROM cdata_spectral_types cspt WHERE cspt.photometric_estimate = 0 AND cspt.spectral_type_number >= 6 AND (cspt.gravity_class REGEXP 'VL|γ|δ')) spt\
				JOIN moca_objects mo USING (moca_oid)\
				LEFT JOIN cdata_distances cdist USING (moca_oid)\
				JOIN (SELECT * FROM \
					(SELECT moca_oid, magnitude, magnitude_unc, ROW_NUMBER() OVER(PARTITION BY moca_oid ORDER BY magnitude_unc ASC) AS nn FROM cdata_photometry WHERE "+str(b1mag_type)+" AND \
						adopted = 1) subq1 WHERE subq1.nn = 1) AS b1mags ON (b1mags.moca_oid = spt.moca_oid)\
				JOIN (SELECT * FROM \
					(SELECT moca_oid, magnitude, magnitude_unc, ROW_NUMBER() OVER(PARTITION BY moca_oid ORDER BY magnitude_unc ASC) AS nn FROM cdata_photometry WHERE "+str(b2mag_type)+" AND \
						adopted = 1) subq2 WHERE subq2.nn = 1) AS b2mags ON (b2mags.moca_oid = spt.moca_oid)\
				JOIN (SELECT * FROM \
					(SELECT moca_oid, magnitude, magnitude_unc, ROW_NUMBER() OVER(PARTITION BY moca_oid ORDER BY magnitude_unc ASC) AS nn FROM cdata_photometry WHERE "+str(Bmag_type)+" AND \
						adopted = 1) subq3 WHERE subq3.nn = 1) AS Bmags ON (Bmags.moca_oid = spt.moca_oid)\
				WHERE\
				spt.complete_spectral_type NOT LIKE '%pec%'\
				AND spt.complete_spectral_type NOT LIKE '%+%'\
				AND spt.complete_spectral_type NOT LIKE '%sd%'\
				AND spt.spectral_type NOT LIKE '%pec%'\
				AND spt.spectral_type NOT LIKE '%blue%'\
				AND spt.spectral_type NOT LIKE '%p%'\
				AND cdist.photometric_estimate = 0\
				AND cdist.adopted = 1\
				AND mo.designation NOT LIKE '%AB'\
				AND mo.designation NOT LIKE '%CD'\
				AND b1mags.magnitude_unc <= 0.1\
				AND b2mags.magnitude_unc <= 0.1\
				AND Bmags.magnitude_unc <= 0.1\
				AND cdist.dmod_unc <= 0.1\
			ORDER BY\
				spt.spectral_type_number")

			df_young_calc = pd.DataFrame({"Bmag_abs" : df_young['Bmag'] - df_young['dmod'], "Bmag_abs_unc" : np.sqrt(df_young['eBmag']**2 + df_young['edmod']**2), "b1b2_unc" : np.sqrt( df_young['eb1mag']**2 + df_young['eb2mag']**2)})
			df_young = pd.concat([df_young,df_young_calc], axis=1)

			#Differentiate intermediate and low gravity substellar objs :
			df_young_int = df_young[df_young['grav_type'] == 'Intermediate gravity']
			df_young_int.reset_index(drop=True, inplace=True)
			df_young_low = df_young[df_young['grav_type'] == 'Low gravity']
			df_young_low.reset_index(drop=True, inplace=True)
			df_young_list = [df_young_int, df_young_low]
			df_young_color = ['#000000', '#696969']
			df_young_color2 = ['#FF0000', '#FFA500']
			marker_list = ['D', 'v']

			def plot_young(df_list, df_color) : 
				for i, dfy in enumerate(df_young_list) :
						ax.errorbar(dfy['b1mag']-dfy['b2mag'], dfy['Bmag_abs'], xerr=dfy['b1b2_unc'], yerr=dfy['Bmag_abs_unc'], 
								mec=df_color[i], mfc = '#FFFFFF', ecolor=df_color[i], marker=marker_list[i], markersize=3.5, markeredgewidth = 0.75, fmt=' ', label= str(dfy.at[0, 'grav_type'])+' substellar objects')

		# Create a figure and an axes :
		fig, ax = plt.subplots()

		# Plot the reference BDs :
		if not spt:
			if ref_err:
				ax.errorbar(dfnew['b1mag']-dfnew['b2mag'], dfnew['Bmag_abs'], xerr=dfnew['b1b2_unc'], yerr=dfnew['Bmag_abs_unc'], 
							markeredgecolor='#808080', ecolor='#808080', marker='.', markersize=3, alpha=0.3, fmt=' ', label='Field substellar objects')
				if young_seq:
					plot_young(df_young_list, df_young_color2)

			else:
				ax.scatter(dfnew['b1mag']-dfnew['b2mag'], dfnew['Bmag_abs'], edgecolors='#808080', marker='.', s=10, alpha=0.3, label='Field substellar objects')
				if young_seq:
					for i, dfy in enumerate(df_young_list) :
						ax.scatter(dfy['b1mag']-dfy['b2mag'], dfy['Bmag_abs'], facecolors = '#FFFFFF', edgecolors=df_young_color2[i], linewidths = 0.75, marker=marker_list[i], s=12, label=str(dfy.at[0, 'grav_type'])+' substellar objects')
		else:
			# Create a colormap for the spectral types
			sptn_list = list(pd.unique(dfnew['sptn'])) 

			norm = mcolors.Normalize(vmin=min(sptn_list), vmax=max(sptn_list))
			cmap = cm.Spectral
			sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
			sm.set_array([])
			sptn_color = np.array([(sm.to_rgba(v)) for v in dfnew['sptn']])

			if ref_err:
				for i, color in enumerate(sptn_color) :
					if i == 0 :
						ax.errorbar(dfnew.at[i, 'b1mag']-dfnew.at[i, 'b2mag'], dfnew.at[i, 'Bmag_abs'], xerr=dfnew.at[i, 'b1b2_unc'], yerr=dfnew.at[i, 'Bmag_abs_unc'], 
								color=sptn_color[i], ecolor='#808080', marker='.', markersize=3, alpha=0.5, fmt=' ', label = 'Field substellar objects')
					else : 
						ax.errorbar(dfnew.at[i, 'b1mag']-dfnew.at[i, 'b2mag'], dfnew.at[i, 'Bmag_abs'], xerr=dfnew.at[i, 'b1b2_unc'], yerr=dfnew.at[i, 'Bmag_abs_unc'], 
								color=sptn_color[i], ecolor='#808080', marker='.', markersize=3, alpha=0.5, fmt=' ')
						
				if young_seq:
					plot_young(df_young_list, df_young_color)
					
			else:
				ax.scatter(dfnew['b1mag'] - dfnew['b2mag'], dfnew['Bmag_abs'], c=dfnew['sptn'], cmap=cmap, norm=norm, marker='.', s=10, alpha=0.5, label = 'Field substellar objects')
				if young_seq:
					for i, dfy in enumerate(df_young_list) :
						ax.scatter(dfy['b1mag']-dfy['b2mag'], dfy['Bmag_abs'], facecolors = '#FFFFFF', edgecolors=df_young_color[i], linewidths = 0.75, marker=marker_list[i], s=12, label=str(dfy.at[0, 'grav_type'])+' substellar objects')
			
			# Add a color bar to the plot
			cbar = plt.colorbar(sm, ax=ax)
			cbar.set_label('Spectral Type Number (Field substellar objects)')

		#plot the given target :
		ax.errorbar(m1m2, M, xerr = em1m2, yerr = eM, color = 'k', ecolor = 'k', marker = '.', markersize = 7, label = 'Entered object')

		#find the range, if not provided :
		xrange = np.array([np.min(dfnew['b1mag']-dfnew['b2mag']-dfnew['b1b2_unc']), np.max(dfnew['b1mag']-dfnew['b2mag']+dfnew['b1b2_unc'])])
		xrange += np.array([-1,1])*(xrange[1]-xrange[0])*0.05
		yrange = np.array([np.min(dfnew['Bmag_abs']-dfnew['Bmag_abs_unc']), np.max(dfnew['Bmag_abs']+dfnew['Bmag_abs_unc'])])
		yrange += np.array([-1,1])*(yrange[1]-yrange[0])*0.05

		if xmin == None :
			if xmax == None :
				ax.set_xlim(xrange[0], xrange[1])
			else :
				ax.set_xlim(xrange[0], xmax)
		else :
			if xmax == None :
				ax.set_xlim(xmin, xrange[1])
			else :
				ax.set_xlim(xmin, xmax)
		
		if ymin == None :
			if ymax == None :
				ax.set_ylim(yrange[0], yrange[1])
			else :
				ax.set_ylim(yrange[0], ymax)
		else :
			if ymax == None :
				ax.set_ylim(ymin, yrange[1])
			else :
				ax.set_ylim(ymin, ymax)

		ax.set_xlabel('$\it{'+str(m1_type)+' - '+str(m2_type)+'}$')
		ax.set_ylabel('Absolute $\ \it{'+str(M_type)+'}$-band magnitude')
		ax.legend()
		plt.title("$\it{"+str(m1_type)+"-"+str(m2_type)+"}$ = "+str(m1m2)+", $\  absolute\ \it{"+str(M_type)+"}$ = "+str(M))
		plt.gca().invert_yaxis()
		plt.tight_layout()
		if path is not None :
			plt.savefig(path)
		plt.show()
		plt.close()

	def get_spectrum(self, moca_specid = None, designation = None, moca_specid2 = None, designation2 = None, spt_ref = False, sptn_int = [7, 20], gravity_class = ['alpha', 'beta', 'gamma'], return_data = False, path = None, con = None) :
		

		'''moca_specid, designation : identification of the provided target
		moca_specid2, designation2 : identification of the provided background target
		spt_ref : (bool) to display the reference spectrum of the spectral type of sptn_int (default = False)
		sptn_int : spectral type number interval (default = [7, 20])
		gravity_class : specified gravity class (alpha, beta, gamma or any combination of them, default = ['alpha', 'beta', 'gamma'])
		return_data : (bool) if True, the spectrum/spectra is/are returned as a pandas dataFrame when calling get_spectrum instead of plotted (default = False)
		path : path of figure saving (default = None)
		con : connection to the database (default = None, public connection)'''

		#Build connection with database :
		moca = MocaEngine()
		if con is not None :
			moca.connection = con

		def find_obj(moca_specid = None, designation = None) : #find the requested object and its spectrum, if possible

			if moca_specid != None :
				df_sp = moca.query('SELECT ds.moca_specid, ms.spectrum_name, ms.flux_units, ds.wavelength_angstrom*1e-4 AS lam, flux_flambda AS sp, flux_flambda_unc AS esp FROM moca_spectra ms\
					JOIN data_spectra ds USING(moca_specid) WHERE ms.moca_specid = '+str(moca_specid)+'')
				
				if df_sp.empty :
					print('The spectrum for the moca_specid '+str(moca_specid)+' cannot be found in the database. Please check the provided moca_specid and the moca_spectra MocaDB table again.')        

			else :
				if designation != None :
					df_des = moca.query('SELECT * FROM mechanics_all_designations WHERE designation = "'+str(designation)+'"')
					des_oid = df_des.at[0, 'moca_oid']

					if des_oid == None :
						print('The object '+str(designation)+' cannot be found in the database.')

					else :
						df_sp_oid = moca.query('SELECT moca_specid, COALESCE(moca_instid,instrument_name) AS instrument, min_wavelength_angstrom*1e-4 AS min_lam_microns, max_wavelength_angstrom*1e-4 AS max_lam_microns, median_snr_per_pix,\
							median_spectral_resolving_power FROM moca_spectra WHERE moca_oid = '+str(des_oid)+'')
						
						if df_sp_oid.empty :
							print('The spectrum for the object '+str(designation)+' cannot be found.')

						elif len(df_sp_oid) > 1:
							print('Multiple results obtained for the object '+str(designation)+'.\nPlease choose a specific moca_specid to call the function get_spectrum :' )
							print(df_sp_oid)

						else :
							moca_specid = df_sp_oid.at[0, 'moca_specid']
							df_sp = moca.query('SELECT ds.moca_specid, ms.spectrum_name, ms.flux_units, ds.wavelength_angstrom*1e-4 AS lam, flux_flambda AS sp, flux_flambda_unc AS esp FROM moca_spectra ms\
								JOIN data_spectra ds USING(moca_specid) WHERE ms.moca_specid = '+str(moca_specid)+'')
				else :
					print('No moca_specid or designation provided.')

			return df_sp
		
		def plot_subfig(df, df_ref, axe, mult_ref = False) :
			
			pd.set_option('future.no_silent_downcasting', True)

			df = df.copy()
			df = df.replace(to_replace=[None], value=np.nan)
			df = df.infer_objects(copy=False)

			#Adjust units of the flux density
			df['flux_units'] = df['flux_units'].replace(to_replace=np.nan, value=' F_lambda $[W.m^{-2}]/[A]$')
			df['flux_units'] = df['flux_units'].infer_objects(copy=False)

			#Adjust the scale of the y-axis values and the units shown in plot:
			if df.at[0, 'flux_units'] == ' F_lambda $[W.m^{-2}]/[A]$' :
				df[['sp', 'esp']] = df[['sp', 'esp']]*1e4
				y_units = ' $[W.m^{-2}]/[\mu m]$'
			elif df.at[0, 'flux_units'] == 'F_lambda [W.m^-2]/[m]' :
				df[['sp', 'esp']] = df[['sp', 'esp']]*1e-6
				y_units = ' $[W.m^{-2}]/[\mu m]$'
			else : y_units = df.at[0, 'flux_units']

			if df_ref is not None and not df_ref.empty : #Underplot the reference spectrum
				
				df_ref = df_ref.copy()
				df_ref = df_ref.reset_index(drop=True)
				df_ref = df_ref.replace(to_replace=[None], value=np.nan)
				df_ref = df_ref.infer_objects(copy=False)

				df_ref['flux_units'] = df_ref['flux_units'].replace(to_replace=np.nan, value=' F_lambda $[W.m^{-2}]/[A]$')
				df_ref['flux_units'] = df_ref['flux_units'].infer_objects(copy=False)

				#Adjust the scale of reference spectrum :
				if df_ref.at[0, 'flux_units'] == ' F_lambda $[W.m^{-2}]/[A]$' :
					df_ref[['sp', 'esp']] = df_ref[['sp', 'esp']] * 1e4
				elif df_ref.at[0, 'flux_units'] == 'F_lambda [W.m^-2]/[m]' : 
					df_ref[['sp', 'esp']] = df_ref[['sp', 'esp']] * 1e-6

				#Adjust the layout of overplotting :
				df[['sp', 'esp']] = df[['sp', 'esp']].div(df['sp'].median())
				df_ref[['sp', 'esp']] = df_ref[['sp', 'esp']].div(df_ref['sp'].median())

				if not mult_ref :
					axe.plot(df_ref['lam'], df_ref['sp'], color = 'darkgray', linewidth = 1, label = df_ref.at[0, 'spectrum_name'])
					axe.legend(loc = 'best', fontsize = 8)
				else :
					axe.plot(df_ref['lam'], df_ref['sp'], color = 'darkgray', linewidth = 1)
					axe.text(0.98, 0.95, df_ref.at[0, 'spectral_type'], transform=axe.transAxes, fontsize=10, verticalalignment='top', horizontalalignment='right')

				#Plot error in y of the reference spectrum :
				axe.fill_between(df_ref['lam'], df_ref['sp'] - df_ref['esp'], df_ref['sp'] + df_ref['esp'], alpha=0.4, facecolor='silver')

			#Adjust range of x-axis :
			xrange = np.array([np.min(df['lam']), np.max(df['lam'])])
			xrange += np.array([-1,1])*(xrange[1]-xrange[0])*0.02
			yrange = np.array([np.min(df['sp']-df['esp']), np.max(df['sp']+df['esp'])])
			yrange += np.array([-1,1])*(yrange[1]-yrange[0])*0.25

			axe.plot(df['lam'], df['sp'], color = 'blue', linewidth = 1)
			axe.fill_between(df['lam'], df['sp'] - df['esp'], df['sp'] + df['esp'], alpha=0.3, facecolor='#089FFF')
			axe.tick_params(axis='x', which='both', direction='in', length=3, width=1, labelsize=9, top=False, bottom=True, left=False, right=False)

			if mult_ref or (moca_specid2 is not None or designation2 is not None) :
				axe.tick_params(axis='y', which='both', direction='in', length=0, labelsize=9, labelleft=False)
			else : 
				axe.tick_params(axis='y', which='both', direction='in', length=3, width = 1, labelsize=9)
				axe.set_ylabel(y_units)

			axe.set_xlim(xrange[0], xrange[1])
			axe.set_ylim(yrange[0], yrange[1])

		def plot_spectrum(df, df_ref = None, sptn_list = ['notprovided'], gravity_class_list = ['notprovided']) :
			
			fig, axs = plt.subplots(nrows = len(sptn_list), ncols= len(gravity_class_list), sharex = True, squeeze = False, figsize  = (len(gravity_class_list)+6, len(sptn_list)+1))

			if spt_ref == True :

				for j, sptn in enumerate(sptn_list) : #Loop over subplots :
					sub_df_ref = None
					sub_df_ref = df_ref[df_ref['spectral_type_number'] == sptn] if df_ref is not None else None

					for i, clas in enumerate(gravity_class_list) :
						sub_df_ref2 = sub_df_ref[sub_df_ref['gravity_class'] == clas] if sub_df_ref is not None else None

						if sub_df_ref is not None and not sub_df_ref2.empty : #if reference spectrum, plot subplot
							plot_subfig(df, sub_df_ref2, axs[j, i], mult_ref = spt_ref)
						else :
							fig.delaxes(axs[j, i]) #if no reference spectrum, remove subplot

			else :
				plot_subfig(df, df_ref, axs[0, 0], mult_ref= spt_ref)
			
			#Identify the axis and plot :
			fig.text(0.02, 0.5, 'Spectral flux density', va='center', rotation='vertical', fontsize=10)
			fig.text(0.52, 0.04, 'Wavelength [$\mu m$]', ha='center', fontsize=10)
			plt.suptitle(df.at[0, 'spectrum_name'], fontsize=11)
			plt.tight_layout(rect=[0.05, 0.05, 1, 0.95])
			if path is not None :
				plt.savefig(path)
			plt.show()
			plt.close()


		#Get spectrum of requested object :
		df_sp = None
		df_sp = find_obj(moca_specid=moca_specid, designation= designation)

		#Get spectrum of second object :
		if moca_specid2 is not None or designation2 is not None :
			df_ref = find_obj(moca_specid2, designation2) #Find the spectrum of the second obj
			unique_values = ['notprovided'] #Get the list of reference moca_specid
			g_class = ['notprovided']

		else : 
			df_ref = None
			unique_values = ['notprovided']
			g_class = ['notprovided']


		#Get spectrum of reference objects (if spt_ref is True):
		if spt_ref == True :

			df_ref = moca.query('''
				SELECT subq.moca_specid, subq.spectral_type, subq.gravity_class, subq.spectral_type_number, subq.flux_units, ds.wavelength_angstrom*1e-4 AS lam, ds.flux_flambda AS sp,
				ds.flux_flambda_unc AS esp 
				FROM (SELECT mref.*, ms.flux_units, ROW_NUMBER() OVER(PARTITION BY spectral_type_number ORDER BY CEIL(nwavelengths/1000) ASC, median_snr_per_pix DESC) nn
				FROM moca_spectral_type_references mref
				JOIN moca_spectra ms USING(moca_specid)
				WHERE mref.spectral_type_number >= '''+str(sptn_int[0])+'''  AND mref.spectral_type_number <= '''+str(sptn_int[1])+'''  AND (mref.luminosity_class IS NULL OR mref.luminosity_class='V') 
					AND (mref.gravity_class IS NULL OR mref.gravity_class='alpha' OR mref.gravity_class='α') AND mref.origin NOT LIKE 'Pickles library') subq
				JOIN data_spectra ds USING(moca_specid)
				WHERE subq.nn=1
			UNION ALL
				SELECT subq.moca_specid, subq.spectral_type, subq.gravity_class, subq.spectral_type_number, subq.flux_units, ds.wavelength_angstrom*1e-4 AS lam, ds.flux_flambda AS sp,
				ds.flux_flambda_unc AS esp 
				FROM (SELECT mref.*, ms.flux_units, ROW_NUMBER() OVER(PARTITION BY spectral_type_number ORDER BY CEIL(nwavelengths/1000) ASC, median_snr_per_pix DESC) nn 
				FROM moca_spectral_type_references mref JOIN moca_spectra ms USING(moca_specid) 
				WHERE mref.spectral_type_number >= '''+str(sptn_int[0])+''' AND mref.spectral_type_number <= '''+str(sptn_int[1])+''' AND (mref.luminosity_class IS NULL OR mref.luminosity_class='V') 
					AND (mref.gravity_class='beta' OR mref.gravity_class='β') AND mref.origin NOT LIKE 'Pickles library') subq 
				JOIN data_spectra ds USING(moca_specid) 
				WHERE subq.nn=1
			UNION ALL
				SELECT subq.moca_specid, subq.spectral_type, subq.gravity_class, subq.spectral_type_number, subq.flux_units, ds.wavelength_angstrom*1e-4 AS lam, ds.flux_flambda AS sp,
				ds.flux_flambda_unc AS esp FROM (SELECT mref.*, ms.flux_units, ROW_NUMBER() OVER(PARTITION BY spectral_type_number ORDER BY CEIL(nwavelengths/1000) ASC, median_snr_per_pix DESC) nn 
				FROM moca_spectral_type_references mref 
				JOIN moca_spectra ms USING(moca_specid) 
				WHERE mref.spectral_type_number >= '''+str(sptn_int[0])+''' AND mref.spectral_type_number <= '''+str(sptn_int[1])+''' AND (mref.luminosity_class IS NULL OR mref.luminosity_class='V') 
					AND (mref.gravity_class='gamma' OR mref.gravity_class='γ') AND mref.origin NOT LIKE 'Pickles library') subq 
				JOIN data_spectra ds USING(moca_specid) 
				WHERE subq.nn=1''')

			#NaN values are atomatic value for alpha :
			df_ref['gravity_class'] = df_ref['gravity_class'].replace(to_replace=np.nan, value='alpha')

			#Get the list of reference sptn :
			unique_values = list(pd.unique(df_ref['spectral_type_number']))
			g_class = gravity_class

		#Plot the spectrums :
		if df_sp is not None and not df_sp.empty and not return_data :
			plot_spectrum(df_sp, df_ref, sptn_list = unique_values, gravity_class_list= g_class)

		#Return data :
		if return_data and df_sp is not None :
			
			if moca_specid2 is None and designation2 is None :

				return df_sp
			
			elif moca_specid2 is not None or designation2 is not None :

				return df_sp, df_ref


#import pdb; pdb.set_trace()