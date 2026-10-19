"""Original numerical attack implementation behind a strict stable preimport gate."""
import sys
from common import BASE,load,activate_gate
activate_gate()
original=load('original_attack',BASE/'method_comparison/attack.py')
if __name__=='__main__':original.main(*sys.argv[1:])
