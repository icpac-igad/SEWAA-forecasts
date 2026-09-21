# Python code to generate the ifs normalisations for cGAN

# So that I can import from the python code
import sys
# insert at 1, 0 is the script path (or '' in REPL)
sys.path.insert(1, 'E:/CGAN/SEWAA-forecasts/24h_accumulations/cGAN/dsrnngan')

from data import gen_fcst_norm

gen_fcst_norm()
