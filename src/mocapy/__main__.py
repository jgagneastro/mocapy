__author__ = 'Jonathan Gagne'
__email__ = 'jonathan.gagne@astro.umontreal.ca'

#Example code

#Import mocapy
from mocapy import *

#Create a moca engine object
moca = MocaEngine()

#Query the moca database to obtain a Pandas DataFrame
df = moca.query("SELECT * FROM moca_objects LIMIT 20")

#See the outputs of the DataFrame
print(df)

#Query the moca database again, but this time upload your own pandas DataFrame to cross-match against the database
df2 = moca.query("SELECT * FROM cdata_spectral_types JOIN tmp_table USING(moca_oid)",tmp_table=df)

#See the outputs of the second DataFrame
print(df2)