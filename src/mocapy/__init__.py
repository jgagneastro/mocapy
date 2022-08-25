__author__ = 'Jonathan Gagne'
__email__ = 'jonathan.gagne@astro.umontreal.ca'
__uri__ = "https://github.com/jgagneastro/mocapy"
__license__ = "MIT"
__description__ = "A Python package to interact with the MOCA database"

#Moca should be available automatically when importing mocapy
__all__ = ["MocaEngine"]

#Import the local moca.py file
from .moca import MocaEngine