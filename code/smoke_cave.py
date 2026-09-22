import sys; sys.path.insert(0, '.')
import numpy as np, pandas as pd, warnings
from src.physics.cave_model import CaveModel, CaveParams
p = CaveParams(); m = CaveModel(p)
for name, ach in [('open', p.ach_open), ('closed', p.ach_closed)]:
    A, B = m._build_thermal_system(ach)
    ev = np.linalg.eigvals(A).real
    print(f'{name:7s} max real eig = {ev.max():+.6g}   (must be < 0)')
with warnings.catch_warnings():
    warnings.simplefilter('error')
    A, B = m._build_thermal_system(p.ach_open); Ad, Bd = m._discretize(A, B, 3600.0)
print('max |Ad| =', round(float(np.abs(Ad).max()), 6), ' finite:', bool(np.isfinite(Ad).all()))

n = 24*30
idx = pd.date_range('2024-01-01', periods=n, freq='h', tz='UTC')
h = np.arange(n)
od = pd.DataFrame({'T2M': 5 + 10*np.sin(h/24*2*np.pi),
                   'RH2M': np.clip(40 + 20*np.sin(h/24*2*np.pi+1), 5, 95),
                   'ALLSKY_SFC_SW_DWN': np.clip(600*np.sin((h % 24 - 6)/12*np.pi), 0, None)}, index=idx)
s = m.simulate(od)
print(s[['T_in', 'RH_in', 'T_wall', 'ACH']].describe().round(3).to_string())
print('\nfinite:', bool(np.isfinite(s[["T_in","RH_in"]].to_numpy()).all()))
